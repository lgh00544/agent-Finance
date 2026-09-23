import subprocess, os, sys
os.chdir(r"D:\self")
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=r"D:\self\backend")
p = subprocess.run([r"D:\self\.venv\Scripts\python.exe", "-m", "pytest",
                    "backend/tests/test_kline_store.py::test_upsert_and_load_roundtrip",
                    "-q", "--no-header", "-p", "no:cacheprovider",
                    "--basetemp=D:\\self\\.pytest_tmp3"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
txt = p.stdout + "\n--- STDERR ---\n" + p.stderr
lines = txt.splitlines()
keep = [l for l in lines if not l.startswith(("  ", "\t")) or "Error" in l or "assert" in l or "line " in l]
out = ["RC=%d total_lines=%d" % (p.returncode, len(lines))] + lines[:60]
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_pytest_clean.txt", "w", encoding="utf-8").write("\n".join(out))
print("OK")