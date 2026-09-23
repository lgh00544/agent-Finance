import sys, os
sys.path.insert(0, r"D:\self\backend")
import requests, pandas as pd
from sqlalchemy import text
from app.services.signal_registry import list_all
from app.indicators import compute_signal_snapshot
from app.datasource.fallback import get_datasource
from app.db.session import SessionLocal
ua = {"User-Agent": "Mozilla/5.0"}
def tx(code, n=320):
    sym = ("sh" if code.startswith("6") else ("bj" if code.startswith(("4","8","9")) else "sz")) + code
    u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)
    d = (requests.get(u, headers=ua, timeout=20).json().get("data") or {}).get(sym) or {}
    return d.get("qfqday") or d.get("day") or []
def frame(arr):
    rows = [{"date": str(x[0])[:10], "open": float(x[1]), "close": float(x[2]), "high": float(x[3]),
             "low": float(x[4]), "volume": float(x[5])*100} for x in arr if len(x) >= 6]
    return pd.DataFrame(rows)
defs = {d.id: d for d in list_all()}
src = get_datasource()
with SessionLocal() as db:
    want = {}
    for c, s in db.execute(text("SELECT stock_code, signal_id FROM signal_trigger WHERE trade_date = :d"), {"d": "2026-09-18"}).all():
        want.setdefault(c, set()).add(s)
for code, sigs in (("600866", ["s04"]), ("600901", ["s03"]), ("603218", ["s04"])):
    arr = tx(code)
    f = frame(arr)
    print("=== %s ===" % code)
    print("  腾讯 bars=%d last_date=%s last_close=%s" % (len(f), f["date"].iloc[-1], f["close"].iloc[-1]))
    snap = compute_signal_snapshot(f)
    print("  snapshot=%s" % ("None" if not snap else {k: snap.get(k) for k in list(snap)[:6]}))
    if snap:
        for sid in sigs:
            d = defs[sid]
            try:
                r = d.func(snap, f, code)
                print("  腾讯 %s hit=%s" % (sid, r.hit))
            except Exception as e:
                print("  腾讯 %s EXC %s" % (sid, e))
    df = src.fetch_daily_kline(code, "2025-07-25", "2026-09-18")
    snap2 = compute_signal_snapshot(df)
    for sid in sigs:
        try:
            r2 = defs[sid].func(snap2, df, code)
            print("  现有链 %s hit=%s" % (sid, r2.hit))
        except Exception as e:
            print("  现有链 %s EXC %s" % (sid, e))
    common = sorted(set(f["date"]) & set(str(x)[:10] for x in df["date"]))[-30:]
    tmap = dict(zip(f["date"], f["close"]))
    amap = {str(x)[:10]: c for x, c in zip(df["date"], df["close"])}
    dev = [(d, tmap[d], amap[d], abs(tmap[d]-amap[d])/amap[d]*100) for d in common if amap[d]]
    if dev:
        import statistics
        print("  近30日 close 偏差 中位=%.4f%% 最大=%.4f%% (示例 %s)" % (statistics.median([x[3] for x in dev]), max(x[3] for x in dev), dev[-1]))