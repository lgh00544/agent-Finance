import json, io
d = json.load(open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\ledger_patch.json", encoding="utf-8"))
p = d["file"]
lines = io.open(p, encoding="utf-8").read().split("\n")
out, report = [], []
for op in d["ops"]:
    hit = False
    for l in lines:
        if l.startswith(op["prefix"]):
            if op.get("old") is not None:
                assert l == op["old"], "line mismatch for prefix %s:\nOLD: %r\nGOT: %r" % (op["prefix"], op["old"], l)
            out.append(op["new"]); hit = True; report.append("OK " + op["prefix"][:24])
            break
        out.append(l)
    lines = out; out = []
    if not hit: report.append("MISS " + op["prefix"][:24])
io.open(p, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(report))