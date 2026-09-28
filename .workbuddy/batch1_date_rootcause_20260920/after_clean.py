import os, glob
root = r"D:\self"
def mb(p):
    try: return os.path.getsize(p)/1048576
    except Exception: return 0.0
left = sorted(glob.glob(os.path.join(root, "backend-dev*.log")) + glob.glob(os.path.join(root, "app.log*")))
print("剩余日志文件=%d  合计=%.2f MB" % (len(left), sum(mb(p) for p in left)))
for p in left:
    print("  %-52s %7.2f MB" % (os.path.basename(p)[:50], mb(p)))
print("")
print("--- 仍存在的临时目录 ---")
for d in sorted(glob.glob(os.path.join(root, ".wb_*")) + glob.glob(os.path.join(root, ".pytest_tmp*"))):
    n = len([f for f in glob.glob(os.path.join(d, "**", "*"), recursive=True) if os.path.isfile(f)])
    print("  %-24s files=%-5d %.2f MB" % (os.path.basename(d), n, sum(mb(f) for f in glob.glob(os.path.join(d, "**", "*"), recursive=True) if os.path.isfile(f))))