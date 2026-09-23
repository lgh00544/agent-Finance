import subprocess, os, ast, sys, shutil
PY = r"D:\self\.venv\Scripts\python.exe"
env = dict(os.environ, PYTHONPATH=r"D:\self\backend", PYTHONIOENCODING="utf-8")
# 门禁② 等价验证：显式 import 本批改动模块 + 入口
code = "import app.main, app.scheduler.jobs as j, app.services.signal_scan as s, app.services.kline_store as k, app.services.kline_ingest as i, app.services.kline_backfill as b; print('IMPORT_OK', hasattr(j, 'kline_backfill_job'), k.series_adjust.__name__, b.pending_codes.__name__)"
p = subprocess.run([PY, "-c", code], cwd=r"D:\self", env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("门禁② rc=%d" % p.returncode)
print("  ", (p.stdout or "").strip()[-120:])
if p.returncode: print("  stderr:", (p.stderr or "").strip()[-300:])
# 门禁③ 测试数（工作区 vs HEAD 版本）
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
def cnt_text(t):
    return sum(1 for n in ast.walk(ast.parse(t)) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
w = r"D:\self\backend\tests\test_kline_store.py"
work = cnt_text(open(w, encoding="utf-8").read())
q = subprocess.run([GIT, "show", "HEAD:backend/tests/test_kline_store.py"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=r"D:\self")
head = cnt_text(q.stdout) if q.returncode == 0 else -1
print("门禁③ test_kline_store: 工作区=%d HEAD=%d 新增=%d" % (work, head, work - head))
sw = r"D:\self\backend\tests\test_datasource_stability.py"
q2 = subprocess.run([GIT, "show", "HEAD:backend/tests/test_datasource_stability.py"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=r"D:\self")
print("   test_datasource_stability: 工作区=%d HEAD=%d" % (cnt_text(open(sw, encoding="utf-8").read()), cnt_text(q2.stdout) if q2.returncode == 0 else -1))
shutil.rmtree(r"D:\self\.wb_gatecopy", ignore_errors=True)
shutil.rmtree(r"D:\self\.wb_gatecopy2", ignore_errors=True)