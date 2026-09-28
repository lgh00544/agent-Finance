import os, re, glob
logs = sorted(glob.glob(r"D:\self\backend-dev.stdout.log"), key=os.path.getmtime)
out = []
for lp in logs[:1]:
    lines = open(lp, encoding="utf-8", errors="replace").read().splitlines()
    out.append("log=%s lines=%d" % (os.path.basename(lp), len(lines)))
    pat = re.compile(r"OperationalError|Can.t connect|2003|denied|quota|1045|1040|too many|pymysql|TiDB|connect to MySQL", re.I)
    hits = [(i + 1, l) for i, l in enumerate(lines) if pat.search(l)]
    out.append("DB 相关异常行数=%d" % len(hits))
    for n, l in hits[-8:]:
        out.append("  L%d %s" % (n, l[:190]))
    errs = [(i + 1, l) for i, l in enumerate(lines) if "[ERROR]" in l]
    out.append("ERROR 行数=%d" % len(errs))
    for n, l in errs[-6:]:
        out.append("  L%d %s" % (n, l[:190]))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_db_health_log.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))