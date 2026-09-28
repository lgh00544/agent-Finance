import os, glob, datetime
root = r"D:\self"
before = 0.0
def mb(p):
    try: return os.path.getsize(p)/1048576
    except Exception: return 0.0
plan = []
# 1) 观察期日志副本（app.log.*-obs.log / backend-dev.*-obs.log）
for pat in ("app.log.*-obs.log", "backend-dev.*-obs.log", "app.log.*-obs.log.*"):
    for p in glob.glob(os.path.join(root, pat)):
        plan.append(("obs-log", p))
# 2) 重启归档：保留最新 3 份，其余删
arch = sorted(glob.glob(os.path.join(root, "backend-dev.stdout.*.log")) +
              glob.glob(os.path.join(root, "backend-dev.stderr.*.log")), key=os.path.getmtime, reverse=True)
keep = set(arch[:3])
for p in arch[3:]:
    plan.append(("old-archive", p))
total = sum(mb(p) for _, p in plan)
print("planned=%d files, %.2f MB" % (len(plan), total))
for kind, p in plan:
    print("  [%s] %-52s %7.2f MB" % (kind, os.path.basename(p)[:50], mb(p)))
print("")
print("keep(newest 3 archives): " + ", ".join(os.path.basename(x) for x in arch[:3]))
# 执行
ok = fail = 0
for kind, p in plan:
    try:
        if os.path.isfile(p):
            os.remove(p); ok += 1
        else: fail += 1
    except Exception as e:
        fail += 1
        print("  FAIL %s: %s" % (os.path.basename(p), type(e).__name__))
print("")
print("deleted=%d failed=%d freed~%.2f MB" % (ok, fail, total))
left = sorted(glob.glob(os.path.join(root, "backend-dev*.log")) + glob.glob(os.path.join(root, "app.log*")))
print("剩余日志文件=%d" % len(left))
for p in left:
    print("  %-52s %7.2f MB" % (os.path.basename(p)[:50], mb(p)))