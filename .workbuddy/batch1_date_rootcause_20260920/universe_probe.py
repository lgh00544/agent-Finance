import sys, os, json, time
sys.path.insert(0, r"D:\self\backend")
import akshare as ak
from app.datasource.akshare_source import _normalize, _SPOT_COLS
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
out = []
for name, fn in (("stock_zh_a_spot_em", lambda: ak.stock_zh_a_spot_em()),
                 ("stock_zh_a_spot(sina)", lambda: ak.stock_zh_a_spot())):
    t0 = time.perf_counter()
    try:
        df = fn()
        secs = round(time.perf_counter() - t0, 1)
        cols = list(df.columns)[:14]
        out.append("%s OK rows=%d sec=%s cols=%s" % (name, len(df), secs, cols))
        if name.startswith("stock_zh_a_spot("):
            head = df.head(12).to_dict("records")
            out.append("  head12=%s" % json.dumps(head, ensure_ascii=False)[:800])
        else:
            try:
                nd = _normalize(df, _SPOT_COLS)
                codes = [str(x) for x in nd["code"].head(12).tolist()] if "code" in nd.columns else []
                out.append("  normalized_rows=%d codes_head=%s" % (len(nd), codes))
            except Exception as e:
                out.append("  normalize_ERR %s: %r" % (type(e).__name__, str(e)[:160]))
    except Exception as e:
        out.append("%s EXC %s: %r" % (name, type(e).__name__, str(e)[:200]))
open(os.path.join(OUT, "_step_i_universe_probe.txt"), "w", encoding="utf-8").write("\n".join(out))
print("OK")