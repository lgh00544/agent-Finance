import os, json
p = r"D:\self\.workbuddy\batch1_date_rootcause_20260920\replay_0920_progress.jsonl"
if os.path.exists(p):
    for i, l in enumerate(open(p, encoding="utf-8"), 1):
        print("%d|%s" % (i, l.strip()[:400]))
else:
    print("no progress file")