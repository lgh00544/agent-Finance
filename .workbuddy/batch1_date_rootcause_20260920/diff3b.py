import sys, requests, pandas as pd
sys.path.insert(0, r"D:\self\backend")
from app.services.signal_registry import list_all
from app.indicators import compute_signal_snapshot
from app.datasource.fallback import get_datasource
ua = {"User-Agent": "Mozilla/5.0"}
def tx(code, n):
    sym = ("sh" if code.startswith("6") else ("bj" if code.startswith(("4","8","9")) else "sz")) + code
    u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)
    d = (requests.get(u, headers=ua, timeout=20).json().get("data") or {}).get(sym) or {}
    return d.get("qfqday") or d.get("day") or []
def frame(code, n):
    arr = tx(code, n)
    rows = [{"date": str(x[0])[:10], "open": float(x[1]), "close": float(x[2]), "high": float(x[3]),
             "low": float(x[4]), "volume": float(x[5])*100} for x in arr if len(x) >= 6]
    return pd.DataFrame(rows)
defs = {d.id: d for d in list_all()}
print("=== 用腾讯 420/600 根重算，对照库内 3 条差异 ===")
for code, sids in (("600866", ["s04"]), ("600901", ["s03"]), ("603218", ["s04"])):
    for n in (320, 420, 600):
        f = frame(code, n)
        if len(f) < 250:
            print("  %s n=%d bars=%d -> 不足" % (code, n, len(f))); continue
        snap = compute_signal_snapshot(f)
        hits = []
        for sid in sids:
            try: hits.append("%s=%s" % (sid, defs[sid].func(snap, f, code).hit))
            except Exception as e: hits.append("%s EXC" % sid)
        print("  %s n=%d bars=%d first=%s %s" % (code, n, len(f), f["date"].iloc[0], " ".join(hits)))
print("")
print("=== 顺带确认：n=420 是否覆盖现有链首日 ===")
src = get_datasource()
df = src.fetch_daily_kline("600866", "2025-07-25", "2026-09-18")
print("  现有链 bars=%d first=%s last=%s" % (len(df), str(df["date"].iloc[0])[:10], str(df["date"].iloc[-1])[:10]))
f420 = frame("600866", 420)
print("  腾讯420 bars=%d first=%s last=%s" % (len(f420), f420["date"].iloc[0], f420["date"].iloc[-1]))