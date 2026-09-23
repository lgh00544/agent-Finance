import sys, os, shutil, sqlite3
sys.path.insert(0, r"D:\self\backend")
target = r"D:\self\.wb_smoke3"
if os.path.isdir(target):
    for f in os.listdir(target):
        try: os.remove(os.path.join(target, f))
        except Exception as e: print("skip", f, e)
os.makedirs(target, exist_ok=True)
os.environ["KLINE_DB_PATH"] = os.path.join(target, "kline.db")
from app.services import kline_ingest, kline_store
hist = [{"stock_code": "600519", "trade_date": "2026-09-17", "open": 1.0, "high": 1.0, "low": 1.0,
         "close": 10.0, "volume": 1.0, "amount": 1.0, "stock_name": "贵州茅台",
         "source": "backfill", "adjust": "qfq"}]
kline_store.upsert_bars(hist)
print("after history:", kline_store.stats(), "series_adjust=", kline_store.series_adjust("600519"))
fields = [""] * 34
fields[0], fields[1], fields[2], fields[3], fields[4], fields[5] = "贵州茅台", "10.1", "10.0", "10.15", "10.2", "10.0"
fields[8], fields[9], fields[30] = "2000", "20300", "2026-09-18"
ing = kline_ingest.ingest_today("2026-09-18", codes=["600519"], path=os.path.join(target, "kline.db"))
print("ingest_today:", ing)
print("series_adjust after:", kline_store.series_adjust("600519"))
con = sqlite3.connect(os.path.join(target, "kline.db"))
for r in con.execute("SELECT trade_date, close, adjust, source, stock_name FROM daily_kline ORDER BY trade_date"):
    print("  ", r)
try:
    f = kline_store.load_frame("600519", "2025-07-25", "2026-09-18")
    print("load_frame OK rows=%s last=%s" % (len(f), f["date"].iloc[-1]))
except Exception as e:
    print("load_frame RAISED %s: %s" % (type(e).__name__, e))