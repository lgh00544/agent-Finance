# -*- coding: utf-8 -*-
"""lugh 阶段3 验证：表存在 + 真实数据条数"""
import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "dev.db")
print("db:", os.path.abspath(db), "exists:", os.path.exists(db))
if not os.path.exists(db):
    print("DB NOT FOUND"); sys.exit(1)

c = sqlite3.connect(db)
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in ("hot_money_profile", "lhb_original_flow"):
    print(f"table {t}: {'Y' if t in tables else 'N'}")
    if t in tables:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  rows: {n}")

# 看 lhb 字段和几条样例（字段名/口径）
if "lhb_original_flow" in tables:
    cols = [r[1] for r in c.execute("PRAGMA table_info(lhb_original_flow)").fetchall()]
    print("  lhb cols:", cols)
    rows = c.execute("SELECT trade_date, stock_code, lhb_type, net_buy, confidence, source FROM lhb_original_flow LIMIT 4").fetchall()
    for r in rows:
        print("   sample:", r)
c.close()
