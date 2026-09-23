import os, shutil, subprocess, sys
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
cleaned = []
for d in (".pytest_tmp", ".pytest_tmp2", ".pytest_tmp3", ".wb_pt", ".wb_harness_tmp", ".wb_smoke", ".wb_smoke2", ".wb_smoke3"):
    p = os.path.join(r"D:\self", d)
    if os.path.isdir(p):
        try:
            shutil.rmtree(p, ignore_errors=True)
            cleaned.append(d + ("(removed)" if not os.path.isdir(p) else "(partial, locked)"))
        except Exception as e:
            cleaned.append("%s(ERR %s)" % (d, type(e).__name__))
p = subprocess.run([GIT, "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace")
lines = p.stdout.splitlines()
print("cleaned:", cleaned)
print("--- git status ---")
for l in lines: print("  " + l)
p2 = subprocess.run([GIT, "diff", "--stat", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("--- diff --stat HEAD ---")
print(p2.stdout)