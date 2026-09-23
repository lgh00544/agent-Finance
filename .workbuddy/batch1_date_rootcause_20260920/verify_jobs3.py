import json, urllib.request, subprocess
out = []
try:
    raw = urllib.request.urlopen("http://127.0.0.1:8000/api/jobs/status", timeout=180).read().decode()
    jobs = json.loads(raw)["jobs"]
    out.append("JOBS_TOTAL=%d (before restart 46)" % len(jobs))
    for jid in ("kline_backfill", "kline_ingest", "signal_scan"):
        j = next((x for x in jobs if x["id"] == jid), None)
        out.append("  %-16s %s" % (jid, ("next_run=" + str(j.get("next_run"))) if j else "MISSING"))
except Exception as e:
    out.append("JOBS_ERR %s: %s" % (type(e).__name__, str(e)[:120]))
pscmd = "Get-Process -Id 32612,29764 -ErrorAction SilentlyContinue | Select-Object Id,StartTime | Format-Table -AutoSize"
p = subprocess.run(["powershell", "-NoProfile", "-Command", pscmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
out.append("--- processes ---")
out.append(p.stdout.strip() or "(none)")
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_restart_jobs.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))