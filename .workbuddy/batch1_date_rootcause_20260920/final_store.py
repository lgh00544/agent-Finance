import sqlite3, collections
con = sqlite3.connect(r"D:\self\data\kline.db")
rows = con.execute("SELECT stock_code, COUNT(*) FROM daily_kline GROUP BY stock_code").fetchall()
codes = [r[0] for r in rows]
pref = collections.Counter(c[:3] for c in codes)
enough = sum(1 for _, n in rows if n >= 250)
print("codes=%d rows=%d 达250根=%d" % (len(rows), sum(n for _, n in rows), enough))
print("段分布=" + str(dict(sorted(pref.items()))))
print("span=%s -> %s" % con.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_kline").fetchone())