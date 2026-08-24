# -*- coding: utf-8 -*-
"""临时脚本：快速查看 dev.db 表结构与最近数据量（不修改任何数据）"""
import sqlite3
from datetime import datetime

con = sqlite3.connect(r"D:\self\data\dev.db")
con.row_factory = sqlite3.Row
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

print(f"[tables] {len(tables)}:")
print("  " + " ".join(tables))
print()

counts = {}
for t in tables:
    try:
        counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except Exception as e:
        counts[t] = f"ERR:{e}"
for t, n in sorted(counts.items(), key=lambda x: str(x[1]), reverse=True):
    print(f"  {t}: {n}")

print()
# 关键业务表最近数据日期
for t, col in [("stock_candidate", "trade_date"), ("stock_score", "created_at"),
               ("monitor_alert", "created_at"), ("trade_review", "created_at"),
               ("position_plan", "created_at"), ("market_condition", "trade_date"),
               ("candidate_track_verify", "trade_date")]:
    try:
        row = con.execute(f"SELECT MAX({col}), COUNT(*) FROM {t}").fetchone()
        print(f"  {t}.{col} MAX={row[0]} rows={row[1]}")
    except Exception as e:
        print(f"  {t}: ERR {e}")
con.close()