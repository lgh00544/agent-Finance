import json, sys, os
sys.path.insert(0, r"D:\self\backend")
os.environ.setdefault("APP_ENV", "dev")
from app.services import kline_backfill
codes = ["920003","920009","920015","920020","920022","920036","920045","920050","920055","920069",
"920076","920078","920080","920081","920086","920096","920119","920121","920124","920158",
"920159","920168","920176","920180","920183","920187","920188","920206","920211"]
out = {}
for c in codes:
    rows = kline_backfill.fetch_history(c)
    out[c] = len(rows)
ge250 = [c for c, n in out.items() if n >= 250]
print(json.dumps({"counts": out, "ge250": ge250, "max": max(out.values()), "min": min(out.values())}, ensure_ascii=False))
