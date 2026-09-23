import sys, os, time, json
sys.path.insert(0, r"D:\self\backend")
from pathlib import Path
DB = r"D:\self\.wb_night\kline.db"
Path(r"D:\self\.wb_night").mkdir(parents=True, exist_ok=True)
os.environ["KLINE_DB_PATH"] = DB
from app.services import kline_backfill, kline_store
from app.datasource.fallback import get_datasource
out = []
out.append("store=%s stats_before=%s" % (kline_store.db_path(), kline_store.stats()))
t0 = time.time()
spot = get_datasource().fetch_spot_universe()
codes_all = [str(c) for c in spot["code"].tolist()] if spot is not None and not spot.empty else []
names = {str(r["code"]): str(r.get("name") or "") for r in spot.to_dict("records")} if codes_all else {}
out.append("universe=%d (%.1fs)" % (len(codes_all), time.time() - t0))
pending = kline_backfill.pending_codes(path=DB, codes=codes_all)
out.append("pending_codes=%d (首次应等于 universe)" % len(pending))
BATCH = pending[:12]
out.append("本夜切片=%d 只 first=%s" % (len(BATCH), BATCH[:5]))
t1 = time.time()
summary = kline_backfill.backfill(BATCH, path=DB, sleep_between=0.5, names=names)
el = round(time.time() - t1, 1)
out.append("backfill=%s wall=%ss" % (summary, el))
out.append("stats_after=%s" % (kline_store.stats(DB),))
out.append("等效单只=%.1fs ⇒ 5564 只约 %.1f 小时 / 每夜300只需 %.0f 夜" % (el / max(1, summary["ok"]),
           5564 * el / max(1, summary["ok"]) / 3600, 5564 / 300))
nm = kline_store.name_map(DB)
out.append("name_map 样例=%s" % dict(list(nm.items())[:3]))
out.append("series_adjust 样例=%s" % {c: kline_store.series_adjust(c, DB) for c in BATCH[:3]})
pending2 = kline_backfill.pending_codes(path=DB, codes=codes_all)
out.append("backfill 后 pending=%d（应减少 %d）" % (len(pending2), len(pending) - len(pending2)))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_night_smoke.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))