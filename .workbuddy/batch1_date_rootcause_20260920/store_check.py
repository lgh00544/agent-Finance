import sys, os, json, sqlite3, collections
db = r"D:\self\data\kline.db"
con = sqlite3.connect(db)
rows = con.execute("SELECT stock_code, COUNT(*) c FROM daily_kline GROUP BY stock_code").fetchall()
codes = [r[0] for r in rows]
pref = collections.Counter(c[:3] for c in codes)
enough = sum(1 for _, c in rows if c >= 250)
print("store: codes=%d rows=%d 达250根=%d" % (len(rows), sum(c for _, c in rows), enough))
print("段分布(已入库):", dict(sorted(pref.items())))
uni = json.load(open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\universe_codes.json", encoding="utf-8"))
u_pref = collections.Counter(c[:3] for c in uni)
print("universe=%d 段分布: %s" % (len(uni), dict(sorted(u_pref.items())[:14])))
bj = [c for c in uni if c.startswith(("4", "8", "9"))]
print("北交所(4/8/9 开头)只数=%d" % len(bj))