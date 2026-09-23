import subprocess, os
os.chdir(r"D:\self")
ws = r"D:\self\.wb_pt"
os.makedirs(ws, exist_ok=True)
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=r"D:\self\backend", TEMP=ws, TMP=ws)
ids = ["test_prev_close_and_has_enough_and_stats", "test_ingest_today_writes_bars",
       "test_ingest_today_empty_universe_writes_nothing", "test_backfill_skips_sufficient_and_fills_missing"]
p = subprocess.run([r"D:\self\.venv\Scripts\python.exe", "-m", "pytest",
                    *["backend/tests/test_kline_store.py::" + i for i in ids],
                    "-q", "--no-header", "-p", "no:cacheprovider", "--basetemp=" + ws + "\\bt"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
lines = (p.stdout or "").splitlines()
keep = [l for l in lines if l.startswith(("FAILED", "PASSED", "ERROR", "=", "1 ", "2 ", "3 ", "4 ", "5 ")) or " passed" in l or " failed" in l or "assert" in l]
out = ["RC=%d" % p.returncode] + keep[:20] + ["--- raw tail ---"] + lines[-12:]
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_pytest_4ids.txt", "w", encoding="utf-8").write("\n".join(out))
print("OK")