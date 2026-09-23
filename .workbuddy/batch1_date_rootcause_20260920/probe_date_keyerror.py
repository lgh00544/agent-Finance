"""只读复现：定位 `数据源 kline 重试失败: 'date'` 的根因。
不写库、不改码、不调 _persist。仅观测 akshare 上游行为与 DataSourceError 包装链路。
"""
import sys, traceback, inspect

sys.path.insert(0, r"D:\self\backend")

out = []
out.append("=== A. 机制静态复核：空表访问 date 列 ===")
try:
    import pandas as pd
    pd.DataFrame([])["date"]
except Exception as e:
    out.append(f"pd.DataFrame([])['date'] -> {type(e).__name__}: {e!r}")

out.append("")
out.append("=== B. 上游源码定位：akshare stock_zh_a_daily 入口前 3 步 ===")
import akshare
from akshare.stock import stock_zh_a_sina as m
src = inspect.getsource(m.stock_zh_a_daily).splitlines()
for i, ln in enumerate(src[:70], start=1):
    if "date" in ln or "requests.get" in ln or "return" in ln:
        out.append(f"  src[{i}] {ln.strip()[:120]}")

out.append("")
out.append("=== C. 实跑 akshare stock_zh_a_daily(adjust='qfq') 看真实异常 ===")
try:
    df = akshare.stock_zh_a_daily(
        symbol="sh600000", start_date="20260101", end_date="20260918", adjust="qfq"
    )
    out.append(f"  OK shape={df.shape} cols={list(df.columns)}")
except Exception as e:
    out.append(f"  EXC {type(e).__name__}: {e!r}")
    out.append("  --- traceback tail ---")
    out.extend("  " + l for l in traceback.format_exc().splitlines()[-12:])

out.append("")
out.append("=== D. 走本项目 DataSourceError 包装链 ===")
try:
    from app.datasource.akshare_source import get_datasource
    ds = get_datasource()
    df = ds.fetch_daily_kline("600000", "2026-01-01", "2026-09-18")
    out.append(f"  OK shape={df.shape}")
except Exception as e:
    out.append(f"  EXC {type(e).__name__}: {e!r}")

with open(r"C:\Users\57388\AppData\Local\Temp\probe_date_keyerror.out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
