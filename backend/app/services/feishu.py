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


def push_alert(stock_name: str, stock_code: str, alert_type: str, severity: str,
               message: str, action: str) -> bool:
    """推送告警到飞书，返回是否推送成功。"""
    if not settings.feishu_webhook_url:
        logger.info("[飞书未配置] %s %s | %s | 建议: %s | %s",
                    stock_name, stock_code, alert_type, action, message)
        return False

    # 股票标识统一格式：代码在前、名称紧随（600519 贵州茅台）
    stock_label = f"{stock_code} {stock_name}" if stock_name and stock_name != stock_code else stock_code
    text = (
        f"【{alert_type}】{stock_label}\n"
        f"严重度: {severity} | 建议操作: {action}\n"
        f"{message}"
    )
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
