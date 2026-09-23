import sys, os, traceback, locale
print("cwd=", os.getcwd())
print("fsenc=", sys.getfilesystemencoding(), "preferred=", locale.getpreferredencoding(False))
sys.path.insert(0, r"D:\self\backend")
try:
    from app.services import signal_scan as ss
    print("import ss OK")
    from app.datasource.fallback import get_datasource
    print("import fallback OK")
    ds = get_datasource()
    print("datasource:", type(ds).__name__)
    ctx = {"trade_date": "2026-09-18", "defs": [], "source": ds, "today": set(), "cooldown": set(),
           "start": "2025-07-25", "end": "2026-09-18"}
    rows, err, drop = ss._scan_batch([{"code": "000001", "name": "平安银行"}], ctx, 30)
    print("scan_batch OK rows=%d errors=%d dropped=%d" % (len(rows), err, drop))
except Exception:
    traceback.print_exc()