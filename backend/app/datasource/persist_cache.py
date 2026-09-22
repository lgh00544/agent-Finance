"""跨进程磁盘缓存（数据源二级缓存）· 只给 TTL 长、按票取一次的外挂数据用

背景：数据源缓存 ``cache``（MemoryCache）随进程结束清空，导致每轮因子回测都把
300 票的财务/资金/新闻重拉一遍（实测 ≈15s/票）。本模块用 SQLite 落盘做二级缓存：
内存未命中 → 磁盘命中即复用（零网络请求）；取数成功则写穿（内存 + 磁盘）。

不进 ``Base.metadata``（同 kline_store：避免云端全表同步被缓存表拖累）。
"""
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings

_LOCK = threading.Lock()

_DDL = ("CREATE TABLE IF NOT EXISTS cache_entry ("
        "cache_key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL NOT NULL)")


def db_path(path: str | None = None) -> Path:
    """磁盘缓存库路径：显式 path > 环境 DATASOURCE_CACHE_DB > settings.data_dir/datasource_cache.db"""
    if path:
        return Path(path)
    env = os.environ.get("DATASOURCE_CACHE_DB")
    if env:
        return Path(env)
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "datasource_cache.db"


@contextmanager
def connect(path: str | None = None):
    """磁盘缓存连接（WAL + busy_timeout，建表幂等）"""
    target = db_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=15)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(_DDL)
        yield conn
    finally:
        conn.close()


def get(key: str, path: str | None = None) -> str | None:
    """命中且未过期返回值；过期条目顺手删除。任何异常按未命中处理（缓存不得影响主流程）"""
    try:
        with _LOCK, connect(path) as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache_entry WHERE cache_key = ?", (key,)).fetchone()
            if row is None:
                return None
            if float(row[1]) <= time.time():
                conn.execute("DELETE FROM cache_entry WHERE cache_key = ?", (key,))
                conn.commit()
                return None
            return row[0]
    except Exception:  # noqa: BLE001 缓存故障一律降级为未命中
        return None


def set(key: str, value: str, ttl_seconds: float, path: str | None = None) -> bool:
    """写穿磁盘缓存；失败返回 False（不影响主流程）"""
    if not ttl_seconds or float(ttl_seconds) <= 0:
        return False
    try:
        with _LOCK, connect(path) as conn:
            conn.execute(
                "INSERT INTO cache_entry (cache_key, value, expires_at) VALUES (?,?,?) "
                "ON CONFLICT(cache_key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at",
                (key, value, time.time() + float(ttl_seconds)))
            conn.commit()
        return True
    except Exception:  # noqa: BLE001
        return False


def purge_expired(path: str | None = None) -> int:
    """清理过期条目，返回删除行数（巡检可用）"""
    try:
        with _LOCK, connect(path) as conn:
            cur = conn.execute("DELETE FROM cache_entry WHERE expires_at <= ?", (time.time(),))
            conn.commit()
            return int(cur.rowcount or 0)
    except Exception:  # noqa: BLE001
        return 0
