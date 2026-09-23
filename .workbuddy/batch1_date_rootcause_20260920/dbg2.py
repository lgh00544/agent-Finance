import sys, os, importlib.util
from pathlib import Path
ws = Path(r"D:\self\.wb_iso\t1"); ws.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, r"D:\self\backend")
spec = importlib.util.spec_from_file_location("tks", r"D:\self\backend\tests\test_kline_store.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from app.services import kline_backfill, kline_store
db = str(ws / "k.db")
n = kline_store.upsert_bars(m._bars(code="A", n=250), db)
print("upserted=%s has_enough(A,250)=%s" % (n, kline_store.has_enough("A", 250, db)))
src = m._Source(default=280)
out = kline_backfill.backfill(["A", "B"], path=db, source=src, sleep_between=0)
print("out=%s" % out)
print("source.calls=%s has_enough(B)=%s" % (src.calls, kline_store.has_enough("B", 250, db)))