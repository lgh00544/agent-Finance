"""
飞书机器人告警推送
- 未配置 FEISHU_WEBHOOK_URL 时自动降级为仅日志（不阻断主链路）
- 采用飞书"文本卡片"格式，消息内容全部来自 LLM 结构化输出
【刚性代码逻辑】只负责消息组装与 HTTP 推送，不产生任何研判内容。
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _direct_alert(text: str) -> int:
    """告警机器人直发管理员单聊，返回成功条数；异常逐条记录，不再静默吞。"""
    from app.services.feishu_sender import send_text

    sent = 0
    for oid in settings.feishu_admin_open_ids.split(","):
        oid = oid.strip()
        if not oid:
            continue
        try:
            if send_text(oid, text):
                sent += 1
        except Exception as exc:  # noqa: BLE001 单条失败不影响其余收件人
            logger.error("飞书直发失败 open_id=%s: %s", oid, exc)
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
        try:
            resp = httpx.post(settings.feishu_webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            webhook_ok = True
            logger.info("飞书推送成功: %s %s", stock_name, stock_code)
        except Exception as exc:  # noqa: BLE001 推送失败不应影响主链路
            logger.error("飞书推送失败: %s", exc)

    channels: list[tuple[str, bool]] = []
    if direct_on and direct_ids:
        channels.append(("direct", direct_sent > 0))
    if webhook_on:
        channels.append(("webhook", webhook_ok))
    if not channels:
        logger.info("[飞书未配置] %s %s | %s | 建议: %s | %s",
                    stock_name, stock_code, alert_type, action, message)
        return {"result": "not_configured", "channel": "none",
                "direct_sent": direct_sent, "webhook_ok": webhook_ok}
    if all(ok for _, ok in channels):
        channel = "both" if len(channels) == 2 else channels[0][0]
        return {"result": "delivered", "channel": channel,
                "direct_sent": direct_sent, "webhook_ok": webhook_ok}
    ok_names = [name for name, ok in channels if ok]
    if ok_names:
        return {"result": "delivered", "channel": ok_names[0],
                "direct_sent": direct_sent, "webhook_ok": webhook_ok}
    return {"result": "failed", "channel": "none",
            "direct_sent": direct_sent, "webhook_ok": webhook_ok}
