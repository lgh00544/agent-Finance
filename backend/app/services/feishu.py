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
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

# S-11 投递可靠性：失败后的重试次数与间隔（飞书限流友好，不做无限重试）
_PUSH_RETRY_TIMES = 2
_PUSH_RETRY_SLEEP = 1.5

# 正文美化：单行超长时按句读断行（避免揉成一团）
_LINE_MAX_CHARS = 60
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；])|(?<=[:：])")


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


def _format_message_body(message: str) -> str:
    """消息正文分段美化（仅展示层排版，不改任何语义内容）。

    - 正文已带换行（含【触发原因】/【建议操作】等小标题）→ 保留原有分段，压缩多余空行；
    - 正文无换行且含【...】小标题 → 按小标题拆段，段间空行；
    - 正文无换行也无小标题 → 按句读断行（每行不超过 _LINE_MAX_CHARS），行间空行。
    避免推送消息揉成一团无法阅读。
    """
    msg = (message or "").strip()
    if not msg:
        return "（无详情）"

    if "\n" in msg:
        # 已分段：仅压缩连续空行，保证段间恰一个空行
        out: list[str] = []
        prev_blank = False
        for ln in msg.split("\n"):
            ln = ln.strip()
            if not ln:
                if out and not prev_blank:
                    out.append("")
                prev_blank = True
                continue
            out.append(ln)
            prev_blank = False
        return "\n".join(out).strip("\n")

    # 无换行：优先按【小标题】切段
    segs = [s.strip() for s in re.split(r"(?=【)", msg) if s.strip()]
    if len(segs) > 1 and all("【" in s for s in segs):
        paras: list[str] = []
        for seg in segs:
            paras.extend(_wrap_long_line(seg))
        return "\n\n".join(paras)

    # 完全无分段：按句读断行
    return "\n\n".join(_wrap_long_line(msg))


def _wrap_long_line(line: str) -> list[str]:
    """按句读把单行切分为 ≤_LINE_MAX_CHARS 的多个自然行（保留原文字内容）。"""
    if len(line) <= _LINE_MAX_CHARS:
        return [line]
    pieces = [p.strip() for p in _SENTENCE_SPLIT_RE.split(line) if p.strip()]
    out: list[str] = []
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) <= _LINE_MAX_CHARS:
            buf += piece
        else:
            if buf:
                out.append(buf)
            # 单句本身超长时硬切，避免无限增长（切块去首尾空白，保持行首干净）
            while len(piece) > _LINE_MAX_CHARS:
                out.append(piece[:_LINE_MAX_CHARS].strip())
                piece = piece[_LINE_MAX_CHARS:].strip()
            buf = piece
    if buf:
        out.append(buf)
    return out


def _format_alert_text(alert_type: str, stock_label: str, severity: str,
                       action: str, message: str) -> str:
    """告警文本组装：标题行 / 严重度建议行 / 分隔线 / 分段正文，保证消息清晰可读。"""
    body = _format_message_body(message)
    return (
        f"【{alert_type}】{stock_label}\n"
        f"严重度: {severity} | 建议操作: {action}\n"
        f"————————————\n"
        f"{body}"
    )


def _post_webhook(payload: dict, stock_name: str, stock_code: str) -> bool:
    """webhook 卡片推送（含重试），返回是否成功。"""
    for attempt in range(_PUSH_RETRY_TIMES + 1):
        try:
            resp = httpx.post(settings.feishu_webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("飞书推送成功: %s %s", stock_name, stock_code)
            return True
        except Exception as exc:  # noqa: BLE001 推送失败不应影响主链路
            logger.error("飞书推送失败（第 %s 次）: %s", attempt + 1, exc)
            if attempt < _PUSH_RETRY_TIMES:
                time.sleep(_PUSH_RETRY_SLEEP)
    return False


def push_alert(stock_name: str, stock_code: str, alert_type: str, severity: str,
               message: str, action: str) -> dict:
    """推送告警，返回 {result, channel, direct_sent, webhook_ok}；
    result 三态 delivered / failed / not_configured（批A A4）。

    单条投递原则：同一逻辑告警只产生一条飞书消息。
    双通道（webhook 卡片 + 机器人直发）同时启用时，优先 webhook 卡片，
    仅当 webhook 失败后才用机器人直发兜底，不再并发双发（消息轰炸根因之一）。
    """
    # 股票标识统一格式：代码在前、名称紧随（600519 贵州茅台）
    stock_label = f"{stock_code} {stock_name}" if stock_name and stock_name != stock_code else stock_code
    text = _format_alert_text(alert_type, stock_label, severity, action, message)
    direct_on = bool(settings.feishu_bridge_alert_direct)
    direct_ids = bool(settings.feishu_admin_open_ids.strip())
    webhook_on = bool(settings.feishu_webhook_url)

    direct_sent = 0
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
        webhook_ok = _post_webhook(payload, stock_name, stock_code)
        # webhook 失败且机器人直发可用时兜底，避免告警静默
        if not webhook_ok and direct_on and direct_ids:
            direct_sent = _direct_alert(text)
    elif direct_on:
        direct_sent = _direct_alert(text)

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
