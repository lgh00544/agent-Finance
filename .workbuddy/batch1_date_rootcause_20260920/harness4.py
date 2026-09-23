import os, sys, traceback, inspect
from pathlib import Path
ws = Path(r"D:\self\.wb_harness_tmp\r3")
ws.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = str(ws); os.environ["TMP"] = str(ws)
os.environ.pop("KLINE_DB_PATH", None)
sys.path.insert(0, r"D:\self\backend")
import importlib.util, _pytest.monkeypatch as mp
spec = importlib.util.spec_from_file_location("tks", r"D:\self\backend\tests\test_kline_store.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
names = sorted(n for n in dir(m) if n.startswith("test_"))
res, p, f = [], 0, 0
for i, n in enumerate(names, 1):
    os.environ.pop("KLINE_DB_PATH", None)
    fn = getattr(m, n); d = ws / ("t%02d" % i)
    try: d.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    sig = inspect.signature(fn).parameters; kw = {}
    if "tmp_path" in sig: kw["tmp_path"] = d
    mk = None
    if "monkeypatch" in sig:
        mk = mp.MonkeyPatch(); kw["monkeypatch"] = mk
    try:
        fn(**kw); p += 1; res.append("PASS " + n)
    except Exception as e:
        f += 1; res.append("FAIL %s :: %s: %s" % (n, type(e).__name__, str(e)[:200]))
    finally:
        if mk is not None:
            try: mk.undo()
            except Exception: pass
res.append("TOTAL=%d PASSED=%d FAILED=%d" % (len(names), p, f))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_harness_final.txt", "w", encoding="utf-8").write("\n".join(res))
print("\n".join(res))