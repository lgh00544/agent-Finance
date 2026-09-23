import sys, os
sys.path.insert(0, r"D:\self\backend")
from app.services import kline_store
out = []
p = kline_store.db_path()
out.append("db_path=%s exists=%s" % (p, os.path.exists(str(p))))
if os.path.exists(str(p)):
    out.append("size=%d bytes" % os.path.getsize(str(p)))
    out.append("stats=%s" % (kline_store.stats(),))
else:
    out.append("stats=N/A (no file yet)")
import subprocess
rc = subprocess.run(["powershell", "-NoProfile", "-Command", "Select-String -Path D:\\self\\backend\\app\\scheduler\\jobs.py -Pattern \"def .*kline|kline_ingest|kline_backfill|16:25|16, 25\" | Select-Object -First 20 | ForEach-Object { $_.LineNumber.ToString() + \": \" + $_.Line.Trim() }"], capture_output=True, text=True, encoding="utf-8", errors="replace")
out.append("--- jobs.py kline refs ---")
out.append(rc.stdout.strip()[:2000] or rc.stderr.strip()[:500])
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_step_k_local_store.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))