import subprocess, os, shutil, ast, sys
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
PY = r"D:\self\.venv\Scripts\python.exe"
COPY = r"D:\self\.wb_gatecopy"
shutil.rmtree(COPY, ignore_errors=True)
os.makedirs(COPY, exist_ok=True)
# 注意：干净副本必须含暂存内容 → 先 add，再 archive（否则验证的是旧 HEAD）
def run(a, cwd=None, env=None):
    p = subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env)
    return p.returncode, p.stdout, p.stderr
rc, o, e = run([GIT, "add"] + ["backend/app/services/kline_store.py", "backend/app/services/kline_ingest.py",
    "backend/app/services/kline_backfill.py", "backend/app/services/signal_scan.py",
    "backend/app/scheduler/jobs.py", "backend/app/core/config.py",
    "backend/scripts/kline_backfill_once.py", "backend/tests/test_kline_store.py"], cwd=r"D:\self")
print("git add rc=%d %s" % (rc, e[:200]))
# 用 git stash create 不方便；直接 tar 出「工作区当前内容」的 backend（等价于暂存）
src = r"D:\self\backend"
dst = os.path.join(COPY, "backend")
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
env = dict(os.environ, PYTHONPATH=dst, PYTHONIOENCODING="utf-8")
rc2, o2, e2 = run([PY, "-c", "import app.main; print('APP_MAIN_IMPORT_OK')"], cwd=COPY, env=env)
print("门禁② 干净副本 import: rc=%d %s %s" % (rc2, o2.strip()[-80:], e2.strip()[-200:]))
def count_tests(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
def count_defs(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_call_with_timeout")
t = os.path.join(dst, "tests", "test_kline_store.py")
w = r"D:\self\backend\tests\test_kline_store.py"
a = count_tests(t); b = count_tests(w)
print("门禁③ test_kline_store 用例数 干净副本=%d 工作区=%d 一致=%s" % (a, b, a == b))
st = os.path.join(dst, "tests", "test_datasource_stability.py")
sw = r"D:\self\backend\tests\test_datasource_stability.py"
if os.path.exists(st):
    print("   test_datasource_stability 干净副本=%d 工作区=%d" % (count_tests(st), count_tests(sw)))