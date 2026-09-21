"""买卖点信号 · 本地日线仓库 · 历史段回补 / 除权重置（批1.5 容量修复）

历史段经 `get_datasource().fetch_daily_kline`（默认 qfq）拉 420 自然日 ≈250+ 根，落本地库。
- **可中断续跑**：默认跳过已足 `min_bars` 的票（断点续跑靠本地库自身状态，不靠外部进度文件）。
- **除权重置**：`kline_ingest` 检出除权后调 `backfill(..., rebuild=True)` —— 先删该票旧行再整段重取，
  避免 qfq 基准漂移导致指标静默失真（核验结论 v2 §11.4 硬要求）。
- 单只失败只计数不抛出；批间 sleep 控速，避免触发源站反爬。
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from app.services import kline_store as store

LOOKBACK_DAYS = 420
MIN_BARS = 250
BATCH_SIZE = 200
SLEEP_BETWEEN = 0.5


def fetch_history(code: str, source=None, lookback_days: int = LOOKBACK_DAYS,
                  end_date: str | None = None, name: str = "") -> list[dict]:
    """拉一只票历史日线（qfq）→ 本地行列表；空/异常返回 []（不抛出）"""
    end = end_date or time.strftime("%Y-%m-%d")
    start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    try:
        if source is None:
            from app.datasource.fallback import get_datasource
            source = get_datasource()
        frame = source.fetch_daily_kline(code, start, end)
    except Exception:  # noqa: BLE001 单只失败由调用方计数
        return []
    if frame is None or len(frame) == 0 or "close" not in getattr(frame, "columns", []):
        return []
    rows = []
    for rec in frame.to_dict("records"):
        close = rec.get("close")
        if close is None or close != close:  # NaN 行跳过
            continue
        rows.append({"stock_code": code, "trade_date": str(rec.get("date"))[:10], "open": rec.get("open"),
                     "high": rec.get("high"), "low": rec.get("low"), "close": close,
                     "volume": rec.get("volume"), "amount": rec.get("amount"),
                     "stock_name": name, "source": "backfill", "adjust": "qfq"})
    return rows


def pending_codes(path: str | None = None, codes: list[str] | None = None,
                 min_bars: int = MIN_BARS) -> list:
    """待回补清单：已足够的不算；**本地完全没记录的票也算**（首次全量填充的关键）

    codes 为空时用股票池补全「库里没记录的」部分；返回去重后的代码列表。
    """
    with store.connect(path) as conn:
        rows = conn.execute(
            "SELECT stock_code, COUNT(*) FROM daily_kline GROUP BY stock_code").fetchall()
    have = {r[0]: int(r[1]) for r in rows}
    pool = codes
    if pool is None:
        try:
            from app.datasource.fallback import get_datasource
            spot = get_datasource().fetch_spot_universe()
            pool = [str(c) for c in spot["code"].tolist()] if spot is not None and not spot.empty else []
        except Exception:  # noqa: BLE001 股票池失败：退化为仅本地已知的不足票
            pool = []
    known = {r[0] for r in rows}
    merged = list(dict.fromkeys([str(c) for c in pool if str(c)] + [c for c in known if c not in pool]))
    return [c for c in merged if have.get(c, 0) < min_bars]


def backfill(codes: list[str], path: str | None = None, batch_size: int = BATCH_SIZE,
             min_bars: int = MIN_BARS, rebuild: bool = False, lookback_days: int = LOOKBACK_DAYS,
             sleep_between: float = SLEEP_BETWEEN, source=None, on_progress=None,
             names: dict | None = None, workers: int = 1) -> dict:
    """批量回补或重建；返回 {requested, written_bars, ok, skipped, failed, seconds}"""
    started = time.time()
    todo = [str(c) for c in codes if str(c)]
    if rebuild:
        for code in todo:
            store.delete_code(code, path)
    summary = {"requested": len(todo), "written_bars": 0, "ok": 0, "skipped": 0,
               "failed": 0, "failed_codes": [], "seconds": 0.0}
    if source is None:
        from app.datasource.fallback import get_datasource
        source = get_datasource()
    names = names or {}
    n_total = len(todo)

    def _one(code: str) -> tuple:
        if not rebuild and store.has_enough(code, min_bars, path):
            return code, "skipped", 0
        rows = fetch_history(code, source=source, lookback_days=lookback_days,
                             name=names.get(code, ""))
        if len(rows) < min_bars:
            return code, "failed", 0
        return code, "ok", store.upsert_bars(rows, path)

    done = 0
    if workers and workers > 1 and n_total > workers:
        pool = ThreadPoolExecutor(max_workers=int(workers))
        try:
            for code, status, n in pool.map(_one, todo):
                if status == "skipped":
                    summary["skipped"] += 1
                elif status == "failed":
                    summary["failed"] += 1
                    if len(summary["failed_codes"]) < 20:
                        summary["failed_codes"].append(code)
                else:
                    summary["ok"] += 1
                    summary["written_bars"] += n
                done += 1
                if on_progress is not None and done % 50 == 0:
                    on_progress(done, n_total, summary)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    else:
        for i, code in enumerate(todo):
            _, status, n = _one(code)
            if status == "skipped":
                summary["skipped"] += 1
            elif status == "failed":
                summary["failed"] += 1
                if len(summary["failed_codes"]) < 20:
                    summary["failed_codes"].append(code)
            else:
                summary["ok"] += 1
                summary["written_bars"] += n
            if on_progress is not None and (i + 1) % 50 == 0:
                on_progress(i + 1, n_total, summary)
            if len(todo) > batch_size and (i + 1) % batch_size == 0:
                time.sleep(sleep_between)
    summary["seconds"] = round(time.time() - started, 1)
    return summary
