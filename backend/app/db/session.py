"""
数据库会话管理：同一套 ORM 模型，默认 SQLite 单文件（data/dev.db，零外部依赖）；
DB_BACKEND=mysql 时切换 MySQL8。业务代码一律通过 repo 网关访问，本模块只被网关使用。
"""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base


def _sqlite_pragmas(dbapi_connection, connection_record):
    """SQLite 打开外键与 WAL，便于多线程读写"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _build_engine_url() -> str:
    if settings.db_backend == "mysql":
        return (
            f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_root_password}"
            f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
            "?charset=utf8mb4"
        )
    # 默认：SQLite 单文件（SQLITE_PATH 便于测试隔离）
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    import os

    db_file = os.environ.get("SQLITE_PATH") or (data_dir / "dev.db")
    return f"sqlite:///{db_file}"


engine = create_engine(
    _build_engine_url(),
    pool_pre_ping=True,
    echo=False,
)

if settings.db_backend != "mysql":
    event.listen(engine, "connect", _sqlite_pragmas)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """建表（幂等）。prod 模式下容器初始化已有 DDL，此处 create_all 兜底保证结构一致。"""
    from app.db import models  # noqa: F401  确保模型注册

    Base.metadata.create_all(bind=engine)
    _ensure_review_result_columns()


def _ensure_review_result_columns(eng=None) -> None:
    """幂等补齐 review_result 建议驳回迭代列（仅增量加列，不重建表不丢数据）"""
    eng = eng or engine
    additions = {
        "suggest_status": "VARCHAR(16) DEFAULT 'pending'",
        "reject_reason": "TEXT DEFAULT ''",
        "suggest_iteration": "INTEGER DEFAULT 1",
        "suggest_history": "JSON",
    }
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(review_result)")}
            for col, ddl in additions.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE review_result ADD COLUMN {col} {ddl}")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            for col, ddl in additions.items():
                try:
                    conn.exec_driver_sql(f"ALTER TABLE review_result ADD COLUMN {col} {ddl}")
                except Exception:  # noqa: BLE001 列已存在
                    pass


def get_session() -> Session:
    """FastAPI 依赖：请求级会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
