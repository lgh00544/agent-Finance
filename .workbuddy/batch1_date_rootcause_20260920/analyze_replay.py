import io, os, json
d = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
raw = open(os.path.join(d, "replay_500b.stderr.txt"), "rb").read()
txt = raw.decode("utf-8", "replace")
lines = [l for l in txt.splitlines() if not l.strip().startswith("Please wait") and "it/s" not in l and "it]" not in l]
print("stderr bytes=%d, non-progress lines=%d" % (len(raw), len(lines)))
for l in lines[-25:]:
    print("  " + l[:260])
print("=== variant comparison ===")
r1 = json.load(open(os.path.join(d, "replay_rows_no_dedup_cold.json"), encoding="utf-8"))
r2 = json.load(open(os.path.join(d, "replay_rows_with_dedup.json"), encoding="utf-8"))
k1 = {(x["stock_code"], x["signal_id"]) for x in r1}
k2 = {(x["stock_code"], x["signal_id"]) for x in r2}
print("v1 hits=%d v2 hits=%d  v1<=v2? %s  v1 subset of v2? %s" % (len(r1), len(r2), len(r1) <= len(r2), k1 <= k2))
print("in v2 not v1:", sorted(k2 - k1))
print("codes covered by v1:", sorted({x["stock_code"] for x in r1}))
print("codes covered by v2:", sorted({x["stock_code"] for x in r2}))
print("sample v1 row:", json.dumps(r1[0], ensure_ascii=False)[:300] if r1 else "-")