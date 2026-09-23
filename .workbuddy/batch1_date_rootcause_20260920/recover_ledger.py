import subprocess, os
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
def run(a):
    p = subprocess.run([GIT] + a, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr
rc, out, err = run(["status", "--porcelain", "--", "买卖点信号体系_批1_观察期台账.md"])
print("STATUS:", repr(out))
rc2, out2, err2 = run(["log", "--oneline", "-3", "--", "买卖点信号体系_批1_观察期台账.md"])
print("LOG:", out2)
rc3, out3, err3 = run(["show", "HEAD:买卖点信号体系_批1_观察期台账.md"])
print("HEAD version lines:", len(out3.splitlines()) if rc3 == 0 else "rc=%d %s" % (rc3, err3[:200]))
ope = r"D:\self\.workbuddy\batch1_date_rootcause_20260920\ledger_from_git.md"
if rc3 == 0:
    open(ope, "w", encoding="utf-8", newline="\n").write(out3)
    print("saved to", ope)