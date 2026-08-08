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
    """SQLite 性能/并发调优：WAL 读写不互斥 + 异步刷盘 + 内存缓存 + 忙等待"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")     # 写前日志：读不阻塞写、写不阻塞读
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")   # WAL 下崩溃安全且大幅降低 fsync 次数
    cursor.execute("PRAGMA cache_size=-20000")    # 页缓存 20MB，降低磁盘 IO
    cursor.execute("PRAGMA busy_timeout=5000")    # 写锁竞争时等待而非立即报错
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
    _ensure_stock_candidate_detail()
    _ensure_trade_record_columns()
    _ensure_indexes()


def _ensure_indexes() -> None:
    """幂等补建高频查询索引（create_all 只对新表建索引，已存在的表需单独补建）。
    SQLite 支持 IF NOT EXISTS；MySQL 走 init.sql（容器初始化 DDL）。"""
    if engine.dialect.name != "sqlite":
        return
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_candidate_date_rank "
        "ON stock_candidate (trade_date, rank)",
        "CREATE INDEX IF NOT EXISTS ix_holding_status ON holding (status)",
        "CREATE INDEX IF NOT EXISTS ix_review_exit_status "
        "ON review_result (exit_date, suggest_status)",
        "CREATE INDEX IF NOT EXISTS ix_suggestion_status ON agent_suggestion (status)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)


def _ensure_stock_candidate_detail(eng=None) -> None:
    """幂等补齐 stock_candidate.detail 列（v2.0 输出详情；仅增量加列，不重建表不丢数据）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(stock_candidate)")}
            if "detail" not in existing:
                conn.exec_driver_sql("ALTER TABLE stock_candidate ADD COLUMN detail JSON")
        else:
            try:
                conn.exec_driver_sql("ALTER TABLE stock_candidate ADD COLUMN detail JSON")
            except Exception:  # noqa: BLE001 列已存在
                pass


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


def _ensure_trade_record_columns(eng=None) -> None:
    """幂等补齐 trade_record.before/after_shares 列（手动操作前后持仓变化留痕，K223；
    仅增量加列，不重建表不丢数据；旧数据为 NULL，展示层兼容）"""
    eng = eng or engine
    additions = {
        "before_shares": "INTEGER",
        "after_shares": "INTEGER",
    }
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(trade_record)")}
            for col, ddl in additions.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE trade_record ADD COLUMN {col} {ddl}")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            for col, ddl in additions.items():
                try:
                    conn.exec_driver_sql(f"ALTER TABLE trade_record ADD COLUMN {col} {ddl}")
                except Exception:  # noqa: BLE001 列已存在
                    pass


def get_session() -> Session:
    """FastAPI 依赖：请求级会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
