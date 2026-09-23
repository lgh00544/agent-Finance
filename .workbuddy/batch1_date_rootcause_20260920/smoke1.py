import sys, os, json
sys.path.insert(0, r"D:\self\backend")
out = []
os.environ.pop("KLINE_DB_PATH", None)
os.environ["KLINE_DB_PATH"] = r"D:\self\.wb_smoke\kline.db"
os.makedirs(r"D:\self\.wb_smoke", exist_ok=True)
import importlib
m = importlib.import_module("app.scheduler.jobs")
out.append("jobs module import OK; has kline_backfill_job=%s" % hasattr(m, "kline_backfill_job"))
out.append("MIN_KLINE_BARS_FOR_BACKFILL=%s" % getattr(m, "MIN_KLINE_BARS_FOR_BACKFILL", None))
from app.services import kline_backfill, kline_store
out.append("store path=%s" % kline_store.db_path())
out.append("before stats=%s" % kline_store.stats())
import time
t0 = time.time()
summary = kline_backfill.backfill(["600519"], sleep_between=0)
out.append("backfill 600519 = %s wall=%.1fs" % (summary, time.time() - t0))
out.append("after stats=%s" % kline_store.stats())
out.append("name_map=%s" % kline_store.name_map())
out.append("has_enough(600519,250)=%s" % kline_store.has_enough("600519", 250))
frm = kline_store.load_frame("600519", "2025-07-25", "2026-09-18")
out.append("load_frame rows=%s cols=%s last_date=%s" % (0 if frm is None else len(frm), list(frm.columns) if frm is not None else None, str(frm["date"].iloc[-1]) if frm is not None else None))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_smoke1.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))