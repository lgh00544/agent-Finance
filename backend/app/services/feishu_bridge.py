"""飞书机器人桥：长连接收文本 + 白名单校验 + 会话上下文 + 智能路由分发回复；ENABLE=false 零加载。
lark-oapi 的 import 与 ws.Client 全部在桥线程内完成（避免主线程 asyncio loop 绑定冲突）。"""
import json
import logging
import re
import threading
import time
from collections import deque
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_ws_client = None
_thread = None
_last_event_at = None
_sessions: dict[str, deque] = {}  # open_id → 最近 5 轮用户文本（供指代消解）
_pending: dict[str, dict] = {}  # open_id → 持仓识别待确认 {result, expires}
_recent_files: dict[str, float] = {}  # file_key → 处理时间（5 分钟幂等）
_PENDING_TTL = 300
_MAX_IMG = 10 * 1024 * 1024
_MAX_MEDIA = 50 * 1024 * 1024
_DESCRIBE_PROMPT = "用一句中文描述这张图片内容；若是 K 线/行情截图请简要说明。只输出描述。"


def _admin_open_ids() -> list:
    return [s.strip() for s in settings.feishu_admin_open_ids.split(",") if s.strip()]


def _reply(open_id: str, text: str) -> None:
    from app.services.feishu_sender import send_text

    send_text(open_id, text)


def _prev_turn(open_id: str) -> str:
    dq = _sessions.get(open_id)
    return dq[-1] if dq else ""


def _remember(open_id: str, user_text: str) -> None:
    _sessions.setdefault(open_id, deque(maxlen=5)).append(user_text)


def _on_message(data) -> None:
    global _last_event_at
    _last_event_at = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        event = data.event
        sender = (event.sender.sender_id.open_id
                  if event.sender and event.sender.sender_id else None)
        if not sender:
            return
        admins = _admin_open_ids()
        if not admins:
            logger.warning("飞书桥未配白名单，收到首条消息 open_id=%s（请填入 FEISHU_ADMIN_OPEN_IDS）", sender)
            return
        if sender not in admins:
            logger.info("飞书桥忽略非白名单 sender=%s", sender)
            return
        msg = event.message
        if msg.message_type == "text":
            try:
                text = (json.loads(msg.content or "{}") or {}).get("text", "")
            except json.JSONDecodeError:
                text = ""
            confirm = _confirm_or_cancel(sender, text)  # 「确认/取消」优先于意图路由
            if confirm:
                _reply(sender, confirm)
                return
            from app.services.chat_router import route_and_execute

            reply = route_and_execute(text, _prev_turn(sender), sender)
            _remember(sender, text)
            _reply(sender, reply)
        elif msg.message_type == "image":
            _handle_image(sender, msg.message_id, msg.content)
        elif msg.message_type in ("media", "file"):
            _handle_file(sender, msg.message_id, msg.content)
        else:
            _reply(sender, "暂不支持该消息类型（批4 上线）")
    except Exception as exc:  # noqa: BLE001 单条消息异常不崩溃
        logger.error("飞书桥消息处理失败: %s", exc)


def _dedup(file_key: str) -> bool:
    """同 file_key 5 分钟幂等；顺带清理过期记录"""
    now = time.monotonic()
    for k in [k for k, ts in _recent_files.items() if now - ts > _PENDING_TTL]:
        _recent_files.pop(k, None)
    if file_key in _recent_files:
        return False
    _recent_files[file_key] = now
    return True


def _download_resource(message_id: str, file_key: str, resource_type: str) -> bytes:
    from app.services.feishu_sender import download_resource

    return download_resource(message_id, file_key, resource_type)


def _media_dir() -> Path:
    p = Path(settings.feishu_media_dir)
    return p if p.is_absolute() else settings.data_dir.parent / p


def _recognize_holding_image(data: bytes) -> dict:
    """持仓截图识别：OCR_ENABLE=true → recognize_holding（minimax→paddle 完整链）；否则仅 minimax"""
    from app.services import ocr
    from app.services.multimodal import get_multimodal_client

    if settings.ocr_enable:
        return ocr.recognize_holding(data, "screenshot.png")
    client = get_multimodal_client()
    if client is not None and settings.minimax_ocr_enable:
        result = ocr.MiniMaxOcrEngine(client).recognize(data, "screenshot.png")
        if result and result["recognized"]:
            return result
    raise RuntimeError("无可用识别引擎")


def _describe_image(data: bytes) -> str:
    """非持仓图：minimax 直接描述（未启用 → 无法识别，不调 paddle 兜底）"""
    from app.services.multimodal import get_multimodal_client

    client = get_multimodal_client()
    if client is None:
        return "图片已收到，无法识别内容"
    try:
        return str(client.analyze_image(data, _DESCRIBE_PROMPT))[:200]
    except Exception as exc:  # noqa: BLE001 描述失败回无法识别
        logger.warning("图片描述失败: %s", exc)
        return "图片已收到，无法识别内容"


def _handle_image(open_id: str, message_id: str, content: str) -> None:
    file_key = (json.loads(content or "{}") or {}).get("image_key", "")
    if not file_key or not _dedup(file_key):
        return
    try:
        data = _download_resource(message_id, file_key, "image")
        if len(data) > _MAX_IMG:
            _reply(open_id, "文件过大：图片限 10MB、视频限 50MB")
            return
        result = _recognize_holding_image(data)
        rows = result.get("recognized") or []
        if rows:  # 持仓图 → 预览 + pending 人工确认
            lines = ["识别到持仓（回「确认」保存，或「取消」丢弃）："]
            for r in rows[:10]:
                lines.append(f"{r.get('stock_code')} {r.get('stock_name') or ''} "
                             f"{r.get('shares')}股 成本{r.get('cost_price')} "
                             f"现价{r.get('current_price')} 盈亏{r.get('pnl_pct')}%")
            _pending[open_id] = {"result": result, "expires": time.monotonic() + _PENDING_TTL}
            _reply(open_id, "\n".join(lines))
        else:  # 非持仓图 → 描述
            _reply(open_id, _describe_image(data))
    except Exception as exc:  # noqa: BLE001 单图失败回无法识别，不崩溃
        logger.warning("飞书图片处理失败: %s", exc)
        _reply(open_id, "图片已收到，无法识别内容")


def _handle_file(open_id: str, message_id: str, content: str) -> None:
    data = json.loads(content or "{}") or {}
    file_key, file_name = data.get("file_key", ""), data.get("file_name", "file") or "file"
    if not file_key or not _dedup(file_key):
        return
    try:
        bytes_ = _download_resource(message_id, file_key, "file")
        if len(bytes_) > _MAX_MEDIA:
            _reply(open_id, "文件过大：图片限 10MB、视频限 50MB")
            return
        media_dir = _media_dir()
        media_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|\s]+', "_", file_name)[:60] or "file"
        (media_dir / f"{int(time.time())}_{safe}").write_bytes(bytes_)
        _reply(open_id, f"已收到并保存：{file_name}")
    except Exception as exc:  # noqa: BLE001 保存失败不崩溃
        logger.warning("飞书文件保存失败: %s", exc)
        _reply(open_id, "文件保存失败，请稍后重试")


def _apply_pending(open_id: str, pending: dict) -> str:
    from app.db import repo

    rows = pending["result"].get("recognized") or []
    _pending.pop(open_id, None)
    saved = 0
    today = time.strftime("%Y-%m-%d")
    for r in rows:
        try:
            code = str(r.get("stock_code") or "").strip()
            shares = int(r.get("shares") or 0)
            cost = float(r.get("cost_price") or 0)
            if not (len(code) == 6 and code.isdigit()) or shares <= 0 or cost <= 0:
                continue
            repo.insert_holding(code, str(r.get("stock_name") or code), today,
                                cost, shares, round(cost * shares, 2))
            saved += 1
        except (TypeError, ValueError):
            continue
    return f"已保存 {saved} 条持仓（回复「查持仓」查看）" if saved else "未保存到有效持仓数据"


def _confirm_or_cancel(open_id: str, text: str) -> str | None:
    """「确认/取消」优先：命中待确认持仓 → 落库/丢弃；无 pending 返回 None 走正常路由"""
    pending = _pending.get(open_id)
    if not pending:
        return None
    if pending["expires"] < time.monotonic():
        _pending.pop(open_id, None)
        return None
    if text.strip() in ("确认", "确认保存", "保存"):
        return _apply_pending(open_id, pending)
    if text.strip() in ("取消", "丢弃", "不保存"):
        _pending.pop(open_id, None)
        return "已取消，未保存"
    return None


def _cleanup_media_dir() -> None:
    """启动清理 >7 天媒体文件"""
    try:
        d = _media_dir()
        if d.is_dir():
            cutoff = time.time() - 7 * 86400
            for f in d.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001 清理失败不阻塞启动
        logger.warning("媒体目录清理失败: %s", exc)


def _run() -> None:
    global _ws_client
    from lark_oapi import EventDispatcherHandler
    from lark_oapi.ws import Client

    handler = (EventDispatcherHandler.builder("", "")
               .register_p2_im_message_receive_v1(_on_message).build())
    _ws_client = Client(settings.feishu_app_id, settings.feishu_app_secret,
                        event_handler=handler)
    _ws_client.start()


def start_bridge() -> None:
    """启动桥线程（仅 FEISHU_BOT_ENABLE=true 生效；false 零加载）"""
    global _thread
    if not settings.feishu_bot_enable:
        return
    _cleanup_media_dir()
    _thread = threading.Thread(target=_run, name="feishu-bridge", daemon=True)
    _thread.start()
    logger.info("飞书桥线程已启动（app_id=%s）", settings.feishu_app_id)


def stop_bridge() -> None:
    """SDK 无公开 stop；守护线程随进程退出，仅记日志"""
    logger.info("飞书桥停止（守护线程随进程退出）")


def status() -> dict:
    """桥状态：bridge_enabled=配置开关 / connected=实际连接态（区分运维）"""
    conn = getattr(_ws_client, "_conn", None) if _ws_client else None
    return {"bridge_enabled": settings.feishu_bot_enable,
            "connected": conn is not None,
            "last_event_at": _last_event_at,
            "admin_count": len(_admin_open_ids())}
