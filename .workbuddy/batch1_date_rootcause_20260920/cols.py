import sys, os, json, time
sys.path.insert(0, r"D:\self\backend")
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.session import SessionLocal
out = []
with SessionLocal() as db:
    cols = db.execute(text("SHOW COLUMNS FROM signal_trigger")).all()
out.append("columns = %s" % [r[0] for r in cols])
    
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_step_j_cols.txt", "w", encoding="utf-8").write("\n".join(out))
print("OK")