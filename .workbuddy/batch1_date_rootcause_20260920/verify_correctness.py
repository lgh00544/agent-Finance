import sys, os, json, time, traceback
sys.path.insert(0, r"D:\self\backend")
from datetime import datetime, timedelta
from sqlalchemy import text
from app.services import signal_scan as ss
from app.services.signal_registry import list_all
from app.datasource.fallback import get_datasource
from app.db.session import SessionLocal
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
DAY = "2026-09-18"
out = []
try:
    with SessionLocal() as db:
        db_keys = {(r[0], r[1]) for r in db.execute(text("SELECT stock_code, signal_id FROM signal_trigger WHERE trade_date = :d"), {"d": DAY}).all()}
    codes = sorted({k[0] for k in db_keys})
    SAMPLE = codes[:5]
    out.append("DB rows=%d distinct_codes=%d sample=%s" % (len(db_keys), len(codes), SAMPLE))
    src = get_datasource()
    start = (datetime.strptime(DAY, "%Y-%m-%d") - timedelta(days=ss._LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    ctx = {"trade_date": DAY, "defs": list_all(), "source": src, "today": set(), "cooldown": set(), "start": start, "end": DAY}
    t = time.perf_counter()
    rows, errors, dropped = ss._scan_batch([{"code": c, "name": ""} for c in SAMPLE], ctx, 900)
    secs = round(time.perf_counter() - t, 1)
    replay_keys = {(r["stock_code"], r["signal_id"]) for r in rows}
    db_sub = {k for k in db_keys if k[0] in set(SAMPLE)}
    out.append("replay(%d codes): hits=%d errors=%d dropped=%d wall=%ss" % (len(SAMPLE), len(rows), errors, dropped, secs))
    out.append("replay_keys=%d db_keys=%d" % (len(replay_keys), len(db_sub)))
    out.append("EXACT MATCH? %s" % (replay_keys == db_sub))
    out.append("in replay not db: %s" % sorted(replay_keys - db_sub))
    out.append("in db not replay: %s" % sorted(db_sub - replay_keys))
    json.dump(rows, open(os.path.join(OUT, "verify_rows_sample.json"), "w", encoding="utf-8"), ensure_ascii=False)
except Exception:
    out.append("FATAL:\n" + traceback.format_exc()[-1200:])
open(os.path.join(OUT, "_step_j_correctness.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))