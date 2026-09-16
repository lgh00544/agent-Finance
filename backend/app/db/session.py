"""
数据库会话管理：同一套 ORM 模型，默认 SQLite 单文件（data/dev.db，零外部依赖）；
DB_BACKEND=mysql 时切换 MySQL8。业务代码一律通过 repo 网关访问，本模块只被网关使用。
"""
import hashlib
import logging
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)
_LAST_INIT_DB_RESULT: dict = {"status": "not_run"}


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
    db_file = os.environ.get("SQLITE_PATH") or settings.sqlite_path or (data_dir / "dev.db")
    return f"sqlite:///{db_file}"


engine = create_engine(
    _build_engine_url(),
    pool_pre_ping=True,
    echo=False,
)

if settings.db_backend != "mysql":
    event.listen(engine, "connect", _sqlite_pragmas)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _database_identity(eng=engine) -> dict:
    """Return non-sensitive database identity for startup diagnostics."""
    if eng.dialect.name == "sqlite":
        database = str(eng.url.database or "")
        digest = hashlib.sha256(database.encode("utf-8")).hexdigest()[:12]
        return {"backend": "sqlite", "sqlite_path_digest": digest}
    return {"backend": eng.dialect.name, "database": str(eng.url.database or "")}


def get_init_db_result() -> dict:
    """Return a read-only copy of the latest startup migration result."""
    return deepcopy(_LAST_INIT_DB_RESULT)


def _safe_error(exc: BaseException) -> str:
    """Keep startup diagnostics useful without exposing credentials."""
    message = str(exc) or exc.__class__.__name__
    message = re.sub(r"(?i)(mysql(?:\+\w+)?://)[^@\s]+@", r"\1<redacted>@", message)
    message = re.sub(r"(?i)(password|passwd|pwd)=([^&\s]+)", r"\1=<redacted>", message)
    return message


def _is_duplicate_column_error(exc: BaseException) -> bool:
    """Only classify an explicit duplicate-column error as an idempotent hit."""
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
        if len(chain) >= 5:
            break
    text = " ".join(str(item) for item in chain).lower()
    if "duplicate column" in text or "duplicate column name" in text:
        return True
    return any("1060" in str(item) and "column" in str(item).lower() for item in chain)


def _add_column(conn, table: str, column: str, ddl: str) -> str:
    """Add one column and distinguish duplicate-column from real DB failures."""
    statement = f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
    try:
        conn.exec_driver_sql(statement)
        return "added"
    except Exception as exc:  # noqa: BLE001 preserve real migration failures
        if _is_duplicate_column_error(exc):
            logger.debug("数据库迁移列已存在 backend=%s table=%s column=%s",
                         conn.engine.dialect.name, table, column)
            return "existing"
        logger.error("数据库迁移失败 backend=%s table=%s column=%s error=%s",
                     conn.engine.dialect.name, table, column, _safe_error(exc))
        raise


def _add_columns(eng, table: str, additions: dict[str, str]) -> dict:
    """Idempotently add columns and return a small diagnostic summary."""
    result = {"table": table, "added": [], "existing": []}
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            for column, ddl in additions.items():
                if column in existing:
                    result["existing"].append(column)
                else:
                    _add_column(conn, table, column, ddl)
                    result["added"].append(column)
        else:
            for column, ddl in additions.items():
                outcome = _add_column(conn, table, column, ddl)
                result["added" if outcome == "added" else "existing"].append(column)
    return result


def init_db() -> dict:
    """建表（幂等）。prod 模式下容器初始化已有 DDL，此处 create_all 兜底保证结构一致。"""
    from app.db import models  # noqa: F401  确保模型注册

    global _LAST_INIT_DB_RESULT
    identity = _database_identity()
    try:
        Base.metadata.create_all(bind=engine)
        _add_columns(engine, "paper_quote_snapshot", {"snapshot": "JSON NULL"})
        _ensure_experience_fts()
        _ensure_review_result_columns()
        _ensure_agent_preference_columns()
        _ensure_stock_candidate_detail()
        _ensure_trade_record_columns()
        _ensure_agent_suggestion_columns()
        _ensure_position_plan_detail()
        _ensure_position_plan_source()
        _ensure_position_plan_history()
        _ensure_hot_money_profile_columns()
        _ensure_holding_high_price()
        _ensure_alert_log_source()
        _ensure_lhb_multi_source_verified()
        _ensure_forward_view_history()
        _ensure_market_condition_next_day()
        _add_factor_scores_column()
        _ensure_sector_forward_tag()
        _ensure_indexes()
        _ensure_sector_snapshot_table()
        _ensure_quote_snapshot_table()
        _ensure_distribution_phase_table()
        _ensure_capital_view_tables()
        _ensure_identity_tables()
        _ensure_user_identity_columns()
        _ensure_user_columns()
        _ensure_account_pnl_user_index()
        _ensure_reasoning_trace_user_scope()
        experience_ownership = _ensure_experience_audit_user_scope()
        knowledge = _ensure_knowledge_hit_columns()
        experience = _ensure_experience_curator_columns()
    except Exception as exc:  # noqa: BLE001 startup must expose migration failures
        _LAST_INIT_DB_RESULT = {
            "status": "failed",
            **identity,
            "initialized_at": datetime.now().isoformat(timespec="seconds"),
            "error": _safe_error(exc),
        }
        logger.error(
            "数据库初始化/迁移失败 identity=%s error=%s",
            identity,
            _safe_error(exc),
        )
        raise
    _LAST_INIT_DB_RESULT = {
        "status": "ok",
        **identity,
        "initialized_at": datetime.now().isoformat(timespec="seconds"),
        "migrations": {
            "knowledge": knowledge,
            "experience": experience,
            "experience_ownership": experience_ownership,
        },
    }
    logger.info(
        "数据库初始化/迁移完成 backend=%s database=%s knowledge_added=%s "
        "knowledge_existing=%s experience_added=%s experience_existing=%s "
        "experience_ownership_columns_added=%s",
        identity.get("backend"),
        identity.get("database") or identity.get("sqlite_path_digest"),
        len(knowledge["added"]),
        len(knowledge["existing"]),
        len(experience["added"]),
        len(experience["existing"]),
        sum(len(result["added"]) for result in experience_ownership["columns"].values()),
    )
    return _LAST_INIT_DB_RESULT


def _ensure_identity_tables() -> None:
    """创建用户/会话/公共事实表并为历史单用户数据准备默认主体。"""
    from app.db.models import PublicFactSnapshot, User, UserSession
    Base.metadata.create_all(bind=engine, tables=[
        User.__table__, UserSession.__table__, PublicFactSnapshot.__table__,
    ])
    _ensure_user_identity_columns()
    from app.db import repo
    default_id = repo.ensure_default_user()
    _ = default_id


def _ensure_user_identity_columns() -> None:
    """Add optional external identity columns to existing app_user tables."""
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(app_user)")}
            if "feishu_open_id" not in existing:
                _add_column(conn, "app_user", "feishu_open_id", "VARCHAR(128) NULL")
    else:
        _add_columns(engine, "app_user", {"feishu_open_id": "VARCHAR(128) NULL"})


def _ensure_account_pnl_user_index() -> None:
    """Move legacy global PnL snapshot uniqueness to a user-scoped key."""
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            indexes = list(conn.exec_driver_sql("PRAGMA index_list(account_pnl_snapshot)"))
            unique_columns = {
                tuple(row[2] for row in conn.exec_driver_sql(f"PRAGMA index_info({index[1]})"))
                for index in indexes if index[2]
            }
            desired = ("user_id", "trade_date", "ts")
            if desired in unique_columns:
                return
            conn.exec_driver_sql("""
                CREATE TABLE account_pnl_snapshot_scoped (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    trade_date VARCHAR(10) NOT NULL,
                    ts VARCHAR(32) NOT NULL,
                    pnl_yk FLOAT,
                    pnl_pct FLOAT,
                    sh_pct FLOAT,
                    chart_data JSON NOT NULL DEFAULT '[]',
                    source VARCHAR(32) NOT NULL DEFAULT 'ths',
                    error TEXT NOT NULL DEFAULT '',
                    token_expired BOOLEAN NOT NULL DEFAULT 0,
                    updated_at DATETIME NOT NULL,
                    user_id INTEGER,
                    CONSTRAINT uq_account_pnl_user_date_ts
                        UNIQUE (user_id, trade_date, ts)
                )
            """)
            conn.exec_driver_sql("""
                INSERT INTO account_pnl_snapshot_scoped (
                    id, trade_date, ts, pnl_yk, pnl_pct, sh_pct, chart_data,
                    source, error, token_expired, updated_at, user_id
                )
                SELECT id, trade_date, ts, pnl_yk, pnl_pct, sh_pct, chart_data,
                       source, error, token_expired, updated_at, user_id
                FROM account_pnl_snapshot
            """)
            conn.exec_driver_sql("DROP TABLE account_pnl_snapshot")
            conn.exec_driver_sql(
                "ALTER TABLE account_pnl_snapshot_scoped RENAME TO account_pnl_snapshot")
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_account_pnl_snapshot_trade_date "
                "ON account_pnl_snapshot (trade_date)")
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_account_pnl_snapshot_user_id "
                "ON account_pnl_snapshot (user_id)")
        return
    with engine.begin() as conn:
        indexes = list(conn.exec_driver_sql(
            "SHOW INDEX FROM account_pnl_snapshot"))
        names = {str(row[2]) for row in indexes}
        if "uq_account_pnl_date_ts" in names:
            conn.exec_driver_sql(
                "ALTER TABLE account_pnl_snapshot DROP INDEX uq_account_pnl_date_ts")
        if "uq_account_pnl_user_date_ts" not in names:
            conn.exec_driver_sql(
                "ALTER TABLE account_pnl_snapshot ADD UNIQUE KEY "
                "uq_account_pnl_user_date_ts (user_id, trade_date, ts)")


def _ensure_user_columns() -> None:
    """给既有私有表增加可空归属列，并把旧数据归档到默认用户。
    对 account_pnl_snapshot 特判：先删 NULL 行中与已有 user_id 行冲突的（避免回填撞 UNIQUE）。"""
    from app.db import repo
    default_id = repo.ensure_default_user()
    # account_pnl_snapshot 在加 UNIQUE 后，user_id=NULL 的行与 user_id=1 已存在行
    # 在 (user_id, trade_date, ts) 上可能撞约束，必须先清掉这些 NULL 行再回填。
    # 该清理为方言无关的标准 SQL：SQLite 同样会撞 uq_account_pnl_user_date_ts，故不设方言守卫。
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM account_pnl_snapshot WHERE user_id IS NULL "
                 "AND (trade_date, ts) IN ("
                 "  SELECT trade_date, ts FROM account_pnl_snapshot WHERE user_id = :uid"
                 ")"),
            {"uid": default_id},
        )
    tables = (
        "position_plan", "holding", "trade_record", "alert_log", "review_result",
        "agent_preference", "sys_trade_profile", "private_knowledge", "sell_decision",
        "account_baseline", "account_pnl_snapshot", "agent_suggestion", "rule_change",
        "agent_chat_message", "paper_account", "paper_position", "paper_execution",
        "paper_review", "paper_quote_snapshot", "paper_context", "paper_web_evidence",
        "paper_alert", "ai_reasoning_trace", "ai_reasoning_trace_history",
    )
    with engine.begin() as conn:
        for table in tables:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")} \
                if engine.dialect.name == "sqlite" else set()
            if "user_id" not in existing:
                try:
                    _add_column(conn, table, "user_id", "INTEGER NULL")
                except Exception:
                    if engine.dialect.name != "sqlite":
                        raise
            conn.execute(
                text(f"UPDATE {table} SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": default_id},
            )


def _ensure_index(eng, table: str, name: str, columns: tuple[str, ...]) -> str:
    """Create a named index once on SQLite or MySQL without replacing existing data."""
    column_sql = ", ".join(columns)
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            before = {
                str(row[1]) for row in conn.exec_driver_sql(f"PRAGMA index_list({table})")
            }
            conn.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column_sql})")
            return "existing" if name in before else "added"
        existing = {
            str(row[2]) for row in conn.exec_driver_sql(f"SHOW INDEX FROM {table}")
        }
        if name in existing:
            return "existing"
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD INDEX {name} ({column_sql})")
        return "added"


def _ensure_experience_audit_user_scope(eng=None, default_user_id: int | None = None) -> dict:
    """Scope private experience history to one account and retain only explicit system logs.

    Experience records and worker execution history are private.  Review/audit rows
    inherit ownership only from a known private target; rows without such a target
    stay NULL as system scope instead of being exposed as an account record.
    """
    eng = eng or engine
    if default_user_id is None:
        from app.db import repo
        default_user_id = repo.ensure_default_user()

    columns = {
        table: _add_columns(eng, table, {"user_id": "INTEGER NULL"})
        for table in (
            "pending_experience", "experience", "review_log", "worker_run", "audit_log",
        )
    }
    with eng.begin() as conn:
        for table in ("pending_experience", "experience", "worker_run"):
            conn.execute(text(
                f"UPDATE {table} SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": int(default_user_id)},
            )

        # Only experience-linked review rows have a private owner.  System actions
        # without an experience_id deliberately retain NULL ownership.
        conn.execute(text("""
            UPDATE review_log
            SET user_id = (
                SELECT owner_row.user_id
                FROM experience AS owner_row
                WHERE owner_row.id = review_log.experience_id
            )
            WHERE review_log.user_id IS NULL
              AND review_log.experience_id IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM experience AS owner_row
                WHERE owner_row.id = review_log.experience_id
                  AND owner_row.user_id IS NOT NULL
            )
        """))

        # Audit ownership is derived only for supported account-scoped targets.
        # Unknown target types remain system scope and must not inherit a default user.
        for target_type, table in (
            ("agent_suggestion", "agent_suggestion"),
            ("pending_experience", "pending_experience"),
            ("experience", "experience"),
            ("rule_change", "rule_change"),
            ("review_result", "review_result"),
        ):
            conn.execute(text(f"""
                UPDATE audit_log
                SET user_id = (
                    SELECT owner_row.user_id
                    FROM {table} AS owner_row
                    WHERE owner_row.id = audit_log.target_id
                )
                WHERE audit_log.user_id IS NULL
                  AND audit_log.target_type = :target_type
                  AND EXISTS (
                    SELECT 1 FROM {table} AS owner_row
                    WHERE owner_row.id = audit_log.target_id
                      AND owner_row.user_id IS NOT NULL
                  )
            """), {"target_type": target_type})

    index_specs = (
        ("pending_experience", "ix_pending_user_status_id", ("user_id", "status", "id")),
        ("experience", "ix_experience_user_status_stage", ("user_id", "status", "stage")),
        ("experience", "ix_experience_user_stage_id", ("user_id", "stage", "id")),
        ("review_log", "ix_reviewlog_user_exp", ("user_id", "experience_id")),
        ("worker_run", "ix_worker_run_user_status", ("user_id", "status")),
        ("audit_log", "ix_audit_user_target", ("user_id", "target_type", "target_id")),
    )
    indexes = {
        name: _ensure_index(eng, table, name, index_columns)
        for table, name, index_columns in index_specs
    }
    return {"columns": columns, "indexes": indexes}


def _ensure_reasoning_trace_user_scope() -> None:
    """Make decision traces private and include their owner in the upsert key."""
    from app.db import repo

    default_id = repo.ensure_default_user()
    _add_columns(engine, "ai_reasoning_trace_history", {"user_id": "INTEGER NULL"})
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            trace_columns = {row[1] for row in conn.exec_driver_sql(
                "PRAGMA table_info(ai_reasoning_trace)")}
            indexes = list(conn.exec_driver_sql("PRAGMA index_list(ai_reasoning_trace)"))
            unique_columns = {
                tuple(row[2] for row in conn.exec_driver_sql(f"PRAGMA index_info({index[1]})"))
                for index in indexes if index[2]
            }
            desired = ("user_id", "stock_code", "generate_date", "source_module")
            if desired not in unique_columns:
                user_expr = "COALESCE(user_id, :user_id)" if "user_id" in trace_columns else ":user_id"
                conn.exec_driver_sql("""
                    CREATE TABLE ai_reasoning_trace_scoped (
                        trace_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NULL,
                        stock_code VARCHAR(16) NOT NULL,
                        stock_name VARCHAR(64) NOT NULL,
                        source_module VARCHAR(16) NOT NULL,
                        generate_date VARCHAR(10) NOT NULL,
                        fact_basis TEXT NOT NULL,
                        technical_reasoning TEXT NOT NULL,
                        capital_reasoning TEXT NOT NULL,
                        fundamental_reasoning TEXT NOT NULL,
                        risk_reasoning TEXT NOT NULL,
                        rule_refs TEXT NOT NULL,
                        final_conclusion TEXT NOT NULL,
                        confidence FLOAT NOT NULL,
                        data_source VARCHAR(64) NOT NULL,
                        create_time VARCHAR(16) NOT NULL,
                        ext_info TEXT NOT NULL,
                        CONSTRAINT uq_trace_code_date_module
                            UNIQUE (user_id, stock_code, generate_date, source_module)
                    )
                """)
                conn.exec_driver_sql(f"""
                    INSERT INTO ai_reasoning_trace_scoped (
                        trace_id, user_id, stock_code, stock_name, source_module, generate_date,
                        fact_basis, technical_reasoning, capital_reasoning, fundamental_reasoning,
                        risk_reasoning, rule_refs, final_conclusion, confidence, data_source,
                        create_time, ext_info
                    )
                    SELECT trace_id, {user_expr}, stock_code, stock_name, source_module, generate_date,
                           fact_basis, technical_reasoning, capital_reasoning, fundamental_reasoning,
                           risk_reasoning, rule_refs, final_conclusion, confidence, data_source,
                           create_time, ext_info
                    FROM ai_reasoning_trace
                """, {"user_id": default_id})
                conn.exec_driver_sql("DROP TABLE ai_reasoning_trace")
                conn.exec_driver_sql("ALTER TABLE ai_reasoning_trace_scoped RENAME TO ai_reasoning_trace")
            elif "user_id" not in trace_columns:
                _add_column(conn, "ai_reasoning_trace", "user_id", "INTEGER NULL")
            conn.execute(text(
                "UPDATE ai_reasoning_trace SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": default_id})
            conn.execute(text(
                "UPDATE ai_reasoning_trace_history SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": default_id})
            for statement in (
                "CREATE INDEX IF NOT EXISTS ix_ai_reasoning_trace_user_id ON ai_reasoning_trace (user_id)",
                "CREATE INDEX IF NOT EXISTS ix_ai_reasoning_trace_stock_code ON ai_reasoning_trace (stock_code)",
                "CREATE INDEX IF NOT EXISTS ix_ai_reasoning_trace_source_module ON ai_reasoning_trace (source_module)",
                "CREATE INDEX IF NOT EXISTS ix_ai_reasoning_trace_generate_date ON ai_reasoning_trace (generate_date)",
                "CREATE INDEX IF NOT EXISTS ix_trace_user_module_date ON ai_reasoning_trace (user_id, source_module, generate_date)",
                "CREATE INDEX IF NOT EXISTS ix_ai_reasoning_trace_history_user_id ON ai_reasoning_trace_history (user_id)",
                "CREATE INDEX IF NOT EXISTS ix_trace_history_user_code_date_module ON ai_reasoning_trace_history (user_id, stock_code, generate_date, source_module)",
                "CREATE INDEX IF NOT EXISTS ix_trace_history_recorded_at ON ai_reasoning_trace_history (recorded_at)",
            ):
                conn.exec_driver_sql(statement)
        return

    _add_columns(engine, "ai_reasoning_trace", {"user_id": "INTEGER NULL"})
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE ai_reasoning_trace SET user_id = :user_id WHERE user_id IS NULL",
        ), {"user_id": default_id})
        conn.execute(text(
            "UPDATE ai_reasoning_trace_history SET user_id = :user_id WHERE user_id IS NULL",
        ), {"user_id": default_id})
        rows = list(conn.exec_driver_sql("SHOW INDEX FROM ai_reasoning_trace"))
        index_columns: dict[str, list[tuple[int, str]]] = {}
        for row in rows:
            index_columns.setdefault(str(row[2]), []).append((int(row[3]), str(row[4])))
        current_key = tuple(column for _, column in sorted(
            index_columns.get("uq_trace_code_date_module", [])))
        desired_key = ("user_id", "stock_code", "generate_date", "source_module")
        if current_key != desired_key:
            if "uq_trace_code_date_module" in index_columns:
                conn.exec_driver_sql("ALTER TABLE ai_reasoning_trace DROP INDEX uq_trace_code_date_module")
            conn.exec_driver_sql("ALTER TABLE ai_reasoning_trace ADD UNIQUE KEY "
                                 "uq_trace_code_date_module "
                                 "(user_id, stock_code, generate_date, source_module)")


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


def _ensure_sector_snapshot_table() -> None:
    """幂等补建 sector_snapshot 表（首页板块快照；create_all 兜底 SQLite/MySQL 通吃）"""
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine, tables=[models.SectorSnapshot.__table__])


def _ensure_quote_snapshot_table() -> None:
    """幂等补建 quote_snapshot 表（持仓实时价快照；create_all 兜底 SQLite/MySQL 通吃）"""
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine, tables=[models.QuoteSnapshot.__table__])


def _ensure_distribution_phase_table() -> None:
    """幂等补建 distribution_phase_log 表（派发期判定；create_all 兜底 SQLite/MySQL 通吃）"""
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine, tables=[models.DistributionPhaseLog.__table__])


def _ensure_capital_view_tables() -> None:
    """幂等补建资本视图 4 表（capital_actor/dragon_tiger/capital_flow/capital_stats；
    批次E 游资真接入；create_all 兜底 SQLite/MySQL 通吃）"""
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine, tables=[
        models.CapitalActor.__table__, models.DragonTiger.__table__,
        models.CapitalFlow.__table__, models.CapitalStats.__table__,
    ])


def _ensure_stock_candidate_detail(eng=None) -> None:
    """幂等补齐 stock_candidate.detail 列（v2.0 输出详情；仅增量加列，不重建表不丢数据）"""
    eng = eng or engine
    _add_columns(eng, "stock_candidate", {"detail": "JSON"})


def _ensure_review_result_columns(eng=None) -> None:
    """幂等补齐 review_result 建议驳回迭代列（仅增量加列，不重建表不丢数据）"""
    eng = eng or engine
    additions = {
        "suggest_status": "VARCHAR(16) DEFAULT 'pending'",
        "reject_reason": "TEXT DEFAULT ''",
        "suggest_iteration": "INTEGER DEFAULT 1",
        "suggest_history": "JSON",
    }
    _add_columns(eng, "review_result", additions)


def _ensure_agent_preference_columns(eng=None) -> None:
    """幂等补齐 agent_preference 审核状态列；历史偏好默认 active，避免升级后失效。"""
    eng = eng or engine
    _add_columns(eng, "agent_preference", {"status": "VARCHAR(16) DEFAULT 'active'"})


def _ensure_knowledge_hit_columns(eng=None) -> dict:
    """幂等补齐 private_knowledge 命中计量与治理元数据列。
    仅增量加列，不重建表不丢数据；历史知识默认 active。"""
    eng = eng or engine
    text_default = "TEXT NOT NULL DEFAULT ''" if eng.dialect.name == "sqlite" else "TEXT"
    additions = {
        "hit_count": "INTEGER NOT NULL DEFAULT 0",
        "last_used_at": "DATETIME",
        "source_type": "VARCHAR(16) NOT NULL DEFAULT 'manual'",
        "methodology_type": "VARCHAR(16) NOT NULL DEFAULT 'general'",
        "market_scope": "VARCHAR(16) NOT NULL DEFAULT 'all'",
        "scenario_tags": "JSON",
        "evidence_level": "VARCHAR(16) NOT NULL DEFAULT 'unverified'",
        "valid_from": "DATETIME",
        "valid_to": "DATETIME",
        "status": "VARCHAR(16) NOT NULL DEFAULT 'active'",
        "risk_note": text_default,
    }
    return _add_columns(eng, "private_knowledge", additions)


def _ensure_experience_curator_columns(eng=None) -> dict:
    """幂等补齐 experience 命中计量与策展字段；只增量加列，不删除旧记忆。"""
    eng = eng or engine
    text_default = "TEXT NOT NULL DEFAULT ''" if eng.dialect.name == "sqlite" else "TEXT"
    additions = {
        "hit_count": "INTEGER NOT NULL DEFAULT 0",
        "last_used_at": "DATETIME",
        "expires_at": "DATETIME",
        "curator_note": text_default,
    }
    return _add_columns(eng, "experience", additions)


def _ensure_trade_record_columns(eng=None) -> None:
    """幂等补齐 trade_record.before/after_shares 列（手动操作前后持仓变化留痕，K223；
    仅增量加列，不重建表不丢数据；旧数据为 NULL，展示层兼容）"""
    eng = eng or engine
    additions = {
        "before_shares": "INTEGER",
        "after_shares": "INTEGER",
    }
    _add_columns(eng, "trade_record", additions)


def _ensure_position_plan_source(eng=None) -> None:
    """幂等补齐 position_plan.source 列（计划来源标记 candidate/manual；
    仅增量加列，不重建表不丢数据；旧数据默认 manual）"""
    eng = eng or engine
    _add_columns(eng, "position_plan", {"source": "VARCHAR(16) DEFAULT 'manual'"})


def _ensure_position_plan_history(eng=None) -> None:
    """幂等补齐 position_plan 替代链字段，不删除既有计划。"""
    eng = eng or engine
    _add_columns(eng, "position_plan", {"supersedes_id": "INTEGER"})


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
        "audit_verdict": "VARCHAR(8) DEFAULT 'pending'",
        "audit_round": "INTEGER DEFAULT 0",
        "last_audit_id": "INTEGER NULL",
    }
    _add_columns(eng, "agent_suggestion", additions)


def _ensure_hot_money_profile_columns(eng=None) -> None:
    """幂等补齐 hot_money_profile 游资复盘列（win_rate_5d 胜率事实 / last_review_at 迭代时间；
    仅增量加列，不重建表不丢数据；旧数据为 NULL/空串，展示层 .get() 兼容）"""
    eng = eng or engine
    additions = {
        "win_rate_5d": "FLOAT",
        "last_review_at": "VARCHAR(16) DEFAULT ''",
    }
    _add_columns(eng, "hot_money_profile", additions)


def _ensure_position_plan_detail(eng=None) -> None:
    """幂等补齐 position_plan.detail 列（v3.0 白盒扩展：dimensions/final_advice/market_regime；
    仅增量加列，不重建表不丢数据；旧数据为 NULL，展示层兼容）"""
    eng = eng or engine
    _add_columns(eng, "position_plan", {"detail": "JSON"})


def _ensure_holding_high_price(eng=None) -> None:
    """幂等补齐 holding.high_price 列（移动止盈线基准；仅增量加列，不重建表不丢数据；
    旧数据为 NULL，MonitorAgent 首次取行情时降级以当前价为基准）"""
    eng = eng or engine
    _add_columns(eng, "holding", {"high_price": "FLOAT"})


def _ensure_alert_log_source(eng=None) -> None:
    """幂等补齐 alert_log.source 列（告警来源标记 monitor/portfolio_sentinel；
    仅增量加列，不重建表不丢数据；旧数据默认 monitor）"""
    eng = eng or engine
    _add_columns(eng, "alert_log", {"source": "VARCHAR(16) DEFAULT 'monitor'"})


def _ensure_lhb_multi_source_verified(eng=None) -> None:
    """幂等补齐 lhb_original_flow.multi_source_verified 列（第二源上榜确认采信标记；
    仅增量加列，不重建表不丢数据；旧数据默认 False）"""
    eng = eng or engine
    _add_columns(eng, "lhb_original_flow", {"multi_source_verified": "BOOLEAN DEFAULT 0"})


def _ensure_forward_view_history(eng=None) -> None:
    """幂等建 forward_view_history 表（预测性选股 2.5 前瞻回填闭环；
    复用模型元数据 create(checkfirst=True)，无手写 DDL；已存在则跳过）"""
    from app.db.models import ForwardViewHistory

    eng = eng or engine
    ForwardViewHistory.__table__.create(bind=eng, checkfirst=True)


def _ensure_market_condition_next_day(eng=None) -> None:
    """幂等补齐 market_condition.next_day_index_pct 列（市况次日指数回填，准确率闭环；
    仅增量加列，不重建表不丢数据；旧数据为 NULL=未回填）"""
    eng = eng or engine
    _add_columns(eng, "market_condition", {"next_day_index_pct": "FLOAT"})


def _ensure_sector_forward_tag(eng=None) -> None:
    """幂等补齐 sector_forward_forecast.sector_tag 列（老数据默认 none）。"""
    eng = eng or engine
    _add_columns(eng, "sector_forward_forecast", {
        "sector_tag": "VARCHAR(16) NOT NULL DEFAULT 'none'",
    })


def _add_factor_scores_column(eng=None) -> None:
    """幂等补齐 candidate_track_verify.factor_scores 列（因子回测校准闭环；
    仅增量加列，不重建表不丢数据；旧数据为 NULL=无因子分诚实留空）"""
    eng = eng or engine
    _add_columns(eng, "candidate_track_verify", {"factor_scores": "JSON"})


def get_session() -> Session:
    """FastAPI 依赖：请求级会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
