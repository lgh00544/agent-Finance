"""
飞书机器人告警推送
- 未配置 FEISHU_WEBHOOK_URL 时自动降级为仅日志（不阻断主链路）
- 采用飞书"文本卡片"格式，消息内容全部来自 LLM 结构化输出
【刚性代码逻辑】只负责消息组装与 HTTP 推送，不产生任何研判内容。
"""
from app.core import clock
import json
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# S-11 投递可靠性：失败后的重试次数与间隔（飞书限流友好，不做无限重试）
_PUSH_RETRY_TIMES = 2
_PUSH_RETRY_SLEEP = 1.5


def _direct_alert(text: str) -> int:
    """告警机器人直发管理员单聊，返回成功条数；异常逐条记录，不再静默吞。

    S-11：每个收件人失败后按 _PUSH_RETRY_TIMES 重试（间隔 _PUSH_RETRY_SLEEP），
    重试耗尽仍失败则由上层 _escalate 升级留痕。
    """
    from app.services.feishu_sender import send_text

    sent = 0
    for oid in settings.feishu_admin_open_ids.split(","):
        oid = oid.strip()
        if not oid:
            continue
        for attempt in range(_PUSH_RETRY_TIMES + 1):
            try:
                if send_text(oid, text):
                    sent += 1
                    break
            except Exception as exc:  # noqa: BLE001 单条失败不影响其余收件人
                logger.error("飞书直发失败 open_id=%s（第 %s 次）: %s",
                             oid, attempt + 1, exc)
            if attempt < _PUSH_RETRY_TIMES:
                time.sleep(_PUSH_RETRY_SLEEP)
    return sent


def push_alert(stock_name: str, stock_code: str, alert_type: str, severity: str,
               message: str, action: str) -> dict:
    """推送告警，返回 {result, channel, direct_sent, webhook_ok}；
    result 三态 delivered / failed / not_configured（批A A4）。"""
    # 股票标识统一格式：代码在前、名称紧随（600519 贵州茅台）
    stock_label = f"{stock_code} {stock_name}" if stock_name and stock_name != stock_code else stock_code
    text = (
        f"【{alert_type}】{stock_label}\n"
        f"严重度: {severity} | 建议操作: {action}\n"
        f"{message}"
    )
    direct_on = bool(settings.feishu_bridge_alert_direct)
    direct_ids = bool(settings.feishu_admin_open_ids.strip())
    direct_sent = _direct_alert(text) if direct_on else 0

    webhook_on = bool(settings.feishu_webhook_url)
    webhook_ok = False
    if webhook_on:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": f"{alert_type} · {stock_label}"},
                           "template": "red" if severity == "critical" else "orange" if severity == "warning" else "blue"},
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
            },
        }
        for attempt in range(_PUSH_RETRY_TIMES + 1):
            try:
                resp = httpx.post(settings.feishu_webhook_url, json=payload, timeout=10)
                resp.raise_for_status()
                webhook_ok = True
                logger.info("飞书推送成功: %s %s", stock_name, stock_code)
                break
            except Exception as exc:  # noqa: BLE001 推送失败不应影响主链路
                logger.error("飞书推送失败（第 %s 次）: %s", attempt + 1, exc)
                if attempt < _PUSH_RETRY_TIMES:
                    time.sleep(_PUSH_RETRY_SLEEP)

    channels: list[tuple[str, bool]] = []
    if direct_on and direct_ids:
        channels.append(("direct", direct_sent > 0))
    if webhook_on:
        channels.append(("webhook", webhook_ok))
    if not channels:
        logger.info("[飞书未配置] %s %s | %s | 建议: %s | %s",
                    stock_name, stock_code, alert_type, action, message)
        return {"result": "not_configured", "channel": "none", "escalated": False,
                "direct_sent": direct_sent, "webhook_ok": webhook_ok}
    if all(ok for _, ok in channels):
        channel = "both" if len(channels) == 2 else channels[0][0]
        return {"result": "delivered", "channel": channel, "escalated": False,
                "direct_sent": direct_sent, "webhook_ok": webhook_ok}
    ok_names = [name for name, ok in channels if ok]
    if ok_names:
        return {"result": "delivered", "channel": ok_names[0], "escalated": False,
                "direct_sent": direct_sent, "webhook_ok": webhook_ok}
    # S-11：全部通道重试耗尽仍失败 → 升级（CRITICAL 日志 + 缓存留痕，供健康检查/
    # 面板发现「告警静默」）。不抛异常、不在本函数内重发：确定性告警通道未置去重位，
    # 下一轮扫描会自动重试，避免在单次调用里放大故障。
    return {"result": "failed", "channel": "none",
            "escalated": _escalate(alert_type, stock_label, severity, message, action,
                                    direct_sent, webhook_ok),
            "direct_sent": direct_sent, "webhook_ok": webhook_ok}


def _escalate(alert_type: str, stock_label: str, severity: str, message: str,
              action: str, direct_sent: int, webhook_ok: bool) -> bool:
    """S-11 投递升级：全部通道重试耗尽仍失败 → CRITICAL 日志 + 缓存留痕。

    留痕供运维/面板发现「告警静默」；不在本函数内重发或抛错（避免放大故障）。
    """
    detail = {"at": clock.now_str(), "alert_type": alert_type,
              "stock": stock_label, "severity": severity, "action": action,
              "direct_sent": direct_sent, "webhook_ok": webhook_ok,
              "retry_times": _PUSH_RETRY_TIMES, "message": message[:200]}
    logger.critical("[告警投递升级] 全部通道重试 %s 次后仍失败，告警未送达: %s",
                    _PUSH_RETRY_TIMES, detail)
    try:
        from app.cache import cache

        cache.set("alert:push_escalated:last", json.dumps(detail, ensure_ascii=False), 86400)
    except Exception as exc:  # noqa: BLE001 留痕失败不影响主链路
        logger.warning("告警升级留痕写入失败: %s", exc)
    return True
