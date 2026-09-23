import sys, os, time, json
sys.path.insert(0, r"D:\self\backend")
import akshare as ak
from app.services import kline_backfill, kline_store
from app.datasource.akshare_source import _normalize, _SPOT_COLS
UNI = r"D:\self\.workbuddy\batch1_date_rootcause_20260920\universe_codes.json"
codes = None
if os.path.exists(UNI):
    codes = json.load(open(UNI, encoding="utf-8"))
    print("using saved universe=%d" % len(codes))
if not codes:
    for attempt in range(3):
        try:
            raw = ak.stock_zh_a_spot()
            raw["代码"] = raw["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
            nd = _normalize(raw, _SPOT_COLS)
            codes = [str(c) for c in nd["code"].tolist() if str(c)]
            if codes:
                json.dump(codes, open(UNI, "w", encoding="utf-8"))
                print("fetched(sina) universe=%d (saved)" % len(codes))
                break
        except Exception as e:
            print("attempt %d: %s" % (attempt + 1, str(e)[:110]))
            time.sleep(15)
if not codes:
    print("NO_UNIVERSE_ABORT")
    raise SystemExit(2)
print("store=%s stats=%s" % (kline_store.db_path(), kline_store.stats()))
pending = kline_backfill.pending_codes(codes=codes)
print("pending=%d" % len(pending))
SIZE = int(os.environ.get("BACKFILL_SIZE", "300"))
BATCH = pending[:SIZE]
print("BATCH=%d first=%s" % (len(BATCH), BATCH[:3]))
t0 = time.time()
s = kline_backfill.backfill(BATCH, sleep_between=0, workers=8)
el = max(1.0, time.time() - t0)
print("RESULT=%s wall=%.0fs" % (s, el))
print("stats_after=%s" % (kline_store.stats(),))
print("等效=%.2f 只/s 失败样例=%s" % (s["ok"]/el, s["failed_codes"][:8]))