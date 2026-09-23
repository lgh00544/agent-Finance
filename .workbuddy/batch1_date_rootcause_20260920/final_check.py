import sys, subprocess, os
sys.path.insert(0, r"D:\self\backend")
from sqlalchemy import text
from app.db.session import SessionLocal
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
with SessionLocal() as db:
    n = db.execute(text("SELECT COUNT(*) FROM signal_trigger")).scalar()
    d = db.execute(text("SELECT MAX(trade_date) FROM signal_trigger")).scalar()
p = subprocess.run([GIT, "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace")
mod = [l for l in p.stdout.splitlines() if l.startswith(" M")]
t = subprocess.run([GIT, "log", "-1", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M"], capture_output=True, text=True, encoding="utf-8")
tg = subprocess.run([GIT, "tag", "--list", "pre-live*"], capture_output=True, text=True)
print("signal_trigger total=%s max_date=%s" % (n, d))
print("HEAD: " + t.stdout.strip())
print("modified tracked count=%d ; backend/app modified=%s" % (len(mod), sorted(l.split("/")[-1] for l in mod if "backend/app" in l)))
print("pre-live tags:", repr(tg.stdout.split()))
for f in ("买卖点信号体系_批1_观察期台账.md", "买卖点信号体系_批1_核验回执_DSH答复_20260920.md"):
    pp = os.path.join(r"D:\self", f)
    print("%s exists=%s lines=%d" % (f, os.path.exists(pp), len(open(pp, encoding="utf-8").read().splitlines())))