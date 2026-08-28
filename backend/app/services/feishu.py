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


def _direct_alert(text: str) -> None:
    """告警机器人直发管理员单聊（webhook 双通道之一；失败内部降级不抛）"""
    try:
        from app.services.feishu_sender import send_text

        for oid in settings.feishu_admin_open_ids.split(","):
            if oid.strip():
                send_text(oid.strip(), text)
    except Exception as exc:  # noqa: BLE001 直发失败不影响 webhook 通道
        logger.error("飞书直发降级失败: %s", exc)


def push_alert(stock_name: str, stock_code: str, alert_type: str, severity: str,
               message: str, action: str) -> bool:
    """推送告警到飞书，返回是否推送成功。"""
    # 股票标识统一格式：代码在前、名称紧随（600519 贵州茅台）
    stock_label = f"{stock_code} {stock_name}" if stock_name and stock_name != stock_code else stock_code
    text = (
        f"【{alert_type}】{stock_label}\n"
        f"严重度: {severity} | 建议操作: {action}\n"
        f"{message}"
    )
    # 直发通道（FEISHU_BRIDGE_ALERT_DIRECT=true 才启用；失败降级 webhook，不阻断）
    if settings.feishu_bridge_alert_direct:
        _direct_alert(text)

    if not settings.feishu_webhook_url:
        logger.info("[飞书未配置] %s %s | %s | 建议: %s | %s",
                    stock_name, stock_code, alert_type, action, message)
        return False

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
        logger.info("飞书推送成功: %s %s", stock_name, stock_code)
        return True
    except Exception as exc:  # noqa: BLE001 推送失败不应影响主链路
        logger.error("飞书推送失败: %s", exc)
        return False
