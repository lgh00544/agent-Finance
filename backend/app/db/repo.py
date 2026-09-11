"""
数据仓库层：Agent 落库/读取的统一入口（幂等 upsert）
【刚性代码逻辑】只做数据存取，不含任何市场判断。
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import pandas as pd

from sqlalchemy import and_, delete, func, or_, select, text, update

from app.cache import cache
from app.core.config import settings
from app.db.models import (
    AccountBaseline, AccountPnlSnapshot, AgentPreference, AgentSuggestion, AiReasoningTrace,
    AiReasoningTraceHistory, AlertLog,
    AuditLog,
    BatchAdjust, CandidateAdjust, CandidateTrackVerify, CandidateTradeable,
    CapitalActor, CapitalFlow, CapitalStats, DragonTiger,
    Experience, ExperienceConfig, ForwardViewHistory, Holding, HotMoneyProfile,
    LhbOriginalFlow, MarketCondition, MarketIntel, NewsArticle, PendingExperience,
    PositionPlan, PrivateKnowledge, KnowledgeShadowHit, QuoteSnapshot, ReviewLog, ReviewResult, RuleChange,
    PaperAccount, PaperPosition, PaperExecution, PaperReview, PaperQuoteSnapshot,
    PaperContext, PaperWebEvidence, PaperAlert,
    SectorSnapshot, SectorDailySnapshot, SectorDailyRankLog, SectorLaunchReason,
    SectorDictV1, SectorForwardForecast, SectorForecastVerify, SectorNextHot,
    SectorNewsAIInterpret, SectorNewsArticle, SectorNewsFeedback, SectorNewsShadowVerify,
    SectorRegimeForecast,
    SellDecision, StockCandidate, StockScore, TradeProfile,
    TradeRecord, WorkerRun, _now, DistributionPhaseLog, User, UserSession,
    PublicFactSnapshot,
)
from app.db.session import SessionLocal
from app.services import reasoning_trace, task_queue

logger = logging.getLogger(__name__)


def _experience_scope_user(user_id: int | None = None, *, for_write: bool = False) -> int | None:
    """Resolve private experience owner; multi-user calls fail closed without context."""
    if user_id is not None:
        return int(user_id)
    try:
        from app.core.auth import current_user_id
        current = current_user_id()
    except Exception:
        current = None
    if current is not None:
        return int(current)
    if settings.multi_user_enabled:
        raise RuntimeError("experience data requires an authenticated user context")
    return 1 if for_write else None


def _json(value: Any) -> Any:
    return value if value is not None else None


# ==================== 多人身份与公共事实 ====================

def ensure_default_user() -> int:
    """幂等创建旧单用户兼容主体并回填其 id。"""
    from app.core.auth import hash_password
    with SessionLocal() as db:
        row = db.execute(select(User).where(User.id == 1)).scalar_one_or_none()
        if row is None:
            if settings.multi_user_enabled and not settings.auth_default_password:
                raise RuntimeError("多人模式禁止使用空默认密码，请设置 AUTH_DEFAULT_PASSWORD")
            row = User(id=1, username=settings.auth_default_username,
                       password_hash=hash_password(settings.auth_default_password or "legacy"),
                       role="admin")
            db.add(row)
            db.commit()
            db.refresh(row)
        return row.id


def create_user(username: str, password: str, role: str = "researcher") -> dict:
    if role not in {"admin", "researcher", "viewer"}:
        raise ValueError("角色仅支持 admin/researcher/viewer")
    from app.core.auth import hash_password
    with SessionLocal() as db:
        if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
            raise ValueError("用户名已存在")
        row = User(username=username.strip(), password_hash=hash_password(password),
                   role=role, is_active=True)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "username": row.username, "role": row.role,
                "is_active": row.is_active, "feishu_open_id": row.feishu_open_id}


def get_user_by_credentials(username: str, password: str) -> dict | None:
    from app.core.auth import verify_password
    with SessionLocal() as db:
        row = db.execute(select(User).where(User.username == username.strip(),
                                             User.is_active.is_(True))).scalar_one_or_none()
        if row is None or not verify_password(password, row.password_hash):
            return None
        return {"id": row.id, "username": row.username, "role": row.role,
                "is_active": row.is_active, "feishu_open_id": row.feishu_open_id}


def get_user_by_feishu_open_id(open_id: str) -> dict | None:
    """Resolve a Feishu sender to an application user without trusting message payloads."""
    if not open_id:
        return None
    with SessionLocal() as db:
        row = db.execute(select(User).where(
            User.feishu_open_id == open_id, User.is_active.is_(True)
        )).scalar_one_or_none()
        if row is None:
            return None
        return {"id": row.id, "username": row.username, "role": row.role,
                "is_active": row.is_active, "feishu_open_id": row.feishu_open_id}


def bind_user_feishu_open_id(user_id: int, open_id: str) -> bool:
    """Bind one Feishu open_id to one user; duplicate bindings are rejected."""
    if not open_id:
        raise ValueError("open_id 不能为空")
    with SessionLocal() as db:
        row = db.get(User, user_id)
        if row is None:
            return False
        other = db.execute(select(User).where(
            User.feishu_open_id == open_id, User.id != user_id
        )).scalar_one_or_none()
        if other is not None:
            raise ValueError("open_id 已绑定其他用户")
        row.feishu_open_id = open_id
        db.commit()
        return True


def list_active_users() -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(User).where(User.is_active.is_(True)).order_by(User.id)).scalars().all()
        return [{"id": r.id, "username": r.username, "role": r.role,
                 "is_active": r.is_active, "feishu_open_id": r.feishu_open_id}
                for r in rows]


def create_user_session(user_id: int, token: str, expires_at: datetime) -> int:
    with SessionLocal() as db:
        row = UserSession(user_id=user_id,
                          token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                          expires_at=expires_at)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_user_by_token(token: str) -> dict | None:
    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with SessionLocal() as db:
        row = db.execute(
            select(User, UserSession).join(UserSession, UserSession.user_id == User.id).where(
                UserSession.token_hash == digest, UserSession.revoked_at.is_(None),
                UserSession.expires_at > _now(), User.is_active.is_(True))
        ).first()
        if row is None:
            return None
        user, _session = row
        return {"id": user.id, "username": user.username, "role": user.role,
                "is_active": user.is_active}


def upsert_public_fact(fact_type: str, source: str, symbol: str, fact_as_of: str,
                       payload: dict, content_hash: str | None = None) -> dict:
    digest = content_hash or hashlib.sha256(
        json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    with SessionLocal() as db:
        row = db.execute(select(PublicFactSnapshot).where(
            PublicFactSnapshot.source == source, PublicFactSnapshot.symbol == symbol,
            PublicFactSnapshot.fact_as_of == fact_as_of,
            PublicFactSnapshot.content_hash == digest)).scalar_one_or_none()
        if row is None:
            row = PublicFactSnapshot(fact_type=fact_type, source=source, symbol=symbol,
                                     fact_as_of=fact_as_of, content_hash=digest,
                                     payload=payload or {})
            db.add(row)
            db.commit()
            db.refresh(row)
        return {"id": row.id, "fact_type": row.fact_type, "source": row.source,
                "symbol": row.symbol, "fact_as_of": row.fact_as_of,
                "content_hash": row.content_hash, "payload": row.payload or {}}


def list_public_facts(symbol: str | None = None, fact_type: str | None = None,
                      limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(PublicFactSnapshot).order_by(PublicFactSnapshot.id.desc())
        if symbol:
            stmt = stmt.where(PublicFactSnapshot.symbol == symbol)
        if fact_type:
            stmt = stmt.where(PublicFactSnapshot.fact_type == fact_type)
        rows = db.execute(stmt.limit(max(1, min(limit, 1000)))).scalars().all()
        return [{"id": r.id, "fact_type": r.fact_type, "source": r.source,
                 "symbol": r.symbol, "fact_as_of": r.fact_as_of,
                 "content_hash": r.content_hash, "payload": r.payload or {},
                 "created_at": str(r.created_at)} for r in rows]


# ==================== 高频读结果缓存（TTL 短缓存，写操作自动失效） ====================

def _dbq(table: str, params: dict, loader: Callable[[], list]) -> list:
    """列表查询 60 秒结果缓存：TTL 内相同参数不落库，直接复用上次结果。
    写操作（_invalidate）删除该表命名空间全部缓存，保证数据一致性。
    防缓存穿透：loader 异常或返回 None 时不写缓存，直接抛出/返回。"""
    if settings.db_query_cache_ttl <= 0:
        return loader()
    digest = hashlib.md5(
        json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    key = f"dbq:{table}:{digest}"
    raw = cache.get(key)
    if raw is not None:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    result = loader()
    if result is None:  # 异常值不缓存，避免缓存穿透
        return result
    cache.set(key, json.dumps(result, ensure_ascii=False, default=str),
              settings.db_query_cache_ttl)
    return result


def _invalidate(table: str) -> None:
    """写操作后失效该表全部读缓存（按命名空间批量删除）"""
    if settings.db_query_cache_ttl > 0:
        cache.delete_prefix(f"dbq:{table}:")


def _context_user_id(default: int | None = None) -> int | None:
    try:
        from app.core.auth import current_user_id
        return current_user_id() or default
    except Exception:
        return default


def upsert_candidate(stock_code: str, stock_name: str, trade_date: str, rank: int,
                     reasons: list, risk_notice: list, snapshot: dict,
                     detail: dict | None = None) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(StockCandidate).where(
                StockCandidate.stock_code == stock_code, StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = StockCandidate(stock_code=stock_code, stock_name=stock_name, trade_date=trade_date)
            db.add(row)
        row.rank, row.reasons, row.risk_notice, row.snapshot = rank, reasons, risk_notice, snapshot
        if detail is not None:
            row.detail = detail
        row.created_at = _now()  # 覆盖更新：同日同股以最新执行时间为准（前端去重取最大）
        task_queue.guarded_commit(db)
        _invalidate("candidate")
        # 推理留痕（异步批量写，零阻塞）：discover 结论=候选理由+风险初判+detail 结构字段
        reasoning_trace.trace_candidate(stock_code, stock_name, trade_date, reasons,
                                        risk_notice, snapshot, detail or {}, row.created_at)


def get_candidate_detail(stock_code: str, trade_date: str) -> dict:
    """读候选 detail（只读，幂等）。供 discover 终选构造 detail 时做防御式 merge：
    在 {**existing, **new_detail} 中保留旧字段（confidence_tier/final_advice/dimensions/enriched 等），
    防止整 dict 覆盖丢键。无记录返回 {}。"""
    with SessionLocal() as db:
        row = db.execute(
            select(StockCandidate.detail).where(
                StockCandidate.stock_code == stock_code, StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        return (row or {}) or {}


def replace_day_candidates(codes: set[str], trade_date: str) -> int:
    """当日候选池快照替换：删除当日不在本次执行结果中的残留候选（不残留历史版本）。
    返回删除条数；仅删除 stock_code 不在 codes 中的记录，本次执行产物保留。"""
    with SessionLocal() as db:
        rows = db.execute(
            select(StockCandidate).where(StockCandidate.trade_date == trade_date)
        ).scalars().all()
        removed = 0
        for row in rows:
            if row.stock_code not in codes:
                db.delete(row)
                removed += 1
        if removed:
            task_queue.guarded_commit(db)
            _invalidate("candidate")
        return removed


def get_candidate_snapshot(stock_code: str, trade_date: str) -> dict | None:
    """某候选当日行情快照（现价判定用；只读 snapshot 列，不影响候选列表契约）"""
    with SessionLocal() as db:
        row = db.execute(
            select(StockCandidate).where(
                StockCandidate.stock_code == stock_code,
                StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        return dict(row.snapshot or {}) if row else None


def get_candidate_context(stock_code: str, trade_date: str) -> dict | None:
    """候选标的选股上下文（ScoreAgent 交叉验证用；只读 detail + reasons，不影响候选列表契约）
    返回 {reasons, confidence_tier, focus_type, final_advice}；无候选记录返回 None"""
    with SessionLocal() as db:
        row = db.execute(
            select(StockCandidate).where(
                StockCandidate.stock_code == stock_code,
                StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            return None
        detail = row.detail or {}
        return {
            "reasons": row.reasons or [],
            "confidence_tier": detail.get("confidence_tier", ""),
            "focus_type": detail.get("focus_type", ""),
            "final_advice": detail.get("final_advice", ""),
        }


# ==================== 市况评分（v2.0 Discover 前置步骤） ====================

def upsert_market_condition(trade_date: str, total_score: int, dims: dict,
                            cap: int, summary: str,
                            next_day_index_pct: float | None = None) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(MarketCondition).where(MarketCondition.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = MarketCondition(trade_date=trade_date)
            db.add(row)
        row.total_score, row.dims, row.cap, row.summary = total_score, dims, cap, summary
        # 防覆盖：仅在参数非 None 才写入，重跑 upsert 不抹掉已回填的次日指数
        if next_day_index_pct is not None:
            row.next_day_index_pct = next_day_index_pct
        db.commit()


def update_market_condition_next_day(trade_date: str, pct: float) -> None:
    """写入 market_condition 某日期的次日沪深300涨跌%（回填链路用；按 trade_date 匹配行，
    幂等由回填侧查询条件 next_day_index_pct IS NULL 保证，本函数不做条件判断）"""
    with SessionLocal() as db:
        row = db.execute(
            select(MarketCondition).where(MarketCondition.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            return
        row.next_day_index_pct = pct
        db.commit()


def get_latest_market_condition() -> dict | None:
    """最新一日市况评分（首页「今日操作提示」数据源）"""
    from app.core.config import market_band_info

    with SessionLocal() as db:
        row = db.execute(
            select(MarketCondition).order_by(MarketCondition.trade_date.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        cap, band, *_ = market_band_info(row.total_score)
        return {"trade_date": row.trade_date, "total_score": row.total_score,
                "band": band, "cap": row.cap, "dims": row.dims,
                "summary": row.summary, "created_at": str(row.created_at)}


def get_prev_market_condition() -> dict | None:
    """上一期市况评分（倒序第二条；表空/仅一条 → 返回 None，调用方对应维度跳过不报错）。
    用于市况切换检测：与 get_latest_market_condition 各自取最近两条，不假设两表同日对齐。"""
    from app.core.config import market_band_info

    with SessionLocal() as db:
        rows = db.execute(
            select(MarketCondition).order_by(MarketCondition.trade_date.desc()).limit(2)
        ).scalars().all()
        if len(rows) < 2:
            return None
        row = rows[1]
        cap, band, *_ = market_band_info(row.total_score)
        return {"trade_date": row.trade_date, "total_score": row.total_score,
                "band": band, "cap": row.cap, "dims": row.dims,
                "summary": row.summary, "created_at": str(row.created_at)}


def upsert_sector_snapshot(rows: list[dict]) -> int:
    """upsert 板块快照（trade_date+sector_name 唯一键冲突时全量覆盖）

    rows 每项字段：trade_date/sector_name/change_pct/leading_stock_name/
                   leading_stock_code/source/rank_no
    返回成功写入行数。
    单次最多 5 条，按 trade_date 一次性「删后插」简单稳，不做 ORM merge。
    """
    if not rows:
        return 0
    trade_date = rows[0].get("trade_date", "")
    if not trade_date:
        return 0
    with SessionLocal() as db:
        # 按 trade_date 全删后插（5 条小数据，简单稳，避免按行 upsert 循环）
        db.execute(
            text("DELETE FROM sector_snapshot WHERE trade_date = :d"),
            {"d": trade_date},
        )
        for r in rows:
            db.add(SectorSnapshot(
                trade_date=r["trade_date"],
                sector_name=r["sector_name"],
                change_pct=r["change_pct"],
                leading_stock_name=r.get("leading_stock_name", ""),
                leading_stock_code=r.get("leading_stock_code", ""),
                source=r.get("source", ""),
                rank_no=r["rank_no"],
            ))
        db.commit()
    return len(rows)


def list_sector_snapshot_by_date(trade_date: str, limit: int = 5) -> list[dict]:
    """按交易日取板块快照（按 rank_no 升序），首页热路径 O(limit)"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorSnapshot)
            .where(SectorSnapshot.trade_date == trade_date)
            .order_by(SectorSnapshot.rank_no.asc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "board_name": r.sector_name,
                "change_pct": r.change_pct,
                "leading_stock": r.leading_stock_name,
                "leading_code": r.leading_stock_code,
                "rank_no": r.rank_no,
                "source": r.source,
            }
            for r in result
        ]


def get_sector_snapshot_updated_at(trade_date: str) -> str | None:
    """取该交易日最近一次更新时间（用于判断是否 stale，格式 YYYY-MM-DD HH:MM:SS）"""
    with SessionLocal() as db:
        row = db.execute(
            select(SectorSnapshot.updated_at)
            .where(SectorSnapshot.trade_date == trade_date)
            .order_by(SectorSnapshot.updated_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        return str(row) if row is not None else None


# ==================== 板块轮动·全板块日快照（sector_daily_snapshot） ====================

def upsert_sector_daily_snapshot(rows: list[dict]) -> int:
    """全板块日快照删后插（trade_date 全删当日覆盖，简单稳，不做 ORM merge）。
    rows 每项字段：trade_date/sector_name/change_pct/rank_no/up_count/down_count/
                   volume_ratio/turnover_rate/leading_stock_name/leading_stock_code/
                   leading_chg/source；返回写入行数。"""
    if not rows:
        return 0
    trade_date = rows[0].get("trade_date", "")
    if not trade_date:
        return 0
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM sector_daily_snapshot WHERE trade_date = :d"),
            {"d": trade_date},
        )
        for r in rows:
            db.add(SectorDailySnapshot(
                trade_date=r["trade_date"],
                sector_name=r["sector_name"],
                change_pct=r["change_pct"],
                rank_no=r["rank_no"],
                up_count=r.get("up_count"),
                down_count=r.get("down_count"),
                volume_ratio=r.get("volume_ratio"),
                turnover_rate=r.get("turnover_rate"),
                leading_stock_name=r.get("leading_stock_name", ""),
                leading_stock_code=r.get("leading_stock_code", ""),
                leading_chg=r.get("leading_chg"),
                source=r.get("source", "em"),
            ))
        db.commit()
    return len(rows)


def list_sector_daily_by_date(trade_date: str) -> list[dict]:
    """按交易日取全板块日快照（rank_no 升序），批次 B 轮动判定输入"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorDailySnapshot)
            .where(SectorDailySnapshot.trade_date == trade_date)
            .order_by(SectorDailySnapshot.rank_no.asc())
        ).scalars().all()
        return [
            {
                "trade_date": r.trade_date,
                "sector_name": r.sector_name,
                "change_pct": r.change_pct,
                "rank_no": r.rank_no,
                "up_count": r.up_count,
                "down_count": r.down_count,
                "volume_ratio": r.volume_ratio,
                "turnover_rate": r.turnover_rate,
                "leading_stock_name": r.leading_stock_name,
                "leading_stock_code": r.leading_stock_code,
                "leading_chg": r.leading_chg,
                "source": r.source,
            }
            for r in result
        ]


def list_sector_daily_history(sector_name: str, days: int) -> list[dict]:
    """按板块名取近 N 日快照（trade_date 升序），批次 B streak 连续居前判定"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorDailySnapshot)
            .where(SectorDailySnapshot.sector_name == sector_name)
            .order_by(SectorDailySnapshot.trade_date.desc())
            .limit(days)
        ).scalars().all()
        return [
            {"trade_date": r.trade_date, "rank_no": r.rank_no,
             "change_pct": r.change_pct, "sector_name": r.sector_name}
            for r in reversed(result)
        ]


def list_sector_daily_dates(limit: int = 60) -> list[str]:
    """取有全板块快照的交易日（trade_date 降序），批次 B 取「昨日 top5」必要管道"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorDailySnapshot.trade_date)
            .distinct()
            .order_by(SectorDailySnapshot.trade_date.desc())
            .limit(limit)
        ).scalars().all()
        return list(result)


# ==================== 板块轮动·轮动指标快照（sector_daily_rank_log） ====================

def upsert_sector_rank_log(row: dict) -> int:
    """轮动指标快照删后插（trade_date 唯一，当日最后一次覆盖）。
    row 字段：trade_date/rotation_state/churn_rate/top5_overlap/mainline_sector/notes"""
    if not row or not row.get("trade_date"):
        return 0
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM sector_daily_rank_log WHERE trade_date = :d"),
            {"d": row["trade_date"]},
        )
        db.add(SectorDailyRankLog(
            trade_date=row["trade_date"],
            rotation_state=row.get("rotation_state", ""),
            churn_rate=row.get("churn_rate"),
            top5_overlap=row.get("top5_overlap"),
            mainline_sector=row.get("mainline_sector"),
            notes=row.get("notes", ""),
        ))
        db.commit()
    return 1


def get_sector_rank_log(trade_date: str) -> dict | None:
    """按交易日取轮动指标快照（无 → None）"""
    with SessionLocal() as db:
        r = db.execute(
            select(SectorDailyRankLog)
            .where(SectorDailyRankLog.trade_date == trade_date)
        ).scalars().first()
        if r is None:
            return None
        return {"trade_date": r.trade_date, "rotation_state": r.rotation_state,
                "churn_rate": r.churn_rate, "top5_overlap": r.top5_overlap,
                "mainline_sector": r.mainline_sector, "notes": r.notes}


def list_sector_launch_by_date(trade_date: str) -> list[dict]:
    """按交易日取启动归因（rank_no 升序）；reason_chain JSON 串解析为 list 返回"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorLaunchReason)
            .where(SectorLaunchReason.trade_date == trade_date)
            .order_by(SectorLaunchReason.rank_no.asc())
        ).scalars().all()
        out = []
        for r in result:
            chain = None
            if r.reason_chain:
                try:
                    chain = json.loads(r.reason_chain)
                except (TypeError, ValueError):
                    chain = None
            out.append({
                "trade_date": r.trade_date, "sector_name": r.sector_name,
                "rank_no": r.rank_no, "reason_tags": r.reason_tags,
                "reason_text": r.reason_text, "reason_chain": chain,
                "evidence": r.evidence or {}, "confidence": r.confidence,
            })
        return out


def upsert_sector_regime_forecast(row: dict) -> int:
    """行情结构预测删后插（trade_date 唯一，当日最后一次覆盖）。"""
    if not row or not row.get("trade_date"):
        return 0
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM sector_regime_forecast WHERE trade_date = :d"),
            {"d": row["trade_date"]},
        )
        db.add(SectorRegimeForecast(
            trade_date=row["trade_date"],
            current_regime=row.get("current_regime", "chaos"),
            regime_stage=row.get("regime_stage", "unknown"),
            regime_confidence=row.get("regime_confidence"),
            forward_bias_t1=row.get("forward_bias_t1", "uncertain"),
            forward_bias_t3=row.get("forward_bias_t3", "uncertain"),
            forward_bias_t5=row.get("forward_bias_t5", "uncertain"),
            evidence=row.get("evidence") or {},
            notes=row.get("notes", ""),
        ))
        db.commit()
    return 1


def get_sector_regime_forecast(trade_date: str) -> dict | None:
    """读取指定交易日行情结构预测。"""
    with SessionLocal() as db:
        r = db.execute(
            select(SectorRegimeForecast)
            .where(SectorRegimeForecast.trade_date == trade_date)
        ).scalars().first()
        if r is None:
            return None
        return {
            "trade_date": r.trade_date,
            "current_regime": r.current_regime,
            "regime_stage": r.regime_stage,
            "regime_confidence": r.regime_confidence,
            "forward_bias_t1": r.forward_bias_t1,
            "forward_bias_t3": r.forward_bias_t3,
            "forward_bias_t5": r.forward_bias_t5,
            "evidence": r.evidence or {},
            "notes": r.notes,
        }


def upsert_sector_forward_forecast(rows: list[dict]) -> int:
    """板块前瞻删后插（trade_date 全量覆盖，板块+窗口唯一）。"""
    if not rows or not rows[0].get("trade_date"):
        return 0
    trade_date = rows[0]["trade_date"]
    with SessionLocal() as db:
        db.execute(text("DELETE FROM sector_forward_forecast WHERE trade_date = :d"),
                   {"d": trade_date})
        for row in rows:
            db.add(SectorForwardForecast(
                trade_date=trade_date,
                sector_name=row["sector_name"],
                rank_no=row["rank_no"],
                stage=row.get("stage", "unknown"),
                continuation_prob=row.get("continuation_prob"),
                exhaustion_risk=row.get("exhaustion_risk"),
                chase_risk=row.get("chase_risk"),
                switch_candidate=bool(row.get("switch_candidate", False)),
                regime=row.get("regime", "unknown"),
                forward_bias=row.get("forward_bias", "uncertain"),
                forecast_horizon=row.get("forecast_horizon", "t1"),
                sector_tag=row.get("sector_tag", "none"),
                evidence=row.get("evidence") or {},
            ))
        db.commit()
    return len(rows)


def list_sector_forward_forecast(trade_date: str) -> list[dict]:
    """读取指定日期板块前瞻，按窗口、排名升序。"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorForwardForecast)
            .where(SectorForwardForecast.trade_date == trade_date)
            .order_by(SectorForwardForecast.forecast_horizon.asc(),
                      SectorForwardForecast.rank_no.asc())
        ).scalars().all()
        return [{
            "trade_date": r.trade_date, "sector_name": r.sector_name,
            "rank_no": r.rank_no, "stage": r.stage,
            "continuation_prob": r.continuation_prob,
            "exhaustion_risk": r.exhaustion_risk, "chase_risk": r.chase_risk,
            "switch_candidate": bool(r.switch_candidate), "regime": r.regime,
            "forward_bias": r.forward_bias, "forecast_horizon": r.forecast_horizon,
            "sector_tag": r.sector_tag,
            "evidence": r.evidence or {},
        } for r in result]


def upsert_sector_next_hot(rows: list[dict], trade_date: str | None = None) -> int:
    """下一个风口预测删后插（trade_date 全量覆盖）。"""
    trade_date = trade_date or (rows[0].get("trade_date") if rows else None)
    if not trade_date:
        return 0
    with SessionLocal() as db:
        db.execute(text("DELETE FROM sector_next_hot WHERE trade_date = :d"),
                   {"d": trade_date})
        for row in rows:
            db.add(SectorNextHot(
                trade_date=trade_date,
                sector_name=row["sector_name"],
                rank_no=row["rank_no"],
                hot_score=row["hot_score"],
                expected_horizon_days=row["expected_horizon_days"],
                confidence=row["confidence"],
                trigger_evidence=row.get("trigger_evidence") or {},
            ))
        db.commit()
    return len(rows)


def list_sector_next_hot_by_date(trade_date: str, limit: int = 5) -> list[dict]:
    """读取指定日期下一个风口候选，按 hot_score 降序。"""
    with SessionLocal() as db:
        result = db.execute(
            select(SectorNextHot)
            .where(SectorNextHot.trade_date == trade_date)
            .order_by(SectorNextHot.hot_score.desc())
            .limit(limit)
        ).scalars().all()
        return [{
            "trade_date": r.trade_date,
            "sector_name": r.sector_name,
            "rank_no": r.rank_no,
            "hot_score": r.hot_score,
            "expected_horizon_days": r.expected_horizon_days,
            "confidence": r.confidence,
            "trigger_evidence": r.trigger_evidence or {},
        } for r in result]


def upsert_sector_forecast_verify(rows: list[dict]) -> int:
    """前瞻验证删后插（forecast_date + horizon 唯一）。"""
    if not rows:
        return 0
    with SessionLocal() as db:
        for row in rows:
            db.execute(
                text("DELETE FROM sector_forecast_verify "
                     "WHERE forecast_date = :d AND verify_horizon = :h"),
                {"d": row["forecast_date"], "h": row["verify_horizon"]},
            )
            db.add(SectorForecastVerify(
                forecast_date=row["forecast_date"],
                verify_horizon=row["verify_horizon"],
                verify_date=row.get("verify_date"),
                regime_hit=row.get("regime_hit"),
                top5_continue_rate=row.get("top5_continue_rate"),
                mainline_hit=row.get("mainline_hit"),
                regime_forecast=row.get("regime_forecast"),
                miss_reason=row.get("miss_reason", ""),
                detail=row.get("detail") or {},
            ))
        db.commit()
    return len(rows)


def list_sector_forecast_verify(start_date: str | None = None,
                                end_date: str | None = None) -> list[dict]:
    """读取前瞻验证结果，供准确率统计只读聚合。"""
    with SessionLocal() as db:
        stmt = select(SectorForecastVerify)
        if start_date:
            stmt = stmt.where(SectorForecastVerify.forecast_date >= start_date)
        if end_date:
            stmt = stmt.where(SectorForecastVerify.forecast_date <= end_date)
        result = db.execute(
            stmt.order_by(SectorForecastVerify.forecast_date.desc(),
                          SectorForecastVerify.verify_horizon.asc())
        ).scalars().all()
        return [{
            "forecast_date": r.forecast_date,
            "verify_horizon": r.verify_horizon,
            "verify_date": r.verify_date,
            "regime_hit": r.regime_hit,
            "top5_continue_rate": r.top5_continue_rate,
            "mainline_hit": r.mainline_hit,
            "regime_forecast": r.regime_forecast,
            "miss_reason": r.miss_reason,
            "detail": r.detail or {},
        } for r in result]


# ==================== 行业消息雷达（观察型 shadow，不进入正式 Agent） ====================

def upsert_sector_dict(rows: list[dict]) -> int:
    """幂等补行业字典；只做人工种子落库，反馈/LLM 不走这里自动改字典。"""
    inserted = 0
    with SessionLocal() as db:
        for r in rows:
            code = str(r.get("sector_code") or "").strip()
            version = str(r.get("version") or "v1")
            if not code:
                continue
            exists = db.execute(select(SectorDictV1.id).where(
                SectorDictV1.sector_code == code,
                SectorDictV1.version == version)).first()
            if exists:
                continue
            db.add(SectorDictV1(
                sector_code=code, sector_name=str(r.get("sector_name") or code),
                aliases=r.get("aliases") or [],
                entity_keywords=r.get("entity_keywords") or [],
                industry_keywords=r.get("industry_keywords") or [],
                version=version, source=str(r.get("source") or "manual"),
                review_status=str(r.get("review_status") or "active"),
                reviewed_by=str(r.get("reviewed_by") or "sir"),
                effective_from=str(r.get("effective_from") or ""),
                effective_to=str(r.get("effective_to") or "")))
            inserted += 1
        db.commit()
    return inserted


def list_sector_dict(active_only: bool = True) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(SectorDictV1).order_by(SectorDictV1.sector_name.asc())
        if active_only:
            stmt = stmt.where(SectorDictV1.review_status == "active")
        rows = db.execute(stmt).scalars().all()
    return [{
        "id": r.id, "sector_code": r.sector_code, "sector_name": r.sector_name,
        "aliases": r.aliases or [], "entity_keywords": r.entity_keywords or [],
        "industry_keywords": r.industry_keywords or [], "version": r.version,
        "source": r.source, "review_status": r.review_status,
        "reviewed_by": r.reviewed_by, "effective_from": r.effective_from,
        "effective_to": r.effective_to, "created_at": str(r.created_at)[:19],
    } for r in rows]


def add_sector_news_article(row: dict) -> tuple[int, bool]:
    content_hash = str(row.get("content_hash") or "").strip()
    if not content_hash:
        raise ValueError("content_hash required")
    with SessionLocal() as db:
        existing = db.execute(select(SectorNewsArticle).where(
            SectorNewsArticle.content_hash == content_hash)).scalars().first()
        if existing:
            return existing.id, False
        rec = SectorNewsArticle(
            source_scope=str(row.get("source_scope") or "company_signal"),
            source_type=str(row.get("source_type") or "company_news"),
            source_name=str(row.get("source_name") or ""),
            external_id=str(row.get("external_id") or ""),
            title=str(row.get("title") or ""),
            content=str(row.get("content") or ""),
            source_url=str(row.get("source_url") or ""),
            published_at=str(row.get("published_at") or ""),
            content_hash=content_hash,
            sector_codes=row.get("sector_codes") or [],
            stock_codes=row.get("stock_codes") or [],
            mapping_method=str(row.get("mapping_method") or "unmapped"),
            mapping_confidence=float(row.get("mapping_confidence") or 0.0),
            status=str(row.get("status") or "accepted"))
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec.id, True


def get_sector_news_articles(article_ids: list[int]) -> list[dict]:
    if not article_ids:
        return []
    with SessionLocal() as db:
        rows = db.execute(select(SectorNewsArticle).where(
            SectorNewsArticle.id.in_([int(i) for i in article_ids]))).scalars().all()
    return [_sector_news_article_dict(r) for r in rows]


def list_sector_news_articles(sector_code: str = "", days: int = 7,
                              status: str | None = None, date: str = "") -> list[dict]:
    with SessionLocal() as db:
        stmt = select(SectorNewsArticle)
        if date:
            day = datetime.strptime(date[:10], "%Y-%m-%d")
            stmt = stmt.where(SectorNewsArticle.created_at >= day,
                              SectorNewsArticle.created_at < day + timedelta(days=1))
        else:
            cutoff = datetime.now() - timedelta(days=max(1, min(int(days or 7), 30)))
            stmt = stmt.where(SectorNewsArticle.created_at >= cutoff)
        if status:
            stmt = stmt.where(SectorNewsArticle.status == status)
        rows = db.execute(stmt.order_by(SectorNewsArticle.created_at.desc())).scalars().all()
    out = [_sector_news_article_dict(r) for r in rows]
    if sector_code:
        out = [r for r in out if sector_code in (r.get("sector_codes") or [])]
    return out


def add_sector_news_interpret(row: dict) -> int:
    with SessionLocal() as db:
        rec = SectorNewsAIInterpret(
            article_ids=row.get("article_ids") or [],
            sector_codes=row.get("sector_codes") or [],
            polarity=str(row.get("polarity") or "uncertain"),
            summary=str(row.get("summary") or ""),
            impact_mechanism=str(row.get("impact_mechanism") or ""),
            impact_horizon=str(row.get("impact_horizon") or "unknown"),
            information_score=float(row.get("information_score") or 0.0),
            direction_confidence=float(row.get("direction_confidence") or 0.0),
            quote_evidence=row.get("quote_evidence") or [],
            affected_stock_codes=row.get("affected_stock_codes") or [],
            stock_relation_basis=str(row.get("stock_relation_basis") or ""),
            human_review_required=bool(row.get("human_review_required")),
            validator_status=str(row.get("validator_status") or "pending"),
            model_version=str(row.get("model_version") or ""))
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec.id


def get_sector_news_interpret(interpret_id: int) -> dict | None:
    with SessionLocal() as db:
        row = db.get(SectorNewsAIInterpret, int(interpret_id))
        return _sector_interpret_dict(row) if row is not None else None


def add_sector_news_shadow(row: dict) -> int:
    interpret_id = int(row.get("interpret_id") or 0)
    if not interpret_id:
        raise ValueError("interpret_id required")
    with SessionLocal() as db:
        existing = db.execute(select(SectorNewsShadowVerify).where(
            SectorNewsShadowVerify.interpret_id == interpret_id)).scalars().first()
        if existing:
            return existing.id
        rec = SectorNewsShadowVerify(
            interpret_id=interpret_id, sector_code=str(row.get("sector_code") or ""),
            sector_name=str(row.get("sector_name") or ""),
            signal_date=str(row.get("signal_date") or time.strftime("%Y-%m-%d")),
            base_index_value=row.get("base_index_value"))
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec.id


def list_sector_shadow_pending(limit: int = 200) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(SectorNewsShadowVerify).where(
            or_(SectorNewsShadowVerify.t1_return.is_(None),
                SectorNewsShadowVerify.t3_return.is_(None),
                SectorNewsShadowVerify.t5_return.is_(None))
        ).order_by(SectorNewsShadowVerify.signal_date.asc()).limit(limit)).scalars().all()
    return [_sector_shadow_dict(r) for r in rows]


def update_sector_shadow(verify_id: int, values: dict) -> bool:
    allowed = {"base_index_value", "t1_return", "t3_return", "t5_return",
               "t1_at", "t3_at", "t5_at", "direction_correct"}
    payload = {k: v for k, v in values.items() if k in allowed}
    if not payload:
        return False
    with SessionLocal() as db:
        row = db.get(SectorNewsShadowVerify, int(verify_id))
        if row is None:
            return False
        for k, v in payload.items():
            setattr(row, k, v)
        db.commit()
        return True


def add_sector_news_feedback(row: dict) -> int:
    with SessionLocal() as db:
        rec = SectorNewsFeedback(
            article_id=row.get("article_id"), interpret_id=row.get("interpret_id"),
            feedback_type=str(row.get("feedback_type") or "dismiss"),
            reason=str(row.get("reason") or ""),
            reviewer=str(row.get("reviewer") or "sir"),
            status="pending")
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec.id


def list_sector_radar(sector_code: str = "", days: int = 7,
                      date: str = "", source_scope: str = "") -> dict:
    articles = list_sector_news_articles(sector_code, days, date=date)
    if source_scope:
        articles = [a for a in articles if a.get("source_scope") == source_scope]
    with SessionLocal() as db:
        interprets = db.execute(select(SectorNewsAIInterpret).order_by(
            SectorNewsAIInterpret.created_at.desc())).scalars().all()
        shadows = db.execute(select(SectorNewsShadowVerify)).scalars().all()
    shadow_by_iid = {s.interpret_id: _sector_shadow_dict(s) for s in shadows}
    out = []
    for article in articles:
        inter = next((i for i in interprets if article["id"] in (i.article_ids or [])), None)
        item = {"article": article, "interpret": None, "shadow": None}
        if inter is not None:
            item["interpret"] = _sector_interpret_dict(inter)
            item["shadow"] = shadow_by_iid.get(inter.id)
        out.append(item)
    return {"items": out, "sectors": list_sector_dict(), "total": len(out)}


def _sector_news_article_dict(r: SectorNewsArticle) -> dict:
    return {
        "id": r.id, "source_scope": r.source_scope, "source_type": r.source_type,
        "source_name": r.source_name, "external_id": r.external_id, "title": r.title,
        "content": r.content, "source_url": r.source_url, "published_at": r.published_at,
        "fetched_at": str(r.fetched_at)[:19], "content_hash": r.content_hash,
        "sector_codes": r.sector_codes or [], "stock_codes": r.stock_codes or [],
        "mapping_method": r.mapping_method, "mapping_confidence": r.mapping_confidence,
        "status": r.status, "created_at": str(r.created_at)[:19],
    }


def _sector_interpret_dict(r: SectorNewsAIInterpret) -> dict:
    return {
        "id": r.id, "article_ids": r.article_ids or [], "sector_codes": r.sector_codes or [],
        "polarity": r.polarity, "summary": r.summary,
        "impact_mechanism": r.impact_mechanism, "impact_horizon": r.impact_horizon,
        "information_score": r.information_score, "direction_confidence": r.direction_confidence,
        "quote_evidence": r.quote_evidence or [], "affected_stock_codes": r.affected_stock_codes or [],
        "stock_relation_basis": r.stock_relation_basis,
        "human_review_required": r.human_review_required,
        "validator_status": r.validator_status, "model_version": r.model_version,
        "created_at": str(r.created_at)[:19],
    }


def _sector_shadow_dict(r: SectorNewsShadowVerify) -> dict:
    return {
        "id": r.id, "interpret_id": r.interpret_id, "sector_code": r.sector_code,
        "sector_name": r.sector_name, "signal_date": r.signal_date,
        "base_index_value": r.base_index_value, "t1_return": r.t1_return,
        "t3_return": r.t3_return, "t5_return": r.t5_return,
        "t1_at": r.t1_at, "t3_at": r.t3_at, "t5_at": r.t5_at,
        "direction_correct": r.direction_correct, "created_at": str(r.created_at)[:19],
    }


# ==================== 持仓实时价快照（quote_snapshot，持仓监控页 DB 兜底） ====================

def upsert_quote_snapshot(rows: list[dict]) -> int:
    """整表清除后批量插入持仓价快照（行数小，删后插简单稳，仿 upsert_sector_snapshot）
    rows 每项字段：stock_code/name/price/change_pct/source/updated_at；返回写入行数。"""
    if not rows:
        return 0
    with SessionLocal() as db:
        db.execute(text("DELETE FROM quote_snapshot"))
        for r in rows:
            db.add(QuoteSnapshot(
                stock_code=r["stock_code"],
                name=r.get("name", ""),
                price=r.get("price", 0.0),
                change_pct=r.get("change_pct"),
                source=r.get("source", ""),
                updated_at=_parse_ts(r.get("updated_at")),
            ))
        db.commit()
    for r in rows:
        upsert_public_fact(
            "quote", str(r.get("source") or "quote_snapshot"),
            str(r.get("stock_code") or ""), str(r.get("updated_at") or _now()),
            {"stock_code": r.get("stock_code"), "name": r.get("name", ""),
             "price": r.get("price", 0.0), "change_pct": r.get("change_pct"),
             "source": r.get("source", "")},
        )
    return len(rows)


def _parse_ts(value) -> datetime:
    """updated_at 容错：datetime 直通；'YYYY-MM-DD HH:MM:SS' 字符串转 datetime；异常回落 now()"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now()


def get_quote_snapshot(within_minutes: int = 10) -> pd.DataFrame | None:
    """读 updated_at 在 N 分钟内的持仓价快照（DB 兜底二级）。

    返回 DataFrame（code/name/price/change_pct/source）；表空或全部过期返回 None
    （调用方走下一级全市场快照兜底）。首页热路径 O(rows) 秒回，无外部请求。"""
    cutoff = datetime.now() - timedelta(minutes=within_minutes)
    with SessionLocal() as db:
        rows = db.execute(
            select(QuoteSnapshot).where(QuoteSnapshot.updated_at >= cutoff)
        ).scalars().all()
    if not rows:
        return None
    return pd.DataFrame([
        {"code": r.stock_code, "name": r.name, "price": r.price,
         "change_pct": r.change_pct, "source": r.source}
        for r in rows
    ])


def upsert_distribution_phase(trade_date: str, symbol: str, phase: int, phase_label: str,
                              confidence: str, six_dim: dict, missing_data: list) -> None:
    """派发期判定结果幂等落库（(trade_date, symbol) 唯一键冲突时覆盖）"""
    with SessionLocal() as db:
        row = db.execute(
            select(DistributionPhaseLog).where(
                DistributionPhaseLog.trade_date == trade_date,
                DistributionPhaseLog.symbol == symbol)
        ).scalar_one_or_none()
        if row is None:
            row = DistributionPhaseLog(trade_date=trade_date, symbol=symbol)
            db.add(row)
        row.phase, row.phase_label, row.confidence = phase, phase_label, confidence
        row.six_dim, row.missing_data = six_dim or {}, missing_data or []
        row.updated_at = _now()
        db.commit()


# ==================== 市场研判底座（market_intel，每日收盘后 1 次 + 手动入口） ====================

def upsert_market_intel(trade_date: str, phase: str, core_conflict: str, risk_appetite: str,
                        volume_signal: dict, operative_meaning: dict, next_day_watch: dict,
                        summary: str, raw: dict) -> None:
    """当日市场研判落库（code 唯一幂等覆盖；只新增，不迁移不改旧表）"""
    with SessionLocal() as db:
        row = db.execute(
            select(MarketIntel).where(MarketIntel.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = MarketIntel(trade_date=trade_date)
            db.add(row)
        row.phase, row.core_conflict, row.risk_appetite = phase, core_conflict, risk_appetite
        row.volume_signal, row.operative_meaning, row.next_day_watch = (
            volume_signal, operative_meaning, next_day_watch)
        row.summary, row.raw = summary, raw
        db.commit()


def get_market_intel(trade_date: str) -> dict | None:
    """当日市场研判（含全部字段，供页面/共享注入）"""
    with SessionLocal() as db:
        row = db.execute(
            select(MarketIntel).where(MarketIntel.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {"trade_date": row.trade_date, "phase": row.phase,
                "core_conflict": row.core_conflict, "risk_appetite": row.risk_appetite,
                "volume_signal": row.volume_signal or {},
                "operative_meaning": row.operative_meaning or {},
                "next_day_watch": row.next_day_watch or {},
                "summary": row.summary, "raw": row.raw or {},
                "created_at": str(row.created_at)}


def get_latest_market_intel() -> dict | None:
    """最新一日市场研判（供 agent 共享注入：当日不存在时回退最近一日）"""
    with SessionLocal() as db:
        row = db.execute(
            select(MarketIntel).order_by(MarketIntel.trade_date.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {"trade_date": row.trade_date, "phase": row.phase,
                "core_conflict": row.core_conflict, "risk_appetite": row.risk_appetite,
                "volume_signal": row.volume_signal or {},
                "operative_meaning": row.operative_meaning or {},
                "next_day_watch": row.next_day_watch or {},
                "summary": row.summary, "raw": row.raw or {},
                "created_at": str(row.created_at)}


def list_market_intel_dates(limit: int = 30) -> list[str]:
    """已生成研判的日期列表（页面选日期用，最新在前）"""
    with SessionLocal() as db:
        return list(db.execute(
            select(MarketIntel.trade_date).distinct()
            .order_by(MarketIntel.trade_date.desc()).limit(limit)).scalars().all())


# ==================== 候选池可建仓标记（每日落库·历史可追溯） ====================

def upsert_candidate_tradeable(stock_code: str, stock_name: str, trade_date: str, tier: str,
                               is_tradeable: int, label: str, plan_exists: int, price_zone: str,
                               current_price: float | None, cond_grade: int, cond_price: int,
                               cond_risk: int, block_reason: str, detail: dict) -> None:
    """按 code+date 幂等 upsert 当日可建仓判定（覆盖更新，口径见 services/candidate_tradeable.py）"""
    with SessionLocal() as db:
        row = db.execute(
            select(CandidateTradeable).where(
                CandidateTradeable.stock_code == stock_code,
                CandidateTradeable.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = CandidateTradeable(stock_code=stock_code, stock_name=stock_name,
                                     trade_date=trade_date)
            db.add(row)
        row.tier, row.is_tradeable, row.label = tier, is_tradeable, label
        row.plan_exists, row.price_zone, row.current_price = plan_exists, price_zone, current_price
        row.cond_grade, row.cond_price, row.cond_risk = cond_grade, cond_price, cond_risk
        row.block_reason, row.detail = block_reason, detail
        task_queue.guarded_commit(db)
        _invalidate("tradeable")


def list_candidate_tradeable(trade_date: str | None = None, limit: int = 200) -> list[dict]:
    """当日/任意日期可建仓判定行（最新在前；历史可追溯查询）"""

    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(CandidateTradeable).order_by(CandidateTradeable.id.desc())
            if trade_date:
                stmt = stmt.where(CandidateTradeable.trade_date == trade_date)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                     "trade_date": r.trade_date, "tier": r.tier,
                     "is_tradeable": r.is_tradeable, "label": r.label,
                     "plan_exists": r.plan_exists, "price_zone": r.price_zone,
                     "current_price": r.current_price, "cond_grade": r.cond_grade,
                     "cond_price": r.cond_price, "cond_risk": r.cond_risk,
                     "block_reason": r.block_reason, "detail": r.detail or {},
                     "created_at": str(r.created_at)} for r in rows]

    return _dbq("tradeable", {"date": trade_date, "limit": limit}, _load)


def has_tradeable_rows(trade_date: str) -> bool:
    """当日是否已有可建仓判定落库（无则需懒补算）"""
    with SessionLocal() as db:
        row = db.execute(
            select(CandidateTradeable.id).where(
                CandidateTradeable.trade_date == trade_date).limit(1)
        ).scalar_one_or_none()
        return row is not None


# ==================== 候选评级/标签人工覆盖（批量对话确认生效·可回滚） ====================

def list_candidate_adjusts(trade_date: str | None = None) -> list[dict]:
    """当日人工覆盖记录（effective_tier 判定用）"""
    with SessionLocal() as db:
        stmt = select(CandidateAdjust)
        if trade_date:
            stmt = stmt.where(CandidateAdjust.trade_date == trade_date)
        rows = db.execute(stmt).scalars().all()
        return [{"stock_code": r.stock_code, "stock_name": r.stock_name,
                 "trade_date": r.trade_date, "tier_override": r.tier_override,
                 "label_override": r.label_override, "reason": r.reason,
                 "operator": r.operator, "created_at": str(r.created_at)} for r in rows]


def upsert_candidate_adjust(stock_code: str, stock_name: str, trade_date: str,
                            tier_override: str, label_override: str, reason: str,
                            operator: str = "") -> None:
    """写入/更新覆盖（幂等）；回滚即删除该行恢复原判定"""
    with SessionLocal() as db:
        row = db.execute(
            select(CandidateAdjust).where(
                CandidateAdjust.stock_code == stock_code,
                CandidateAdjust.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = CandidateAdjust(stock_code=stock_code, stock_name=stock_name,
                                  trade_date=trade_date)
            db.add(row)
        row.tier_override, row.label_override = tier_override, label_override
        row.reason, row.operator = reason, operator
        db.commit()
        _invalidate("tradeable")


def delete_candidate_adjust(stock_code: str, trade_date: str) -> bool:
    """回滚：删除覆盖记录恢复原判定"""
    with SessionLocal() as db:
        row = db.execute(
            select(CandidateAdjust).where(
                CandidateAdjust.stock_code == stock_code,
                CandidateAdjust.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        _invalidate("tradeable")
        return True


# ==================== 批量对话调整留痕（pending→applied→rolled_back） ====================

def add_batch_adjust(scope: str, scope_codes: list, question: str, trade_date: str,
                     adjust_plan: list, before_snapshot: dict,
                     chat_user_msg_id: int, operator: str = "") -> int:
    with SessionLocal() as db:
        row = BatchAdjust(scope=scope, scope_codes=scope_codes, question=question,
                          trade_date=trade_date, adjust_plan=adjust_plan,
                          before_snapshot=before_snapshot, after_snapshot={},
                          status="pending", operator=operator,
                          chat_user_msg_id=chat_user_msg_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_batch_adjust(batch_id: int) -> dict | None:
    with SessionLocal() as db:
        r = db.get(BatchAdjust, batch_id)
        if r is None:
            return None
        return {"id": r.id, "scope": r.scope, "scope_codes": r.scope_codes,
                "question": r.question, "trade_date": r.trade_date,
                "adjust_plan": r.adjust_plan, "before_snapshot": r.before_snapshot,
                "after_snapshot": r.after_snapshot, "status": r.status,
                "rollback_reason": r.rollback_reason, "rollback_time": r.rollback_time,
                "operator": r.operator, "chat_user_msg_id": r.chat_user_msg_id,
                "created_at": str(r.created_at)}


def update_batch_adjust_status(batch_id: int, status: str, after_snapshot: dict | None = None,
                               rollback_reason: str = "", rollback_time: str = "") -> None:
    with SessionLocal() as db:
        row = db.get(BatchAdjust, batch_id)
        if row is None:
            return
        row.status = status
        if after_snapshot is not None:
            row.after_snapshot = after_snapshot
        if rollback_reason:
            row.rollback_reason = rollback_reason
        if rollback_time:
            row.rollback_time = rollback_time
        db.commit()


def list_batch_adjusts(limit: int = 50) -> list[dict]:
    """批量调整记录（最新在前，供追溯）"""
    with SessionLocal() as db:
        rows = db.execute(
            select(BatchAdjust).order_by(BatchAdjust.id.desc()).limit(limit)).scalars().all()
        return [{"id": r.id, "scope": r.scope, "scope_codes": r.scope_codes,
                 "question": r.question, "trade_date": r.trade_date,
                 "adjust_plan": r.adjust_plan, "status": r.status,
                 "rollback_reason": r.rollback_reason, "rollback_time": r.rollback_time,
                 "operator": r.operator, "created_at": str(r.created_at)} for r in rows]


def upsert_score(stock_code: str, stock_name: str, trade_date: str, score: float,
                 grade: str, detail: dict, risk_list: list,
                 thinking_summary: tuple[str, str] | None = None) -> None:
    """业务表存干净 detail；agentic thinking 只透传 trace（thinking_summary=(model_thinking, tool_trace)）。"""
    with SessionLocal() as db:
        row = db.execute(
            select(StockScore).where(
                StockScore.stock_code == stock_code, StockScore.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = StockScore(stock_code=stock_code, stock_name=stock_name, trade_date=trade_date)
            db.add(row)
        row.score, row.grade, row.detail, row.risk_list = score, grade, detail, risk_list
        task_queue.guarded_commit(db)
        _invalidate("score")
        # 推理留痕：score 五维分项研判（dimensions[].comment 按维度归入技术/资金/基本面）
        # thinking 仅注入 trace 副本，绝不进业务表 detail
        trace_ctx = dict(detail)
        if thinking_summary:
            trace_ctx["model_thinking"], trace_ctx["tool_trace"] = thinking_summary
        reasoning_trace.trace_score(stock_code, stock_name, trade_date,
                                    score, grade, trace_ctx, risk_list)


def insert_plan(stock_code: str, stock_name: str, plan_date: str, total_pct: float,
                batches: list, stop_loss: float, take_profit: float, rationale: str,
                detail: dict | None = None, source: str = "manual",
                user_id: int | None = None) -> int:
    """detail: v3.0 白盒扩展（dimensions/final_advice/market_regime/freshness/quant），可选；
    旧调用零影响。同一标的同一交易日追加新版本，旧的 proposed 版本标记 superseded；
    已采纳版本保留原状态。source: candidate=每日候选池联动 / manual=手动生成。"""
    if user_id is None:
        try:
            from app.core.auth import current_user_id
            user_id = current_user_id() or 1
        except Exception:
            user_id = 1
    with SessionLocal() as db:
        stmt = (select(PositionPlan).where(
            PositionPlan.stock_code == stock_code, PositionPlan.plan_date == plan_date)
                .order_by(PositionPlan.id.desc()))
        stmt = stmt.where(PositionPlan.user_id == user_id)
        previous = db.execute(stmt).scalars().all()
        previous_id = previous[0].id if previous else None
        for old in previous:
            if old.status == "proposed":
                old.status = "superseded"
        row = PositionPlan(stock_code=stock_code, stock_name=stock_name, plan_date=plan_date,
                           total_pct=total_pct, batches=batches, stop_loss=stop_loss,
                           take_profit=take_profit, rationale=rationale, detail=detail,
                           source=source if source in ("candidate", "manual") else "manual",
                           supersedes_id=previous_id, user_id=user_id)
        db.add(row)
        task_queue.guarded_commit(db)
        db.refresh(row)
        _invalidate("plan")
        # 推理留痕：position 分批区间/止损止盈/总仓 + 建仓逻辑说明 + v3.0 维度归因
        reasoning_trace.trace_plan(stock_code, stock_name, plan_date, total_pct,
                                   batches, stop_loss, take_profit, rationale, row.id,
                                   detail=detail)
        return row.id


def insert_alert(stock_code: str, stock_name: str, alert_type: str, severity: str,
                 message: str, action: str, signal: dict, pushed: bool,
                 source: str = "monitor", extra: dict | None = None,
                 user_id: int | None = None) -> int:
    """写告警日志；source 标记来源（monitor/portfolio_sentinel）。extra=thinking 摘要，仅进 trace_alert.ext_info，
    业务表 signal 保持干净。默认 None 零行为。"""
    with SessionLocal() as db:
        row = AlertLog(stock_code=stock_code, stock_name=stock_name, alert_type=alert_type,
                       severity=severity, message=message, action=action, signal=signal,
                       pushed=pushed, source=source, user_id=user_id)
        db.add(row)
        task_queue.guarded_commit(db)
        db.refresh(row)
        _invalidate("alert")
        # 推理留痕仅 monitor 信号（LLM 研判）：pre_market/market_shift 等代码级检测
        # 无 LLM 研判，不写留痕（避免污染推理留痕视图）
        if source == "monitor":
            reasoning_trace.trace_alert(stock_code, stock_name, _now().strftime("%Y-%m-%d"),
                                        alert_type, severity, message, action, signal or {},
                                        extra=extra)
        return row.id


def insert_review(stock_code: str, stock_name: str, holding_id: int, exit_date: str,
                  hold_days: int, pnl_pct: float, plan_vs_actual: dict, lesson: str,
                  feedback: dict, user_id: int | None = None) -> int:
    with SessionLocal() as db:
        row = ReviewResult(stock_code=stock_code, stock_name=stock_name, holding_id=holding_id,
                           exit_date=exit_date, hold_days=hold_days, pnl_pct=pnl_pct,
                           plan_vs_actual=plan_vs_actual, lesson=lesson, feedback=feedback,
                           user_id=user_id)
        db.add(row)
        task_queue.guarded_commit(db)
        db.refresh(row)
        _invalidate("review")
        # 推理留痕：review 计划兑现对比 + 经验教训 + 反馈偏好
        reasoning_trace.trace_review(stock_code, stock_name, exit_date,
                                     plan_vs_actual, lesson, feedback)
        return row.id


# ==================== 复盘建议·驳回迭代（人工审核闭环） ====================

def update_review_suggestion_status(review_id: int, status: str) -> None:
    """更新建议状态：pending=待审核 / adopted=已采纳 / rejected=已驳回"""
    with SessionLocal() as db:
        row = db.get(ReviewResult, review_id)
        if row is None:
            return
        row.suggest_status = status
        # 旧复盘入口的人工采纳也必须打开同一条偏好门禁；生成时保持 pending。
        # 驳回则关闭该版本，保留记录供审计但不能再次被误认为待处理反馈。
        if status in ("adopted", "rejected"):
            pref = db.execute(
                select(AgentPreference).where(
                    AgentPreference.source_review_id == review_id
                ).order_by(AgentPreference.version.desc()).limit(1)
            ).scalar_one_or_none()
            if pref is not None:
                pref.status = "active" if status == "adopted" else "rejected"
        db.commit()
        _invalidate("review")


def append_review_iteration(review_id: int, reject_reason: str) -> None:
    """驳回时快照当前建议 + 驳回原因进 suggest_history（留存完整迭代轨迹）"""
    with SessionLocal() as db:
        row = db.get(ReviewResult, review_id)
        if row is None:
            return
        suggestion = (row.feedback or {}).get("profile_suggestion")
        history = list(row.suggest_history or [])
        history.append({
            "iteration": row.suggest_iteration,
            "suggestion": suggestion,
            "reject_reason": reject_reason,
        })
        row.suggest_history = history
        row.reject_reason = reject_reason
        row.suggest_status = "rejected"
        db.commit()
        _invalidate("review")


def apply_rethink_suggestion(review_id: int, feedback: dict, new_iteration: int) -> None:
    """重新思考结果落库：新建议写入 feedback，迭代次数+1，状态回待审核"""
    with SessionLocal() as db:
        row = db.get(ReviewResult, review_id)
        if row is None:
            return
        row.feedback = feedback
        row.suggest_iteration = new_iteration
        row.suggest_status = "pending"
        db.commit()
        _invalidate("review")


def get_review_reject_history(code: str | None = None, limit: int = 10) -> list[dict]:
    """历史驳回记录（含迭代轨迹），供后续复盘 Agent 注入参考，持续对齐用户真实偏好"""
    with SessionLocal() as db:
        stmt = select(ReviewResult).order_by(ReviewResult.id.desc())
        if code:
            stmt = stmt.where(ReviewResult.stock_code == code)
        rows = db.execute(stmt.limit(limit)).scalars().all()
        result = []
        for r in rows:
            for h in (r.suggest_history or []):
                sug = h.get("suggestion") or {}
                result.append({
                    "stock_code": r.stock_code, "stock_name": r.stock_name,
                    "iteration": h.get("iteration"), "field": sug.get("field"),
                    "value": sug.get("value"), "suggest_reason": sug.get("reason"),
                    "reject_reason": h.get("reject_reason"),
                })
        return result


def get_latest_preference(user_id: int | None = None) -> dict | None:
    if user_id is None:
        user_id = _context_user_id(1 if settings.multi_user_enabled else None)
    with SessionLocal() as db:
        stmt = select(AgentPreference).where(
            (AgentPreference.status == "active") | AgentPreference.status.is_(None))
        if user_id is not None:
            stmt = stmt.where((AgentPreference.user_id == user_id) |
                              AgentPreference.user_id.is_(None))
        row = db.execute(stmt.order_by(AgentPreference.version.desc()).limit(1)
                         ).scalar_one_or_none()
        return _json(row.content) if row else None


def get_latest_preference_version(user_id: int | None = None) -> int:
    with SessionLocal() as db:
        stmt = select(AgentPreference.version).where(
            (AgentPreference.status == "active") | AgentPreference.status.is_(None))
        if user_id is not None:
            stmt = stmt.where((AgentPreference.user_id == user_id) | AgentPreference.user_id.is_(None))
        value = db.execute(stmt.order_by(AgentPreference.version.desc()).limit(1)).scalar_one_or_none()
        return int(value or 0)


def upsert_preference(content: dict, source_review_id: int | None = None,
                      status: str | None = None) -> None:
    """写入偏好版本。

    有效复盘来源默认 pending，由审核采纳后激活；无复盘来源的旧调用默认 active，
    保持历史导入/接口兼容。调用方可显式传 status 覆盖默认值。
    """
    try:
        from app.core.auth import current_user_id
        user_id = current_user_id() or 1
    except Exception:
        user_id = 1
    with SessionLocal() as db:
        if status is None:
            status = "active"
            if source_review_id is not None and db.get(ReviewResult, source_review_id) is not None:
                status = "pending"
        latest = db.execute(
            select(AgentPreference).where(
                (AgentPreference.user_id == user_id) | AgentPreference.user_id.is_(None)
            ).order_by(AgentPreference.version.desc()).limit(1)
        ).scalar_one_or_none()
        version = (latest.version + 1) if latest else 1
        db.add(AgentPreference(version=version, content=content,
                               source_review_id=source_review_id, status=status,
                               user_id=user_id))
        db.commit()


def activate_preference_for_review(review_id: int) -> bool:
    """人工采纳复盘反馈对应的最新偏好版本。

    返回是否找到对应反馈；重复采纳保持幂等。状态变更只作用于该复盘来源，
    不会把其他复盘或无来源偏好带入正式评分。
    """
    with SessionLocal() as db:
        pref = db.execute(
            select(AgentPreference).where(
                AgentPreference.source_review_id == review_id
            ).order_by(AgentPreference.version.desc()).limit(1)
        ).scalar_one_or_none()
        if pref is None:
            return False
        pref.status = "active"
        db.commit()
        return True


# ==================== 存储空间维护（低频；仅清理非核心数据，不动关键分析数据） ====================

def maintenance_db() -> dict:
    """空间维护：超期新闻/公告清理 + SQLite 真空收缩（VACUUM）。
    保留周期见 settings.news_retention_days（默认 90 天）；MySQL 模式仅清理不收缩（无对应操作）。
    单项失败降级不中断；返回清理统计与库体积变化（MB）。
    """
    from datetime import datetime, timedelta

    from app.core.config import settings
    from app.db.session import engine

    cutoff = datetime.now() - timedelta(days=settings.news_retention_days)
    news_deleted = 0
    try:
        with SessionLocal() as db:
            news_deleted = db.execute(
                delete(NewsArticle).where(NewsArticle.created_at < cutoff)
            ).rowcount
            db.commit()
    except Exception as exc:  # noqa: BLE001 清理失败不中断主链路
        logger.warning("新闻保留期清理失败（不影响使用）: %s", exc)

    size_before = _db_size_mb()
    if engine.dialect.name == "sqlite":
        try:
            with engine.connect() as conn:
                conn.execute(text("VACUUM"))
        except Exception as exc:  # noqa: BLE001 VACUUM 失败不影响使用
            logger.warning("SQLite 真空收缩失败（不影响使用）: %s", exc)
    else:
        logger.info("MySQL 模式无 VACUUM 对应操作，仅执行超期数据清理")
    size_after = _db_size_mb()
    logger.info("空间维护: 清理新闻 %s 条，库体积 %s → %s MB",
                news_deleted, size_before, size_after)
    return {"news_deleted": news_deleted, "size_before_mb": size_before, "size_after_mb": size_after}


def _db_size_mb() -> float | None:
    """SQLite 库文件体积（MB）；MySQL 返回 None"""
    import os
    from pathlib import Path

    from app.db.session import engine

    if engine.dialect.name != "sqlite":
        return None
    raw = str(engine.url).replace("sqlite:///", "")
    path = Path(raw)
    return round(path.stat().st_size / 1024 / 1024, 2) if path.exists() else None


def add_news(stock_code: str, stock_name: str, title: str, content: str,
             source: str, url: str, published_at: str) -> bool:
    """写入新闻原文（按 code+title 去重），返回是否新增"""
    with SessionLocal() as db:
        exists = db.execute(
            select(NewsArticle.id).where(
                NewsArticle.stock_code == stock_code, NewsArticle.title == title)
        ).first()
        if exists:
            return False
        db.add(NewsArticle(stock_code=stock_code, stock_name=stock_name, title=title,
                           content=content[:2000], source=source, url=url, published_at=published_at))
        db.commit()
        upsert_public_fact(
            "news", source or "news_article", stock_code,
            published_at or _now().isoformat(timespec="seconds"),
            {"stock_code": stock_code, "stock_name": stock_name, "title": title,
             "content": content[:2000], "source": source, "url": url,
             "published_at": published_at},
        )
        return True


def get_recent_news(stock_code: str, days: int = 7) -> list[dict]:
    """查询某股近 N 日新闻/公告（只读，按发布时间倒序；无数据返回空列表）。
    published_at 为空的历史行按入库时间 created_at 兜底参与过滤与排序。"""
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with SessionLocal() as db:
        rows = db.execute(
            select(NewsArticle).where(NewsArticle.stock_code == stock_code)
        ).scalars().all()
    out = []
    for r in rows:
        day = str(r.published_at or "")[:10] or str(r.created_at)[:10]
        if day < cutoff:
            continue
        out.append({"title": r.title, "content": r.content, "source": r.source,
                    "url": r.url, "published_at": r.published_at or str(r.created_at)[:19],
                    "created_at": str(r.created_at)[:19]})
    out.sort(key=lambda x: (x["published_at"], x["created_at"]), reverse=True)
    return out


def get_trade_profile() -> TradeProfile | None:
    """读取当前用户交易偏好档案；关闭多人模式时兼容 legacy id=1。"""
    try:
        from app.core.auth import current_user_id
        user_id = current_user_id() or 1
    except Exception:
        user_id = 1
    with SessionLocal() as db:
        row = db.execute(select(TradeProfile).where(
            (TradeProfile.user_id == user_id) | (TradeProfile.id == user_id)
        ).order_by(TradeProfile.id).limit(1)).scalar_one_or_none()
        if row is None:
            row = TradeProfile(id=user_id, user_id=user_id, version=1,
                               content=_default_profile())
            db.add(row)
            db.commit()
            db.refresh(row)
        return row


def get_trade_profile_content() -> dict:
    row = get_trade_profile()
    return row.content if row else {}


def update_trade_profile(content: dict) -> int:
    """更新当前用户偏好档案，version 递增（用于 LLM 缓存失效）。"""
    try:
        from app.core.auth import current_user_id
        user_id = current_user_id() or 1
    except Exception:
        user_id = 1
    with SessionLocal() as db:
        row = db.execute(select(TradeProfile).where(
            (TradeProfile.user_id == user_id) | (TradeProfile.id == user_id)
        ).order_by(TradeProfile.id).limit(1)).scalar_one_or_none()
        if row is None:
            row = TradeProfile(id=user_id, user_id=user_id, version=1, content=content)
            db.add(row)
        else:
            row.version += 1
            row.content = content
        db.commit()
        return row.version


def insert_account_baseline(trade_date: str, total_asset: float, available_cash: float,
                            position_pct: float, source: str = "ocr",
                            user_id: int | None = None) -> int:
    """保存账户基准快照（人工确认后调用；每次插入一行保留历史，读取取最新）"""
    user_id = _context_user_id(user_id)
    with SessionLocal() as db:
        row = AccountBaseline(trade_date=trade_date, total_asset=total_asset,
                              available_cash=available_cash, position_pct=position_pct,
                              source=source, user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_latest_account_baseline(user_id: int | None = None, *, is_admin: bool = False) -> dict | None:
    """读取最新账户基准快照；无记录返回 None"""
    user_id = _context_user_id(user_id)
    with SessionLocal() as db:
        stmt = select(AccountBaseline).order_by(AccountBaseline.id.desc())
        if user_id is not None and not is_admin:
            stmt = stmt.where(AccountBaseline.user_id == user_id)
        row = db.execute(stmt.limit(1)).first()
        if row is None:
            return None
        r = row[0]
        return {"id": r.id, "trade_date": r.trade_date, "total_asset": r.total_asset,
                "available_cash": r.available_cash, "position_pct": r.position_pct,
                "source": r.source, "created_at": str(r.created_at)}


# ==================== 同花顺真实账户今日盈亏快照（ths_pnl，默认关闭） ====================

def upsert_account_pnl_snapshot(trade_date: str, ts: str, pnl_yk: float | None = None,
                                pnl_pct: float | None = None, sh_pct: float | None = None,
                                chart_data: list | None = None, source: str = "ths",
                                error: str = "", token_expired: bool = False,
                                user_id: int | None = None) -> int:
    """按 (trade_date, ts) 幂等 upsert 同花顺盈亏快照；返回行 id"""
    user_id = _context_user_id(user_id)
    with SessionLocal() as db:
        stmt = select(AccountPnlSnapshot).where(
                AccountPnlSnapshot.trade_date == trade_date,
                AccountPnlSnapshot.ts == ts,
            )
        if user_id is not None:
            stmt = stmt.where(AccountPnlSnapshot.user_id == user_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            row = AccountPnlSnapshot(
                trade_date=trade_date, ts=ts, pnl_yk=pnl_yk, pnl_pct=pnl_pct,
                sh_pct=sh_pct, chart_data=chart_data or [], source=source,
                error=error, token_expired=token_expired, user_id=user_id)
            db.add(row)
        else:
            row.pnl_yk = pnl_yk
            row.pnl_pct = pnl_pct
            row.sh_pct = sh_pct
            row.chart_data = chart_data or []
            row.source = source
            row.error = error
            row.token_expired = token_expired
        db.commit()
        db.refresh(row)
        return row.id


def get_latest_account_pnl(user_id: int | None = None, *, is_admin: bool = False) -> dict | None:
    """读取最新同花顺盈亏快照；无记录返回 None"""
    user_id = _context_user_id(user_id)
    with SessionLocal() as db:
        stmt = select(AccountPnlSnapshot).order_by(AccountPnlSnapshot.id.desc())
        if user_id is not None and not is_admin:
            stmt = stmt.where(AccountPnlSnapshot.user_id == user_id)
        row = db.execute(stmt.limit(1)).first()
        if row is None:
            return None
        r = row[0]
        return {"id": r.id, "trade_date": r.trade_date, "ts": r.ts, "pnl_yk": r.pnl_yk,
                "pnl_pct": r.pnl_pct, "sh_pct": r.sh_pct, "chart_data": r.chart_data,
                "source": r.source, "error": r.error, "token_expired": r.token_expired,
                "updated_at": str(r.updated_at)}


def list_account_pnl_history(days: int = 30, user_id: int | None = None,
                             *, is_admin: bool = False) -> list[dict]:
    """近 N 天同花顺盈亏快照历史（按日降序；每行只取核心字段）"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    user_id = _context_user_id(user_id)
    with SessionLocal() as db:
        stmt = select(AccountPnlSnapshot).where(AccountPnlSnapshot.trade_date >= cutoff)
        if user_id is not None and not is_admin:
            stmt = stmt.where(AccountPnlSnapshot.user_id == user_id)
        rows = db.execute(
            stmt
            .order_by(AccountPnlSnapshot.trade_date.desc(), AccountPnlSnapshot.ts.desc())
            .limit(500)
        ).scalars().all()
    return [{"trade_date": r.trade_date, "ts": r.ts, "pnl_yk": r.pnl_yk, "pnl_pct": r.pnl_pct,
             "sh_pct": r.sh_pct, "source": r.source, "error": r.error,
             "token_expired": r.token_expired} for r in rows]


def _default_profile() -> dict:
    """默认偏好（全部外部化，用户可在面板自由修改）"""
    return {
        "持仓周期偏好": "波段趋势，持仓数周至数月",
        "市值偏好": "中大盘为主（100亿以上）",
        "行业黑白名单": {"白名单": [], "黑名单": []},
        "单票仓位上限": 40,
        "整体仓位上限": 80,
        "风控容忍度": "中等，单笔最大回撤容忍 8%",
        "选股倾向": "回踩低吸为主，突破确认辅助",
        "重点规避风险类型": ["立案", "商誉减值", "大额减持"],
    }


def get_holding(holding_id: int) -> Holding | None:
    with SessionLocal() as db:
        return db.get(Holding, holding_id)


def get_holding_for_user(holding_id: int, user_id: int, *, is_admin: bool = False) -> Holding | None:
    if user_id is None:
        user_id = _context_user_id(1)
    with SessionLocal() as db:
        stmt = select(Holding).where(Holding.id == holding_id)
        if not is_admin:
            stmt = stmt.where(Holding.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()


def get_active_holding_by_code(stock_code: str, user_id: int | None = None,
                               *, is_admin: bool = False) -> Holding | None:
    """读取同代码当前唯一有效持仓，防止人工/OCR重复建仓污染生命周期口径。"""
    with SessionLocal() as db:
        stmt = select(Holding).where(Holding.stock_code == stock_code,
                                     Holding.status == "holding")
        if user_id is not None and not is_admin:
            stmt = stmt.where(Holding.user_id == user_id)
        return db.execute(
            stmt
            .order_by(Holding.id.desc()).limit(1)
        ).scalar_one_or_none()


def insert_holding(stock_code: str, stock_name: str, entry_date: str, entry_price: float,
                   shares: int, cost: float, stop_loss: float = 0.0, take_profit: float = 0.0,
                   target_pct: float = 0.0, plan_id: int | None = None, note: str = "",
                   user_id: int | None = None) -> int:
    with SessionLocal() as db:
        row = Holding(stock_code=stock_code, stock_name=stock_name, entry_date=entry_date,
                      entry_price=entry_price, shares=shares, cost=cost, stop_loss=stop_loss,
                      take_profit=take_profit, target_pct=target_pct, plan_id=plan_id, note=note,
                      user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        _invalidate("holding")
    # 建仓即补开仓 buy 流水（新建仓恒缺首笔；幂等，cost/shares 非法时跳过不抛）
    ensure_opening_trade(row)
    return row.id


def ensure_opening_trade(holding_row: Holding) -> dict:
    """确保持仓有建仓 buy 流水：缺首笔时补录 note='建仓补录'（幂等，禁止重复插入）。

    补法（§二口径）：金额 = cost − Σ已有 buy；股数 = 首条 buy 的 before_shares
    （无 buy 则取当时 shares）；价格 = 金额÷股数 四舍五入 2 位。
    K227：cost≤0 / Σbuy>cost / 股数未知 → 不硬凑，如实跳过。
    返回 {"applied", "amount", "shares", "price", "reason"}。
    """
    with SessionLocal() as db:
        if db.execute(select(TradeRecord).where(
                TradeRecord.holding_id == holding_row.id,
                TradeRecord.note == "建仓补录")).scalar_one_or_none() is not None:
            return {"applied": False, "amount": 0.0, "shares": 0, "price": None,
                    "reason": "already-backfilled"}
        trades = list(db.execute(
            select(TradeRecord).where(TradeRecord.holding_id == holding_row.id)
            .order_by(TradeRecord.trade_date, TradeRecord.id)).scalars().all())
        buys = [t for t in trades if t.side == "buy"]
        first_buy = buys[0] if buys else None
        # 缺首笔判定：首条 buy 的 before_shares>0（操作前已有底仓）或全无 buy
        if first_buy is not None and not (first_buy.before_shares or 0) > 0:
            return {"applied": False, "amount": 0.0, "shares": 0, "price": None,
                    "reason": "opening-exists"}
        cost = holding_row.cost or 0.0
        buy_sum = round(sum(t.amount for t in buys), 2)
        missing = round(cost - buy_sum, 2)
        if cost <= 0:
            return {"applied": False, "amount": 0.0, "shares": 0, "price": None,
                    "reason": "cost-invalid"}
        if missing < -0.01:
            return {"applied": False, "amount": 0.0, "shares": 0, "price": None,
                    "reason": "buy-overflow"}
        if missing <= 0.01:
            return {"applied": False, "amount": 0.0, "shares": 0, "price": None,
                    "reason": "complete"}
        shares = first_buy.before_shares if first_buy else holding_row.shares
        if not shares or shares <= 0:
            return {"applied": False, "amount": 0.0, "shares": 0, "price": None,
                    "reason": "shares-unknown"}
        price = round(missing / shares, 2)
        db.add(TradeRecord(holding_id=holding_row.id, stock_code=holding_row.stock_code,
                           side="buy", price=price, shares=shares, amount=missing,
                           trade_date=holding_row.entry_date, note="建仓补录",
                           before_shares=0, after_shares=shares))
        db.commit()
        _invalidate("holding")
        return {"applied": True, "amount": missing, "shares": shares, "price": price,
                "reason": "backfilled"}


def add_trade(holding_id: int, stock_code: str, side: str, price: float,
              shares: int, trade_date: str, note: str = "", user_id: int | None = None) -> int:
    with SessionLocal() as db:
        row = TradeRecord(holding_id=holding_id, stock_code=stock_code, side=side,
                          price=price, shares=shares, amount=round(price * shares, 2),
                          trade_date=trade_date, note=note, user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def update_holding(holding_id: int, **fields) -> None:
    with SessionLocal() as db:
        row = db.get(Holding, holding_id)
        if row is None:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        _invalidate("holding")


def record_holding_trade(holding_id: int, *, side: str, price: float, shares: int,
                         trade_date: str, note: str,
                         before_shares: int | None = None,
                         after_shares: int | None = None,
                         holding_fields: dict | None = None,
                         user_id: int | None = None) -> int:
    """事务化持仓操作写入（手动加仓/减仓/清仓/成本修正共用）：
    操作流水 + 持仓字段更新在单 session 一次 commit，失败整体回滚，保证流水与持仓
    状态一致（K223 留痕与事实一致）。仅数据存取，业务计算（加权成本/C3 等）由调用方
    算好后经 holding_fields 传入。返回流水 id。"""
    with SessionLocal() as db:
        row = db.get(Holding, holding_id)
        if row is None:
            raise ValueError("持仓不存在")
        db.add(TradeRecord(holding_id=holding_id, stock_code=row.stock_code, side=side,
                           price=price, shares=shares, amount=round(price * shares, 2),
                           trade_date=trade_date, note=note,
                           before_shares=before_shares, after_shares=after_shares,
                           user_id=user_id if user_id is not None else row.user_id))
        if holding_fields:
            for k, v in holding_fields.items():
                setattr(row, k, v)
        db.commit()
        _invalidate("holding")
        return row.id


def get_active_holdings(user_id: int | None = None, *, is_admin: bool = False) -> list[Holding]:
    user_id = _context_user_id(user_id)
    with SessionLocal() as db:
        stmt = select(Holding).where(Holding.status == "holding")
        if user_id is not None and not is_admin:
            stmt = stmt.where(Holding.user_id == user_id)
        return list(db.execute(stmt).scalars().all())


def get_trades(holding_id: int) -> list[TradeRecord]:
    with SessionLocal() as db:
        return list(db.execute(
            select(TradeRecord).where(TradeRecord.holding_id == holding_id)
            .order_by(TradeRecord.trade_date)).scalars().all())


def get_latest_score(code: str, as_of: str | None = None) -> StockScore | None:
    """读取该股最新评分；as_of 存在时只允许使用不晚于该日的版本。

    默认行为保持为读取当前最新评分，供实时建仓/评分链路使用；历史复盘应传入
    入场日，避免把退出后新生成的评分带入历史事实包。
    """
    with SessionLocal() as db:
        stmt = select(StockScore).where(StockScore.stock_code == code)
        if as_of:
            stmt = stmt.where(StockScore.trade_date <= as_of)
        return db.execute(stmt.order_by(StockScore.trade_date.desc()).limit(1)).scalar_one_or_none()


def get_closest_score_grade(stock_code: str, trade_date: str) -> str | None:
    """该股最接近 trade_date 且不晚于 trade_date 的权威评分 grade（ScoreAgent，只读幂等）：
    当日评分优先，回退到最近一条过去评分；无任何评分返回 None。
    供候选池「可建仓」c1 评级判定唯一读取（与建仓 gate run_position 同源），
    不做 Discover confidence_tier 兜底——无评分即「未评级/不可建仓」。"""
    with SessionLocal() as db:
        score = db.execute(
            select(StockScore).where(StockScore.stock_code == stock_code,
                                     StockScore.trade_date == trade_date)
        ).scalar_one_or_none()
        if score is None:
            score = db.execute(
                select(StockScore).where(StockScore.stock_code == stock_code,
                                         StockScore.trade_date <= trade_date)
                .order_by(StockScore.trade_date.desc()).limit(1)).scalar_one_or_none()
        if score is not None and score.grade:
            return score.grade.strip()
        return None


def get_latest_plan(code: str) -> PositionPlan | None:
    with SessionLocal() as db:
        return db.execute(
            select(PositionPlan).where(PositionPlan.stock_code == code)
            .order_by(PositionPlan.id.desc()).limit(1)).scalar_one_or_none()


def get_plan(plan_id: int | None, user_id: int | None = None,
             *, is_admin: bool = False) -> PositionPlan | None:
    """按明确版本读取建仓计划。"""
    if not plan_id:
        return None
    with SessionLocal() as db:
        stmt = select(PositionPlan).where(PositionPlan.id == plan_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(PositionPlan.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()


def get_plan_for_entry(stock_code: str, entry_date: str) -> tuple[PositionPlan | None, str]:
    """按入场日前最近版本推断旧持仓关联，并返回关联来源。"""
    with SessionLocal() as db:
        plan = db.execute(
            select(PositionPlan).where(
                PositionPlan.stock_code == stock_code,
                PositionPlan.plan_date <= entry_date,
            ).order_by(PositionPlan.plan_date.desc(), PositionPlan.id.desc()).limit(1)
        ).scalar_one_or_none()
        return (plan, "inferred_before_entry") if plan else (None, "missing")


def update_plan_status(plan_id: int, status: str, user_id: int | None = None,
                       *, is_admin: bool = False) -> dict | None:
    """人工确认建仓计划状态；只改生命周期，不触发交易或持仓变更。"""
    with SessionLocal() as db:
        stmt = select(PositionPlan).where(PositionPlan.id == plan_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(PositionPlan.user_id == user_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        row.status = status
        task_queue.guarded_commit(db)
        db.refresh(row)
        _invalidate("plan")
        return {"id": row.id, "stock_code": row.stock_code, "stock_name": row.stock_name,
                "plan_date": row.plan_date, "status": row.status,
                "total_pct": row.total_pct, "batches": row.batches,
                "stop_loss": row.stop_loss, "take_profit": row.take_profit,
                "rationale": row.rationale, "detail": row.detail or {},
                "source": row.source or "manual",
                "supersedes_id": row.supersedes_id,
                "created_at": str(row.created_at)}


# ==================== 面板读取（API 层统一经此网关，禁止直连会话） ====================

def list_candidates(date: str | None = None, limit: int = 50) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(StockCandidate).order_by(
                StockCandidate.trade_date.desc(), StockCandidate.rank)
            if date:
                stmt = stmt.where(StockCandidate.trade_date == date)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"stock_code": r.stock_code, "stock_name": r.stock_name,
                     "trade_date": r.trade_date, "rank": r.rank,
                     "reasons": r.reasons, "risk_notice": r.risk_notice,
                     "detail": r.detail or {}, "snapshot": r.snapshot or {},
                     "created_at": str(r.created_at)} for r in rows]

    return _dbq("candidate", {"date": date, "limit": limit}, _load)


def list_traces(code: str | None = None, date: str | None = None,
                module: str | None = None, limit: int = 50,
                end_date: str | None = None, user_id: int | None = None,
                *, is_admin: bool = False) -> list[dict]:
    """推理留痕轻量列表（不含长文本，详情按需单查；L1 缓存 dbq:trace:，写后由
    reasoning_trace._flush 失效）"""
    user_id = _context_user_id(user_id)
    if settings.multi_user_enabled and user_id is None and not is_admin:
        return []

    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(AiReasoningTrace).order_by(
                AiReasoningTrace.generate_date.desc(), AiReasoningTrace.trace_id.desc())
            if code:
                stmt = stmt.where(AiReasoningTrace.stock_code == code)
            if date:
                stmt = stmt.where(AiReasoningTrace.generate_date == date)
            if end_date:
                stmt = stmt.where(AiReasoningTrace.generate_date <= end_date)
            if module:
                stmt = stmt.where(AiReasoningTrace.source_module == module)
            if settings.multi_user_enabled and not is_admin:
                stmt = stmt.where(AiReasoningTrace.user_id == user_id)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"trace_id": r.trace_id, "stock_code": r.stock_code,
                     "stock_name": r.stock_name, "source_module": r.source_module,
                     "generate_date": r.generate_date, "confidence": r.confidence,
                     "data_source": r.data_source, "create_time": r.create_time}
                    for r in rows]

    return _dbq("trace", {"code": code, "date": date, "module": module,
                           "limit": limit, "end_date": end_date, "user_id": user_id,
                           "is_admin": is_admin}, _load)


def get_trace(trace_id: int, user_id: int | None = None, *, is_admin: bool = False) -> dict | None:
    """推理留痕完整详情（含全部推理分层文本）"""
    user_id = _context_user_id(user_id)
    if settings.multi_user_enabled and user_id is None and not is_admin:
        return None

    def _load() -> dict | None:
        with SessionLocal() as db:
            stmt = select(AiReasoningTrace).where(AiReasoningTrace.trace_id == trace_id)
            if settings.multi_user_enabled and not is_admin:
                stmt = stmt.where(AiReasoningTrace.user_id == user_id)
            r = db.execute(stmt).scalar_one_or_none()
            if r is None:
                return None
            return {"trace_id": r.trace_id, "stock_code": r.stock_code,
                    "stock_name": r.stock_name, "source_module": r.source_module,
                    "generate_date": r.generate_date, "fact_basis": r.fact_basis,
                    "technical_reasoning": r.technical_reasoning,
                    "capital_reasoning": r.capital_reasoning,
                    "fundamental_reasoning": r.fundamental_reasoning,
                    "risk_reasoning": r.risk_reasoning, "rule_refs": r.rule_refs,
                    "final_conclusion": r.final_conclusion, "confidence": r.confidence,
                    "data_source": r.data_source, "create_time": r.create_time,
                    "ext_info": r.ext_info}

    return _dbq("trace", {"id": trace_id, "user_id": user_id,
                           "is_admin": is_admin}, _load)


def list_trace_history(code: str | None = None, date: str | None = None,
                       module: str | None = None, limit: int = 100,
                       user_id: int | None = None, *, is_admin: bool = False) -> list[dict]:
    """推理留痕追加历史轻量列表；当前 /traces 投影接口保持最新版本语义。"""
    user_id = _context_user_id(user_id)
    if settings.multi_user_enabled and user_id is None and not is_admin:
        return []

    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(AiReasoningTraceHistory).order_by(
                AiReasoningTraceHistory.generate_date.desc(),
                AiReasoningTraceHistory.history_id.desc())
            if code:
                stmt = stmt.where(AiReasoningTraceHistory.stock_code == code)
            if date:
                stmt = stmt.where(AiReasoningTraceHistory.generate_date == date)
            if module:
                stmt = stmt.where(AiReasoningTraceHistory.source_module == module)
            if settings.multi_user_enabled and not is_admin:
                stmt = stmt.where(AiReasoningTraceHistory.user_id == user_id)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"history_id": r.history_id, "stock_code": r.stock_code,
                     "stock_name": r.stock_name, "source_module": r.source_module,
                     "generate_date": r.generate_date, "confidence": r.confidence,
                     "data_source": r.data_source, "create_time": r.create_time,
                     "recorded_at": str(r.recorded_at)} for r in rows]

    return _dbq("trace_history",
                {"code": code, "date": date, "module": module, "limit": limit,
                 "user_id": user_id, "is_admin": is_admin}, _load)


def get_trace_history(history_id: int, user_id: int | None = None,
                      *, is_admin: bool = False) -> dict | None:
    """读取单条推理留痕历史全文；只读，不影响当前投影。"""
    user_id = _context_user_id(user_id)
    if settings.multi_user_enabled and user_id is None and not is_admin:
        return None

    def _load() -> dict | None:
        with SessionLocal() as db:
            stmt = select(AiReasoningTraceHistory).where(
                AiReasoningTraceHistory.history_id == history_id)
            if settings.multi_user_enabled and not is_admin:
                stmt = stmt.where(AiReasoningTraceHistory.user_id == user_id)
            r = db.execute(stmt).scalar_one_or_none()
            if r is None:
                return None
            return {"history_id": r.history_id, "stock_code": r.stock_code,
                    "stock_name": r.stock_name, "source_module": r.source_module,
                    "generate_date": r.generate_date, "fact_basis": r.fact_basis,
                    "technical_reasoning": r.technical_reasoning,
                    "capital_reasoning": r.capital_reasoning,
                    "fundamental_reasoning": r.fundamental_reasoning,
                    "risk_reasoning": r.risk_reasoning, "rule_refs": r.rule_refs,
                    "final_conclusion": r.final_conclusion, "confidence": r.confidence,
                    "data_source": r.data_source, "create_time": r.create_time,
                    "ext_info": r.ext_info, "recorded_at": str(r.recorded_at)}

    return _dbq("trace_history", {"id": history_id, "user_id": user_id,
                                   "is_admin": is_admin}, _load)


def list_candidate_dates(limit: int = 30) -> list[str]:
    """候选池可选日期（去重降序，默认最新在前）：页面只加载最新一天，
    切换历史日期时再按需查询，避免初始化全量加载"""

    def _load() -> list[str]:
        with SessionLocal() as db:
            rows = db.execute(
                select(StockCandidate.trade_date)
                .distinct()
                .order_by(StockCandidate.trade_date.desc())
                .limit(limit)).scalars().all()
            return list(rows)

    return _dbq("candidate", {"dates": limit}, _load)


# ==================== 候选池 T+N 验证（选股效果闭环·代码侧客观统计） ====================

def upsert_track_verify(stock_code: str, stock_name: str, select_date: str,
                        select_rating: str, base_close_price: float,
                        factor_scores: dict | None = None) -> int:
    """初始化追踪行：同 (code, select_date) 已存在则返回既有 id（幂等，重复执行安全）"""
    with SessionLocal() as db:
        row = db.execute(
            select(CandidateTrackVerify).where(
                CandidateTrackVerify.stock_code == stock_code,
                CandidateTrackVerify.select_date == select_date)
        ).scalar_one_or_none()
        if row is None:
            row = CandidateTrackVerify(stock_code=stock_code, stock_name=stock_name,
                                       select_date=select_date, select_rating=select_rating,
                                       base_close_price=base_close_price,
                                       factor_scores=factor_scores)
            db.add(row)
            db.commit()
            db.refresh(row)
            _invalidate("track_verify")
        return row.id


def update_track_verify(row_id: int, *, t3_pct=None, t5_pct=None, t10_pct=None,
                        max_drawdown=None, verify_result: dict | None = None,
                        factor_scores: dict | None = None,
                        is_finished: int = 0) -> None:
    """增量更新已追踪行（未提供的参数保持原值）；update_time 取当前时间戳"""
    with SessionLocal() as db:
        row = db.get(CandidateTrackVerify, row_id)
        if row is None:
            return
        if t3_pct is not None:
            row.t3_pct = t3_pct
        if t5_pct is not None:
            row.t5_pct = t5_pct
        if t10_pct is not None:
            row.t10_pct = t10_pct
        if max_drawdown is not None:
            row.max_drawdown = max_drawdown
        if verify_result is not None:
            row.verify_result = verify_result
        if factor_scores is not None:
            row.factor_scores = factor_scores
        row.is_finished = is_finished
        row.update_time = time.strftime("%Y-%m-%d %H:%M")
        db.commit()
        _invalidate("track_verify")


# ==================== 前瞻回填闭环（预测性选股 2.5） ====================

def upsert_forward_view(stock_code: str, trade_date: str, forward_view: str,
                        forward_signals: dict) -> int:
    """落库前瞻快照（幂等：同 code+date 已存在则更新 forward_view/signals，不重复插）。
    返回行 id；missing_data 跳过判定在服务层完成，本函数只做存取。"""
    with SessionLocal() as db:
        row = db.execute(
            select(ForwardViewHistory).where(
                ForwardViewHistory.stock_code == stock_code,
                ForwardViewHistory.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = ForwardViewHistory(stock_code=stock_code, trade_date=trade_date,
                                     forward_view=forward_view,
                                     forward_signals=forward_signals or {})
            db.add(row)
            db.commit()
            db.refresh(row)
        else:
            row.forward_view = forward_view
            row.forward_signals = forward_signals or {}
            db.commit()
        _invalidate("forward_view")
        return row.id


def list_unfilled_forward_view(cutoff_date: str, limit: int = 500) -> list[dict]:
    """待回填前瞻快照：选入日 ≤ cutoff 且 t5_pct_actual IS NULL（每日 16:00 回填 cron 用）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = (select(ForwardViewHistory)
                    .where(ForwardViewHistory.trade_date <= cutoff_date,
                           ForwardViewHistory.t5_pct_actual.is_(None))
                    .order_by(ForwardViewHistory.trade_date)
                    .limit(limit))
            return [{"id": r.id, "stock_code": r.stock_code, "trade_date": r.trade_date,
                     "forward_view": r.forward_view, "forward_signals": r.forward_signals or {}}
                    for r in db.execute(stmt).scalars().all()]
    return _dbq("forward_view", {"cutoff": cutoff_date}, _load)


def get_track_verify_t5_pct(stock_code: str, select_date: str) -> float | None:
    """追踪行 T+5 实际涨跌幅（回填 t5_pct_actual 用；无行/无值返回 None，不补 0）"""
    with SessionLocal() as db:
        row = db.execute(
            select(CandidateTrackVerify).where(
                CandidateTrackVerify.stock_code == stock_code,
                CandidateTrackVerify.select_date == select_date)
        ).scalar_one_or_none()
        return row.t5_pct if row is not None else None


def update_forward_view_actual(row_id: int, actual: float, bucket: str) -> None:
    """回填 t5_pct_actual + 校准 bucket（correct/wrong/neutral；幂等覆盖）"""
    with SessionLocal() as db:
        row = db.get(ForwardViewHistory, row_id)
        if row is None:
            return
        row.t5_pct_actual = float(actual)
        row.t5_filled_at = datetime.now()
        row.accuracy_bucket = bucket
        db.commit()
        _invalidate("forward_view")


def compute_forward_view_accuracy(lookback_days: int = 30) -> dict:
    """近 lookback_days 日前瞻准确率（校准先验用）：按 forward_view 分桶统计。
    准确率 = correct / (correct + wrong)，neutral 不计入分母；无样本返回 0（诚实标注）。"""
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    with SessionLocal() as db:
        rows = db.execute(
            select(ForwardViewHistory)
            .where(ForwardViewHistory.trade_date >= cutoff,
                   ForwardViewHistory.accuracy_bucket.isnot(None))
        ).scalars().all()
    strong_c = sum(1 for r in rows if r.forward_view == "强" and r.accuracy_bucket == "correct")
    strong_d = sum(1 for r in rows if r.forward_view == "强" and r.accuracy_bucket != "neutral")
    weak_c = sum(1 for r in rows if r.forward_view == "弱" and r.accuracy_bucket == "correct")
    weak_d = sum(1 for r in rows if r.forward_view == "弱" and r.accuracy_bucket != "neutral")
    return {
        "strong": round(strong_c / strong_d, 4) if strong_d else 0.0,
        "strong_n": strong_d,
        "weak": round(weak_c / weak_d, 4) if weak_d else 0.0,
        "weak_n": weak_d,
        "neutral_n": sum(1 for r in rows if r.accuracy_bucket == "neutral"),
        "total": len(rows),
        "lookback_days": lookback_days,
    }


def list_untracked_candidates() -> list[dict]:
    """候选池中尚未进入追踪表的全部标的（自愈初始化数据源：无日期过滤，
    任何一天漏跑下次运行自动补齐）；每日仅调用一次，不走 _dbq"""
    with SessionLocal() as db:
        stmt = (
            select(StockCandidate, CandidateTrackVerify.id)
            .outerjoin(
                CandidateTrackVerify,
                (CandidateTrackVerify.stock_code == StockCandidate.stock_code)
                & (CandidateTrackVerify.select_date == StockCandidate.trade_date))
            .where(CandidateTrackVerify.id.is_(None))
            .order_by(StockCandidate.trade_date, StockCandidate.rank)
        )
        return [{"stock_code": c.stock_code, "stock_name": c.stock_name,
                 "trade_date": c.trade_date, "rank": c.rank,
                 "snapshot": c.snapshot or {}, "detail": c.detail or {}}
                for c, _ in db.execute(stmt).all()]


def list_track_verify(select_date: str = "", start_date: str = "", end_date: str = "",
                      rating: str = "", is_finished: int | None = None,
                      limit: int = 200) -> list[dict]:
    """追踪验证行列表（select_date 兼容旧单参；start_date/end_date 时间范围；60s 缓存，写后失效）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(CandidateTrackVerify).order_by(
                CandidateTrackVerify.select_date.desc(), CandidateTrackVerify.id)
            if select_date:
                stmt = stmt.where(CandidateTrackVerify.select_date == select_date)
            elif start_date or end_date:
                if start_date:
                    stmt = stmt.where(CandidateTrackVerify.select_date >= start_date)
                if end_date:
                    stmt = stmt.where(CandidateTrackVerify.select_date <= end_date)
            if rating:
                stmt = stmt.where(CandidateTrackVerify.select_rating == rating)
            if is_finished is not None:
                stmt = stmt.where(CandidateTrackVerify.is_finished == is_finished)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                     "select_date": r.select_date, "select_rating": r.select_rating,
                     "base_close_price": r.base_close_price, "t3_pct": r.t3_pct,
                     "t5_pct": r.t5_pct, "t10_pct": r.t10_pct,
                     "max_drawdown": r.max_drawdown, "verify_result": r.verify_result or {},
                     "factor_scores": r.factor_scores,
                     "is_finished": r.is_finished, "update_time": r.update_time,
                     "created_at": str(r.created_at)} for r in rows]

    return _dbq("track_verify",
                {"date": select_date, "start": start_date, "end": end_date,
                 "rating": rating, "finished": is_finished, "limit": limit}, _load)


def fetch_daily_kline(code: str, start_date: str, end_date: str) -> list[dict]:
    """单股日K（透传 datasource；供 kline 接口/多日盈亏曲线渲染；纯数据无判断）。
    失败返回空列表（不抛，单标的行情缺失不阻塞）。"""
    try:
        from app.datasource.fallback import get_datasource
        df = get_datasource().fetch_daily_kline(code, start_date, end_date)
        if df is None or df.empty:
            return []
        out = []
        for _, r in df.iterrows():
            out.append({"date": str(r.get("date") or "")[:10], "open": r.get("open"),
                        "high": r.get("high"), "low": r.get("low"), "close": r.get("close"),
                        "volume": r.get("volume")})
        return out
    except Exception:  # noqa: BLE001 单股行情失败降级空列表
        return []


def list_track_verify_dates(limit: int = 30) -> list[str]:
    """追踪验证可选日期（去重降序，页面日期筛选）"""

    def _load() -> list[str]:
        with SessionLocal() as db:
            rows = db.execute(
                select(CandidateTrackVerify.select_date)
                .distinct()
                .order_by(CandidateTrackVerify.select_date.desc())
                .limit(limit)).scalars().all()
            return list(rows)

    return _dbq("track_verify", {"dates": limit}, _load)


def get_score_factors(stock_code: str, trade_date: str) -> list[dict] | None:
    """从 stock_score.detail 提取六因子分值（只读，幂等）。
    返回 [{"factor": "动量", "score": 7}, ...] 或 None（无评分/旧格式无 factors）。
    当日评分优先，回退到最近一条过去评分。"""
    with SessionLocal() as db:
        score = db.execute(
            select(StockScore).where(StockScore.stock_code == stock_code,
                                     StockScore.trade_date == trade_date)
        ).scalar_one_or_none()
        if score is None:
            score = db.execute(
                select(StockScore).where(StockScore.stock_code == stock_code)
                .order_by(StockScore.trade_date.desc()).limit(1)
            ).scalar_one_or_none()
        if score is None:
            return None
        detail = score.detail or {}
        factors = detail.get("factors")
        if not isinstance(factors, list) or not factors:
            return None
        return [{"factor": f.get("factor", ""), "score": f.get("score", 0)}
                for f in factors if isinstance(f, dict)]


def get_candidate_rating(stock_code: str, trade_date: str) -> str:
    """候选评级解析（决策：评分 grade 优先，无则 confidence_tier 原文）：
    ① 当日 StockScore.grade（A/B/C）→ ② 最近一次评分 grade → ③ 候选 detail.confidence_tier 原文 → ④ 空串"""
    with SessionLocal() as db:
        score = db.execute(
            select(StockScore).where(StockScore.stock_code == stock_code,
                                     StockScore.trade_date == trade_date)
        ).scalar_one_or_none()
        if score is None:
            score = db.execute(
                select(StockScore).where(StockScore.stock_code == stock_code)
                .order_by(StockScore.trade_date.desc()).limit(1)).scalar_one_or_none()
        if score is not None and score.grade:
            return score.grade.strip()
        cand = db.execute(
            select(StockCandidate).where(StockCandidate.stock_code == stock_code,
                                         StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        if cand is not None:
            tier = (cand.detail or {}).get("confidence_tier", "")
            if tier:
                return str(tier).strip()
        return ""


def has_pending_suggestion(rule_name: str, target_agent: str) -> bool:
    """建议去重检查：同 rule_name + target_agent 已有 pending 建议则不重复插入"""
    with SessionLocal() as db:
        return db.execute(
            select(func.count()).select_from(AgentSuggestion)
            .where(AgentSuggestion.rule_name == rule_name,
                   AgentSuggestion.target_agent == target_agent,
                   AgentSuggestion.status == "pending")
        ).scalar_one() > 0


def _backfill_stock_names(rows: list[dict]) -> list[dict]:
    """股票名称补齐（历史脏数据修复，查询层只读不写库）：
    记录名称缺失或等于代码时，按「候选池最新 → 持仓 → 新闻」顺序批量反查真实名称；
    仍查不到保留空名，前端统一展示「未知名称」。不修改任何落库逻辑与存储结构。"""
    missing = {r["stock_code"] for r in rows
               if not r.get("stock_name") or r["stock_name"] == r["stock_code"]}
    if not missing:
        return rows
    names: dict[str, str] = {}
    with SessionLocal() as db:
        cand = db.execute(
            select(StockCandidate.stock_code, StockCandidate.stock_name)
            .where(StockCandidate.stock_code.in_(missing))
            .order_by(StockCandidate.trade_date.desc())).all()
        for code, name in cand:
            if name and name != code and code not in names:
                names[code] = name
        still = missing - set(names)
        if still:
            hold = db.execute(
                select(Holding.stock_code, Holding.stock_name)
                .where(Holding.stock_code.in_(still))).all()
            for code, name in hold:
                if name and name != code and code not in names:
                    names[code] = name
        still -= set(names)
        if still:
            news = db.execute(
                select(NewsArticle.stock_code, NewsArticle.stock_name)
                .where(NewsArticle.stock_code.in_(still))).all()
            for code, name in news:
                if name and name != code and code not in names:
                    names[code] = name
    for r in rows:
        if not r.get("stock_name") or r["stock_name"] == r["stock_code"]:
            r["stock_name"] = names.get(r["stock_code"], "")
    return rows


def list_scores(code: str | None = None, date: str | None = None, limit: int = 100) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(StockScore).order_by(StockScore.trade_date.desc())
            if code:
                stmt = stmt.where(StockScore.stock_code == code)
            if date:
                stmt = stmt.where(StockScore.trade_date == date)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "trade_date": r.trade_date, "score": r.score,
                                           "grade": r.grade, "detail": r.detail,
                                           "risk_list": r.risk_list,
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("score", {"code": code, "date": date, "limit": limit}, _load)


def list_plans(code: str | None = None, limit: int = 50, user_id: int | None = None,
               *, is_admin: bool = False) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(PositionPlan).order_by(PositionPlan.id.desc())
            if code:
                stmt = stmt.where(PositionPlan.stock_code == code)
            if user_id is not None and not is_admin:
                stmt = stmt.where(PositionPlan.user_id == user_id)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "plan_date": r.plan_date, "status": r.status,
                                           "total_pct": r.total_pct, "batches": r.batches,
                                           "stop_loss": r.stop_loss, "take_profit": r.take_profit,
                                           "rationale": r.rationale,
                                           "detail": r.detail or {},
                                           "source": r.source or "manual",
                                           "execution_mode": "planning",
                                           "source_label": "建仓计划",
                                           "audit_status": "not_required",
                                           "supersedes_id": r.supersedes_id,
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("plan", {"code": code, "limit": limit, "user_id": user_id,
                           "is_admin": is_admin}, _load)


def list_holdings(status: str | None = None, user_id: int | None = None,
                  *, is_admin: bool = False) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(Holding).order_by(Holding.id.desc())
            if status:
                stmt = stmt.where(Holding.status == status)
            if user_id is not None and not is_admin:
                stmt = stmt.where(Holding.user_id == user_id)
            rows = db.execute(stmt).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "entry_date": r.entry_date,
                                           "entry_price": r.entry_price, "shares": r.shares,
                                           "cost": r.cost, "stop_loss": r.stop_loss,
                                           "take_profit": r.take_profit,
                                           "target_pct": r.target_pct, "status": r.status,
                                           "plan_id": r.plan_id, "note": r.note,
                                           "execution_mode": "real",
                                           "source_label": "真实交易",
                                           "audit_status": "not_required",
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("holding", {"status": status, "user_id": user_id,
                              "is_admin": is_admin}, _load)


def list_alerts(limit: int = 100, user_id: int | None = None,
                *, is_admin: bool = False) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(AlertLog).order_by(AlertLog.id.desc())
            if user_id is not None and not is_admin:
                stmt = stmt.where(AlertLog.user_id == user_id)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "alert_type": r.alert_type, "severity": r.severity,
                                           "message": r.message, "action": r.action,
                                           "signal": r.signal, "pushed": r.pushed,
                                           "source": r.source,
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("alert", {"limit": limit, "user_id": user_id,
                            "is_admin": is_admin}, _load)


def list_reviews(code: str | None = None, limit: int = 50, user_id: int | None = None,
                 *, is_admin: bool = False) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(ReviewResult).order_by(ReviewResult.id.desc())
            if code:
                stmt = stmt.where(ReviewResult.stock_code == code)
            if user_id is not None and not is_admin:
                stmt = stmt.where(ReviewResult.user_id == user_id)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "exit_date": r.exit_date, "hold_days": r.hold_days,
                                           "pnl_pct": r.pnl_pct,
                                           "plan_vs_actual": r.plan_vs_actual, "lesson": r.lesson,
                                           "feedback": r.feedback,
                                           "suggest_status": r.suggest_status,
                                           "reject_reason": r.reject_reason,
                                           "suggest_iteration": r.suggest_iteration,
                                           "suggest_history": r.suggest_history or [],
                                           "execution_mode": "real",
                                           "review_source": "真实复盘",
                                           "audit_status": "not_required",
                                           "created_at": str(r.created_at)}
                                          for r in rows])

    return _dbq("review", {"code": code, "limit": limit, "user_id": user_id,
                             "is_admin": is_admin}, _load)


# ==================== 独立 AI 模拟账本（严禁写入 Holding/TradeRecord） ====================

def _paper_account_dict(row: PaperAccount) -> dict:
    return {"id": row.id, "name": row.name, "strategy_variant": row.strategy_variant,
            "initial_cash": row.initial_cash, "cash": row.cash, "status": row.status,
            "rule_version": row.rule_version, "model_version": row.model_version,
            "source_label": row.source_label, "user_id": row.user_id,
            "created_at": str(row.created_at),
            "updated_at": str(row.updated_at)}


def create_paper_account(name: str, initial_cash: float, strategy_variant: str = "current_gate",
                         rule_version: str = "", model_version: str = "",
                         user_id: int | None = None) -> dict:
    if initial_cash <= 0:
        raise ValueError("模拟账户初始资金必须大于 0")
    with SessionLocal() as db:
        row = PaperAccount(name=name or "AI模拟账户", initial_cash=round(initial_cash, 2),
                           cash=round(initial_cash, 2), strategy_variant=strategy_variant,
                           rule_version=rule_version, model_version=model_version,
                           user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _paper_account_dict(row)


def get_paper_account(account_id: int) -> PaperAccount | None:
    with SessionLocal() as db:
        return db.get(PaperAccount, account_id)


def get_paper_account_for_user(account_id: int, user_id: int, *, is_admin: bool = False) -> PaperAccount | None:
    with SessionLocal() as db:
        stmt = select(PaperAccount).where(PaperAccount.id == account_id)
        if not is_admin:
            stmt = stmt.where(PaperAccount.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()


def list_paper_accounts(status: str | None = None, user_id: int | None = None,
                        *, is_admin: bool = False) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(PaperAccount).order_by(PaperAccount.id.desc())
        if status:
            stmt = stmt.where(PaperAccount.status == status)
        if user_id is not None and not is_admin:
            stmt = stmt.where(PaperAccount.user_id == user_id)
        return [_paper_account_dict(r) for r in db.execute(stmt).scalars().all()]


def update_paper_account_status(account_id: int, status: str) -> dict | None:
    if status not in ("active", "paused"):
        raise ValueError("模拟账户状态仅支持 active/paused")
    with SessionLocal() as db:
        row = db.get(PaperAccount, account_id)
        if row is None:
            return None
        row.status = status
        db.commit()
        return _paper_account_dict(row)


def release_paper_t1(account_id: int, trade_date: str) -> int:
    """新交易日开始释放前一交易日以前买入的股数，幂等。"""
    with SessionLocal() as db:
        rows = db.execute(select(PaperPosition).where(
            PaperPosition.account_id == account_id, PaperPosition.status == "holding",
            PaperPosition.opened_trade_date < trade_date)).scalars().all()
        changed = 0
        for row in rows:
            if row.available_shares < row.shares:
                row.available_shares = row.shares
                changed += 1
        if changed:
            db.commit()
        return changed


def paper_apply_execution(account_id: int, payload: dict) -> dict:
    """原子写入模拟流水并更新独立现金/持仓；execution_key 提供幂等保护。"""
    key = str(payload.get("execution_key") or "").strip()
    if not key:
        raise ValueError("模拟执行缺少 execution_key")
    with SessionLocal() as db:
        # 同一账户的盘中任务、手动运行按账户行串行结算。
        account = db.execute(select(PaperAccount).where(PaperAccount.id == account_id).with_for_update()).scalar_one_or_none()
        if account is None:
            raise ValueError("模拟账户不存在")
        if account.status != "active":
            raise ValueError("模拟账户已暂停")
        existing = db.execute(select(PaperExecution).where(
            PaperExecution.execution_key == key)).scalar_one_or_none()
        if existing is not None:
            return paper_execution_dict(existing)
        execution = PaperExecution(account_id=account_id, user_id=account.user_id, **{
            k: v for k, v in payload.items() if k in {
                "execution_key", "decision_id", "candidate_id", "score_id", "plan_id",
                "stock_code", "stock_name", "side", "requested_price", "executed_price",
                "shares", "gross_amount", "commission", "stamp_tax", "transfer_fee",
                "total_amount", "trade_date", "fact_as_of", "available_on", "status",
                "reject_reason", "strategy_variant", "rule_version", "model_version",
                "source_label", "metadata_json",
            }
        })
        if execution.status == "filled":
            side = execution.side
            if execution.shares <= 0 or execution.shares % 100 or side not in {"buy", "sell"}:
                raise ValueError("模拟成交方向或整手数量无效")
            if side == "buy":
                if account.cash + 1e-8 < execution.total_amount:
                    raise ValueError("模拟账户现金不足")
                account.cash = round(account.cash - execution.total_amount, 2)
                pos = db.execute(select(PaperPosition).where(
                    PaperPosition.account_id == account_id,
                    PaperPosition.stock_code == execution.stock_code)).scalar_one_or_none()
                if pos is None:
                    pos = PaperPosition(account_id=account_id, user_id=account.user_id,
                                        stock_code=execution.stock_code,
                                        stock_name=execution.stock_name or execution.stock_code,
                                        plan_id=execution.plan_id, shares=0, available_shares=0,
                                        cost=0.0, avg_price=0.0, high_price=0.0,
                                        stop_loss=float((payload.get("metadata_json") or {}).get("stop_loss") or 0),
                                        take_profit=float((payload.get("metadata_json") or {}).get("take_profit") or 0))
                    db.add(pos)
                elif pos.status == "holding" and pos.shares:
                    raise ValueError("模拟持仓已存在，禁止并发重复买入")
                else:
                    pos.opened_trade_date = execution.trade_date
                    pos.available_shares = 0
                    pos.cost = 0.0
                    pos.high_price = 0.0
                    pos.plan_id = execution.plan_id
                    pos.stop_loss = float((payload.get("metadata_json") or {}).get("stop_loss") or 0)
                    pos.take_profit = float((payload.get("metadata_json") or {}).get("take_profit") or 0)
                old_cost = pos.cost or 0.0
                pos.shares += execution.shares
                pos.available_shares += 0
                pos.cost = round(old_cost + execution.total_amount, 2)
                pos.avg_price = round(pos.cost / pos.shares, 4) if pos.shares else 0.0
                pos.opened_trade_date = pos.opened_trade_date or execution.trade_date
                pos.high_price = max(pos.high_price or 0, execution.executed_price or 0)
                pos.status = "holding"
            elif side == "sell":
                pos = db.execute(select(PaperPosition).where(
                    PaperPosition.account_id == account_id,
                    PaperPosition.stock_code == execution.stock_code,
                    PaperPosition.status == "holding")).scalar_one_or_none()
                if pos is None or pos.available_shares < execution.shares or pos.opened_trade_date >= execution.trade_date:
                    raise ValueError("模拟持仓可卖股数不足（T+1 或数量限制）")
                account.cash = round(account.cash + execution.total_amount, 2)
                pos.shares -= execution.shares
                pos.available_shares -= execution.shares
                pos.cost = round(pos.avg_price * pos.shares, 2)
                if pos.shares <= 0:
                    pos.shares = pos.available_shares = 0
                    pos.status = "exited"
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return paper_execution_dict(execution)


def paper_execution_dict(row: PaperExecution) -> dict:
    return {"id": row.id, "execution_key": row.execution_key, "account_id": row.account_id,
            "decision_id": row.decision_id, "candidate_id": row.candidate_id,
            "score_id": row.score_id, "plan_id": row.plan_id, "stock_code": row.stock_code,
            "stock_name": row.stock_name, "side": row.side, "requested_price": row.requested_price,
            "executed_price": row.executed_price, "shares": row.shares,
            "gross_amount": row.gross_amount, "commission": row.commission,
            "stamp_tax": row.stamp_tax, "transfer_fee": row.transfer_fee,
            "total_amount": row.total_amount, "trade_date": row.trade_date,
            "fact_as_of": row.fact_as_of, "available_on": row.available_on,
            "status": row.status, "reject_reason": row.reject_reason,
            "strategy_variant": row.strategy_variant, "rule_version": row.rule_version,
            "model_version": row.model_version, "source_label": row.source_label,
            "metadata": row.metadata_json or {}, "created_at": str(row.created_at)}


def list_paper_positions(account_id: int, status: str | None = None) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(PaperPosition).where(PaperPosition.account_id == account_id)
        if status:
            stmt = stmt.where(PaperPosition.status == status)
        rows = db.execute(stmt.order_by(PaperPosition.id.desc())).scalars().all()
        return [{"id": r.id, "account_id": r.account_id, "stock_code": r.stock_code,
                 "stock_name": r.stock_name, "shares": r.shares,
                 "available_shares": r.available_shares, "avg_price": r.avg_price,
                 "cost": r.cost, "opened_trade_date": r.opened_trade_date,
                 "plan_id": r.plan_id, "stop_loss": r.stop_loss, "take_profit": r.take_profit,
                 "high_price": r.high_price, "status": r.status,
                 "metadata": r.metadata_json or {}, "updated_at": str(r.updated_at)} for r in rows]


def list_paper_executions(account_id: int, limit: int = 200) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(PaperExecution).where(
            PaperExecution.account_id == account_id).order_by(PaperExecution.id.desc()).limit(limit)
        ).scalars().all()
        return [paper_execution_dict(r) for r in rows]


def upsert_paper_quotes(account_id: int, rows: list[dict]) -> int:
    """幂等写入模拟账户专用行情快照。"""
    if not rows:
        return 0
    with SessionLocal() as db:
        count = 0
        for item in rows:
            code = str(item.get("stock_code") or "").strip()
            if not code:
                continue
            row = db.execute(select(PaperQuoteSnapshot).where(
                PaperQuoteSnapshot.account_id == account_id,
                PaperQuoteSnapshot.stock_code == code)).scalar_one_or_none()
            if row is None:
                row = PaperQuoteSnapshot(account_id=account_id, stock_code=code)
                db.add(row)
            for key in ("stock_name", "price", "change_pct", "source", "quote_time",
                        "fact_as_of", "status", "error", "snapshot"):
                if key in item:
                    setattr(row, key, item.get(key))
            row.updated_at = _now()
            count += 1
        db.commit()
        return count


def list_paper_quotes(account_id: int, within_minutes: int | None = 10) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(PaperQuoteSnapshot).where(PaperQuoteSnapshot.account_id == account_id)
        if within_minutes is not None:
            stmt = stmt.where(PaperQuoteSnapshot.updated_at >= _now() - timedelta(minutes=max(0, within_minutes)))
        rows = db.execute(stmt.order_by(PaperQuoteSnapshot.id.desc())).scalars().all()
        return [{**(r.snapshot or {}), "id": r.id, "account_id": r.account_id, "stock_code": r.stock_code,
                 "stock_name": r.stock_name, "price": r.price, "change_pct": r.change_pct,
                 "source": r.source, "quote_time": r.quote_time, "fact_as_of": r.fact_as_of,
                 "status": r.status, "error": r.error, "updated_at": str(r.updated_at)}
                for r in rows]


def create_paper_context(account_id: int, trade_date: str, mode: str, stock_code: str,
                         stage: str, facts: dict, tool_trace: list | None = None,
                         source_refs: list | None = None) -> int:
    with SessionLocal() as db:
        account = db.get(PaperAccount, account_id)
        row = PaperContext(account_id=account_id, user_id=account.user_id if account else None,
                           trade_date=trade_date, mode=mode,
                           stock_code=stock_code or "", stage=stage or "",
                           facts=facts or {}, tool_trace=tool_trace or [],
                           source_refs=source_refs or [])
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_paper_contexts(account_id: int, limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(PaperContext).where(PaperContext.account_id == account_id)
                          .order_by(PaperContext.id.desc()).limit(limit)).scalars().all()
        return [{"id": r.id, "account_id": r.account_id, "trade_date": r.trade_date,
                 "mode": r.mode, "stock_code": r.stock_code, "stage": r.stage,
                 "facts": r.facts or {}, "tool_trace": r.tool_trace or [],
                 "source_refs": r.source_refs or [], "status": r.status,
                 "created_at": str(r.created_at)} for r in rows]


def create_paper_web_evidence(account_id: int, trade_date: str, stock_code: str,
                              values: dict) -> int:
    with SessionLocal() as db:
        account = db.get(PaperAccount, account_id)
        row = PaperWebEvidence(account_id=account_id, trade_date=trade_date,
                               user_id=account.user_id if account else None,
                               stock_code=stock_code or "", **{
                                   key: values.get(key, "") for key in (
                                       "url", "domain", "title", "excerpt", "published_at",
                                       "fetched_at", "fact_as_of", "content_hash", "status", "error")
                               })
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_paper_web_evidence(account_id: int, limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(PaperWebEvidence).where(
            PaperWebEvidence.account_id == account_id).order_by(PaperWebEvidence.id.desc())
                          .limit(limit)).scalars().all()
        return [{"id": r.id, "account_id": r.account_id, "trade_date": r.trade_date,
                 "stock_code": r.stock_code, "url": r.url, "domain": r.domain,
                 "title": r.title, "excerpt": r.excerpt, "published_at": r.published_at,
                 "fetched_at": r.fetched_at, "fact_as_of": r.fact_as_of,
                 "content_hash": r.content_hash, "status": r.status, "error": r.error,
                 "created_at": str(r.created_at)} for r in rows]


def create_paper_alert(account_id: int, stock_code: str, trade_date: str, values: dict) -> int:
    with SessionLocal() as db:
        account = db.get(PaperAccount, account_id)
        row = PaperAlert(account_id=account_id, stock_code=stock_code or "",
                         user_id=account.user_id if account else None,
                         trade_date=trade_date, severity=values.get("severity") or "info",
                         alert_type=values.get("alert_type") or "",
                         message=values.get("message") or "",
                         source=values.get("source") or "paper_monitor",
                         context_id=values.get("context_id"))
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_paper_alerts(account_id: int, limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(PaperAlert).where(PaperAlert.account_id == account_id)
                          .order_by(PaperAlert.id.desc()).limit(limit)).scalars().all()
        return [{"id": r.id, "account_id": r.account_id, "stock_code": r.stock_code,
                 "trade_date": r.trade_date, "severity": r.severity,
                 "alert_type": r.alert_type, "message": r.message, "source": r.source,
                 "context_id": r.context_id, "created_at": str(r.created_at)} for r in rows]


def create_paper_review(account_id: int, stock_code: str, stock_name: str,
                        review_date: str, content: dict, execution_id: int | None = None) -> int:
    with SessionLocal() as db:
        account = db.get(PaperAccount, account_id)
        row = PaperReview(account_id=account_id, execution_id=execution_id,
                          user_id=account.user_id if account else None,
                          stock_code=stock_code, stock_name=stock_name,
                          review_date=review_date, content=content or {}, source_type="paper")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_paper_review_for_user(review_id: int, user_id: int, *, is_admin: bool = False) -> PaperReview | None:
    with SessionLocal() as db:
        stmt = select(PaperReview).where(PaperReview.id == review_id)
        if not is_admin:
            stmt = stmt.where(PaperReview.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()


def list_paper_reviews(account_id: int | None = None, limit: int = 100,
                       user_id: int | None = None, *, is_admin: bool = False) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(PaperReview).order_by(PaperReview.id.desc())
        if account_id is not None:
            stmt = stmt.where(PaperReview.account_id == account_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(PaperReview.user_id == user_id)
        rows = db.execute(stmt.limit(limit)).scalars().all()
        return [{"id": r.id, "account_id": r.account_id, "execution_id": r.execution_id,
                 "user_id": r.user_id,
                 "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "review_date": r.review_date, "source_type": r.source_type,
                 "content": r.content or {}, "audit_status": r.audit_status,
                 "audit_verdict": r.audit_verdict, "audit_reason": r.audit_reason,
                 "shadow_status": r.shadow_status, "created_at": str(r.created_at),
                 "audited_at": str(r.audited_at) if r.audited_at else None} for r in rows]


def audit_paper_review(review_id: int, verdict: str, reason: str) -> dict | None:
    if verdict not in ("pass", "fail"):
        raise ValueError("审核结论仅支持 pass/fail")
    with SessionLocal() as db:
        row = db.get(PaperReview, review_id)
        if row is None:
            return None
        row.audit_status = "passed" if verdict == "pass" else "failed"
        row.audit_verdict, row.audit_reason, row.audited_at = verdict, reason or "", _now()
        if verdict != "pass":
            row.shadow_status = "blocked"
        db.commit()
        return {"id": row.id, "audit_status": row.audit_status,
                "audit_verdict": row.audit_verdict, "audit_reason": row.audit_reason,
                "shadow_status": row.shadow_status}


def mark_paper_shadow(review_id: int) -> dict | None:
    with SessionLocal() as db:
        row = db.get(PaperReview, review_id)
        if row is None:
            return None
        if row.audit_status != "passed":
            raise ValueError("模拟复盘必须先通过 AI 审核")
        row.shadow_status = "pending"
        db.commit()
        return {"id": row.id, "source_type": "paper", "shadow_status": row.shadow_status,
                "audit_status": row.audit_status}


def get_review(review_id: int) -> ReviewResult | None:
    with SessionLocal() as db:
        return db.get(ReviewResult, review_id)


def get_review_for_user(review_id: int, user_id: int, *, is_admin: bool = False) -> ReviewResult | None:
    with SessionLocal() as db:
        stmt = select(ReviewResult).where(ReviewResult.id == review_id)
        if not is_admin:
            stmt = stmt.where(ReviewResult.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()


def get_review_for_holding_exit(holding_id: int, exit_date: str) -> ReviewResult | None:
    """按持仓周期和离场日读取已有复盘，供复盘任务幂等保护使用。"""
    with SessionLocal() as db:
        return db.execute(
            select(ReviewResult).where(ReviewResult.holding_id == holding_id,
                                       ReviewResult.exit_date == exit_date)
            .order_by(ReviewResult.id.desc()).limit(1)
        ).scalar_one_or_none()


def list_sell_decisions(holding_id: int, limit: int = 10, user_id: int | None = None,
                        *, is_admin: bool = False) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(SellDecision).where(SellDecision.holding_id == holding_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(SellDecision.user_id == user_id)
        rows = db.execute(stmt.order_by(SellDecision.id.desc()).limit(limit)).scalars().all()
        return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                        "stock_name": r.stock_name,
                                        "decision": r.decision,
                                       "created_at": str(r.created_at)} for r in rows])


# ==================== 私有知识库（人工录入，Agent 启动自动检索注入） ====================

def knowledge_version(user_id: int | None = None) -> tuple[int, int]:
    """知识库变更感知（数量 + 最大ID），供 LLM 缓存键使用"""
    if user_id is None:
        user_id = _context_user_id(1 if settings.multi_user_enabled else None)
    with SessionLocal() as db:
        stmt = select(func.count(), func.max(PrivateKnowledge.id)).select_from(PrivateKnowledge)
        if user_id is not None:
            stmt = stmt.where((PrivateKnowledge.user_id == user_id) |
                              PrivateKnowledge.user_id.is_(None))
        count, max_id = db.execute(stmt).one()
        return int(count or 0), int(max_id or 0)


def add_knowledge(title: str, content: str, agent_tag: str = "all", *,
                  source_type: str = "manual", methodology_type: str = "general",
                  market_scope: str = "all", scenario_tags: list[str] | None = None,
                  evidence_level: str = "unverified", valid_from: datetime | None = None,
                  valid_to: datetime | None = None, status: str = "active",
                  risk_note: str = "", user_id: int | None = None) -> int:
    if user_id is None:
        user_id = _context_user_id(1)
    with SessionLocal() as db:
        row = PrivateKnowledge(
            title=title, content=content, agent_tag=agent_tag,
            source_type=source_type, methodology_type=methodology_type,
            market_scope=market_scope, scenario_tags=scenario_tags or [],
            evidence_level=evidence_level, valid_from=valid_from, valid_to=valid_to,
            status=status, risk_note=risk_note, user_id=user_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_knowledge(agent_tag: str | None = None, *, status: str | None = None,
                   source_type: str | None = None, methodology_type: str | None = None,
                   market_scope: str | None = None, scenario_tag: str | None = None,
                   user_id: int | None = None, is_admin: bool = False
                   ) -> list[PrivateKnowledge]:
    with SessionLocal() as db:
        stmt = select(PrivateKnowledge).order_by(PrivateKnowledge.id.desc())
        if user_id is not None and not is_admin:
            stmt = stmt.where(PrivateKnowledge.user_id == user_id)
        if agent_tag:
            stmt = stmt.where(PrivateKnowledge.agent_tag == agent_tag)
        if status:
            stmt = stmt.where(PrivateKnowledge.status == status)
        if source_type:
            stmt = stmt.where(PrivateKnowledge.source_type == source_type)
        if methodology_type:
            stmt = stmt.where(PrivateKnowledge.methodology_type == methodology_type)
        if market_scope:
            stmt = stmt.where(PrivateKnowledge.market_scope == market_scope)
        rows = list(db.execute(stmt).scalars().all())
        if scenario_tag:
            rows = [r for r in rows if scenario_tag in (r.scenario_tags or [])]
        return rows


def delete_knowledge(knowledge_id: int, user_id: int | None = None,
                     *, is_admin: bool = False) -> bool:
    with SessionLocal() as db:
        stmt = select(PrivateKnowledge).where(PrivateKnowledge.id == knowledge_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(PrivateKnowledge.user_id == user_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def update_knowledge_status(knowledge_id: int, status: str, reason: str = "",
                            user_id: int | None = None, *, is_admin: bool = False) -> bool:
    """人工调整知识生命周期；只改状态和留痕，不删除正文，不做自动升级。"""
    allowed = {"active", "shadow", "archived", "expired"}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    with SessionLocal() as db:
        stmt = select(PrivateKnowledge).where(PrivateKnowledge.id == knowledge_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(PrivateKnowledge.user_id == user_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        row.status = status
        note = (reason or "").strip()
        if note:
            stamp = _now().strftime("%Y-%m-%d %H:%M")
            entry = f"[{stamp} status->{status}] {note}"
            row.risk_note = "\n".join([p for p in [row.risk_note or "", entry] if p])
        db.commit()
        _invalidate("knowledge")
        return True


def record_knowledge_shadow_hit(knowledge_id: int, agent: str, stock_code: str,
                                stock_name: str, trade_date: str, query: str = "",
                                scenario_tags: list[str] | None = None,
                                shadow_bias: str = "unknown",
                                shadow_summary: str = "") -> int:
    """幂等记录 shadow 知识旁路命中；不写正式候选/评分/交易结果。"""
    allowed_bias = {"boost", "reduce", "risk", "neutral", "unknown"}
    if shadow_bias not in allowed_bias:
        shadow_bias = "unknown"
    with SessionLocal() as db:
        row = db.execute(
            select(KnowledgeShadowHit).where(
                KnowledgeShadowHit.knowledge_id == int(knowledge_id),
                KnowledgeShadowHit.agent == agent,
                KnowledgeShadowHit.stock_code == stock_code,
                KnowledgeShadowHit.trade_date == trade_date,
            )
        ).scalar_one_or_none()
        if row is None:
            row = KnowledgeShadowHit(
                knowledge_id=int(knowledge_id), agent=agent, stock_code=stock_code,
                stock_name=stock_name or "", trade_date=trade_date,
            )
            db.add(row)
        row.query = query or ""
        row.scenario_tags = scenario_tags or []
        row.shadow_bias = shadow_bias
        row.shadow_summary = shadow_summary or ""
        row.updated_at = _now()
        db.commit()
        db.refresh(row)
        _invalidate("knowledge_shadow_hit")
        return row.id


def list_knowledge_shadow_hits(knowledge_id: int | None = None, agent: str = "",
                               stock_code: str = "", trade_date: str = "",
                               verify_status: str = "", limit: int = 200) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(KnowledgeShadowHit).order_by(
                KnowledgeShadowHit.trade_date.desc(), KnowledgeShadowHit.id.desc())
            if knowledge_id is not None:
                stmt = stmt.where(KnowledgeShadowHit.knowledge_id == int(knowledge_id))
            if agent:
                stmt = stmt.where(KnowledgeShadowHit.agent == agent)
            if stock_code:
                stmt = stmt.where(KnowledgeShadowHit.stock_code == stock_code)
            if trade_date:
                stmt = stmt.where(KnowledgeShadowHit.trade_date == trade_date)
            if verify_status:
                stmt = stmt.where(KnowledgeShadowHit.verify_status == verify_status)
            rows = db.execute(stmt.limit(min(max(int(limit), 1), 500))).scalars().all()
            return [{
                "id": r.id, "knowledge_id": r.knowledge_id, "agent": r.agent,
                "stock_code": r.stock_code, "stock_name": r.stock_name,
                "trade_date": r.trade_date, "query": r.query or "",
                "scenario_tags": r.scenario_tags or [],
                "shadow_bias": r.shadow_bias or "unknown",
                "shadow_summary": r.shadow_summary or "",
                "t3_pct": r.t3_pct, "t5_pct": r.t5_pct, "t10_pct": r.t10_pct,
                "max_drawdown": r.max_drawdown,
                "verify_status": r.verify_status or "pending",
                "created_at": str(r.created_at), "updated_at": str(r.updated_at),
            } for r in rows]

    return _dbq("knowledge_shadow_hit",
                {"kid": knowledge_id, "agent": agent, "code": stock_code,
                 "date": trade_date, "status": verify_status, "limit": limit}, _load)


def refresh_knowledge_shadow_outcomes() -> dict:
    """从 CandidateTrackVerify 回填 shadow 命中的 T+N 后验表现，不改变 T+N 口径。"""
    with SessionLocal() as db:
        hits = db.execute(select(KnowledgeShadowHit)).scalars().all()
        updated = 0
        for hit in hits:
            verify = db.execute(
                select(CandidateTrackVerify).where(
                    CandidateTrackVerify.stock_code == hit.stock_code,
                    CandidateTrackVerify.select_date == hit.trade_date,
                )
            ).scalar_one_or_none()
            if verify is None:
                status = "pending"
                values = (None, None, None, None)
            else:
                values = (verify.t3_pct, verify.t5_pct, verify.t10_pct, verify.max_drawdown)
                has_any = any(v is not None for v in values)
                status = "finished" if verify.is_finished == 1 or verify.t10_pct is not None else (
                    "partial" if has_any else "pending")
            hit.t3_pct, hit.t5_pct, hit.t10_pct, hit.max_drawdown = values
            hit.verify_status = status
            hit.updated_at = _now()
            updated += 1
        db.commit()
        _invalidate("knowledge_shadow_hit")
        return {"updated": updated, "total": len(hits)}


def bump_knowledge_hits(knowledge_ids: list[int]) -> int:
    """私有知识命中计量（决策级归因）：hit_count+1 + last_used_at=now，批量一次 UPDATE。
    只加不自减（保留历史累计命中，不因"未用"清零）；空列表不执行；
    调用方已降级（知识检索/对话回吐失败仅 warning，不阻塞主链路）。"""
    ids = [int(i) for i in knowledge_ids if i]
    if not ids:
        return 0
    with SessionLocal() as db:
        res = db.execute(
            update(PrivateKnowledge)
            .where(PrivateKnowledge.id.in_(ids))
            .values(hit_count=PrivateKnowledge.hit_count + 1, last_used_at=datetime.now())
        )
        db.commit()
        return int(res.rowcount or 0)


# ==================== 卖出决策（SellAgent 输出，仅供参考） ====================

def insert_sell_decision(holding_id: int, stock_code: str, stock_name: str, decision: dict) -> int:
    with SessionLocal() as db:
        row = SellDecision(holding_id=holding_id, stock_code=stock_code,
                           stock_name=stock_name, decision=decision)
        db.add(row)
        task_queue.guarded_commit(db)
        db.refresh(row)
        # 推理留痕：sell 卖出决策依据/离场区间/检查清单
        reasoning_trace.trace_sell(stock_code, stock_name, _now().strftime("%Y-%m-%d"), decision)
        return row.id


def get_sell_decisions(holding_id: int) -> list[SellDecision]:
    with SessionLocal() as db:
        return list(db.execute(
            select(SellDecision).where(SellDecision.holding_id == holding_id)
            .order_by(SellDecision.id.desc())).scalars().all())


def get_latest_sell_decision(holding_id: int) -> SellDecision | None:
    with SessionLocal() as db:
        return db.execute(
            select(SellDecision).where(SellDecision.holding_id == holding_id)
            .order_by(SellDecision.id.desc()).limit(1)).scalar_one_or_none()


def get_sell_decisions_by_code(stock_code: str, limit: int = 20,
                               holding_id: int | None = None,
                               start_date: str | None = None,
                               end_date: str | None = None) -> list[SellDecision]:
    """读取卖出建议；可按持仓及生成日期限定历史事实窗口。"""
    with SessionLocal() as db:
        stmt = select(SellDecision).where(SellDecision.stock_code == stock_code)
        if holding_id is not None:
            stmt = stmt.where(SellDecision.holding_id == holding_id)
        if start_date:
            stmt = stmt.where(func.date(SellDecision.created_at) >= start_date)
        if end_date:
            stmt = stmt.where(func.date(SellDecision.created_at) <= end_date)
        return list(db.execute(
            stmt.order_by(SellDecision.id.desc()).limit(limit)).scalars().all())


# ==================== 策略闭环建议（复盘进化Agent 输出，人工审核后生效） ====================

def insert_agent_suggestion(review_id: int, target_agent: str, rule_name: str,
                            current_value: str, suggested_value: str,
                            reason: str, evidence: str,
                            target_kind: str = "profile",
                            rule_type: str = "soft", priority: str = "medium",
                            problem_desc: str = "", rule_text: str = "",
                            expected_effect: str = "", risk_note: str = "",
                            file_path: str = "", insert_position: str = "",
                            suggestion_source: str = "llm",
                            user_id: int | None = None) -> int:
    if user_id is None:
        user_id = _context_user_id(1)
    with SessionLocal() as db:
        if review_id:
            review = db.get(ReviewResult, review_id)
            if review and review.user_id is not None:
                user_id = review.user_id
        row = AgentSuggestion(review_id=review_id, target_agent=target_agent, rule_name=rule_name,
                              current_value=current_value, suggested_value=suggested_value,
                              reason=reason, evidence=evidence,
                              target_kind=target_kind, status="pending",
                              rule_type=rule_type, priority=priority,
                              problem_desc=problem_desc, rule_text=rule_text,
                               expected_effect=expected_effect, risk_note=risk_note,
                               file_path=file_path, insert_position=insert_position,
                               suggestion_source=suggestion_source, user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


# ==================== 通用审核 Agent（批1：audit_log + agent_suggestion audit 字段） ====================

def insert_audit_log(target_type: str, target_id: int, audit_round: int, verdict: str,
                     confidence: int, support_view: str, dissent_view: str, boundary_cases: str,
                     evidence_refs: list, audit_model: str, reasoning: str,
                     duration_ms: int, user_id: int | None = None) -> int:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        row = AuditLog(target_type=target_type, target_id=target_id, round=audit_round,
                       verdict=verdict, confidence=confidence, support_view=support_view,
                       dissent_view=dissent_view, boundary_cases=boundary_cases,
                       evidence_refs=evidence_refs or [], audit_model=audit_model,
                       reasoning=reasoning or "", duration_ms=duration_ms,
                       user_id=owner_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_audit_log(audit_id: int, user_id: int | None = None) -> AuditLog | None:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(AuditLog).where(AuditLog.id == audit_id)
        if owner_id is not None:
            stmt = stmt.where(AuditLog.user_id == owner_id)
        return db.execute(stmt).scalar_one_or_none()


def get_latest_audit_log_by_target(target_type: str, target_id: int,
                                   user_id: int | None = None) -> dict | None:
    """按目标查最新一条审核记录（created_at desc；含 dissent_view 完整字段）；无 → None"""
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(AuditLog).where(AuditLog.target_type == target_type,
                                      AuditLog.target_id == target_id)
        if owner_id is not None:
            stmt = stmt.where(AuditLog.user_id == owner_id)
        row = db.execute(
            stmt
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {"id": row.id, "target_type": row.target_type, "target_id": row.target_id,
                "round": row.round, "verdict": row.verdict, "confidence": row.confidence,
                "support_view": row.support_view, "dissent_view": row.dissent_view,
                "boundary_cases": row.boundary_cases, "evidence_refs": row.evidence_refs or [],
                "audit_model": row.audit_model, "reasoning": row.reasoning,
                "duration_ms": row.duration_ms, "created_at": str(row.created_at)}


def update_audit_log_verdict(audit_id: int, verdict: str, user_id: int | None = None) -> None:
    """人工/应急标绿（批4 confirm-fail 前留位）：仅改 verdict"""
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(AuditLog).where(AuditLog.id == audit_id)
        if owner_id is not None:
            stmt = stmt.where(AuditLog.user_id == owner_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            return
        row.verdict = verdict
        db.commit()


def update_agent_suggestion_audit(suggestion_id: int, audit_verdict: str,
                                  audit_round: int, last_audit_id: int | None,
                                  user_id: int | None = None) -> None:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(AgentSuggestion).where(AgentSuggestion.id == suggestion_id)
        if owner_id is not None:
            stmt = stmt.where(AgentSuggestion.user_id == owner_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            return
        row.audit_verdict = audit_verdict
        row.audit_round = audit_round
        row.last_audit_id = last_audit_id
        db.commit()


def list_agent_suggestions_for_audit(cursor_id: int, limit: int = 50,
                                     user_id: int | None = None) -> list[AgentSuggestion]:
    """扫描待审/漏审/未完成二审的建议（id > 游标；pass 或 round2-fail 不再返回）"""
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(AgentSuggestion).where(
                AgentSuggestion.id > cursor_id,
                or_(AgentSuggestion.audit_verdict == "pending",
                    AgentSuggestion.last_audit_id.is_(None),
                    and_(AgentSuggestion.audit_verdict == "fail",
                         AgentSuggestion.audit_round < 2)))
        if owner_id is not None:
            stmt = stmt.where(AgentSuggestion.user_id == owner_id)
        return list(db.execute(stmt.order_by(AgentSuggestion.id).limit(limit)).scalars().all())


def get_agent_suggestion(suggestion_id: int) -> AgentSuggestion | None:
    with SessionLocal() as db:
        return db.get(AgentSuggestion, suggestion_id)


def get_agent_suggestion_for_user(suggestion_id: int, user_id: int,
                                  *, is_admin: bool = False) -> AgentSuggestion | None:
    with SessionLocal() as db:
        stmt = select(AgentSuggestion).where(AgentSuggestion.id == suggestion_id)
        if not is_admin:
            stmt = stmt.where(AgentSuggestion.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()


def get_agent_suggestions(review_id: int | None = None,
                          status: str | None = None,
                          user_id: int | None = None,
                          *, is_admin: bool = False) -> list[AgentSuggestion]:
    with SessionLocal() as db:
        stmt = select(AgentSuggestion).order_by(AgentSuggestion.id.desc())
        if user_id is not None and not is_admin:
            stmt = stmt.where(AgentSuggestion.user_id == user_id)
        if review_id is not None:
            stmt = stmt.where(AgentSuggestion.review_id == review_id)
        if status:
            stmt = stmt.where(AgentSuggestion.status == status)
        return list(db.execute(stmt).scalars().all())


def update_agent_suggestion_status(suggestion_id: int, status: str,
                                   reason: str = "") -> AgentSuggestion | None:
    """人工审核动作：approved / rejected（严格禁止系统自动修改，仅人工调用）；
    reason 为驳回原因（审核留痕，驳回时必填由前端约束，此处仅落库）"""
    with SessionLocal() as db:
        row = db.get(AgentSuggestion, suggestion_id)
        if row is None:
            return None
        row.status = status
        if status == "rejected" and reason:
            row.reject_reason = reason.strip()
        # profile 建议与复盘反馈共用 source_review_id；采纳建议时打开该复盘
        # 的最新偏好版本，避免 feedback 在建议审核前旁路进入评分。
        if status == "approved" and row.target_kind == "profile":
            pref = db.execute(
                select(AgentPreference).where(
                    AgentPreference.source_review_id == row.review_id
                ).order_by(AgentPreference.version.desc()).limit(1)
            ).scalar_one_or_none()
            if pref is not None:
                pref.status = "active"
        db.commit()
        db.refresh(row)
        return row


def reset_agent_suggestion_to_pending(suggestion_id: int) -> AgentSuggestion | None:
    """重新审核：仅 rejected → pending，并清空驳回原因。"""
    with SessionLocal() as db:
        row = db.get(AgentSuggestion, suggestion_id)
        if row is None:
            return None
        if row.status != "rejected":
            return row
        row.status = "pending"
        row.reject_reason = ""
        db.commit()
        db.refresh(row)
        return row


def update_agent_suggestion_notes(suggestion_id: int, conflict_note: str = "",
                                  dedup_note: str = "") -> None:
    """校验拦截回填：采纳被拦时把冲突/去重说明写回建议记录（前端直接展示原因）"""
    with SessionLocal() as db:
        row = db.get(AgentSuggestion, suggestion_id)
        if row is None:
            return
        row.conflict_note = conflict_note
        row.dedup_note = dedup_note
        db.commit()


# ==================== 复盘采纳规则（一键采纳自动落地：规则存库 + agent_call 动态注入） ====================

def get_active_rules(user_id: int | None = None) -> list[dict]:
    """生效中规则列表（agent_call 注入数据源；采纳/回滚后 _invalidate 失效）"""
    if user_id is None:
        user_id = _context_user_id(1 if settings.multi_user_enabled else None)

    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(RuleChange).where(RuleChange.status == "active")
            if user_id is not None:
                stmt = stmt.where((RuleChange.user_id == user_id) | RuleChange.user_id.is_(None))
            rows = db.execute(stmt.order_by(RuleChange.id)).scalars().all()
            return [{"id": r.id, "target_agent": r.target_agent, "rule_type": r.rule_type,
                      "rule_name": r.rule_name, "rule_text": r.rule_text} for r in rows]

    return _dbq("rule_change", {"active": 1, "user_id": user_id}, _load)


def rule_version(user_id: int | None = None) -> str:
    """生效规则内容指纹（count+max_id）→ 入 LLM 缓存键：
    采纳/回滚后指纹变化，当日 LLM 缓存自动失效（同 _knowledge_version 语义）"""
    if user_id is None:
        user_id = _context_user_id(1 if settings.multi_user_enabled else None)

    def _load() -> list:
        with SessionLocal() as db:
            stmt = select(func.count(), func.max(RuleChange.id)).select_from(RuleChange).where(
                RuleChange.status == "active")
            if user_id is not None:
                stmt = stmt.where((RuleChange.user_id == user_id) | RuleChange.user_id.is_(None))
            cnt, max_id = db.execute(stmt).one()
            return [{"count": int(cnt), "max_id": int(max_id or 0)}]

    rows = _dbq("rule_change", {"ver": 1, "user_id": user_id}, _load)
    row = rows[0] if rows else {}
    return f"{row.get('count', 0)}:{row.get('max_id', 0)}"


def list_rule_changes(status: str | None = None, target_agent: str | None = None,
                      suggestion_id: int | None = None, limit: int = 50,
                      user_id: int | None = None, *, is_admin: bool = False) -> list[dict]:
    """规则变更记录轻量列表（记录页数据源，不含长文本；详情按需单查）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(RuleChange).order_by(RuleChange.id.desc()).limit(limit)
            if user_id is not None and not is_admin:
                stmt = stmt.where(RuleChange.user_id == user_id)
            if status:
                stmt = stmt.where(RuleChange.status == status)
            if target_agent:
                stmt = stmt.where(RuleChange.target_agent == target_agent)
            if suggestion_id is not None:
                stmt = stmt.where(RuleChange.source_suggestion_id == suggestion_id)
            rows = db.execute(stmt).scalars().all()
            return [{"id": r.id, "source_suggestion_id": r.source_suggestion_id,
                     "review_id": r.review_id, "stock_code": r.stock_code,
                     "stock_name": r.stock_name, "target_agent": r.target_agent,
                     "rule_type": r.rule_type, "rule_name": r.rule_name,
                     "rule_text": r.rule_text, "priority": r.priority,
                     "status": r.status, "operator": r.operator,
                     "user_id": r.user_id,
                     "created_at": str(r.created_at),
                     "rollback_time": r.rollback_time} for r in rows]

    return _dbq("rule_change", {"status": status, "agent": target_agent,
                                "suggestion_id": suggestion_id, "limit": limit,
                                "user_id": user_id, "admin": is_admin}, _load)


def get_rule_change(rule_change_id: int, user_id: int | None = None,
                    *, is_admin: bool = False) -> dict | None:
    """规则变更完整详情（变更前后对比/回滚原因/落地元数据，供记录页展开）"""
    def _load() -> list:
        with SessionLocal() as db:
            r = db.get(RuleChange, rule_change_id)
            if r is None:
                return []
            if user_id is not None and not is_admin and r.user_id != user_id:
                return []
            return [{"id": r.id, "source_suggestion_id": r.source_suggestion_id,
                     "review_id": r.review_id, "stock_code": r.stock_code,
                     "stock_name": r.stock_name, "target_agent": r.target_agent,
                     "rule_type": r.rule_type, "rule_name": r.rule_name,
                     "rule_text": r.rule_text, "priority": r.priority,
                     "before_text": r.before_text, "after_text": r.after_text,
                     "reason": r.reason, "evidence": r.evidence,
                     "expected_effect": r.expected_effect, "risk_note": r.risk_note,
                     "file_path": r.file_path, "insert_position": r.insert_position,
                      "status": r.status, "rollback_reason": r.rollback_reason,
                      "rollback_time": r.rollback_time, "operator": r.operator,
                      "user_id": r.user_id,
                      "created_at": str(r.created_at)}]

    rows = _dbq("rule_change", {"detail": rule_change_id, "user_id": user_id,
                                "admin": is_admin}, _load)
    return rows[0] if rows else None


def adopt_rule_suggestion(suggestion_id: int, operator: str = "") -> int:
    """一键采纳：写 rule_change(status=active) + 建议置 approved（单事务，并发兜底复查 pending）。
    返回 rule_change.id；建议不存在或已处理返回 0。"""
    with SessionLocal() as db:
        sug = db.get(AgentSuggestion, suggestion_id)
        if sug is None or sug.status != "pending":
            return 0
        review = db.get(ReviewResult, sug.review_id) if sug.review_id else None
        change = RuleChange(
            source_suggestion_id=sug.id,
            review_id=sug.review_id,
            stock_code=review.stock_code if review else "",
            stock_name=review.stock_name if review else "",
            target_agent=sug.target_agent,
            rule_type=sug.rule_type or "soft",
            rule_name=sug.rule_name,
            rule_text=sug.rule_text,
            priority=sug.priority or "medium",
            before_text="（此前无生效规则）",
            after_text=sug.rule_text,
            reason=sug.reason,
            evidence=sug.evidence,
            expected_effect=sug.expected_effect,
            risk_note=sug.risk_note,
            file_path=sug.file_path,
            insert_position=sug.insert_position,
            operator=operator,
            user_id=sug.user_id or (review.user_id if review else None),
        )
        db.add(change)
        sug.status = "approved"
        db.commit()
        db.refresh(change)
        _invalidate("rule_change")
        return change.id


def rollback_rule_change(rule_change_id: int, reason: str, user_id: int | None = None,
                         *, is_admin: bool = False) -> bool:
    """一键回滚：status=active → rolled_back + 原因/时间留痕；返回是否成功"""
    with SessionLocal() as db:
        stmt = select(RuleChange).where(RuleChange.id == rule_change_id)
        if user_id is not None and not is_admin:
            stmt = stmt.where(RuleChange.user_id == user_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None or row.status != "active":
            return False
        row.status = "rolled_back"
        row.rollback_reason = reason.strip()
        row.rollback_time = _now().strftime("%Y-%m-%d %H:%M")
        db.commit()
        _invalidate("rule_change")
        return True


# ==================== 监控信号历史（ReviewAgent 复盘聚合用） ====================

def get_alerts_by_code(stock_code: str, limit: int = 50,
                       start_date: str | None = None,
                       end_date: str | None = None) -> list[AlertLog]:
    """读取告警日志；可限定 created_at 落在指定日期闭区间内。"""
    with SessionLocal() as db:
        stmt = select(AlertLog).where(AlertLog.stock_code == stock_code)
        if start_date:
            stmt = stmt.where(func.date(AlertLog.created_at) >= start_date)
        if end_date:
            stmt = stmt.where(func.date(AlertLog.created_at) <= end_date)
        return list(db.execute(
            stmt.order_by(AlertLog.id.desc()).limit(limit)).scalars().all())


# ==================== Agent 专属对话（Agent 对话页，全程可回溯） ====================

def add_chat_message(agent: str, role: str, content: str, message_type: str = "qa",
                     verdict: str = "", knowledge_id: int | None = None,
                     meta: dict | None = None) -> int:
    """记录一条 Agent 对话消息（问答/规则调教/多模态学习）"""
    from app.db.models import AgentChatMessage

    with SessionLocal() as db:
        row = AgentChatMessage(agent=agent, role=role, content=content,
                               message_type=message_type, verdict=verdict,
                               knowledge_id=knowledge_id, meta=meta or {})
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_chat_messages(agent: str, limit: int = 50, message_type: str | None = None) -> list[dict]:
    """某 Agent 的对话历史（最新在前）；message_type 可选过滤（如 batch=批量对话）"""
    from app.db.models import AgentChatMessage

    with SessionLocal() as db:
        stmt = (select(AgentChatMessage)
                .where(AgentChatMessage.agent == agent))
        if message_type:
            stmt = stmt.where(AgentChatMessage.message_type == message_type)
        stmt = stmt.order_by(AgentChatMessage.id.desc()).limit(min(limit, 200))
        rows = list(db.execute(stmt).scalars().all())
    return [{"id": r.id, "agent": r.agent, "role": r.role, "message_type": r.message_type,
             "content": r.content, "verdict": r.verdict, "knowledge_id": r.knowledge_id,
             "meta": r.meta or {}, "created_at": str(r.created_at)}
            for r in rows]


# ================= 游资档案（hot_money_profile，低频字典） =================

def upsert_hot_money_profile(actor_name: str, seat_code: str, tier: str = "观察",
                             style_tags: list | None = None, good_themes: list | None = None,
                             co_seats: list | None = None, source: str = "手动") -> int:
    """按 seat_code 幂等 upsert 游资档案（一席位一主力游资）"""
    with SessionLocal() as db:
        row = db.execute(select(HotMoneyProfile).where(
            HotMoneyProfile.seat_code == seat_code)).scalar_one_or_none()
        if row is None:
            row = HotMoneyProfile(actor_name=actor_name, seat_code=seat_code, tier=tier,
                                  style_tags=style_tags or [], good_themes=good_themes or [],
                                  co_seats=co_seats or [], source=source)
            db.add(row)
        else:
            row.actor_name = actor_name
            row.tier = tier
            row.style_tags = style_tags or row.style_tags or []
            row.good_themes = good_themes or row.good_themes or []
            row.co_seats = co_seats or row.co_seats or []
            row.source = source
        db.commit()
        db.refresh(row)
        _invalidate("hot_money")
        return row.id


def seed_default_hot_money_profiles() -> int:
    """初始游资档案种子（幂等：按 seat_code 已存在则跳过）。
    ⚠️ 席位名仅作模糊匹配参考（源文件示例），真实席位以抓到的龙虎榜为准。"""
    seeds = [
        # (游资名, 席位名, 梯队, 风格标签, 擅长题材)
        ("赵老哥", "中信证券上海分公司", "一线",
         ["高位接力", "题材龙头"], ["次新", "科技"]),
        ("章盟主", "国泰君安证券上海分公司", "一线",
         ["趋势跟随", "大市值票"], ["蓝筹", "白马"]),
        ("孙哥", "中信证券杭州延安路", "一线",
         ["打板", "情绪票"], ["连板", "题材"]),
        ("欢乐海", "华泰证券深圳益田路荣超商务中心", "一线",
         ["低吸", "首板"], ["题材轮动"]),
        ("佛山系", "光大证券佛山绿景路", "二线",
         ["反包", "超跌反弹"], ["低价股"]),
        ("炒股养家", "华鑫证券上海分公司", "二线",
         ["趋势", "波段"], ["科技", "新能源"]),
        ("宁波桑田路", "国盛证券宁波桑田路", "二线",
         ["打板", "接力"], ["次新", "军工"]),
    ]
    n = 0
    for actor, seat, tier, tags, themes in seeds:
        try:
            upsert_hot_money_profile(actor, seat, tier, tags, themes,
                                     source="手动·种子参考")
            n += 1
        except Exception:  # noqa: BLE001 单条种子失败不阻断（如席位冲突）
            logger.warning("游资种子写入失败: %s/%s", actor, seat)
    return n


def list_hot_money_profiles() -> list[dict]:
    """全部游资档案（模糊匹配用；含游资复盘胜率统计字段）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            rows = db.execute(select(HotMoneyProfile)
                              .order_by(HotMoneyProfile.id)).scalars().all()
        return [{"id": r.id, "actor_name": r.actor_name, "seat_code": r.seat_code,
                 "tier": r.tier, "style_tags": r.style_tags or [],
                 "good_themes": r.good_themes or [], "co_seats": r.co_seats or [],
                 "source": r.source, "win_rate_5d": r.win_rate_5d,
                 "last_review_at": r.last_review_at or "",
                 "updated_at": str(r.updated_at)}
                for r in rows]

    return _dbq("hot_money", {}, _load)


def get_profile_by_actor(actor_name: str) -> dict | None:
    """游资名 → 档案（精确匹配，未命中 None）；权重迭代建议应用用"""
    name = (actor_name or "").strip()
    if not name:
        return None
    for p in list_hot_money_profiles():
        if p["actor_name"] == name:
            return p
    return None


def update_profile_win_rate(profile_id: int, win_rate_5d: float | None,
                            last_review_at: str) -> None:
    """胜率迭代事实落库：win_rate_5d（信号后5日上涨胜率，代码统计事实）+
    last_review_at（迭代时间）。只写统计事实，不改 tier——降/升档必须经人工审核。"""
    with SessionLocal() as db:
        row = db.execute(select(HotMoneyProfile).where(
            HotMoneyProfile.id == profile_id)).scalar_one_or_none()
        if row is None:
            return
        row.win_rate_5d = win_rate_5d
        row.last_review_at = last_review_at
        db.commit()
        _invalidate("hot_money")


def get_profile_by_seat(seat_name: str) -> dict | None:
    """席位 → 游资档案：先精确匹配，再停用词归一化后包含模糊匹配；未命中返回 None。
    真实龙虎榜席位名带「股份有限公司/证券营业部」等后缀（如 中信证券股份有限公司上海分公司），
    种子席位名为简写（中信证券上海分公司）——归一化后即可命中。"""
    seat = (seat_name or "").strip()
    if not seat:
        return None
    for p in list_hot_money_profiles():
        if p["seat_code"] == seat:
            return p
    # 停用词归一化：去掉公司/营业部常见后缀词，保留主体（如 中信证券股份有限公司上海分公司
    # → 中信 上海分公司），种子与真实席位都归一化后做包含匹配
    norm = normalize_seat(seat)
    for p in list_hot_money_profiles():
        p_norm = normalize_seat(p.get("seat_code") or "")
        if p_norm and (p_norm in norm or norm in p_norm):
            return p
    return None


def normalize_seat(seat: str) -> str:
    """席位名停用词归一化（模糊匹配辅助，非市场判断；游资信号归一化匹配复用）"""
    for word in ("股份有限公司", "有限责任公司", "证券营业部", "营业部", "证券", "分公司"):
        seat = seat.replace(word, "")
    return seat.strip()


# ================= 龙虎榜原始流水（lhb_original_flow，口径硬隔离） =================

def insert_lhb_flows(rows: list[dict]) -> int:
    """批量插入龙虎榜流水（rows: trade_date/stock_code/stock_name/lhb_type/
    disclosure_reason/seat_name/buy_amt/sell_amt/net_buy/confidence/source/
    multi_source_verified）"""
    if not rows:
        return 0
    with SessionLocal() as db:
        for r in rows:
            db.add(LhbOriginalFlow(
                trade_date=r["trade_date"], stock_code=r["stock_code"],
                stock_name=r.get("stock_name", ""), lhb_type=r.get("lhb_type", "1d"),
                disclosure_reason=r.get("disclosure_reason", ""),
                seat_name=r.get("seat_name", ""),
                buy_amt=float(r.get("buy_amt") or 0.0), sell_amt=float(r.get("sell_amt") or 0.0),
                net_buy=float(r.get("net_buy") or 0.0),
                confidence=float(r.get("confidence") or 1.0),
                source=r.get("source", "eastmoney"),
                multi_source_verified=bool(r.get("multi_source_verified") or False)))
        db.commit()
        _invalidate("lhb")
    return len(rows)


def list_lhb_flows(trade_date: str | None = None, stock_code: str | None = None,
                   lhb_type: str | None = None, seat_name: str | None = None,
                   limit: int = 2000) -> list[dict]:
    """龙虎榜流水查询（按 日期/标的/口径/席位 过滤；游资信号回溯用 seat_name）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(LhbOriginalFlow).order_by(LhbOriginalFlow.id.desc())
            if trade_date:
                stmt = stmt.where(LhbOriginalFlow.trade_date == trade_date)
            if stock_code:
                stmt = stmt.where(LhbOriginalFlow.stock_code == stock_code)
            if lhb_type:
                stmt = stmt.where(LhbOriginalFlow.lhb_type == lhb_type)
            if seat_name:
                stmt = stmt.where(LhbOriginalFlow.seat_name == seat_name)
            rows = db.execute(stmt.limit(limit)).scalars().all()
        return [{"id": r.id, "trade_date": r.trade_date, "stock_code": r.stock_code,
                 "stock_name": r.stock_name, "lhb_type": r.lhb_type,
                 "disclosure_reason": r.disclosure_reason, "seat_name": r.seat_name,
                 "buy_amt": r.buy_amt, "sell_amt": r.sell_amt, "net_buy": r.net_buy,
                 "confidence": r.confidence, "source": r.source,
                 "multi_source_verified": bool(r.multi_source_verified),
                 "created_at": str(r.created_at)} for r in rows]

    return _dbq("lhb", {"trade_date": trade_date, "stock_code": stock_code,
                        "lhb_type": lhb_type, "seat_name": seat_name, "limit": limit}, _load)


def hot_money_fingerprint() -> str:
    """游资数据指纹（供 LLM cache_key 并入，防缓存吞新数据）：
    龙虎榜流水的最近写入时间 + 行数；无数据返回 '0'"""
    with SessionLocal() as db:
        n = db.execute(select(func.count()).select_from(LhbOriginalFlow)).scalar_one()
        last = db.execute(select(func.max(LhbOriginalFlow.created_at))).scalar_one()
    return f"{n}:{last.strftime('%Y%m%d%H%M%S') if last else '0'}"


# ==================== 批次E 资本视图 4 表落库（游资真接入；聚合由 services/capital_view 计算） ====================

def upsert_capital_view(snapshot: dict) -> int:
    """资本视图快照落库 4 表（同 stock_code+trade_date 删后插，仿 upsert_sector_snapshot）。
    snapshot 字段：trade_date/stock_code 必填；recent_actors/dragon_tiger_rows/capital_flow_rows/
    stats(wash_suspect/coordination/win_rate/payoff_ratio/avg_hold_days/theme_resonance/
    source/missing_data)/raw。返回写入行数。"""
    trade_date = snapshot.get("trade_date", "")
    stock_code = snapshot.get("stock_code", "")
    if not trade_date or not stock_code:
        return 0
    source = snapshot.get("source", "sse_only")
    stats = snapshot.get("stats") or {}
    with SessionLocal() as db:
        db.execute(text("DELETE FROM capital_actor WHERE trade_date = :d AND stock_code = :c"),
                   {"d": trade_date, "c": stock_code})
        for a in snapshot.get("recent_actors") or []:
            db.add(CapitalActor(trade_date=trade_date, stock_code=stock_code,
                                actor_name=a.get("name", ""), seat_code=a.get("seat") or "",
                                tier=a.get("tier") or "观察", net_buy=float(a.get("net_buy") or 0),
                                days_active=int(a.get("days_active") or 0), source=source))
        db.execute(text("DELETE FROM dragon_tiger WHERE trade_date = :d AND stock_code = :c"),
                   {"d": trade_date, "c": stock_code})
        for r in snapshot.get("dragon_tiger_rows") or []:
            db.add(DragonTiger(trade_date=r.get("trade_date", trade_date), stock_code=stock_code,
                               stock_name=r.get("stock_name", ""), lhb_type=r.get("lhb_type", "1d"),
                               net_buy=float(r.get("net_buy") or 0), buy_amt=float(r.get("buy_amt") or 0),
                               sell_amt=float(r.get("sell_amt") or 0), top_seat=r.get("top_seat") or "",
                               top_seat_net=float(r.get("top_seat_net") or 0),
                               disclosure_reason=r.get("disclosure_reason") or "",
                               confidence=float(r.get("confidence") or 0.8), source=source))
        db.execute(text("DELETE FROM capital_flow WHERE trade_date = :d AND stock_code = :c"),
                   {"d": trade_date, "c": stock_code})
        for f in snapshot.get("capital_flow_rows") or []:
            db.add(CapitalFlow(trade_date=f.get("trade_date", trade_date), stock_code=stock_code,
                               main_net_inflow=float(f.get("main_net_inflow") or 0),
                               super_large_net=float(f.get("super_large_net") or 0),
                               large_net=float(f.get("large_net") or 0),
                               medium_net=float(f.get("medium_net") or 0),
                               small_net=float(f.get("small_net") or 0), source=source))
        db.execute(text("DELETE FROM capital_stats WHERE trade_date = :d AND stock_code = :c"),
                   {"d": trade_date, "c": stock_code})
        db.add(CapitalStats(trade_date=trade_date, stock_code=stock_code,
                            wash_suspect=bool(stats.get("wash_suspect")),
                            coordination=stats.get("coordination") or "数据不足",
                            win_rate=stats.get("win_rate"), payoff_ratio=stats.get("payoff_ratio"),
                            avg_hold_days=stats.get("avg_hold_days"),
                            theme_resonance=stats.get("theme_resonance"),
                            source=source, missing_data=stats.get("missing_data") or [],
                            raw_json=snapshot.get("raw") or {}))
        db.commit()
    return 1 + len(snapshot.get("recent_actors") or []) + len(snapshot.get("dragon_tiger_rows") or []) \
        + len(snapshot.get("capital_flow_rows") or [])


def get_capital_stats(stock_code: str, trade_date: str) -> dict | None:
    """读资本视图统计快照（capitals × 展示用；不存在返回 None）"""
    with SessionLocal() as db:
        stmt = (select(CapitalStats).where(CapitalStats.stock_code == stock_code,
                                           CapitalStats.trade_date == trade_date)
                .order_by(CapitalStats.id.desc()).limit(1))
        row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    return {"trade_date": row.trade_date, "stock_code": row.stock_code,
            "wash_suspect": bool(row.wash_suspect), "coordination": row.coordination,
            "win_rate": row.win_rate, "payoff_ratio": row.payoff_ratio,
            "avg_hold_days": row.avg_hold_days, "theme_resonance": row.theme_resonance,
            "source": row.source, "missing_data": row.missing_data or [],
            "updated_at": str(row.updated_at)}


# ==================== 经验沉淀闭环（pending → worker → experience → review_log → 检索注入） ====================

def _parse_monitor_summary(summary):
    """summary "000725 监控信号 hold" → (000725, hold)；其他形态（候选 N 只/评分/建仓/复盘）→ (None, None)"""
    if not summary:
        return None, None
    parts = str(summary).split(" 监控信号 ")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return None, None
    return parts[0].strip(), parts[1].strip()


def _artifacts_meta(ref, code, sig, original_ref) -> dict:
    """artifacts_ref 读兼容：新 JSON 直接解；旧 int/其他 → 从零构造（旧数据读不报错）"""
    if ref:
        try:
            meta = json.loads(ref)
            if isinstance(meta, dict):
                meta.setdefault("count", 1)
                meta.setdefault("first_at", datetime.now().isoformat(timespec="seconds"))
                meta.setdefault("last_at", datetime.now().isoformat(timespec="seconds"))
                meta.setdefault("stock_code", code)
                meta.setdefault("signal_type", sig)
                meta.setdefault("original_ref", original_ref)
                return meta
        except (TypeError, ValueError):
            pass
    now = datetime.now().isoformat(timespec="seconds")
    return {"count": 1, "first_at": now, "last_at": now, "stock_code": code,
            "signal_type": sig, "original_ref": original_ref}


def merge_pending_duplicate(task_id, stage, summary, artifacts_ref, user_id=None) -> int | None:
    """Merge same-hour pending signal only within the current account."""
    owner_id = _experience_scope_user(user_id)
    code, sig = _parse_monitor_summary(summary)
    if not code:
        return None
    hour_start = datetime.now().replace(minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        stmt = select(PendingExperience).where(PendingExperience.status == "pending", PendingExperience.created_at >= hour_start)
        if owner_id is not None:
            stmt = stmt.where(PendingExperience.user_id == owner_id)
        for r in db.execute(stmt.order_by(PendingExperience.id.desc())).scalars().all():
            r_code, r_sig = _parse_monitor_summary(r.summary)
            if r_code == code and r_sig == sig:
                meta = _artifacts_meta(r.artifacts_ref, code, sig, str(artifacts_ref or ""))
                meta["count"] = int(meta.get("count") or 1) + 1
                meta["last_at"] = datetime.now().isoformat(timespec="seconds")
                r.artifacts_ref = json.dumps(meta, ensure_ascii=False)
                db.commit(); _invalidate("pending_experience")
                return r.id
    return None


def add_pending_experience(task_id, stage, summary, artifacts_ref, user_id=None) -> int:
    owner_id = _experience_scope_user(user_id)
    merged = merge_pending_duplicate(task_id, stage, summary, artifacts_ref, owner_id)
    if merged:
        return merged
    code, sig = _parse_monitor_summary(summary)
    meta = _artifacts_meta(artifacts_ref, code, sig, str(artifacts_ref or ""))
    with SessionLocal() as db:
        row = PendingExperience(task_id=task_id, stage=stage, summary=summary, artifacts_ref=json.dumps(meta, ensure_ascii=False), status="pending", user_id=owner_id)
        db.add(row); db.commit(); _invalidate("pending_experience"); return row.id


def list_pending_experience(status=None, stage=None, limit=50, user_id=None) -> list:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(PendingExperience)
        if owner_id is not None: stmt = stmt.where(PendingExperience.user_id == owner_id)
        if status: stmt = stmt.where(PendingExperience.status == status)
        if stage: stmt = stmt.where(PendingExperience.stage == stage)
        rows = db.execute(stmt.order_by(PendingExperience.id.desc()).limit(limit)).scalars().all()
        return [_pending_row(r) for r in rows]


def claim_pending_batch(batch_size=20, user_id=None) -> list:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(PendingExperience).where(PendingExperience.status == "pending")
        if owner_id is not None: stmt = stmt.where(PendingExperience.user_id == owner_id)
        pending = db.execute(stmt.order_by(PendingExperience.id).limit(batch_size)).scalars().all()
        claimed = []
        for row in pending:
            q = PendingExperience.__table__.update().where(PendingExperience.id == row.id, PendingExperience.status == "pending")
            if owner_id is not None: q = q.where(PendingExperience.user_id == owner_id)
            res = db.execute(q.values(status="processing"))
            if res.rowcount == 1: claimed.append(_pending_row(row))
        if claimed: db.commit(); _invalidate("pending_experience")
        return claimed


def release_pending(id, error=None, user_id=None) -> None:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(PendingExperience).where(PendingExperience.id == id)
        if owner_id is not None: stmt = stmt.where(PendingExperience.user_id == owner_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None: return
        row.status = "done"; row.error = error; db.commit(); _invalidate("pending_experience")


def watchdog_reset_stale_processing(older_than_hours=2.0, user_id=None) -> int:
    owner_id = _experience_scope_user(user_id)
    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    with SessionLocal() as db:
        stmt = select(PendingExperience).where(PendingExperience.status == "processing", PendingExperience.created_at < cutoff)
        if owner_id is not None: stmt = stmt.where(PendingExperience.user_id == owner_id)
        rows = db.execute(stmt).scalars().all()
        for row in rows: row.status = "pending"; row.error = "watchdog_timeout"
        if rows: db.commit(); _invalidate("pending_experience")
        return len(rows)


def pending_backlog_count(user_id=None) -> int:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(func.count()).select_from(PendingExperience).where(PendingExperience.status == "pending")
        if owner_id is not None: stmt = stmt.where(PendingExperience.user_id == owner_id)
        return db.execute(stmt).scalar_one()


def _pending_row(r) -> dict:
    return dict(id=r.id, task_id=r.task_id, stage=r.stage, summary=r.summary,
                artifacts_ref=r.artifacts_ref, status=r.status, error=r.error,
                created_at=str(r.created_at))


def insert_experience(title, body, stage, tags, impact, confidence, auto_merged=0, source_pending_id=None, status="pending_review", user_id=None) -> int:
    owner_id = _experience_scope_user(user_id)
    tags_json = json.dumps(tags, ensure_ascii=False) if isinstance(tags, (list, tuple)) else tags
    with SessionLocal() as db:
        if source_pending_id is not None and owner_id is not None:
            source = db.execute(select(PendingExperience).where(PendingExperience.id == source_pending_id, PendingExperience.user_id == owner_id)).scalar_one_or_none()
            if source is None: raise LookupError("source pending experience is not owned by current user")
        row = Experience(title=title, body=body, stage=stage, tags=tags_json, impact=impact, confidence=float(confidence), auto_merged=auto_merged, source_pending_id=source_pending_id, status=status, user_id=owner_id)
        db.add(row); db.commit(); _invalidate("experience"); return row.id


def list_experience(status=None, stage=None, auto_merged=None, limit=50, user_id=None) -> list:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(Experience)
        if owner_id is not None: stmt = stmt.where(Experience.user_id == owner_id)
        if status: stmt = stmt.where(Experience.status == status)
        if stage: stmt = stmt.where(Experience.stage == stage)
        if auto_merged is not None: stmt = stmt.where(Experience.auto_merged == auto_merged)
        return [_exp_row(r) for r in db.execute(stmt.order_by(Experience.id.desc()).limit(limit)).scalars().all()]


def get_experience(id, user_id=None) -> dict | None:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(Experience).where(Experience.id == id)
        if owner_id is not None: stmt = stmt.where(Experience.user_id == owner_id)
        row = db.execute(stmt).scalar_one_or_none()
        if row is None: return None
        out = _exp_row(row)
        if row.source_pending_id:
            stmt = select(PendingExperience).where(PendingExperience.id == row.source_pending_id)
            if owner_id is not None: stmt = stmt.where(PendingExperience.user_id == owner_id)
            pend = db.execute(stmt).scalar_one_or_none()
            if pend: out.update(source_summary=pend.summary, source_task_id=pend.task_id)
        return out


def _exp_row(r) -> dict:
    return dict(id=r.id, title=r.title, body=r.body, stage=r.stage, tags=r.tags, impact=r.impact, confidence=r.confidence, auto_merged=r.auto_merged, source_pending_id=r.source_pending_id, status=r.status, created_at=str(r.created_at), last_reviewed_at=str(r.last_reviewed_at) if r.last_reviewed_at else None, hit_count=int(getattr(r, "hit_count", 0) or 0), last_used_at=str(r.last_used_at) if getattr(r, "last_used_at", None) else None, expires_at=str(r.expires_at) if getattr(r, "expires_at", None) else None, curator_note=getattr(r, "curator_note", "") or "")


def bump_experience_hits(ids: list[int], user_id=None) -> int:
    owner_id = _experience_scope_user(user_id); exp_ids = [int(i) for i in ids if i]
    if not exp_ids: return 0
    with SessionLocal() as db:
        stmt = update(Experience).where(Experience.id.in_(exp_ids))
        if owner_id is not None: stmt = stmt.where(Experience.user_id == owner_id)
        res = db.execute(stmt.values(hit_count=Experience.hit_count + 1, last_used_at=datetime.now())); db.commit(); _invalidate("experience"); return int(res.rowcount or 0)


def list_curator_candidates(status="active", stage="", older_than_days=None, max_hit_count=None, max_confidence=None, limit=100, user_id=None) -> list[dict]:
    owner_id = _experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt = select(Experience)
        if owner_id is not None: stmt = stmt.where(Experience.user_id == owner_id)
        if status: stmt = stmt.where(Experience.status == status)
        if stage: stmt = stmt.where(Experience.stage == stage)
        if older_than_days is not None: stmt = stmt.where(Experience.created_at <= datetime.now() - timedelta(days=int(older_than_days)))
        if max_hit_count is not None: stmt = stmt.where(Experience.hit_count <= int(max_hit_count))
        if max_confidence is not None: stmt = stmt.where(Experience.confidence <= float(max_confidence))
        return [_exp_row(r) for r in db.execute(stmt.order_by(Experience.created_at, Experience.id).limit(min(max(int(limit),1),500))).scalars().all()]


def mark_experience_curated(eid, status, note, reviewer="auto", user_id=None) -> bool:
    owner_id = _experience_scope_user(user_id); actions={"archived":"curator_archive","expired":"curator_expire","pending_review":"curator_propose"}
    if status not in actions: raise ValueError("status must be archived/expired/pending_review")
    with SessionLocal() as db:
        stmt=select(Experience).where(Experience.id==int(eid))
        if owner_id is not None: stmt=stmt.where(Experience.user_id==owner_id)
        row=db.execute(stmt).scalar_one_or_none()
        if row is None:return False
        row.status=status; row.curator_note=note or ""; row.last_reviewed_at=_now(); db.add(ReviewLog(experience_id=row.id, action=actions[status], reviewer=reviewer, note=note or "", user_id=owner_id)); db.commit(); _invalidate("experience"); _invalidate("review_log"); return True


def set_experience_expires_at(eid, expires_at, note="", reviewer="sir", user_id=None) -> bool:
    owner_id=_experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt=select(Experience).where(Experience.id==int(eid))
        if owner_id is not None: stmt=stmt.where(Experience.user_id==owner_id)
        row=db.execute(stmt).scalar_one_or_none()
        if row is None:return False
        row.expires_at=expires_at; row.curator_note=note or row.curator_note or ""; row.last_reviewed_at=_now(); db.add(ReviewLog(experience_id=row.id, action="curator_set_expiry", reviewer=reviewer, note=note or str(expires_at), user_id=owner_id)); db.commit(); _invalidate("experience"); _invalidate("review_log"); return True


def update_experience_status(id, status, reviewer=None, action=None, note=None, user_id=None) -> None:
    owner_id=_experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt=select(Experience).where(Experience.id==id)
        if owner_id is not None: stmt=stmt.where(Experience.user_id==owner_id)
        row=db.execute(stmt).scalar_one_or_none()
        if row is None:return
        row.status=status; row.last_reviewed_at=_now()
        if action and reviewer: db.add(ReviewLog(experience_id=id, action=action, reviewer=reviewer, note=note, user_id=owner_id))
        db.commit(); _invalidate("experience"); _invalidate("review_log")


def experience_version(user_id=None) -> str:
    owner_id=_experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt=select(func.count(), func.max(Experience.id))
        if owner_id is not None: stmt=stmt.select_from(Experience).where(Experience.user_id==owner_id)
        else: stmt=stmt.select_from(Experience)
        count,max_id=db.execute(stmt).one(); return f"e{count}:{max_id or 0}"


def write_review_log(experience_id, action, reviewer, note=None, user_id=None) -> None:
    owner_id=_experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt=select(Experience).where(Experience.id==experience_id)
        if owner_id is not None: stmt=stmt.where(Experience.user_id==owner_id)
        exp=db.execute(stmt).scalar_one_or_none()
        if exp is None and experience_id is not None:
            return
        if exp is None:
            db.add(ReviewLog(experience_id=None, action=action, reviewer=reviewer,
                             note=note, user_id=None))
            db.commit(); _invalidate("review_log"); return
        db.add(ReviewLog(experience_id=experience_id, action=action, reviewer=reviewer, note=note, user_id=owner_id)); db.commit(); _invalidate("review_log")


def start_worker_run(user_id=None) -> int:
    owner_id=_experience_scope_user(user_id)
    with SessionLocal() as db:
        row=WorkerRun(status="running", user_id=owner_id); db.add(row); db.commit(); return row.id


def finish_worker_run(run_id, processed_count, status, error=None, user_id=None) -> None:
    owner_id=_experience_scope_user(user_id)
    with SessionLocal() as db:
        stmt=select(WorkerRun).where(WorkerRun.id==run_id)
        if owner_id is not None: stmt=stmt.where(WorkerRun.user_id==owner_id)
        row=db.execute(stmt).scalar_one_or_none()
        if row is None:return
        row.ended_at=_now(); row.processed_count=processed_count; row.status=status; row.error=error; db.commit()


def search_experience(stage=None, tags=None, query=None, k=5, status="active", user_id=None) -> list:
    owner_id=_experience_scope_user(user_id)
    return _search_experience_like(stage,tags,query,k,status,owner_id)


def _search_experience_like(stage=None, tags=None, query=None, k=5, status="active", user_id=None) -> list:
    with SessionLocal() as db:
        stmt=select(Experience).where(Experience.status==status)
        if user_id is not None: stmt=stmt.where(Experience.user_id==int(user_id))
        if status=="active": stmt=stmt.where(or_(Experience.expires_at.is_(None),Experience.expires_at>datetime.now()))
        if stage: stmt=stmt.where(Experience.stage==stage)
        if tags: stmt=stmt.where(Experience.tags.like(f"%{tags}%"))
        if query and str(query).strip():
            kw=f"%{str(query)}%"; stmt=stmt.where(Experience.title.like(kw)|Experience.body.like(kw))
        return [_exp_row(r) for r in db.execute(stmt.order_by(Experience.id.desc()).limit(k)).scalars().all()]


def _exp_map_row(r) -> dict:
    return _exp_row(r) if hasattr(r, "__table__") else dict(id=r["id"], title=r["title"], body=r["body"], stage=r["stage"], tags=r["tags"], impact=r["impact"], confidence=r["confidence"], auto_merged=r["auto_merged"], source_pending_id=r["source_pending_id"], status=r["status"], created_at=str(r["created_at"]))


# ==================== 经验沉淀设置中心（key-value 热加载） ====================

def get_config(key: str, default: str | None = None) -> str | None:
    """读取配置值（无记录返回 default）；经验 Worker 每次运行前热加载，无需重启"""
    with SessionLocal() as db:
        row = db.execute(select(ExperienceConfig).where(ExperienceConfig.key == key)
                         ).scalar_one_or_none()
        return row.value if row else default


def set_config(key: str, value: str) -> None:
    """写入/覆盖配置（key 为主键，幂等 upsert）"""
    with SessionLocal() as db:
        row = db.execute(select(ExperienceConfig).where(ExperienceConfig.key == key)
                         ).scalar_one_or_none()
        if row is None:
            row = ExperienceConfig(key=key, value=value)
            db.add(row)
        else:
            row.value = value
        db.commit()
