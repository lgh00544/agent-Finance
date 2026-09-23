import sys, traceback, inspect, io, os
sys.path.insert(0, r"D:\self\backend")
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
out = []
out.append("=== A. mechanism: empty df date access ===")
try:
    import pandas as pd
    pd.DataFrame([])["date"]
except Exception as e:
    out.append("pd.DataFrame([])['date'] -> %s: %r" % (type(e).__name__, e))
out.append("")
out.append("=== B. upstream source: stock_zh_a_daily first 70 lines, date/requests lines ===")
import akshare
from akshare.stock import stock_zh_a_sina as m
src = inspect.getsource(m.stock_zh_a_daily).splitlines()
for i, ln in enumerate(src[:70], start=1):
    if "date" in ln or "requests.get" in ln or "return" in ln:
        out.append("  src[%d] %s" % (i, ln.strip()[:120]))
out.append("")
out.append("=== B2. actual file:line of the data_df[\"date\"] access ===")
fp = inspect.getsourcefile(m.stock_zh_a_daily)
start = inspect.getsourcelines(m.stock_zh_a_daily)[1]
out.append("  file=%s  def starts at line %d" % (fp, start))
for i, ln in enumerate(src, start=1):
    if 'data_df["date"]' in ln:
        out.append("  LINE %d: %s" % (i, ln.strip()[:140]))
out.append("")
out.append("=== C. live akshare stock_zh_a_daily(sh600000) ===")
try:
    df = akshare.stock_zh_a_daily(symbol="sh600000", start_date="20260101", end_date="20260918", adjust="qfq")
    out.append("  OK shape=%s cols=%s" % (df.shape, list(df.columns)))
except Exception as e:
    out.append("  EXC %s: %r" % (type(e).__name__, e))
out.append("")
out.append("=== D. project wrapper fetch_daily_kline(600000) ===")
try:
    from app.datasource.akshare_source import get_datasource
    ds = get_datasource()
    df = ds.fetch_daily_kline("600000", "2026-01-01", "2026-09-18")
    out.append("  OK shape=%s" % (df.shape,))
except Exception as e:
    out.append("  EXC %s: %r" % (type(e).__name__, e))
open(os.path.join(OUT, "dsl_rerun_probe1.out.txt"), "w", encoding="utf-8").write("\n".join(out))
print("PROBE1_DONE")