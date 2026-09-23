"""只读复现 3：确认 `'date'` 的根因是「基准指数 000300 走个股日K接口」。
不写库、不改码。
"""
import sys, time
sys.path.insert(0, r"D:\self\backend")
out = []

from app.datasource.akshare_source import get_datasource, _market_of
import akshare as ak

out.append("=== 1. 代码归属判定 ===")
out.append(f"  _market_of('000300') = {_market_of('000300')!r}   <- 沪深300 被判成深市个股前缀 sz")
out.append(f"  _market_of('600000') = {_market_of('600000')!r}")
out.append(f"  _market_of('688620') = {_market_of('688620')!r}")

out.append("")
out.append("=== 2. 主源（东财 stock_zh_a_hist）对指数代码 000300 的行为 ===")
for sym in ["000300", "600000"]:
    try:
        df = ak.stock_zh_a_hist(symbol=sym, period="daily", start_date="20260101",
                                end_date="20260918", adjust="qfq")
        out.append(f"  stock_zh_a_hist(symbol={sym!r}) OK shape={df.shape} cols={list(df.columns)[:6]}")
    except Exception as e:
        out.append(f"  stock_zh_a_hist(symbol={sym!r}) EXC {type(e).__name__}: {e!r}")

out.append("")
out.append("=== 3. 备用源（新浪 stock_zh_a_daily）对 sz000300 的行为 ===")
for sym in ["sz000300", "sh000300", "sh600000"]:
    try:
        df = ak.stock_zh_a_daily(symbol=sym, start_date="20260101", end_date="20260918", adjust="qfq")
        out.append(f"  stock_zh_a_daily({sym!r}) OK shape={df.shape}")
    except Exception as e:
        out.append(f"  stock_zh_a_daily({sym!r}) EXC {type(e).__name__}: {e!r}")

out.append("")
out.append("=== 4. 项目内的「指数」正确接口 fetch_index_daily ===")
ds = get_datasource()
for sym in ["sh000300", "sh000001"]:
    try:
        df = ds.fetch_index_daily(sym, "2026-01-01", "2026-09-18")
        out.append(f"  fetch_index_daily({sym!r}) OK rows={0 if df is None else len(df)}")
    except Exception as e:
        out.append(f"  fetch_index_daily({sym!r}) EXC {type(e).__name__}: {e!r}")

out.append("")
out.append("=== 5. 端到端：real_price_lookup 用 000300 作为基准 ===")
from app.services import hot_money_review as hmr
out.append(f"  _BENCH_INDEX = {hmr._BENCH_INDEX!r}")
try:
    r = hmr.real_price_lookup("600000", "2026-09-16")
    out.append(f"  real_price_lookup('600000','2026-09-16') -> {r!r}")
except Exception as e:
    out.append(f"  EXC {type(e).__name__}: {e!r}")

with open(r"C:\Users\57388\AppData\Local\Temp\probe3.out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
