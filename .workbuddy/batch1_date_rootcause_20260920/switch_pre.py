import os, sqlite3, datetime, re
out = []
db = r"D:\self\data\dev.db"
if os.path.exists(db):
    st = os.stat(db)
    out.append("dev.db size=%.1f MB mtime=%s" % (st.st_size/1048576, datetime.datetime.fromtimestamp(st.st_mtime)))
    con = sqlite3.connect(db)
    tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    out.append("表数=%d" % len(tabs))
    for t in ("signal_trigger", "holdings", "alert_log", "review_result", "candidate"):
        if t in tabs:
            n = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            out.append("  %-16s rows=%s" % (t, n))
        else:
            out.append("  %-16s (表不存在)" % t)
else:
    out.append("dev.db 不存在！")
# 其他快照文件
import glob
snaps = sorted(glob.glob(r"D:\self\data\dev.db.*"), key=os.path.getmtime)[-4:]
out.append("--- 快照文件 ---")
for s in snaps:
    out.append("  %s  %.1f MB  %s" % (os.path.basename(s), os.path.getsize(s)/1048576, datetime.datetime.fromtimestamp(os.path.getmtime(s))))
# config 是否支持 sqlite
cfg = open(r"D:\self\backend\app\core\config.py", encoding="utf-8").read()
out.append("--- config db_backend 支持 ---")
for l in cfg.splitlines():
    if "db_backend" in l or "sqlite" in l.lower():
        out.append("  " + l.strip()[:130])
# .env 里 SYNC_ON_START
for l in open(r"D:\self\.env", encoding="utf-8", errors="replace"):
    if "SYNC_ON_START" in l or "DB_BACKEND" in l:
        out.append("ENV: " + l.strip()[:100])
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_local_switch_pre.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))