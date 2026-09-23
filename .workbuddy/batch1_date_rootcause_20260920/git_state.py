import subprocess, os
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
def run(a):
    p = subprocess.run([GIT] + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()
for a in (["log", "-3", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M"],
          ["status", "--porcelain", "--", "backend/"]) :
    rc, o, e = run(a)
    print("$ git " + " ".join(a))
    print(o or e or "(empty)")
rc, o, e = run(["ls-files", "--error-unmatch", "backend/app/services/kline_store.py"])
print("kline_store tracked? " + ("YES -> " + o if rc == 0 else "NO (untracked)"))
rc, o, e = run(["ls-files", "--error-unmatch", "backend/app/services/kline_ingest.py"])
print("kline_ingest tracked? " + ("YES" if rc == 0 else "NO (untracked)"))