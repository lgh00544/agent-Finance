# -*- coding: utf-8 -*-
"""
TiDB 云端主库 ↔ 本地 SQLite 冷备 同步管理脚本（项目根，独立于业务代码运行）

架构（已定型，勿改方向）：
- 主库 = 云端 TiDB Serverless（.env DB_BACKEND=mysql，连接参数/密码全部只从 .env 读，本文件零硬编码）
- 本地 SQLite data/dev.db = 定时冷备快照（断网时可改回 DB_BACKEND=sqlite 查最近快照）

命令：
  python sync_manager.py check    → 云端连通性（超时 5s，输出连通/不可达+原因）
  python sync_manager.py init     → 首次：建库+建表（走项目 init_db 逻辑），并把本地 dev.db 全量灌入云端（按唯一键 upsert）
  python sync_manager.py backup   → 定时冷备：备份当前 dev.db 到 backup/（保留最近 10 份），云端全量拉回本地 dev.db
  python sync_manager.py restore  → 用 backup/ 里最近一份快照覆盖 data/dev.db（断网手动回看用）

约束：表名/字段名与现有 ORM 完全一致；所有库操作 try/except，失败打日志不崩；同步前自动备份可回滚。
"""
import logging
import shutil
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))  # 项目自身 import：backend.app.db.*

from sqlalchemy import create_engine, select, UniqueConstraint, PrimaryKeyConstraint  # noqa: E402
from sqlalchemy.dialects.mysql import insert as mysql_insert  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

# 项目配置（.env）与 ORM 元数据：唯一数据源，不手写任何 DDL/表名
from app.core.config import settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.models import Base  # noqa: E402

BACKUP_DIR = PROJECT_DIR / "backup"
LOCAL_DB = PROJECT_DIR / "data" / "dev.db"
BACKUP_KEEP = 10          # 本地快照保留份数
CLOUD_TIMEOUT = 5         # 连通探测超时（秒）

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("sync_manager")


# ==================== 引擎 ====================

def cloud_engine() -> Engine:
    """云端 TiDB 引擎：复用项目 session 的 engine（.env DB_BACKEND=mysql + SSL 已配）。"""
    return db_session.engine


def local_engine() -> Engine:
    """本地 SQLite 引擎（独立构建，不随 DB_BACKEND 变化；WAL 性能参数与项目一致）。"""
    LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{LOCAL_DB}", pool_pre_ping=True)
    from sqlalchemy import event

    @event.listens_for(eng, "connect")
    def _pragmas(dbapi_connection, connection_record):  # noqa: ARG001
        cur = dbapi_connection.cursor()
        # foreign_keys=OFF：本地库在本脚本里是「全表快照替换」语义（先删后插），
        # 外键顺序与批量替换互斥（如 experience 先于 pending_experience），完整性由云端保证
        for stmt in ("PRAGMA journal_mode=WAL", "PRAGMA foreign_keys=OFF",
                     "PRAGMA synchronous=NORMAL", "PRAGMA busy_timeout=5000"):
            cur.execute(stmt)
        cur.close()

    return eng


# ==================== 表清单（与 ORM 完全一致，不擅自改结构） ====================

def all_tables() -> list[str]:
    return sorted(Base.metadata.tables.keys())


def _ordered_tables() -> list[str]:
    """外键依赖拓扑序（父表在前）：先插父表再插子表，避免云端 FK 1452
    （如 experience.source_pending_id → pending_experience.id，字母序会先插子表）。
    循环依赖/未知父表兜底按字母序收尾，不阻塞同步。"""
    parents = {n: {fk.column.table.name for fk in Base.metadata.tables[n].foreign_keys}
               for n in all_tables()}
    ordered: list[str] = []
    remaining = set(all_tables())
    while remaining:
        ready = sorted(n for n in remaining if not (parents[n] & remaining))
        if not ready:
            ready = sorted(remaining)
        ordered.extend(ready)
        remaining -= set(ready)
    return ordered


def table_pk_and_unique(name: str) -> tuple[list[str], list[str]]:
    """返回 (主键列, 首个唯一约束列组)；无唯一约束的表用主键。

    约束判定必须用 isinstance：UniqueConstraint 对象没有 .unique 属性，
    此前 getattr 探测恒为 False → 全部表退化成按主键 upsert；本地历史数据
    含同唯一键多行时（旧 dev.db 建表早于唯一约束上线，SQLite 不迁移旧表），
    TiDB 对多行 INSERT 内重复唯一键直接报 1062（MySQL 则可自行处理）。
    """
    tbl = Base.metadata.tables[name]
    pk = [c.name for c in tbl.primary_key.columns]
    uniqs = []
    for constr in tbl.constraints:
        if isinstance(constr, UniqueConstraint) and not isinstance(constr, PrimaryKeyConstraint):
            cols = [c.name for c in constr.columns]
            uniqs.append(cols)
    return pk, uniqs


# ==================== check ====================

def cmd_check() -> int:
    print(f"云端目标: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
          f" (user={settings.mysql_user})")
    t0 = time.time()
    try:
        eng = cloud_engine()
        with eng.connect() as conn:
            ver = conn.exec_driver_sql("SELECT VERSION()").scalar()
            n = conn.exec_driver_sql("SELECT COUNT(*) FROM information_schema.tables"
                                     " WHERE table_schema = DATABASE()").scalar()
        print(f"[OK] 连通（{time.time() - t0:.1f}s）: 服务器 {ver}")
        print(f"   当前库内表数: {n}")
        return 0
    except Exception as exc:  # noqa: BLE001 探测失败只报告，不崩
        print(f"[FAIL] 不可达: {type(exc).__name__}: {exc}")
        return 1


# ==================== init ====================

def _ensure_database() -> None:
    """建库 stock_agent（纯 pymysql 无库连接；参数全部来自 .env，零硬编码）。"""
    import pymysql

    conn = pymysql.connect(
        host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_root_password,
        connect_timeout=CLOUD_TIMEOUT, charset="utf8mb4",
        ssl={"check_hostname": False, "verify_mode": 0},  # TiDB Serverless 强制 TLS
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}`")
        log.info("数据库已就绪: %s", settings.mysql_database)
    finally:
        conn.close()


def _dedup_by_unique(rows: list[dict], pk: list[str], key_cols: list[str]) -> list[dict]:
    """同批内按唯一键去重，保留 id 最大（最新写入）的一行。

    场景：本地 dev.db 建表早于唯一约束上线（SQLite 不迁移旧表），历史数据
    含同唯一键多行；TiDB 对多行 INSERT 内重复唯一键直接报 1062。按
    「最后一次写入为准」语义取最大 id 行，其余丢弃。
    """
    if not key_cols or len(rows) < 2:
        return rows
    id_col = pk[0] if pk else None
    best: dict[tuple, dict] = {}
    for r in rows:
        k = tuple(r[c] for c in key_cols)
        prev = best.get(k)
        if prev is None or (id_col and (r.get(id_col) or 0) > (prev.get(id_col) or 0)):
            best[k] = r
    return list(best.values())


def _upsert_rows(eng: Engine, name: str, rows: list[dict]) -> int:
    """按唯一键批量 upsert：MySQL/TiDB 方言 INSERT ... ON DUPLICATE KEY UPDATE
    （SQLAlchemy dialects.mysql 内置，非手写 DDL；一次提交全部行，规避海外节点往返延迟）。"""
    if not rows:
        return 0
    tbl = Base.metadata.tables[name]
    pk, uniqs = table_pk_and_unique(name)
    key_cols = uniqs[0] if uniqs else pk
    rows = _dedup_by_unique(rows, pk, key_cols)
    non_key = [c.name for c in tbl.columns
               if c.name not in key_cols and c.name not in pk]
    stmt = mysql_insert(tbl).values(rows)
    if non_key:
        stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_key})
    with eng.begin() as conn:
        conn.execute(stmt)
    return len(rows)


# 历史上模型列宽过窄（SQLite 不校验、TiDB 严格模式拒绝）的兼容修正表：
# {表: {列: 目标宽度}}，init 时幂等 MODIFY（create_all 不改已建表，需显式扩宽一次）
_COLUMN_WIDTH_FIXES = {
    "agent_chat_message": {"role": 16},
    "alert_log": {"source": 32},            # 实际值 portfolio_sentinel=18 > 16
    "batch_adjust": {"rollback_time": 32},  # 实际值含秒（YYYY-MM-DD HH:mm:ss）19 > 16
    "market_intel": {"phase": 128},         # LLM 阶段定性长句 58 > 32
    "review_log": {"action": 32},           # 实际值 strictness_freeze=17 > 16
}


def _ensure_column_widths(eng: Engine) -> None:
    """幂等扩宽云端列：查 information_schema 实际宽度，不足才 ALTER MODIFY。"""
    if not _COLUMN_WIDTH_FIXES:
        return
    for tbl_name, cols in _COLUMN_WIDTH_FIXES.items():
        try:
            with eng.connect() as conn:
                for col, width in cols.items():
                    row = conn.exec_driver_sql(
                        "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.columns"
                        " WHERE table_schema = DATABASE() AND table_name = %s"
                        " AND column_name = %s", (tbl_name, col)).fetchone()
                    if row is not None and row[0] is not None and int(row[0]) < width:
                        conn.exec_driver_sql(
                            f"ALTER TABLE `{tbl_name}` MODIFY `{col}` VARCHAR({width})")
                        log.info("已扩宽 %s.%s -> VARCHAR(%s)", tbl_name, col, width)
        except Exception as exc:  # noqa: BLE001 扩宽失败不阻塞主体
            log.warning("列宽修正 %s.%s 失败（跳过）: %s", tbl_name, col, exc)


def cmd_init() -> int:
    print("== init：建库 → 建表 → 本地数据灌云端 ==")
    _ensure_database()

    # 建表走项目自身 init_db()（create_all + 全部 _ensure_* 增量，幂等；禁手写 DDL）
    try:
        db_session.init_db()
        log.info("云端建表完成（init_db 幂等）")
    except Exception as exc:  # noqa: BLE001
        log.error("建表失败: %s", exc)
        return 1
    _ensure_column_widths(cloud_engine())

    # 读本地 SQLite 全量数据 → 云端 upsert（外键拓扑序：父表先插）
    local = local_engine()
    cloud = cloud_engine()
    print(f"{'表名':<28}{'本地行数':>8}{'灌云行数':>8}  状态")
    total_ok, total_fail = 0, 0
    for name in _ordered_tables():
        try:
            with local.connect() as conn:
                rows = [dict(r._mapping) for r in conn.execute(select(Base.metadata.tables[name]))]
            raw_n = len(rows)
            done = _upsert_rows(cloud, name, rows) if rows else 0
            note = f"（去重 {raw_n - done}）" if done != raw_n else ""
            total_ok += raw_n
            print(f"{name:<28}{raw_n:>8}{done:>8}  [OK]{note}")
        except Exception as exc:  # noqa: BLE001 单表失败不中断
            total_fail += 1
            print(f"{name:<28}{'-':>8}{'-':>8}  [FAIL] {type(exc).__name__}: {str(exc)[:80]}")
    print(f"完成：共灌入 {total_ok} 行（失败表 {total_fail} 张）")
    return 0 if total_fail == 0 else 1


# ==================== backup ====================

def _snapshot_files() -> list[Path]:
    """backup/ 下真实快照（排除 sqlite 附属的 -wal/-shm，它们不是数据库文件）。"""
    return sorted((p for p in BACKUP_DIR.glob("dev.db.*")
                   if not p.name.endswith(("-wal", "-shm"))), reverse=True)


def _snapshot_local_db() -> Path | None:
    """同步前备份当前 dev.db 到 backup/（时间戳命名，保留最近 10 份）。"""
    if not LOCAL_DB.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"dev.db.{stamp}"
    try:
        shutil.copy2(LOCAL_DB, dest)
    except Exception as exc:  # noqa: BLE001
        log.warning("本地备份失败（继续同步）: %s", exc)
        return None
    # 保留最近 BACKUP_KEEP 份（只数真实快照）
    snaps = _snapshot_files()
    for old in snaps[:-BACKUP_KEEP]:
        try:
            old.unlink()
        except OSError:
            pass
    log.info("已备份本地库 -> %s（保留 %d 份）", dest.name, BACKUP_KEEP)
    return dest


def cmd_backup() -> int:
    print("== backup：云端全量 → 本地 SQLite 快照 ==")
    _snapshot_local_db()

    local = local_engine()
    cloud = cloud_engine()
    print(f"{'表名':<28}{'云端行数':>8}{'本地写入':>8}  状态")
    total_ok, total_fail = 0, 0
    for name in _ordered_tables():
        tbl = Base.metadata.tables[name]
        try:
            with cloud.connect() as conn:
                rows = [dict(r._mapping) for r in conn.execute(select(tbl))]
            with local.begin() as conn:
                conn.execute(tbl.delete())  # 快照语义：本地全表替换为云端当前数据
                if rows:
                    conn.execute(tbl.insert(), rows)
            total_ok += len(rows)
            print(f"{name:<28}{len(rows):>8}{len(rows):>8}  [OK]")
        except Exception as exc:  # noqa: BLE001 单表失败不中断
            total_fail += 1
            print(f"{name:<28}{'-':>8}{'-':>8}  [FAIL] {type(exc).__name__}: {str(exc)[:80]}")
    print(f"完成：共写回 {total_ok} 行（失败表 {total_fail} 张）")
    return 0 if total_fail == 0 else 1


# ==================== restore ====================

def cmd_restore() -> int:
    snaps = _snapshot_files()
    if not snaps:
        print("[FAIL] backup/ 下无快照，无法恢复")
        return 1
    src = snaps[0]
    print(f"== restore：用 {src.name} 覆盖 data/dev.db ==")
    try:
        # 覆盖前保留当前库（防误恢复），WAL 附属文件一并清理
        for suf in ("", "-wal", "-shm"):
            p = Path(str(LOCAL_DB) + suf)
            if p.exists():
                shutil.copy2(p, BACKUP_DIR / f"pre_restore_{p.name}") if suf == "" else p.unlink()
        shutil.copy2(src, LOCAL_DB)
        log.info("已恢复: %s（断网查快照后如需回主库，改回 DB_BACKEND=mysql 重启后端）", src.name)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.error("恢复失败: %s", exc)
        return 1


# ==================== 入口 ====================

COMMANDS = {"check": cmd_check, "init": cmd_init, "backup": cmd_backup, "restore": cmd_restore}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    try:
        return COMMANDS[sys.argv[1]]()
    except Exception as exc:  # noqa: BLE001 顶层兜底：任何失败不崩项目
        log.error("执行 %s 失败: %s", sys.argv[1], exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
