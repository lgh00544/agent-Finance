"""日线单只耗时定点测量（只读）：用于剥离沙箱代理影响，判断 540s 预算是否真有风险。

用法: D:/self/.venv/Scripts/python.exe D:/self/kline_timing.py [YYYY-MM-DD] [N]
"""
import os
import sys
import time

sys.path.insert(0, r"D:/self/backend")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from app.datasource.fallback import get_datasource  # noqa: E402

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-09-17"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5

CODES = ["600519", "600036", "601318", "000001", "300750", "688981", "600030", "002415"][:N]

print("proxy env:", {k: v for k, v in os.environ.items() if "proxy" in k.lower()} or "<none>")
src = get_datasource()
for code in CODES:
    t = time.time()
    try:
        k = src.fetch_daily_kline(code, "2025-07-01", DAY)
        last = str(k["date"].iloc[-1])[:10] if "date" in getattr(k, "columns", []) else "?"
        print("  %s rows=%d last=%s  %.0fms" % (code, len(k), last, (time.time() - t) * 1000))
    except Exception as exc:  # noqa: BLE001
        print("  %s FAIL %s: %s  %.0fms" % (code, type(exc).__name__, exc, (time.time() - t) * 1000))
