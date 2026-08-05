# -*- coding: utf-8 -*-
"""一次性清理脚本：删除真实库中测试验证产生的脏数据（仅删候选池测试记录）。
【刚性代码逻辑】纯数据清理，不包含任何市场判断。"""
import sqlite3

DB = "D:/self/data/dev.db"

con = sqlite3.connect(DB)
cur = con.cursor()

# 测试验证产生的脏数据：候选「缓存测试A」600101（2026-08-04）
rows = cur.execute(
    "SELECT stock_code, stock_name, trade_date, rank FROM stock_candidate "
    "WHERE stock_name IN ('缓存测试A', '缓存测试B', '时间测试股A') OR "
    "stock_code IN ('600101', '600998', '600999') OR "
    "(trade_date IN ('2099-01-01', '2098-01-01'))"
).fetchall()
print("待删除候选:", rows)
cur.execute(
    "DELETE FROM stock_candidate WHERE stock_name IN ('缓存测试A', '缓存测试B', '时间测试股A') OR "
    "stock_code IN ('600101', '600998', '600999') OR "
    "(trade_date IN ('2099-01-01', '2098-01-01'))")

# 同批测试数据可能残留的评分（时间测试股系列，名称特征）
score_rows = cur.execute(
    "SELECT stock_code, stock_name, trade_date FROM stock_score "
    "WHERE stock_name IN ('缓存测试A', '缓存测试B', '时间测试股B') OR "
    "stock_code IN ('600101', '600998', '600997', '600102')"
).fetchall()
print("待删除评分:", score_rows)
cur.execute(
    "DELETE FROM stock_score WHERE stock_name IN ('缓存测试A', '缓存测试B', '时间测试股B') OR "
    "stock_code IN ('600101', '600998', '600997', '600102')")

# 同批测试产生的建仓方案/复盘（时间测试股系列）
for table in ("position_plan", "review_result", "alert_log"):
    n = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE stock_name LIKE '%测试股%' OR stock_name LIKE '%缓存测试%'").fetchone()[0]
    if n:
        print(f"删除 {table} 测试残留: {n} 条")
        cur.execute(f"DELETE FROM {table} WHERE stock_name LIKE '%测试股%' OR stock_name LIKE '%缓存测试%'")

con.commit()

print("\n清理后候选池:")
for r in cur.execute("SELECT stock_code, stock_name, trade_date, rank FROM stock_candidate ORDER BY trade_date DESC, rank"):
    print(" ", r)
con.close()
