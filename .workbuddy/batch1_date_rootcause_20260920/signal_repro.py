import time, json, os, sys, statistics
sys.path.insert(0, r"D:\self\backend")
import requests, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from app.services.signal_registry import list_all
from app.indicators import compute_signal_snapshot
from app.db.session import SessionLocal
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
out = []
def tx(code, n=320):
    sym = ("sh" if code.startswith("6") else ("bj" if code.startswith(("4", "8", "9")) else "sz")) + code
    u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)
    r = requests.get(u, headers=UA, timeout=20)
    j = r.json(); d = (j.get("data") or {}).get(sym) or {}
    return d.get("qfqday") or d.get("day") or []
def frame(code):
    arr = tx(code)
    rows = [{"date": str(x[0])[:10], "open": float(x[1]), "close": float(x[2]), "high": float(x[3]),
             "low": float(x[4]), "volume": float(x[5])} for x in arr if len(x) >= 6]
    return pd.DataFrame(rows) if rows else None
# 16 并发吞吐
CODES = ["600519","000001","601318","600036","000002","601398","600030","000063","601888","600276",
         "002415","300750","600887","000858","601166","600028","601288","000651","600585","002594",
         "600050","601857","600900","000333","002304","600048","601628","300059","002142","600438"]
def one(c):
    t0 = time.perf_counter()
    try: return c, len(tx(c)), round(time.perf_counter()-t0, 2), ""
    except Exception as e: return c, 0, round(time.perf_counter()-t0, 2), type(e).__name__
for w in (16,):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=w) as p: res = list(p.map(one, CODES))
    wall = time.perf_counter() - t0
    out.append("并发 %d：wall=%.1fs 成功=%d/%d 等效=%.2f 只/s ⇒ 全量 %.1f 分钟；耗时中位=%.2fs 最大=%.2fs 失败=%s" % (
        w, wall, sum(1 for r in res if r[1] >= 250), len(res), len(res)/wall, 5564/(len(res)/wall)/60,
        statistics.median([r[2] for r in res]), max(r[2] for r in res), [r[0] for r in res if r[3]]))
# 信号级对账：库内 09-18 的 108 只逐只重算，比较 (code, signal_id) 集合
with SessionLocal() as db:
    db_rows = db.execute(text("SELECT stock_code, signal_id FROM signal_trigger WHERE trade_date = :d"), {"d": "2026-09-18"}).all()
    codes_db = sorted({r[0] for r in db_rows})
    db_keys = {(r[0], r[1]) for r in db_rows}
defs = list_all()
def repro(c):
    try:
        f = frame(c)
        if f is None or len(f) < 250: return c, None, "short<%d" % (0 if f is None else len(f))
        if str(f["date"].iloc[-1]) != "2026-09-18": return c, None, "last=%s" % f["date"].iloc[-1]
        snap = compute_signal_snapshot(f)
        if not snap: return c, None, "no_snap"
        hits = set()
        for d in defs:
            try:
                if d.func(snap, f, c).hit: hits.add((c, d.id))
            except Exception: pass
        return c, hits, ""
    except Exception as e:
        return c, None, "%s" % type(e).__name__
with ThreadPoolExecutor(max_workers=16) as p:
    rr = list(p.map(repro, codes_db))
bad = [r for r in rr if r[1] is None]
have = [r for r in rr if r[1] is not None]
repro_keys = set().union(*[r[1] for r in have]) if have else set()
db_sub = {k for k in db_keys if k[0] in {r[0] for r in have}}
out.append("")
out.append("=== 信号级对账（库内 09-18 的 %d 只）===" % len(codes_db))
out.append("  可重算=%d 不可重算=%d（原因：%s）" % (len(have), len(bad), bad[:3]))
out.append("  重算命中=%d 库内同码命中=%d  EXACT MATCH? %s" % (len(repro_keys), len(db_sub), repro_keys == db_sub))
out.append("  仅重算有: %s" % sorted(repro_keys - db_sub)[:8])
out.append("  仅库内有: %s" % sorted(db_sub - repro_keys)[:8])
open(os.path.join(OUT, "_step_n_signal_repro.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))