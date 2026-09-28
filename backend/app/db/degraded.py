"""数据库容灾降级标记（A 方案：防丢）。

背景：降级期间应用写的是本地 SQLite；云端恢复后若照常执行 sync_manager backup，
本地表会被「全表 DELETE + 云端覆盖」（sync_manager.py:305）⇒ 降级期数据从活库消失。
本模块把「上一轮处于降级态」持久化到 <data_dir>/db_degraded.json，供启动同步与
sync_manager 判断：有标记时禁止云端→本地覆盖，必须先合并（merge-up）或显式放弃。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from app.core.config import settings

MARKER_NAME = "db_degraded.json"


def marker_path() -> Path:
    """标记文件路径；DB_DEGRADED_MARKER 可覆盖（测试隔离用）。"""
    override = os.environ.get("DB_DEGRADED_MARKER")
    if override:
        return Path(override)
    return Path(settings.data_dir) / MARKER_NAME


def read() -> dict | None:
    """读取降级标记；不存在或损坏一律返回 None（不得阻塞启动）。"""
    path = marker_path()
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def mark(reason: str, requested: str, active: str, db_path: str = "") -> dict:
    """写入降级标记；已存在则保留最初的 degraded_since（记录降级起点，供水位合并用）。"""
    existing = read() or {}
    now = datetime.now().isoformat(timespec="seconds")
    info = {
        "degraded_since": existing.get("degraded_since") or now,
        "last_seen": now,
        "requested_backend": requested,
        "active_backend": active,
        "reason": reason,
        "sqlite_path": db_path,
        "pid": os.getpid(),
    }
    try:
        path = marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 写标记失败也不能拖垮启动
        pass
    return info


def clear() -> bool:
    """清除标记：仅在合并上云成功后，或人工明确放弃合并时调用。"""
    try:
        path = marker_path()
        if path.exists():
            path.unlink()
        return True
    except Exception:  # noqa: BLE001
        return False


def guard_backup() -> dict:
    """启动同步/备份前的守卫：有降级标记则禁止云端→本地覆盖。"""
    info = read()
    if not info:
        return {"blocked": False, "marker": None, "reason": ""}
    reason = (
        "检测到上一轮处于容灾降级（%s 起；%s）：本地库可能含降级期数据，"
        "已禁止云端→本地全表覆盖。请先执行 python sync_manager.py merge-up 合并上云"
        "（或 degraded-clear 明确放弃合并）"
        % (info.get("degraded_since"), info.get("reason"))
    )
    return {"blocked": True, "marker": info, "reason": reason}
