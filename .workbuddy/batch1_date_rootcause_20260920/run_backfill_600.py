import sys, os, time
sys.path.insert(0, r"D:\self\backend")
from app.services import kline_backfill, kline_store
from app.datasource.fallback import get_datasource
os.environ.pop("KLINE_DB_PATH", None)
print("REAL store=%s stats=%s" % (kline_store.db_path(), kline_store.stats()))
spot = get_datasource().fetch_spot_universe()
codes = [str(c) for c in spot["code"].tolist()]
names = {str(r["code"]): str(r.get("name") or "") for r in spot.to_dict("records")}
pending = kline_backfill.pending_codes(codes=codes)
print("universe=%d pending=%d" % (len(codes), len(pending)))
BATCH = pending[:600]
print("本夜切片=%d first=%s" % (len(BATCH), BATCH[:3]))
t0 = time.time()
s = kline_backfill.backfill(BATCH, sleep_between=0, names=names, workers=8)
el = time.time() - t0
print("RESULT=%s wall=%.0fs" % (s, el))
print("stats_after=%s" % (kline_store.stats(),))
ok = max(1, s["ok"])
print("等效=%.2f 只/s ⇒ 剩余 %d 只约 %.1f 小时" % (s["ok"]/el, len(pending) - s["ok"], (len(pending)-s["ok"])/(s["ok"]/el)/3600))
print("failed_sample=%s" % s["failed_codes"][:10])