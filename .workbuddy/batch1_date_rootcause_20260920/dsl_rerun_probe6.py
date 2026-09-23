import sys, io, os, logging
sys.path.insert(0, r"D:\self\backend")
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
lines = []
from app.services import hot_money_review as hmr
from app.datasource import fallback as fb
class FakeSrc:
    def __init__(self, bad): self.bad = bad
    def fetch_daily_kline(self, code, start, end):
        if code == self.bad: raise RuntimeError("FAKE_FAIL_FOR_%s" % code)
        import pandas as pd
        return pd.DataFrame({"date": ["2026-09-16"], "close": [1.0]})
lines.append("=== A. force STOCK fetch to fail (bad=600000) -> what does the log blame? ===")
fb.get_datasource = lambda: FakeSrc("600000")
hmr.get_datasource = None  # keep module import path honest
buf = io.StringIO()
h = logging.StreamHandler(buf)
logging.getLogger("app.services.hot_money_review").addHandler(h)
logging.getLogger("app.services.hot_money_review").setLevel(logging.WARNING)
r = hmr.real_price_lookup("600000", "2026-09-16")
lines.append("  return=%r" % (r,))
log1 = buf.getvalue().strip()
lines.append("  LOG: %s" % log1)
lines.append("  -> message names stock_code=600000; actual failure was 600000 too? %s" % ("YES (this run cannot distinguish)" if "FAKE_FAIL_FOR_600000" in log1 else "inspect"))
lines.append("")
lines.append("=== B. force BENCH fetch to fail (bad=000300), stock SUCCEEDS ===")
buf2 = io.StringIO()
h2 = logging.StreamHandler(buf2)
logging.getLogger("app.services.hot_money_review").addHandler(h2)
fb.get_datasource = lambda: FakeSrc("000300")
r2 = hmr.real_price_lookup("600000", "2026-09-16")
log2 = buf2.getvalue().strip()
lines.append("  return=%r" % (r2,))
lines.append("  LOG: %s" % log2)
lines.append("  -> actual failing code = 000300 (bench); logged stock_code = 600000 => misattribution")
lines.append("")
lines.append("=== C. source proof: hot_money_review.py:105-109 ===")
import inspect
src = inspect.getsource(hmr.real_price_lookup).splitlines()
for i, l in enumerate(src, start=96):
    lines.append("  %d|%s" % (i, l))
open(os.path.join(OUT, "dsl_rerun_probe6_attribution.out.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("PROBE6_DONE")