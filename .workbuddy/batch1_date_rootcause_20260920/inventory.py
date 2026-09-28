import os, glob, datetime, sqlite3, collections
out = []
def sz(p):
    try: return os.path.getsize(p)/1048576
    except Exception: return 0
# A) 根目录散落文件（按 mtime 倒序前 30）
out.append("=== A. 根目录散落文件（top 30 by mtime）===")
files = [p for p in glob.glob(r"D:\self\*") if os.path.isfile(p)]
files.sort(key=os.path.getmtime, reverse=True)
for p in files[:30]:
    out.append("  %-52s %7.2f MB  %s" % (os.path.basename(p)[:50], sz(p), datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")))
# B) 我建过的临时目录
out.append("")
out.append("=== B. 临时/证据目录 ===")
for d in sorted(glob.glob(r"D:\self\.wb_*") + glob.glob(r"D:\self\.pytest_tmp*") + glob.glob(r"D:\self\.workbuddy\batch*")):
    n = len(glob.glob(os.path.join(d, "**", "*"), recursive=True))
    tot = sum(sz(f) for f in glob.glob(os.path.join(d, "**", "*"), recursive=True) if os.path.isfile(f))
    out.append("  %-46s files=%-5d %8.2f MB  %s" % (os.path.basename(d)[:44], n, tot, datetime.datetime.fromtimestamp(os.path.getmtime(d)).strftime("%m-%d %H:%M")))
# C) kline.db 规模与分布
out.append("")
out.append("=== C. data/kline.db ===")
k = r"D:\self\data\kline.db"
if os.path.exists(k):
    out.append("  size=%.1f MB mtime=%s" % (sz(k), datetime.datetime.fromtimestamp(os.path.getmtime(k))))
    con = sqlite3.connect(k)
    tot = con.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    codes = con.execute("SELECT COUNT(DISTINCT stock_code) FROM daily_kline").fetchone()[0]
    out.append("  rows=%d codes=%d" % (tot, codes))
    dup = con.execute("SELECT COUNT(*) FROM (SELECT stock_code, trade_date, COUNT(*) c FROM daily_kline GROUP BY stock_code, trade_date HAVING c > 1)").fetchone()[0]
    out.append("  重复主键组=%d（主键约束应为 0）" % dup)
    rows = con.execute("SELECT stock_code, COUNT(*) FROM daily_kline GROUP BY stock_code ORDER BY COUNT(*) DESC LIMIT 5").fetchall()
    out.append("  每票根数 top5: %s" % rows)
    low = con.execute("SELECT COUNT(*) FROM (SELECT stock_code FROM daily_kline GROUP BY stock_code HAVING COUNT(*) < 250)").fetchone()[0]
    out.append("  不足250根的票=%d" % low)
# D) dev.db 里可疑的表（测试痕 / 重复 / 空表）
out.append("")
out.append("=== D. data/dev.db 表盘点（行数）===")
d = r"D:\self\data\dev.db"
if os.path.exists(d):
    con = sqlite3.connect(d)
    tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    info = []
    for t in tabs:
        try: info.append((t, con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]))
        except Exception: info.append((t, -1))
    zero = [t for t, n in info if n == 0]
    out.append("  表数=%d 空表=%d" % (len(tabs), len(zero)))
    out.append("  空表: %s" % ", ".join(zero[:20]))
    out.append("  行数 top15: %s" % sorted([(n, t) for t, n in info], reverse=True)[:15])
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_inventory.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in out))
print("\n".join(str(x) for x in out))