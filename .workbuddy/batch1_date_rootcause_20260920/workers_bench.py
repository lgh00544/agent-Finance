import sys, os, time
sys.path.insert(0, r"D:\self\backend")
from pathlib import Path
DB = r"D:\self\.wb_night2\kline.db"
Path(r"D:\self\.wb_night2").mkdir(parents=True, exist_ok=True)
os.environ["KLINE_DB_PATH"] = DB
from app.services import kline_backfill, kline_store
from app.datasource.fallback import get_datasource
out = []
spot = get_datasource().fetch_spot_universe()
codes = [str(c) for c in spot["code"].tolist()]
names = {str(r["code"]): str(r.get("name") or "") for r in spot.to_dict("records")}
pending = kline_backfill.pending_codes(path=DB, codes=codes)
BATCH = pending[:24]
for w in (1, 8):
    import shutil, sqlite3
    for f in os.listdir(r"D:\self\.wb_night2"):
        try: os.remove(os.path.join(r"D:\self\.wb_night2", f))
        except Exception: pass
    t0 = time.time()
    s = kline_backfill.backfill(BATCH, path=DB, sleep_between=0, names=names, workers=w)
    el = round(time.time() - t0, 1)
    out.append("workers=%d wall=%ss ok=%d failed=%d bars=%d 等效=%.2f 只/s ⇒ 5564 只需 %.1f 小时" % (
        w, el, s["ok"], s["failed"], s["written_bars"], s["ok"]/el if el else 0, 5564/(s["ok"]/el)/3600 if s["ok"] and el else 0))
out.append("failed_codes=%s" % s["failed_codes"][:8])
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_workers_bench.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))