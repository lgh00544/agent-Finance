import os, sys, shutil, traceback, inspect
from pathlib import Path
ws = Path(r"D:\self\.pytest_tmp\harness")
os.makedirs(str(ws), exist_ok=True)
os.environ["TEMP"] = str(ws)
os.environ["TMP"] = str(ws)
sys.path.insert(0, r"D:\self\backend")
import importlib.util
spec = importlib.util.spec_from_file_location("tks", r"D:\self\backend\tests\test_kline_store.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
names = [n for n in dir(m) if n.startswith("test_")]
out, passed, failed = [], 0, 0
for i, n in enumerate(sorted(names), 1):
    fn = getattr(m, n)
    d = ws / ("t%02d" % i)
    d.mkdir(parents=True, exist_ok=True)
    kwargs = {}
    sig = inspect.signature(fn).parameters
    if "tmp_path" in sig:
        kwargs["tmp_path"] = d
    if "monkeypatch" in sig:
        import _pytest.monkeypatch as mp
        kwargs["monkeypatch"] = mp.MonkeyPatch()
    try:
        fn(**kwargs)
        passed += 1
        out.append("PASS " + n)
    except Exception:
        failed += 1
        out.append("FAIL " + n + "\n" + traceback.format_exc()[-700:])
    finally:
        mk = kwargs.get("monkeypatch")
        if mk is not None:
            try: mk.undo()
            except Exception: pass
        for f in list(d.glob("*")):
            try:
                if f.is_file():
                    f.unlink()
            except Exception: pass
out.append("")
out.append("TOTAL=%d PASSED=%d FAILED=%d" % (len(names), passed, failed))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_harness_result.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out[-6:]))