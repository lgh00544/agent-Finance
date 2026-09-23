import json, urllib.request, os, datetime
out = []
try:
    h = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=20).read().decode()
    out.append("HEALTH=%s" % h)
except Exception as e:
    out.append("HEALTH_ERR=%s: %s" % (type(e).__name__, str(e)[:120]))
try:
    jobs = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/jobs/status", timeout=60).read().decode())["jobs"]
    ids = [j["id"] for j in jobs]
    out.append("JOBS=%d  kline_backfill present=%s  kline_ingest present=%s" % (len(jobs), "kline_backfill" in ids, "kline_ingest" in ids))
    for j in jobs:
        if j["id"] in ("kline_backfill", "kline_ingest", "signal_scan"):
            out.append("  %-16s next_run=%s" % (j["id"], j.get("next_run")))
except Exception as e:
    out.append("JOBS_ERR=%s" % str(e)[:120])
log = r"D:\self\backend-dev.stdout.log"
if os.path.exists(log):
    lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
    out.append("LOG lines=%d first=%s" % (len(lines), lines[0][:40] if lines else ""))
    keys = [l for l in lines if "系统启动完成" in l or "迁移完成" in l or "同步完成" in l or "kline" in l.lower()]
    for l in keys[-6:]:
        out.append("  " + l[:170])
    errs = [l for l in lines if "[ERROR]" in l]
    out.append("ERROR lines=%d %s" % (len(errs), errs[-1][:140] if errs else ""))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_restart_verify.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))