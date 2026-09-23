import sys, os, json, time
sys.path.insert(0, r"D:\self\backend")
from datetime import datetime, timedelta
import akshare as ak
from app.services import signal_scan as ss
from app.services.signal_registry import list_all
from app.datasource.akshare_source import _normalize, _SPOT_COLS
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
DAY = "2026-09-18"
PROG = os.path.join(OUT, "replay_0920_progress.jsonl")
def log(obj):
    open(PROG, "a", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(json.dumps(obj, ensure_ascii=False), flush=True)
log({"stage": "start", "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "day": DAY, "mode": "read_only_no_persist"})
t0 = time.perf_counter()
raw = ak.stock_zh_a_spot()
raw["代码"] = raw["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
spot = _normalize(raw, _SPOT_COLS)
log({"stage": "universe", "rows": int(len(spot)), "sec": round(time.perf_counter() - t0, 1)})
recs = [{"code": str(r.get("code") or ""), "name": str(r.get("name") or "")} for r in spot.to_dict("records") if r.get("code")]
assigned = sorted(recs, key=lambda x: x["code"])
json.dump(assigned, open(os.path.join(OUT, "replay_universe_0920.json"), "w", encoding="utf-8"), ensure_ascii=False)
BATCH = assigned[:500]
log({"stage": "slice", "n": len(BATCH), "codes_head": [x["code"] for x in BATCH[:10]], "codes_tail": [x["code"] for x in BATCH[-5:]], "prefix": sorted({x["code"][:3] for x in BATCH})})
start = (datetime.strptime(DAY, "%Y-%m-%d") - timedelta(days=ss._LOOKBACK_DAYS)).strftime("%Y-%m-%d")
defs = list_all()
today_keys, cooldown_keys = ss._load_keys(DAY)
log({"stage": "keys", "today": len(today_keys), "cooldown": len(cooldown_keys)})
def run(tag, today, cooldown, timeout):
    ctx = {"trade_date": DAY, "defs": defs, "source": None, "today": today, "cooldown": cooldown, "start": start, "end": DAY}
    from app.datasource.fallback import get_datasource
    ctx["source"] = get_datasource()
    t = time.perf_counter()
    rows, errors, dropped = ss._scan_batch(BATCH, ctx, timeout)
    secs = round(time.perf_counter() - t, 1)
    codes = sorted({r["stock_code"] for r in rows})
    sigs = {}
    for r in rows: sigs[r["signal_id"]] = sigs.get(r["signal_id"], 0) + 1
    rec = {"stage": "variant", "tag": tag, "n_batch": len(BATCH), "hits": len(rows), "errors": errors,
           "dropped": dropped, "wall_s": secs, "throughput": round(len(BATCH) / secs, 4),
           "distinct_codes_with_signal": len(codes), "by_signal": dict(sorted(sigs.items())),
           "dedup1": sum(1 for r in rows if r.get("dedup") == 1),
           "dedup0": sum(1 for r in rows if r.get("dedup") == 0), "exec_mode": "read_only_no_persist"}
    log(rec)
    json.dump(rows, open(os.path.join(OUT, "replay_rows_%s.json" % tag), "w", encoding="utf-8"), ensure_ascii=False)
    return rec
r1 = run("no_dedup_cold", set(), set(), 120)
r2 = run("with_dedup", today_keys, cooldown_keys, 120)
log({"stage": "done", "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})