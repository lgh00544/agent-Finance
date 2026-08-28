"""飞书机器人直发文本：手取 tenant_access_token + requests 发单聊消息。
lark-oapi 1.7.3 的 Client.im.v1.message.create 链路在该版本不可用（Client 类无 im 属性，
Client.__init__ 注释列了但实际未注入 im service），改用 SDK 构造 request + requests 发 REST。
失败记日志返回 False，不抛异常不阻断主链路。"""
import json
import logging
import threading
import time
from typing import Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

_token_cache: dict = {"token": None, "expire_at": 0.0}
_token_lock = threading.Lock()
_create_request_cls = None  # 懒加载


def _ensure_request_cls():
    """懒加载 SDK 的 CreateMessageRequest/Body 类；只用来校验 builder，不发请求。"""
    global _create_request_cls
    if _create_request_cls is None:
        from lark_oapi.api.im.v1.model import CreateMessageRequest, CreateMessageRequestBody
        _create_request_cls = (CreateMessageRequest, CreateMessageRequestBody)
    return _create_request_cls


def _get_tenant_token() -> Optional[str]:
    """取 tenant_access_token，本地缓存到过期前 5 分钟。失败返回 None。"""
    now = time.time()
    with _token_lock:
        if _token_cache["token"] and _token_cache["expire_at"] > now:
            return _token_cache["token"]
    try:
        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
            timeout=5,
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.warning("取 token 失败: %s", data)
            return None
        token = data["tenant_access_token"]
        expire = int(data.get("expire", 7200)) - 300
        with _token_lock:
            _token_cache["token"] = token
            _token_cache["expire_at"] = now + expire
        return token
    except Exception as exc:  # noqa: BLE001
        logger.error("取 token 异常: %s", exc)
        return None


def send_text(open_id: str, text: str) -> bool:
    """直发文本到管理员单聊；未启用/无凭证/失败均返回 False。"""
    if not (settings.feishu_bot_enable and settings.feishu_app_id and open_id):
        return False
    try:
        _ensure_request_cls()  # 验证 SDK builder 可用
        token = _get_tenant_token()
        if not token:
            return False
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "open_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            logger.info("飞书直发成功: %s", open_id)
            return True
        logger.warning("飞书直发失败 code=%s msg=%s", data.get("code"), data.get("msg"))
    except Exception as exc:  # noqa: BLE001 直发失败不阻断主链路
        logger.error("飞书直发异常: %s", exc)
    return False


def download_resource(message_id: str, file_key: str, resource_type: str = "image") -> bytes:
    """下载消息资源（图片/文件）→ bytes；token 复用本模块缓存，失败抛异常。"""
    token = _get_tenant_token()
    if not token:
        raise RuntimeError("获取飞书 token 失败")
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}",
        params={"type": resource_type},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def send_card(open_id: str, title: str, text: str, buttons: list[dict] | None = None) -> bool:
    """发交互卡片（msg_type=interactive，按钮 value 回传 action）；复用现有 token。"""
    if not (settings.feishu_bot_enable and settings.feishu_app_id and open_id):
        return False
    try:
        token = _get_tenant_token()
        if not token:
            return False
        elements = [{"tag": "div", "text": {"tag": "lark_md", "content": text}}]
        for b in buttons or []:
            elements.append({"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": b["label"]},
                 "type": b.get("type", "default"), "value": b.get("value", {})}]})
        card = {"config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
                "elements": elements}
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "open_id"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
            json={"receive_id": open_id, "msg_type": "interactive",
                  "content": json.dumps(card, ensure_ascii=False)}, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            logger.info("飞书卡片发送成功: %s", open_id)
            return True
        logger.warning("飞书卡片发送失败 code=%s msg=%s", data.get("code"), data.get("msg"))
    except Exception as exc:  # noqa: BLE001 卡片失败不阻断
        logger.error("飞书卡片发送异常: %s", exc)
    return False


_bot_open_id: str = ""


def get_bot_open_id() -> str:
    """取机器人自身 open_id（群聊 @ 过滤用）；进程内缓存，失败返回空。"""
    global _bot_open_id
    if _bot_open_id:
        return _bot_open_id
    token = _get_tenant_token()
    if not token:
        return ""
    try:
        resp = requests.get("https://open.feishu.cn/open-apis/bot/v3/info",
                            headers={"Authorization": f"Bearer {token}"}, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            _bot_open_id = str((data.get("bot") or {}).get("open_id", ""))
    except Exception as exc:  # noqa: BLE001 bot 信息获取失败不阻断
        logger.warning("获取机器人 open_id 失败: %s", exc)
    return _bot_open_id
