import os, datetime, shutil, re, subprocess
env = r"D:\self\.env"
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak = env + ".bak-mysql-" + stamp
shutil.copy2(env, bak)
raw = open(env, "rb").read()
txt = raw.decode("utf-8", "replace")
lines = txt.splitlines(keepends=True)
changed = []
out = []
for l in lines:
    if re.match(r"^\s*DB_BACKEND\s*=", l) and not l.lstrip().startswith("#"):
        out.append("DB_BACKEND=sqlite\n")
        changed.append(l.strip() + "  ->  DB_BACKEND=sqlite")
    else:
        out.append(l)
open(env, "w", encoding="utf-8", newline="").write("".join(out))
print("env backup=%s" % os.path.basename(bak))
print("changes=%s" % changed)
# 确认
for l in open(env, encoding="utf-8", errors="replace"):
    s = l.strip()
    if s and not s.startswith("#") and ("DB_BACKEND" in s or "MYSQL_HOST" in s):
        print("  now: " + s[:90])
# 当前 sqlite_path 配置
from pathlib import Path
sys.path.insert(0, r"D:\self\backend")