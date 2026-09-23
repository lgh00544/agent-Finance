import subprocess, os, shutil, ast
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
PY = r"D:\self\.venv\Scripts\python.exe"
COPY = r"D:\self\.wb_gatecopy2"
shutil.rmtree(COPY, ignore_errors=True)
dst = os.path.join(COPY, "backend")
shutil.copytree(r"D:\self\backend", dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
env = dict(os.environ, PYTHONPATH=dst, PYTHONIOENCODING="utf-8")
p = subprocess.run([PY, "-c", "import app.main; print('APP_MAIN_IMPORT_OK')"], cwd=COPY, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("门禁② 干净副本 import: rc=%d" % p.returncode)
print("  stdout:", (p.stdout or "").strip()[-90:])
if p.returncode != 0:
    print("  stderr tail:", (p.stderr or "").strip()[-400:])
def cnt(path):
    return sum(1 for n in ast.walk(ast.parse(open(path, encoding="utf-8").read())) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
a, b = cnt(os.path.join(dst, "tests", "test_kline_store.py")), cnt(r"D:\self\backend\tests\test_kline_store.py")
print("门禁③ test_kline_store: 干净副本=%d 工作区=%d 一致=%s" % (a, b, a == b))
st, sw = os.path.join(dst, "tests", "test_datasource_stability.py"), r"D:\self\backend\tests\test_datasource_stability.py"
if os.path.exists(st):
    print("   test_datasource_stability: 干净副本=%d 工作区=%d" % (cnt(st), cnt(sw)))