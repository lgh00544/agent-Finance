import sys, os
sys.path.insert(0, r"D:\self\backend")
out = []
# SYNC_ON_START 现值
for l in open(r"D:\self\.env", encoding="utf-8", errors="replace"):
    s = l.strip()
    if s and not s.startswith("#") and "SYNC_ON_START" in s:
        out.append("ENV " + s)
else:
    out.append("SYNC_ON_START 未显式设置（走默认）")
from app.core.config import settings
out.append("settings.db_backend=%r sqlite_path=%r" % (settings.db_backend, settings.sqlite_path))
from sqlalchemy import text
from app.db.session import SessionLocal
with SessionLocal() as db:
    for t in ("holding", "signal_trigger", "alert_log", "review_result", "position_plan"):
        try:
            n = db.execute(text("SELECT COUNT(*) FROM " + t)).scalar()
            out.append("  %-16s %s" % (t, n))
        except Exception as e:
            out.append("  %-16s ERR %s" % (t, str(e)[:60]))
print("\n".join(out))