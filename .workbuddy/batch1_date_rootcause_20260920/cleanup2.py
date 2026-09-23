import os, shutil
for f in (".pytest_tmp_out.txt",):
    p = os.path.join(r"D:\self", f)
    if os.path.isfile(p):
        try: os.remove(p); print("removed", f)
        except Exception as e: print("cant remove", f, type(e).__name__)
for d in (".pytest_tmp", ".pytest_tmp2", ".pytest_tmp3", ".wb_pt"):
    p = os.path.join(r"D:\self", d)
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
        print("%s exists_after=%s" % (d, os.path.isdir(p)))
locks = [d for d in os.listdir(r"D:\self") if d.startswith((".pytest_tmp", ".wb_"))]
print("leftover temp dirs:", locks)