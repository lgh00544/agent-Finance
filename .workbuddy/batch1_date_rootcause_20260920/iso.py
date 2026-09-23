import os, sys, traceback, inspect
from pathlib import Path
ws = Path(r"D:\self\.wb_harness_tmp\iso")
ws.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = str(ws); os.environ["TMP"] = str(ws)
os.environ.pop("KLINE_DB_PATH", None)
sys.path.insert(0, r"D:\self\backend")
import importlib.util, _pytest.monkeypatch as mp
spec = importlib.util.spec_from_file_location("tks", r"D:\self\backend\tests\test_kline_store.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
targets = ["test_ingest_skips_ex_dividend_bar_until_rebuild", "test_ingest_today_writes_bars",
           "test_ingest_today_empty_universe_writes_nothing", "test_local_only_marks_data_missing_and_never_touches_remote",
           "test_backfill_skips_sufficient_and_fills_missing"]
res = []
for i, n in enumerate(targets, 1):
    os.environ.pop("KLINE_DB_PATH", None)
    fn = getattr(m, n); d = ws / ("t%02d" % i); d.mkdir(parents=True, exist_ok=True)
    sig = inspect.signature(fn).parameters; kw = {}
    if "tmp_path" in sig: kw["tmp_path"] = d
    mk = None
    if "monkeypatch" in sig:
        mk = mp.MonkeyPatch(); kw["monkeypatch"] = mk
    try:
        fn(**kw); res.append("PASS " + n)
    except Exception as e:
        res.append("FAIL %s :: %s: %s" % (n, type(e).__name__, str(e)[:250]))
    finally:
        if mk is not None:
            try: mk.undo()
            except Exception: pass
print("\n".join(res))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_iso.txt", "w", encoding="utf-8").write("\n".join(res))