import re, os
p = r"D:\self\sync_manager.py"
src = open(p, encoding="utf-8", errors="replace").read()
def body(name):
    m = re.search(r"def " + name + r"\(.*?\n(.*?)(?=\ndef |\Z)", src, re.S)
    return (m.group(0) if m else "")[:900]
print("=== cmd_init（云端→本地 还是 本地→云端？）===")
b = body("cmd_init")
print(b[:700])
print("")
print("=== 是否有「写本地/降级」逻辑 ===")
for kw in ("fallback", "降级", "except OperationalError", "SQLITE", "dev.db", "read_only", "双写"):
    hits = [i + 1 for i, l in enumerate(src.splitlines()) if kw.lower() in l.lower()]
    print("  %-22s %s" % (kw, hits[:6] or "无"))