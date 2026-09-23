import subprocess, os
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
def run(a):
    p = subprocess.run([GIT] + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()
rc, o, e = run(["show", "--stat", "--format=%h %s", "74281bd"])
print("=== 74281bd commit stat ===")
print(o)
rc, o, e = run(["grep", "-n", "\"universe\"", "74281bd", "--", "backend/app/services/signal_scan.py"])
print("=== universe lines in committed signal_scan ===")
print(o[:800])