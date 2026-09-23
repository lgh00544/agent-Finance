import subprocess, os
os.chdir(r"D:\self")
ws_tmp = r"D:\self\.pytest_tmp"
os.makedirs(ws_tmp, exist_ok=True)
env = dict(os.environ)
env.update({"PYTHONIOENCODING": "utf-8", "PYTHONPATH": r"D:\self\backend",
            "TEMP": ws_tmp, "TMP": ws_tmp, "TMPDIR": ws_tmp})
p = subprocess.run([r"D:\self\.venv\Scripts\python.exe", "-m", "pytest",
                    "backend/tests/test_kline_store.py", "-q", "--no-header",
                    "-p", "no:cacheprovider", "--basetemp=" + ws_tmp, "--keep-basetemp"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
txt = (p.stdout or "")
lines = [l for l in txt.splitlines()]
out = ["RC=%d" % p.returncode] + lines[-25:]
if p.stderr and "cleanup_dead_symlinks" not in p.stderr:
    out += ["--- STDERR (filtered) ---"] + [l for l in p.stderr.splitlines() if "cleanup_dead_symlinks" not in l][-8:]
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_pytest_clean2.txt", "w", encoding="utf-8").write("\n".join(out))
print("OK")