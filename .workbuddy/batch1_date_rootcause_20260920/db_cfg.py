import os, re
root = r"D:\self"
env = os.path.join(root, ".env")
if os.path.exists(env):
    for line in open(env, encoding="utf-8", errors="replace"):
        if re.search(r"DB_|MYSQL|TIDB|SQLITE|BACKUP|FALLBACK|LOCAL", line, re.I):
            print("ENV: " + line.strip()[:140])
print("--- sync_manager 函数清单 ---")
sm = os.path.join(root, "sync_manager.py")
if os.path.exists(sm):
    for line in open(sm, encoding="utf-8", errors="replace"):
        if line.lstrip().startswith("def ") or "cmd_" in line[:40]:
            print("  " + line.strip()[:120])