import json, urllib.request
def get(p):
    with urllib.request.urlopen("http://127.0.0.1:8000" + p, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))
out = []
h = get("/api/holdings")
out.append("API /holdings = %d 行（本地 holding=13）" % len(h))
out.append("  样例状态: %s" % [x.get("status") for x in h[:5]])
j = get("/api/jobs/status")["jobs"]
out.append("API /jobs/status = %d job" % len(j))
al = get("/api/alerts?limit=5")
out.append("API /alerts = %d 行（本地 alert_log=1065）" % len(al))
print("\n".join(out))