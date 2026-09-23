import sys, os
sys.path.insert(0, r"D:\self\backend")
os.environ["KLINE_DB_PATH"] = r"D:\self\.wb_smoke2\kline.db"
os.makedirs(r"D:\self\.wb_smoke2", exist_ok=True)
from app.services import kline_store
out = []
hist = [{"stock_code": "600519", "trade_date": "2026-09-17", "open": 1.0, "high": 1.0, "low": 1.0,
         "close": 10.0, "volume": 1.0, "amount": 1.0, "stock_name": "贵州茅台",
         "source": "backfill", "adjust": "qfq"}]
kline_store.upsert_bars(hist)
print("after history:", kline_store.name_map(), kline_store.stats())
# 日增量按实现写 adjust="none"
bar = [{"stock_code": "600519", "trade_date": "2026-09-18", "open": 10.1, "high": 10.2, "low": 10.0,
        "close": 10.15, "volume": 2.0, "amount": 2.0, "stock_name": "",
        "source": "hq_snapshot", "adjust": "none"}]
kline_store.upsert_bars(bar)
print("after daily bar:", kline_store.stats())
try:
    f = kline_store.load_frame("600519", "2025-07-25", "2026-09-18")
    print("load_frame OK rows=%s cols=%s" % (len(f), list(f.columns)))
except Exception as e:
    print("load_frame RAISED %s: %s" % (type(e).__name__, e))
print("--- adjust values in store ---")
import sqlite3
con = sqlite3.connect(r"D:\self\.wb_smoke2\kline.db")
for r in con.execute("SELECT trade_date, close, adjust, stock_name FROM daily_kline ORDER BY trade_date"):
    print("  ", r)