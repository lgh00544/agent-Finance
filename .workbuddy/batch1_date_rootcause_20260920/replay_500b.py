import sys, os, json, time, traceback
sys.path.insert(0, r"D:\self\backend")
from datetime import datetime, timedelta
from app.services import signal_scan as ss
from app.services.signal_registry import list_all
from app.datasource.fallback import get_datasource
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
DAY = "2026-09-18"
PROG = os.path.join(OUT, "replay_0920_progress.jsonl")
def log(obj):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(json.dumps(obj, ensure_ascii=False), flush=True)
try:
    uni = json.load(open(os.path.join(OUT, "replay_universe_0920.json"), encoding="utf-8"))
    BATCH = uni[:500]
    log({"stage": "slice_loaded", "n": len(BATCH), "head": BATCH[0], "tail": BATCH[-1]})
    start = (datetime.strptime(DAY, "%Y-%m-%d") - timedelta(days=ss._LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    defs = list_all()
    today_keys, cooldown_keys = ss._load_keys(DAY)
    src = get_datasource()
    log({"stage": "ready", "defs": len(defs), "today": len(today_keys), "cooldown": len(cooldown_keys), "src": type(src).__name__})
    results = {}
    for tag, today, cooldown in (("no_dedup_cold", set(), set()), ("with_dedup", today_keys, cooldown_keys)):
        ctx = {"trade_date": DAY, "defs": defs, "source": src, "today": today, "cooldown": cooldown, "start": start, "end": DAY}
        t = time.perf_counter()
        try:
            rows, errors, dropped = ss._scan_batch(BATCH, ctx, 120)
        except BaseException as exc:
            log({"stage": "ERR", "tag": tag, "type": type(exc).__name__, "msg": str(exc)[:300],
                 "tb": traceback.format_exc()[-1200:]})
            raise
        secs = round(time.perf_counter() - t, 1)
        sigs = {}
        for r in rows: sigs[r["signal_id"]] = sigs.get(r["signal_id"], 0) + 1
        rec = {"stage": "variant", "tag": tag, "n_batch": len(BATCH), "hits": len(rows), "errors": errors,
               "dropped": dropped, "wall_s": secs, "throughput": round(len(BATCH) / secs, 4),
               "distinct_codes_with_signal": len({r["stock_code"] for r in rows}),
               "by_signal": dict(sorted(sigs.items())),
               "dedup1": sum(1 for r in rows if r.get("dedup") == 1),
               "dedup0": sum(1 for r in rows if r.get("dedup") == 0), "exec_mode": "read_only_no_persist"}
        log(rec)
        with open(os.path.join(OUT, "replay_rows_%s.json" % tag), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        results[tag] = rec
    log({"stage": "done", "results": {k: {kk: vv for kk, vv in v.items() if kk != "by_signal"} for k, v in results.items()}})
except BaseException:
    log({"stage": "FATAL", "tb": traceback.format_exc()[-2000:]})
    raise