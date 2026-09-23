"""只读复现 2：用 09-18 16:30 失败的原始参数重跑，定位 `'date'` 抛出点。
不写库、不改码。
"""
import sys, time, traceback

sys.path.insert(0, r"D:\self\backend")
out = []

from app.services import hot_money_review as hmr
out.append(f"=== 0. 调用方常量 ===")
out.append(f"  _BENCH_INDEX = {getattr(hmr, '_BENCH_INDEX', 'N/A')!r}")

from app.datasource.akshare_source import get_datasource, _market_of
ds = get_datasource()

START, END = "2026-01-01", "2026-09-18"
out.append("")
out.append(f"=== 1. 原参数复跑 fetch_daily_kline(start={START}, end={END}, adjust=qfq) ===")
for code in ["688620", "688004", "601579", "600000"]:
    t0 = time.time()
    try:
        df = ds.fetch_daily_kline(code, START, END)
        out.append(f"  {code} ({_market_of(code)}) OK rows={0 if df is None else len(df)} "
                   f"cols={list(df.columns) if df is not None else None} {time.time()-t0:.2f}s")
    except Exception as e:
        out.append(f"  {code} ({_market_of(code)}) EXC {type(e).__name__}: {e!r} {time.time()-t0:.2f}s")

bench = getattr(hmr, "_BENCH_INDEX", None)
if bench:
    try:
        df = ds.fetch_daily_kline(bench, START, END)
        out.append(f"  BENCH {bench} ({_market_of(bench)}) OK rows={0 if df is None else len(df)}")
    except Exception as e:
        out.append(f"  BENCH {bench} ({_market_of(bench)}) EXC {type(e).__name__}: {e!r}")

out.append("")
out.append("=== 2. 直调 akshare 上游（绕过本项目包装），看异常类名与抛出点 ===")
import akshare as ak
for code in ["688620", "688004", "601579"]:
    sym = f"{_market_of(code)}{code}"
    try:
        df = ak.stock_zh_a_daily(symbol=sym, start_date=START.replace("-", ""),
                                 end_date=END.replace("-", ""), adjust="qfq")
        out.append(f"  {sym} OK shape={df.shape}")
    except Exception as e:
        out.append(f"  {sym} EXC {type(e).__name__}: {e!r}")
        tb = traceback.format_exc().splitlines()
        out.append("    | " + " | ".join(l.strip() for l in tb[-6:] if l.strip()))
    # 不带复权
    try:
        df = ak.stock_zh_a_daily(symbol=sym, start_date=START.replace("-", ""),
                                 end_date=END.replace("-", ""), adjust="")
        out.append(f"  {sym} adjust='' OK shape={df.shape}")
    except Exception as e:
        out.append(f"  {sym} adjust='' EXC {type(e).__name__}: {e!r}")

out.append("")
out.append("=== 3. 上游 :184 行为验证：空/异常响应 -> KeyError 'date' ===")
import pandas as pd
out.append(f"  pd.DataFrame(None)['date'] -> ", )
try:
    pd.DataFrame(None)["date"]
except Exception as e:
    out.append(f"    {type(e).__name__}: {e!r}")
out.append(f"  pd.DataFrame([]).index.name = {pd.DataFrame([]).index.name!r} (unnamed -> reset_index 产出 'index' 而非 'date')")

with open(r"C:\Users\57388\AppData\Local\Temp\probe2.out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
