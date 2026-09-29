# -*- coding: utf-8 -*-
"""临时脚本：本地 dev.db schema 迁移（合并远端后新增表/列补齐）。用完即删。"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from app.db import session  # noqa: E402
from app.core.config import settings  # noqa: E402
from sync_manager import local_engine  # noqa: E402

orig_engine, orig_backend = session.engine, settings.db_backend
session.engine = local_engine()
settings.db_backend = "sqlite"  # 让 _ensure_experience_fts 对本地生效
try:
    session.init_db()
    print("[OK] 本地 schema 迁移完成 (create_all + _ensure_* 全量幂等)")
finally:
    session.engine, settings.db_backend = orig_engine, orig_backend
