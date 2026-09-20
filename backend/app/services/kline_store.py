"""买卖点信号 · 本地日线仓库（批1.5 容量修复）· 存储层

设计要点：
- **只落本地 SQLite**（默认 `data/kline.db`，`KLINE_DB_PATH` 可覆盖），**不进 `Base.metadata`**
  —— 否则 `sync_manager.cmd_backup()`（全表云→地同步）会被百万行日线炸掉（37k 行 ≈6.8min）。
- 主键 `(stock_code, trade_date)`，写入幂等（`ON CONFLICT DO UPDATE`）。
- 当日不复权快照与 qfq 历史在「当日」等价（核验结论 v2 §11.4 已验证）；除权日由调用方
  （`kline_ingest`）用「快照昨收 ≠ 本地前收」检出并触发该票历史段重建。
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.core.config import settings

_LOCK = threading.Lock()

_DDL = """
CREATE TABLE IF NOT EXISTS daily_kline (
    stock_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL,
    source TEXT NOT NULL DEFAULT '',
    adjust TEXT NOT NULL DEFAULT 'qfq',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (stock_code, trade_date)
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_daily_kline_date ON daily_kline (trade_date)",
    "CREATE INDEX IF NOT EXISTS ix_daily_kline_code ON daily_kline (stock_code)",
)

_BAR_COLS = ("open", "high", "low", "close", "volume", "amount")


def db_path(path: str | None = None) -> Path:
    """本地日线库路径：显式 path > 环境 KLINE_DB_PATH > settings.data_dir/kline.db"""
    if path:
        return Path(path)
    env = os.environ.get("KLINE_DB_PATH")
    if env:
        return Path(env)
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "kline.db"


@contextmanager
def connect(path: str | None = None):
    """本地库连接（WAL + busy_timeout，建表幂等）"""
    target = db_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=15)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        for ddl in (_DDL, *_INDEXES):
            conn.execute(ddl)
        yield conn
    finally:
        conn.close()


def upsert_bars(rows: list[dict], path: str | None = None) -> int:
    """幂等写入日线（每行需 stock_code/trade_date + _BAR_COLS 任一）；返回写入行数"""
    if not rows:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    payload = []
    for row in rows:
        if not row.get("stock_code") or not row.get("trade_date"):
            continue
        payload.append((
            str(row["stock_code"]), str(row["trade_date"]),
            *(None if row.get(c) is None else float(row[c]) for c in _BAR_COLS),
            str(row.get("source") or ""), str(row.get("adjust") or "qfq"), now,
        ))
    if not payload:
        return 0
    sql = ("INSERT INTO daily_kline "
           "(stock_code, trade_date, open, high, low, close, volume, amount, source, adjust, updated_at) "
           "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
           "ON CONFLICT(stock_code, trade_date) DO UPDATE SET "
           "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, "
           "volume=excluded.volume, amount=excluded.amount, source=excluded.source, "
           "adjust=excluded.adjust, updated_at=excluded.updated_at")
    with _LOCK, connect(path) as conn:
        conn.executemany(sql, payload)
        conn.commit()
    return len(payload)


def load_bars(code: str, start: str | None = None, end: str | None = None,
              path: str | None = None) -> list[dict]:
    """读某票 [start, end] 的日线（升序）；日期为 'YYYY-MM-DD'"""
    sql = ("SELECT stock_code, trade_date, open, high, low, close, volume, amount "
           "FROM daily_kline WHERE stock_code = ?")
    args: list = [code]
    if start:
        sql += " AND trade_date >= ?"
        args.append(start)
    if end:
        sql += " AND trade_date <= ?"
        args.append(end)
    sql += " ORDER BY trade_date ASC"
    with connect(path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [{"stock_code": r[0], "trade_date": r[1], "date": r[1], "open": r[2], "high": r[3],
             "low": r[4], "close": r[5], "volume": r[6], "amount": r[7]} for r in rows]


def load_frame(code: str, start: str | None = None, end: str | None = None, path: str | None = None):
    """读为 DataFrame（date/open/high/low/close/volume，升序）；不足 1 行返回 None

    不注入 change_pct：由 `services/indicator.pct_change` 口径统一推导，避免第二套算法。
    """
    rows = load_bars(code, start, end, path)
    if not rows:
        return None
    import pandas as pd
    frame = pd.DataFrame(rows)
    return frame[["date", "open", "high", "low", "close", "volume"]]


def prev_close(code: str, before: str, path: str | None = None) -> float | None:
    """`before` 之前最近一根的收盘价（用于除权检测：与快照昨收比对）"""
    with connect(path) as conn:
        row = conn.execute(
            "SELECT close FROM daily_kline WHERE stock_code = ? AND trade_date < ? "
            "ORDER BY trade_date DESC LIMIT 1", (code, before)).fetchone()
    return None if row is None or row[0] is None else float(row[0])


def stats(path: str | None = None) -> dict:
    """仓库概览：总行数 / 股票数 / 日期范围（用于回补与巡检）"""
    with connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
        codes = conn.execute("SELECT COUNT(DISTINCT stock_code) FROM daily_kline").fetchone()[0]
        span = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_kline").fetchone()
    return {"rows": total, "codes": codes, "min_date": span[0], "max_date": span[1]}


def has_enough(code: str, min_bars: int, path: str | None = None) -> bool:
    """该票本地是否已有 ≥min_bars 根（扫描是否可完全离线判定）"""
    with connect(path) as conn:
        n = conn.execute("SELECT COUNT(*) FROM daily_kline WHERE stock_code = ?", (code,)).fetchone()[0]
    return int(n) >= int(min_bars)


def delete_code(code: str, path: str | None = None) -> int:
    """清空某票全部本地日线（除权重建前调用）"""
    with _LOCK, connect(path) as conn:
        cur = conn.execute("DELETE FROM daily_kline WHERE stock_code = ?", (code,))
        conn.commit()
        return int(cur.rowcount or 0)
