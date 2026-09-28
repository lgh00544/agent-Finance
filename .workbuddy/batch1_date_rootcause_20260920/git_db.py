import subprocess, os, glob, datetime
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
def run(a):
    p = subprocess.run([GIT] + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()
out = []
# 1) dev.db / data 是否被 git 跟踪/忽略
for f in ("data/dev.db", "data/kline.db", "data/", "*.db"):
    rc, o, e = run(["check-ignore", "-v", f])
    out.append("check-ignore %-16s -> %s" % (f, o if rc == 0 else "(未被 ignore)"))
rc, o, e = run(["ls-files", "--error-unmatch", "data/dev.db"])
out.append("dev.db 是否已入库: %s" % ("是" if rc == 0 else "否"))
# 2) data 目录下实际文件 + 大小
out.append("--- data/ 文件 ---")
for p in sorted(glob.glob(r"D:\self\data\*"), key=os.path.getmtime)[-12:]:
    if os.path.isfile(p):
        st = os.stat(p)
        out.append("  %-34s %9.1f MB  %s" % (os.path.basename(p), st.st_size/1048576, datetime.datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M")))
# 3) git 里有没有历史提交过 db
rc, o, e = run(["log", "--oneline", "-3", "--", "data/dev.db"])
out.append("--- git log data/dev.db ---")
out.append(o or "(无历史提交)")
# 4) 最近提交
rc, o, e = run(["log", "-3", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M"])
out.append("--- 最近提交 ---")
out.append(o)
rc, o, e = run(["status", "--porcelain"])
out.append("--- 工作区（前 12 行）---")
out.append("\n".join(o.splitlines()[:12]) or "(clean)")
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_git_db_check.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))