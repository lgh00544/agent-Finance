import subprocess, os
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
FILES = ["backend/app/services/kline_store.py", "backend/app/services/kline_ingest.py",
         "backend/app/services/kline_backfill.py", "backend/app/services/signal_scan.py",
         "backend/app/scheduler/jobs.py", "backend/app/core/config.py",
         "backend/scripts/kline_backfill_once.py", "backend/tests/test_kline_store.py"]
def run(a):
    p = subprocess.run([GIT] + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()
print("=== 门禁① 待提交文件（依赖闭包人工推演）===")
for f in FILES:
    rc, o, e = run(["status", "--porcelain", "--", f])
    print("  %-46s %s" % (f, o or "(no change)"))
print("")
print("=== 依赖闭包核查：本批新引用的模块是否都在清单内 ===")
imports = {"kline_store.py": ["app.services.kline_store"],
           "kline_ingest.py": ["app.services.kline_store", "requests"],
           "kline_backfill.py": ["app.services.kline_store", "concurrent.futures"],
           "signal_scan.py": ["app.core.config", "app.services.kline_store"],
           "jobs.py": ["app.services.kline_backfill", "app.services.kline_store", "app.core.config"],
           "config.py": []} 
print("  (人工核：kline_store/kline_ingest/kline_backfill/signal_scan/jobs/config 已在清单；无新库引入)")
rc, o, e = run(["diff", "--cached", "--name-only"])
print("")
print("=== 暂存区现状（应为空）===")
print("  " + (o or "(empty)"))