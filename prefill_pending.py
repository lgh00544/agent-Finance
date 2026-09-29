# -*- coding: utf-8 -*-
"""临时脚本：backup 前先把云端 pending_experience 灌入本地（解决字母序 FK 先决失败）。用完即删。"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from sqlalchemy import select  # noqa: E402
from app.db.models import Base  # noqa: E402
from sync_manager import cloud_engine, local_engine  # noqa: E402

tbl = Base.metadata.tables["pending_experience"]
cloud, local = cloud_engine(), local_engine()
with cloud.connect() as c:
    rows = [dict(r._mapping) for r in c.execute(select(tbl))]
with local.begin() as c:
    c.execute(tbl.delete())
    if rows:
        c.execute(tbl.insert(), rows)
print(f"[OK] pending_experience 预灌 {len(rows)} 行")
