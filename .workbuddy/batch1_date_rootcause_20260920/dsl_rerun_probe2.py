import sys, time, traceback, os
sys.path.insert(0, r"D:\self\backend")
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
out = []
from app.services import hot_money_review as hmr
out.append("=== 0. caller constant ===")
out.append("  _BENCH_INDEX = %r" % getattr(hmr, "_BENCH_INDEX", "N/A"))
from app.datasource.akshare_source import get_datasource, _market_of
ds = get_datasource()
START, END = "2026-01-01", "2026-09-18"
out.append("")
out.append("=== 1. rerun original params: fetch_daily_kline(start=%s, end=%s) ===" % (START, END))
for code in ["688620", "688004", "601579", "600000"]:
    t0 = time.time()
    try:
        df = ds.fetch_daily_kline(code, START, END)
        out.append("  %s (%s) OK rows=%s cols=%s %.2fs" % (code, _market_of(code), 0 if df is None else len(df), list(df.columns) if df is not None else None, time.time() - t0))
    except Exception as e:
        out.append("  %s (%s) EXC %s: %r %.2fs" % (code, _market_of(code), type(e).__name__, e, time.time() - t0))
bench = getattr(hmr, "_BENCH_INDEX", None)
if bench:
    t0 = time.time()
    try:
        df = ds.fetch_daily_kline(bench, START, END)
        out.append("  BENCH %s (%s) OK rows=%s %.2fs" % (bench, _market_of(bench), 0 if df is None else len(df), time.time() - t0))
    except Exception as e:
        out.append("  BENCH %s (%s) EXC %s: %r %.2fs" % (bench, _market_of(bench), type(e).__name__, e, time.time() - t0))
out.append("")
out.append("=== 2. direct akshare upstream (bypass project wrapper) ===")
import akshare as ak
for sym in ["sz000300", "sh000300", "sh600000"]:
    try:
        df = ak.stock_zh_a_daily(symbol=sym, start_date=START.replace("-", ""), end_date=END.replace("-", ""), adjust="qfq")
        out.append("  %s OK shape=%s" % (sym, df.shape))
    except Exception as e:
        out.append("  %s EXC %s: %r" % (sym, type(e).__name__, e))
        tb = [x.strip() for x in traceback.format_exc().splitlines() if x.strip()]
        out.append("    TB: " + " | ".join(tb[-4:])[:300])
out.append("")
out.append("=== 3. upstream empty-frame behaviour ===")
import pandas as pd
for label, frame in (("pd.DataFrame(None)", pd.DataFrame(None)), ("pd.DataFrame([])", pd.DataFrame([]))):
    try:
        frame["date"]
        out.append("  %s[\"date\"] -> no error (cols=%s)" % (label, list(frame.columns)))
    except Exception as e:
        out.append("  %s[\"date\"] -> %s: %r (cols=%s)" % (label, type(e).__name__, e, list(frame.columns)))
open(os.path.join(OUT, "dsl_rerun_probe2.out.txt"), "w", encoding="utf-8").write("\n".join(out))
print("PROBE2_DONE")