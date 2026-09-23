import json, urllib.request, subprocess
out = []
jobs = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/jobs/status", timeout=60).read().decode())["jobs"]
ids = {j["id"] for j in jobs}
out.append("JOBS_TOTAL=%d（重启前 46）" % len(jobs))
for jid in ("kline_backfill", "kline_ingest", "signal_scan"):
    j = next((x for x in jobs if x["id"] == jid), None)
    out.append("  %-16s %s" % (jid, ("next_run=" + str(j.get("next_run"))) if j else "**缺失**"))
out.append("新增任务: %s" % sorted(ids - {"ths_pnl_mid"} if False else []))
p = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process -Id 32612,29764 -ErrorAction SilentlyContinue | Select-Object Id,StartTime,@{n='MB';e={[math]::Round($_.WorkingSet64/1MB,1)}} | Format-Table -AutoSize"], capture_output=True, text=True, encoding="utf-8", errors="replace")
out.append("--- processes ---")
out.append(p.stdout.strip())
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_restart_jobs.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))