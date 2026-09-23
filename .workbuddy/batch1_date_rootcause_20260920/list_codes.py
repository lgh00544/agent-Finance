import sys, os
sys.path.insert(0, r"D:\self\backend")
from sqlalchemy import text
from app.db.session import SessionLocal
with SessionLocal() as db:
    codes = sorted({r[0] for r in db.execute(text("SELECT stock_code FROM signal_trigger WHERE trade_date = :d"), {"d": "2026-09-18"}).all()})
print("all_db_codes(%d): %s" % (len(codes), codes))
print("first5:", codes[:5])
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_step_j_codes.txt", "w", encoding="utf-8").write("\n".join(["%d|%s" % (i + 1, c) for i, c in enumerate(codes)]))