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
        # ssl_verify_cert/identity=0：TiDB Serverless 强制 TLS 但用系统默认证书、
        # 不校验主机名（等效 pymysql ssl={"check_hostname":False,"verify_mode":0}，已实测连通）
        return (
            f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_root_password}"
            f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
            "?charset=utf8mb4&ssl_verify_cert=0&ssl_verify_identity=0"
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
    _ensure_experience_fts()
    _ensure_review_result_columns()
    _ensure_stock_candidate_detail()
    _ensure_trade_record_columns()
    _ensure_agent_suggestion_columns()
    _ensure_position_plan_detail()
    _ensure_position_plan_source()
    _ensure_hot_money_profile_columns()
    _ensure_holding_high_price()
    _ensure_alert_log_source()
    _ensure_market_condition_next_day()
    _add_factor_scores_column()
    _ensure_indexes()


def _ensure_experience_fts() -> None:
    """经验全文检索 FTS5 虚拟表 + 触发器（幂等）。SQLAlchemy 不直接支持虚拟表，
    用原生 SQL；仅 SQLite 模式启用（MySQL 无 FTS5，检索走 LIKE 降级，见 repo.search_experience）。
    必须与 create_all 后同一会话执行：FTS 内容表触发器引用 experience 表须已存在。"""
    if settings.db_backend == "mysql":
        return
    statements = [
        "CREATE VIRTUAL TABLE IF NOT EXISTS experience_fts USING fts5("
        "title, body, tags, content='experience', content_rowid='id')",
        "CREATE TRIGGER IF NOT EXISTS experience_ai AFTER INSERT ON experience BEGIN "
        "INSERT INTO experience_fts(rowid, title, body, tags) "
        "VALUES (new.id, new.title, new.body, new.tags); END",
        "CREATE TRIGGER IF NOT EXISTS experience_ad AFTER DELETE ON experience BEGIN "
        "INSERT INTO experience_fts(experience_fts, rowid, title, body, tags) "
        "VALUES('delete', old.id, old.title, old.body, old.tags); END",
        "CREATE TRIGGER IF NOT EXISTS experience_au AFTER UPDATE ON experience BEGIN "
        "INSERT INTO experience_fts(experience_fts, rowid, title, body, tags) "
        "VALUES('delete', old.id, old.title, old.body, old.tags); "
        "INSERT INTO experience_fts(rowid, title, body, tags) "
        "VALUES (new.id, new.title, new.body, new.tags); END",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)


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
        "CREATE INDEX IF NOT EXISTS ix_rule_change_status ON rule_change (status)",
        "CREATE INDEX IF NOT EXISTS ix_track_status "
        "ON candidate_track_verify (is_finished, select_date)",
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


def _ensure_position_plan_source(eng=None) -> None:
    """幂等补齐 position_plan.source 列（计划来源标记 candidate/manual；
    仅增量加列，不重建表不丢数据；旧数据默认 manual）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(position_plan)")}
            if "source" not in existing:
                conn.exec_driver_sql("ALTER TABLE position_plan ADD COLUMN source VARCHAR(16) DEFAULT 'manual'")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            try:
                conn.exec_driver_sql("ALTER TABLE position_plan ADD COLUMN source VARCHAR(16) DEFAULT 'manual'")
            except Exception:  # noqa: BLE001 列已存在
                pass


def _ensure_agent_suggestion_columns(eng=None) -> None:
    """幂等补齐 agent_suggestion 列（人工驳回原因留痕 + v2 一键采纳落地信息列；
    仅增量加列，不重建表不丢数据；旧数据 default 兼容）"""
    eng = eng or engine
    additions = {
        "reject_reason": "TEXT DEFAULT ''",
        "priority": "VARCHAR(8) DEFAULT 'medium'",
        "rule_type": "VARCHAR(8) DEFAULT 'soft'",
        "problem_desc": "TEXT DEFAULT ''",
        "rule_text": "TEXT DEFAULT ''",
        "expected_effect": "TEXT DEFAULT ''",
        "risk_note": "TEXT DEFAULT ''",
        "file_path": "VARCHAR(255) DEFAULT ''",
        "insert_position": "VARCHAR(32) DEFAULT ''",
        "conflict_note": "TEXT DEFAULT ''",
        "dedup_note": "TEXT DEFAULT ''",
        "suggestion_source": "VARCHAR(16) DEFAULT 'llm'",
    }
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(agent_suggestion)")}
            for col, ddl in additions.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE agent_suggestion ADD COLUMN {col} {ddl}")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            for col, ddl in additions.items():
                try:
                    conn.exec_driver_sql(f"ALTER TABLE agent_suggestion ADD COLUMN {col} {ddl}")
                except Exception:  # noqa: BLE001 列已存在
                    pass


def _ensure_hot_money_profile_columns(eng=None) -> None:
    """幂等补齐 hot_money_profile 游资复盘列（win_rate_5d 胜率事实 / last_review_at 迭代时间；
    仅增量加列，不重建表不丢数据；旧数据为 NULL/空串，展示层 .get() 兼容）"""
    eng = eng or engine
    additions = {
        "win_rate_5d": "FLOAT",
        "last_review_at": "VARCHAR(16) DEFAULT ''",
    }
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(hot_money_profile)")}
            for col, ddl in additions.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE hot_money_profile ADD COLUMN {col} {ddl}")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            for col, ddl in additions.items():
                try:
                    conn.exec_driver_sql(f"ALTER TABLE hot_money_profile ADD COLUMN {col} {ddl}")
                except Exception:  # noqa: BLE001 列已存在
                    pass


def _ensure_position_plan_detail(eng=None) -> None:
    """幂等补齐 position_plan.detail 列（v3.0 白盒扩展：dimensions/final_advice/market_regime；
    仅增量加列，不重建表不丢数据；旧数据为 NULL，展示层兼容）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(position_plan)")}
            if "detail" not in existing:
                conn.exec_driver_sql("ALTER TABLE position_plan ADD COLUMN detail JSON")
        else:
            try:
                conn.exec_driver_sql("ALTER TABLE position_plan ADD COLUMN detail JSON")
            except Exception:  # noqa: BLE001 列已存在
                pass


def _ensure_holding_high_price(eng=None) -> None:
    """幂等补齐 holding.high_price 列（移动止盈线基准；仅增量加列，不重建表不丢数据；
    旧数据为 NULL，MonitorAgent 首次取行情时降级以当前价为基准）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(holding)")}
            if "high_price" not in existing:
                conn.exec_driver_sql("ALTER TABLE holding ADD COLUMN high_price FLOAT")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            try:
                conn.exec_driver_sql("ALTER TABLE holding ADD COLUMN high_price FLOAT")
            except Exception:  # noqa: BLE001 列已存在
                pass


def _ensure_alert_log_source(eng=None) -> None:
    """幂等补齐 alert_log.source 列（告警来源标记 monitor/portfolio_sentinel；
    仅增量加列，不重建表不丢数据；旧数据默认 monitor）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(alert_log)")}
            if "source" not in existing:
                conn.exec_driver_sql("ALTER TABLE alert_log ADD COLUMN source VARCHAR(16) DEFAULT 'monitor'")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            try:
                conn.exec_driver_sql("ALTER TABLE alert_log ADD COLUMN source VARCHAR(16) DEFAULT 'monitor'")
            except Exception:  # noqa: BLE001 列已存在
                pass


def _ensure_market_condition_next_day(eng=None) -> None:
    """幂等补齐 market_condition.next_day_index_pct 列（市况次日指数回填，准确率闭环；
    仅增量加列，不重建表不丢数据；旧数据为 NULL=未回填）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market_condition)")}
            if "next_day_index_pct" not in existing:
                conn.exec_driver_sql("ALTER TABLE market_condition ADD COLUMN next_day_index_pct FLOAT")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            try:
                conn.exec_driver_sql("ALTER TABLE market_condition ADD COLUMN next_day_index_pct FLOAT")
            except Exception:  # noqa: BLE001 列已存在
                pass


def _add_factor_scores_column(eng=None) -> None:
    """幂等补齐 candidate_track_verify.factor_scores 列（因子回测校准闭环；
    仅增量加列，不重建表不丢数据；旧数据为 NULL=无因子分诚实留空）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(candidate_track_verify)")}
            if "factor_scores" not in existing:
                conn.exec_driver_sql("ALTER TABLE candidate_track_verify ADD COLUMN factor_scores JSON")
        else:
            # MySQL 8 无 ADD COLUMN IF NOT EXISTS：已存在时报错，忽略即可
            try:
                conn.exec_driver_sql("ALTER TABLE candidate_track_verify ADD COLUMN factor_scores JSON")
            except Exception:  # noqa: BLE001 列已存在
                pass


def get_session() -> Session:
    """FastAPI 依赖：请求级会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
