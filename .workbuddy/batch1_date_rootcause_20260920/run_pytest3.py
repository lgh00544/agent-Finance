import subprocess, os
os.chdir(r"D:\self")
ws_tmp = r"D:\self\.pytest_tmp"
env = dict(os.environ)
env.update({"PYTHONIOENCODING": "utf-8", "PYTHONPATH": r"D:\self\backend",
            "TEMP": ws_tmp, "TMP": ws_tmp, "TMPDIR": ws_tmp})
p = subprocess.run([r"D:\self\.venv\Scripts\python.exe", "-m", "pytest",
                    "backend/tests/test_kline_store.py", "-q", "--no-header",
                    "-p", "no:cacheprovider", "--basetemp=" + ws_tmp],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
lines = (p.stdout or "").splitlines()
err = [l for l in (p.stderr or "").splitlines() if "cleanup_dead_symlinks" not in l and "File \"" not in l]
out = ["RC=%d" % p.returncode, "--- STDOUT tail ---"] + lines[-22:]
if any("Traceback" in e for e in err):
    out += ["--- STDERR (filtered) ---"] + err[-10:]
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_pytest_clean3.txt", "w", encoding="utf-8").write("\n".join(out))
print("OK")