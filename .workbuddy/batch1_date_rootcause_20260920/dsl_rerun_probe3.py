import sys, os
sys.path.insert(0, r"D:\self\backend")
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
out = []
from app.datasource.akshare_source import get_datasource, _market_of
import akshare as ak
out.append("=== 1. code attribution ===")
for c in ("000300", "600000", "688620", "000001"):
    out.append("  _market_of(%r) = %r" % (c, _market_of(c)))
out.append("")
out.append("=== 2. primary (eastmoney stock_zh_a_hist) on 000300 vs 600000 ===")
for sym in ["000300", "600000"]:
    try:
        df = ak.stock_zh_a_hist(symbol=sym, period="daily", start_date="20260101", end_date="20260918", adjust="qfq")
        out.append("  stock_zh_a_hist(%r) OK shape=%s cols=%s" % (sym, df.shape, list(df.columns)[:6]))
    except Exception as e:
        out.append("  stock_zh_a_hist(%r) EXC %s: %r" % (sym, type(e).__name__, str(e)[:150]))
out.append("")
out.append("=== 3. right index interface fetch_index_daily ===")
ds = get_datasource()
for sym in ["sh000300", "sh000001"]:
    try:
        df = ds.fetch_index_daily(sym, "2026-01-01", "2026-09-18")
        out.append("  fetch_index_daily(%r) OK rows=%s" % (sym, 0 if df is None else len(df)))
    except Exception as e:
        out.append("  fetch_index_daily(%r) EXC %s: %r" % (sym, type(e).__name__, str(e)[:150]))
out.append("")
out.append("=== 4. end-to-end real_price_lookup (read-only) ===")
from app.services import hot_money_review as hmr
out.append("  _BENCH_INDEX = %r" % hmr._BENCH_INDEX)
try:
    r = hmr.real_price_lookup("600000", "2026-09-16")
    out.append("  real_price_lookup('600000','2026-09-16') -> %r" % (r,))
except Exception as e:
    out.append("  EXC %s: %r" % (type(e).__name__, e))
out.append("")
out.append("=== 5. what a correct bench call would give ===")
try:
    idx = ds.fetch_index_daily("sh000300", "2026-01-01", "2026-09-18")
    stk = ds.fetch_daily_kline("600000", "2026-01-01", "2026-09-18")
    out.append("  bench sh000300 rows=%s  stock 600000 rows=%s" % (len(idx), len(stk)))
    out.append("  _forward_5d_returns with correct bench -> %r" % (hmr._forward_5d_returns(stk, idx, "2026-09-16"),))
except Exception as e:
    out.append("  EXC %s: %r" % (type(e).__name__, str(e)[:200]))
open(os.path.join(OUT, "dsl_rerun_probe3.out.txt"), "w", encoding="utf-8").write("\n".join(out))
print("PROBE3_DONE")