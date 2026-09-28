import sqlite3, os
con = sqlite3.connect(r"D:\self\data\dev.db")
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()]
print("tables=%d" % len(tabs))
for i in range(0, len(tabs), 4):
    print("  " + " | ".join("%-26s" % t for t in tabs[i:i+4]))
print("")
print("key table rows:")
for t in tabs:
    if any(k in t for k in ("hold", "signal", "alert", "review", "candidate", "plan", "score", "position", "trade", "paper")):
        try:
            n = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            print("  %-34s %d" % (t, n))
        except Exception as e:
            print("  %-34s ERR %s" % (t, str(e)[:40]))
print("")
print("env actual:")
for l in open(r"D:\self\.env", encoding="utf-8", errors="replace"):
    s = l.strip()
    if s and not s.startswith("#") and ("DB_BACKEND" in s or "SYNC_ON_START" in s):
        print("  " + s)