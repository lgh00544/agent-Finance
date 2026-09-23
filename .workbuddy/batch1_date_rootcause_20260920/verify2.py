import json, urllib.request, os
out = []
try:
    h = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=20).read().decode()
    out.append("HEALTH=%s" % h)
except Exception as e:
    out.append("HEALTH_ERR=%s" % str(e)[:100])
log = r"D:\self\backend-dev.stdout.log"
lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
out.append("LOG lines=%d" % len(lines))
for l in lines[-12:]:
    out.append("  " + l[:170])
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_restart_verify2.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))