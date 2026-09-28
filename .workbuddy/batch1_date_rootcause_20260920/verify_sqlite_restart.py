import json, urllib.request, os, re
out = []
try:
    h = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=20).read().decode()
    out.append("HEALTH=" + h)
except Exception as e:
    out.append("HEALTH_ERR=" + str(e)[:100])
try:
    d = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/holdings", timeout=30).read().decode())
    out.append("API /holdings rows=%d (本地库 holding=13)" % len(d))
except Exception as e:
    out.append("HOLDINGS_ERR=" + str(e)[:120])
try:
    jobs = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/jobs/status", timeout=90).read().decode())["jobs"]
    out.append("JOBS=%d" % len(jobs))
except Exception as e:
    out.append("JOBS_ERR=" + str(e)[:100])
log = r"D:\self\backend-dev.stdout.log"
if os.path.exists(log):
    lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
    out.append("LOG lines=%d" % len(lines))
    for l in lines[-5:]:
        out.append("  " + l[:150])
    bad = [l for l in lines if re.search(r"OperationalError|mysql|TiDB|quota|SYNC", l, re.I)]
    out.append("DB/sync 相关行=%d %s" % (len(bad), bad[-1][:130] if bad else ""))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_sqlite_restart_verify.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))