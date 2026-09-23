"""买卖点信号体系 · 只读预演（不落库、不改码、不重启、不改观测数据）

用途：在 16:50 正式跑之前，回答「现在这条链路到底能不能跑通」。

零写入保证：
  - 只调用 _scan_one / _scan_batch（`signal_scan.py:56/:100`：两者都不落库）
  - 落库动作仅在 `_persist()`（`signal_scan.py:130`），本脚本**不调用** `scan_signal_triggers()`
  - 不重启后端、不动任何归档、不写 signal_trigger 任何一行

用法:
    D:/self/.venv/Scripts/python.exe D:/self/signal_rehearsal.py [交易日 YYYY-MM-DD] [抽样只数]
    默认: 2026-09-17（已收盘完整数据） 40 只
"""
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, r"D:/self/backend")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from app.datasource import market_hours  # noqa: E402
from app.datasource.fallback import get_datasource  # noqa: E402
from app.services import signal_scan as ss  # noqa: E402
from app.services.signal_registry import list_all  # noqa: E402

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-09-17"
SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 40

print("== 0. 前置状态 ==")
print("  now                  =", datetime.now().strftime("%Y-%m-%d %H:%M:%S %A"))
print("  is_trading_day(now)  =", market_hours.is_trading_day())
try:
    print("  snapshot_allowed     =", market_hours.snapshot_allowed())
except Exception as exc:  # noqa: BLE001
    print("  snapshot_allowed     = <err>", exc)

defs = list_all()
print("  signal defs          =", len(defs))
print("  defs ids             =", ",".join(d.id for d in defs))
print("  target trade_date    =", DAY, "| sample =", SAMPLE)

src = get_datasource()

print("== A. 股票池 fetch_spot_universe（09-17 失败点） ==")
spot, recs = None, []
t = time.time()
try:
    spot = src.fetch_spot_universe()
    recs = spot.to_dict("records") if spot is not None else []
    print("  OK rows=%s elapsed=%.1fs" % (0 if spot is None else len(spot), time.time() - t))
except Exception as exc:  # noqa: BLE001
    print("  FAIL %s: %s" % (type(exc).__name__, exc))

print("== B. 日线源 fetch_daily_kline（单只、end=%s） ==" % DAY)
for code in ("600519", "000001", "300750"):
    t = time.time()
    try:
        k = src.fetch_daily_kline(code, "2025-07-01", DAY)
        last = str(k["date"].iloc[-1])[:10] if "date" in getattr(k, "columns", []) else "?"
        print("  %s OK rows=%d last=%s elapsed=%.1fs" % (code, len(k), last, time.time() - t))
    except Exception as exc:  # noqa: BLE001
        print("  %s FAIL %s: %s" % (code, type(exc).__name__, exc))

print("== C. 抽样干跑 _scan_batch（不落库） ==")
codes = [str(r.get("code") or "") for r in recs if r.get("code")]
names = {str(r.get("code")): str(r.get("name") or "") for r in recs if r.get("code")}
print("  universe=%d" % len(codes))
if codes:
    step = max(1, len(codes) // SAMPLE)
    pick = codes[::step][:SAMPLE]
    items = [{"code": c, "name": names.get(c, "")} for c in pick]
    ctx = {
        "trade_date": DAY, "defs": defs, "source": src, "today": set(), "cooldown": set(),
        "start": (datetime.strptime(DAY, "%Y-%m-%d") - timedelta(days=ss._LOOKBACK_DAYS)).strftime("%Y-%m-%d"),
        "end": DAY,
    }
    t = time.time()
    rows, errors, dropped = ss._scan_batch(items, ctx, 120)
    el = time.time() - t
    dist = Counter(r["signal_id"] for r in rows)
    print("  elapsed=%.1fs | 单只=%.0fms | rows=%d errors=%d dropped=%d"
          % (el, el * 1000 / max(1, len(items)), len(rows), errors, dropped))
    print("  命中信号分布:", dict(dist))
    print("  命中明细(前 12):", [(r["stock_code"], r["signal_id"], r["trigger_close"]) for r in rows[:12]])
    print("  外推全市场 ≈ %.0fs（%d 只；内部总预算 %ds / 单批预算 %ds）"
          % (el * len(codes) / max(1, len(items)), len(codes), ss._TOTAL_BUDGET_SECONDS, ss._BATCH_BUDGET_SECONDS))

print("== D. 今日 bar 可得性（16:50 依赖 dt 匹配） ==")
today = datetime.now().strftime("%Y-%m-%d")
if today == DAY:
    print("  target == today，已由上面覆盖")
else:
    for code in ("600519", "000001"):
        try:
            k = src.fetch_daily_kline(code, "2025-07-01", today)
            last = str(k["date"].iloc[-1])[:10] if "date" in getattr(k, "columns", []) else "?"
            print("  %s end=%s last=%s rows=%d" % (code, today, last, len(k)))
        except Exception as exc:  # noqa: BLE001
            print("  %s FAIL %s: %s" % (code, type(exc).__name__, exc))

print("== 完成：本脚本未写 signal_trigger 任何一行 ==")
