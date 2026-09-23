import sys, os
sys.path.insert(0, r"D:\self\backend")
import pandas as pd
from app.services import hot_money_review as hmr
from app.datasource.akshare_source import get_datasource, _market_of
ds = get_datasource()
out = []
out.append("=== _forward_5d_returns signature/behaviour ===")
import inspect
out.append(inspect.getsource(hmr._forward_5d_returns)[:900])
out.append("")
idx = ds.fetch_index_daily("sh000300", "2026-01-01", "2026-09-18")
stk = ds.fetch_daily_kline("600000", "2026-01-01", "2026-09-18")
out.append("bench sh000300 rows=%s cols=%s" % (len(idx), list(idx.columns)))
out.append("stock 600000 rows=%s cols=%s" % (len(stk), list(stk.columns)))
out.append("bench date range: %s -> %s" % (idx["date"].iloc[0] if "date" in idx.columns else "?", idx["date"].iloc[-1] if "date" in idx.columns else "?"))
out.append("trade_date=2026-09-16 present in bench? %s" % ("2026-09-16" in set(idx["date"].astype(str)) if "date" in idx.columns else "no date col"))
out.append("trade_date=2026-09-16 present in stock? %s" % ("2026-09-16" in set(stk["date"].astype(str)) if "date" in stk.columns else "no date col"))
for td in ("2026-09-16", "2026-08-27", "2026-08-25"):
    out.append("  _forward_5d_returns(stk, idx, %s) -> %r" % (td, hmr._forward_5d_returns(stk, idx, td)))
out.append("")
out.append("=== does fetch_daily_kline(000300) raise or return empty? (path evidence) ===")
try:
    df = ds.fetch_daily_kline("000300", "2026-01-01", "2026-09-18")
    out.append("  returned type=%s rows=%s" % (type(df).__name__, 0 if df is None else len(df)))
except Exception as e:
    out.append("  raised %s: %r" % (type(e).__name__, e))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\dsl_rerun_probe5.out.txt", "w", encoding="utf-8").write("\n".join(out))
print("PROBE5_DONE")