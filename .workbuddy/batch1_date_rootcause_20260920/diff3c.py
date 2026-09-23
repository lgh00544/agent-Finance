import sys, requests, pandas as pd, statistics
sys.path.insert(0, r"D:\self\backend")
from app.services.signal_registry import list_all
from app.indicators import compute_signal_snapshot
from app.datasource.fallback import get_datasource
ua = {"User-Agent": "Mozilla/5.0"}
def txf(code, n=420):
    sym = ("sh" if code.startswith("6") else ("bj" if code.startswith(("4","8","9")) else "sz")) + code
    u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)
    d = (requests.get(u, headers=ua, timeout=20).json().get("data") or {}).get(sym) or {}
    arr = d.get("qfqday") or d.get("day") or []
    return pd.DataFrame([{"date": str(x[0])[:10], "open": float(x[1]), "close": float(x[2]),
                          "high": float(x[3]), "low": float(x[4]), "volume": float(x[5])*100}
                         for x in arr if len(x) >= 6])
src = get_datasource()
defs = {d.id: d for d in list_all()}
for code, sid in (("600866", "s04"), ("600901", "s03"), ("603218", "s04")):
    t = txf(code); a = src.fetch_daily_kline(code, "2025-07-25", "2026-09-18").copy()
    a["date"] = a["date"].astype(str).str.slice(0, 10)
    tm = t.set_index("date"); am = a.set_index("date")
    common = sorted(set(tm.index) & set(am.index))
    devs = [(abs(tm.loc[d, "close"] - am.loc[d, "close"]) / am.loc[d, "close"] * 100) for d in common if am.loc[d, "close"]]
    print("=== %s (%s) ===" % (code, sid))
    print("  共同交易日=%d close偏差 中位=%.4f%% 最大=%.4f%%" % (len(common), statistics.median(devs), max(devs)))
    worst = sorted(((abs(tm.loc[d,"close"]-am.loc[d,"close"])/am.loc[d,"close"]*100, d) for d in common), reverse=True)[:3]
    print("  最大偏差日: %s" % [(round(x,4), d) for x, d in worst])
    # change_pct 有无：对 snapshot 的影响
    st = compute_signal_snapshot(t); sa = compute_signal_snapshot(a)
    print("  snapshot(腾讯) change_pct=%s | snapshot(现有链) change_pct=%s" % (st.get("change_pct"), sa.get("change_pct")))
    try:
        r1 = defs[sid].func(st, t, code); r2 = defs[sid].func(sa, a, code)
        print("  %s 腾讯hit=%s 现有hit=%s" % (sid, r1.hit, r2.hit))
        extra = set(st) ^ set(sa)
        print("  snapshot 键差集=%s" % sorted(extra)[:8])
    except Exception as e:
        print("  EXC %s" % e)