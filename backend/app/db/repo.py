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

from sqlalchemy import delete, func, select, text

from app.cache import cache
from app.core.config import settings
from app.db.models import (
    AccountBaseline, AgentPreference, AgentSuggestion, AiReasoningTrace, AlertLog,
    BatchAdjust, CandidateAdjust, CandidateTrackVerify, CandidateTradeable,
    Experience, ExperienceConfig, Holding, HotMoneyProfile, LhbOriginalFlow,
    MarketCondition, MarketIntel, NewsArticle, PendingExperience, PositionPlan,
    PrivateKnowledge, QuoteSnapshot, ReviewLog, ReviewResult, RuleChange,
    SectorSnapshot, SellDecision, StockCandidate, StockScore, TradeProfile,
    TradeRecord, WorkerRun, _now,
)
from app.db.session import SessionLocal
from app.services import reasoning_trace

logger = logging.getLogger(__name__)


def _json(value: Any) -> Any:
    return value if value is not None else None


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
        db.commit()
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
            db.commit()
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
        cap, band = market_band_info(row.total_score)
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
        cap, band = market_band_info(row.total_score)
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
        db.commit()
        _invalidate("tradeable")


def list_candidate_tradeable(trade_date: str | None = None, limit: int = 200) -> list[dict]:
    """当日/任意日期可建仓判定行（最新在前；历史可追溯查询）"""

    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(CandidateTradeable).order_by(CandidateTradeable.id.desc())
            if trade_date:
                stmt = stmt.where(CandidateTradeable.trade_date == trade_date)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"stock_code": r.stock_code, "stock_name": r.stock_name,
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
                 grade: str, detail: dict, risk_list: list) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(StockScore).where(
                StockScore.stock_code == stock_code, StockScore.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = StockScore(stock_code=stock_code, stock_name=stock_name, trade_date=trade_date)
            db.add(row)
        row.score, row.grade, row.detail, row.risk_list = score, grade, detail, risk_list
        db.commit()
        _invalidate("score")
        # 推理留痕：score 五维分项研判（dimensions[].comment 按维度归入技术/资金/基本面）
        reasoning_trace.trace_score(stock_code, stock_name, trade_date,
                                    score, grade, detail, risk_list)


def insert_plan(stock_code: str, stock_name: str, plan_date: str, total_pct: float,
                batches: list, stop_loss: float, take_profit: float, rationale: str,
                detail: dict | None = None, source: str = "manual") -> int:
    """detail: v3.0 白盒扩展（dimensions/final_advice/market_regime/freshness/quant），可选；
    旧调用零影响。去重规则：同一标的同一交易日仅保留最新一份（旧记录删除，
    新记录 id 保持最新），杜绝列表重复冗余。source: candidate=每日候选池联动 / manual=手动生成。"""
    with SessionLocal() as db:
        stale = db.execute(select(PositionPlan).where(
            PositionPlan.stock_code == stock_code, PositionPlan.plan_date == plan_date)
        ).scalars().all()
        for s in stale:
            db.delete(s)
        row = PositionPlan(stock_code=stock_code, stock_name=stock_name, plan_date=plan_date,
                           total_pct=total_pct, batches=batches, stop_loss=stop_loss,
                           take_profit=take_profit, rationale=rationale, detail=detail,
                           source=source if source in ("candidate", "manual") else "manual")
        db.add(row)
        db.commit()
        db.refresh(row)
        _invalidate("plan")
        # 推理留痕：position 分批区间/止损止盈/总仓 + 建仓逻辑说明 + v3.0 维度归因
        reasoning_trace.trace_plan(stock_code, stock_name, plan_date, total_pct,
                                   batches, stop_loss, take_profit, rationale, row.id,
                                   detail=detail)
        return row.id


def insert_alert(stock_code: str, stock_name: str, alert_type: str, severity: str,
                 message: str, action: str, signal: dict, pushed: bool,
                 source: str = "monitor") -> int:
    """写告警日志；source 标记来源（monitor/portfolio_sentinel），默认 monitor 保持旧链路不变"""
    with SessionLocal() as db:
        row = AlertLog(stock_code=stock_code, stock_name=stock_name, alert_type=alert_type,
                       severity=severity, message=message, action=action, signal=signal,
                       pushed=pushed, source=source)
        db.add(row)
        db.commit()
        db.refresh(row)
        _invalidate("alert")
        # 推理留痕仅 monitor 信号（LLM 研判）：pre_market/market_shift 等代码级检测
        # 无 LLM 研判，不写留痕（避免污染推理留痕视图）
        if source == "monitor":
            reasoning_trace.trace_alert(stock_code, stock_name, _now().strftime("%Y-%m-%d"),
                                        alert_type, severity, message, action, signal or {})
        return row.id


def insert_review(stock_code: str, stock_name: str, holding_id: int, exit_date: str,
                  hold_days: int, pnl_pct: float, plan_vs_actual: dict, lesson: str,
                  feedback: dict) -> int:
    with SessionLocal() as db:
        row = ReviewResult(stock_code=stock_code, stock_name=stock_name, holding_id=holding_id,
                           exit_date=exit_date, hold_days=hold_days, pnl_pct=pnl_pct,
                           plan_vs_actual=plan_vs_actual, lesson=lesson, feedback=feedback)
        db.add(row)
        db.commit()
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


def get_latest_preference() -> dict | None:
    with SessionLocal() as db:
        row = db.execute(
            select(AgentPreference).order_by(AgentPreference.version.desc()).limit(1)
        ).scalar_one_or_none()
        return _json(row.content) if row else None


def upsert_preference(content: dict, source_review_id: int | None = None) -> None:
    with SessionLocal() as db:
        latest = db.execute(
            select(AgentPreference).order_by(AgentPreference.version.desc()).limit(1)
        ).scalar_one_or_none()
        version = (latest.version + 1) if latest else 1
        db.add(AgentPreference(version=version, content=content, source_review_id=source_review_id))
        db.commit()


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
    """读取交易偏好档案（全局单行，id=1）"""
    with SessionLocal() as db:
        row = db.get(TradeProfile, 1)
        if row is None:
            row = TradeProfile(id=1, version=1, content=_default_profile())
            db.add(row)
            db.commit()
            db.refresh(row)
        return row


def get_trade_profile_content() -> dict:
    row = get_trade_profile()
    return row.content if row else {}


def update_trade_profile(content: dict) -> int:
    """更新偏好档案，version 递增（用于 LLM 缓存失效）"""
    with SessionLocal() as db:
        row = db.get(TradeProfile, 1)
        if row is None:
            row = TradeProfile(id=1, version=1, content=content)
            db.add(row)
        else:
            row.version += 1
            row.content = content
        db.commit()
        return row.version


def insert_account_baseline(trade_date: str, total_asset: float, available_cash: float,
                            position_pct: float, source: str = "ocr") -> int:
    """保存账户基准快照（人工确认后调用；每次插入一行保留历史，读取取最新）"""
    with SessionLocal() as db:
        row = AccountBaseline(trade_date=trade_date, total_asset=total_asset,
                              available_cash=available_cash, position_pct=position_pct,
                              source=source)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_latest_account_baseline() -> dict | None:
    """读取最新账户基准快照；无记录返回 None"""
    with SessionLocal() as db:
        row = db.execute(
            select(AccountBaseline).order_by(AccountBaseline.id.desc()).limit(1)
        ).first()
        if row is None:
            return None
        r = row[0]
        return {"id": r.id, "trade_date": r.trade_date, "total_asset": r.total_asset,
                "available_cash": r.available_cash, "position_pct": r.position_pct,
                "source": r.source, "created_at": str(r.created_at)}


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


def insert_holding(stock_code: str, stock_name: str, entry_date: str, entry_price: float,
                   shares: int, cost: float, stop_loss: float = 0.0, take_profit: float = 0.0,
                   target_pct: float = 0.0, plan_id: int | None = None, note: str = "") -> int:
    with SessionLocal() as db:
        row = Holding(stock_code=stock_code, stock_name=stock_name, entry_date=entry_date,
                      entry_price=entry_price, shares=shares, cost=cost, stop_loss=stop_loss,
                      take_profit=take_profit, target_pct=target_pct, plan_id=plan_id, note=note)
        db.add(row)
        db.commit()
        db.refresh(row)
        _invalidate("holding")
        return row.id


def add_trade(holding_id: int, stock_code: str, side: str, price: float,
              shares: int, trade_date: str, note: str = "") -> int:
    with SessionLocal() as db:
        row = TradeRecord(holding_id=holding_id, stock_code=stock_code, side=side,
                          price=price, shares=shares, amount=round(price * shares, 2),
                          trade_date=trade_date, note=note)
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
                         holding_fields: dict | None = None) -> int:
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
                           before_shares=before_shares, after_shares=after_shares))
        if holding_fields:
            for k, v in holding_fields.items():
                setattr(row, k, v)
        db.commit()
        _invalidate("holding")
        return row.id


def get_active_holdings() -> list[Holding]:
    with SessionLocal() as db:
        return list(db.execute(
            select(Holding).where(Holding.status == "holding")).scalars().all())


def get_trades(holding_id: int) -> list[TradeRecord]:
    with SessionLocal() as db:
        return list(db.execute(
            select(TradeRecord).where(TradeRecord.holding_id == holding_id)
            .order_by(TradeRecord.trade_date)).scalars().all())


def get_latest_score(code: str) -> StockScore | None:
    """该股最新一次评分（PositionAgent 建仓输入用）"""
    with SessionLocal() as db:
        return db.execute(
            select(StockScore).where(StockScore.stock_code == code)
            .order_by(StockScore.trade_date.desc()).limit(1)).scalar_one_or_none()


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
                module: str | None = None, limit: int = 50) -> list[dict]:
    """推理留痕轻量列表（不含长文本，详情按需单查；L1 缓存 dbq:trace:，写后由
    reasoning_trace._flush 失效）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(AiReasoningTrace).order_by(
                AiReasoningTrace.generate_date.desc(), AiReasoningTrace.trace_id.desc())
            if code:
                stmt = stmt.where(AiReasoningTrace.stock_code == code)
            if date:
                stmt = stmt.where(AiReasoningTrace.generate_date == date)
            if module:
                stmt = stmt.where(AiReasoningTrace.source_module == module)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [{"trace_id": r.trace_id, "stock_code": r.stock_code,
                     "stock_name": r.stock_name, "source_module": r.source_module,
                     "generate_date": r.generate_date, "confidence": r.confidence,
                     "data_source": r.data_source, "create_time": r.create_time}
                    for r in rows]

    return _dbq("trace", {"code": code, "date": date, "module": module, "limit": limit}, _load)


def get_trace(trace_id: int) -> dict | None:
    """推理留痕完整详情（含全部推理分层文本）"""
    def _load() -> dict | None:
        with SessionLocal() as db:
            r = db.get(AiReasoningTrace, trace_id)
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

    return _dbq("trace", {"id": trace_id}, _load)


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


def list_track_verify(select_date: str = "", rating: str = "",
                      is_finished: int | None = None, limit: int = 200) -> list[dict]:
    """追踪验证行列表（按选中日+排序；60s 缓存，写后失效）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(CandidateTrackVerify).order_by(
                CandidateTrackVerify.select_date.desc(), CandidateTrackVerify.id)
            if select_date:
                stmt = stmt.where(CandidateTrackVerify.select_date == select_date)
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
                {"date": select_date, "rating": rating,
                 "finished": is_finished, "limit": limit}, _load)


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


def list_plans(code: str | None = None, limit: int = 50) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(PositionPlan).order_by(PositionPlan.id.desc())
            if code:
                stmt = stmt.where(PositionPlan.stock_code == code)
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "plan_date": r.plan_date, "status": r.status,
                                           "total_pct": r.total_pct, "batches": r.batches,
                                           "stop_loss": r.stop_loss, "take_profit": r.take_profit,
                                           "rationale": r.rationale,
                                           "detail": r.detail or {},
                                           "source": r.source or "manual",
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("plan", {"code": code, "limit": limit}, _load)


def list_holdings(status: str | None = None) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(Holding).order_by(Holding.id.desc())
            if status:
                stmt = stmt.where(Holding.status == status)
            rows = db.execute(stmt).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "entry_date": r.entry_date,
                                           "entry_price": r.entry_price, "shares": r.shares,
                                           "cost": r.cost, "stop_loss": r.stop_loss,
                                           "take_profit": r.take_profit,
                                           "target_pct": r.target_pct, "status": r.status,
                                           "plan_id": r.plan_id, "note": r.note,
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("holding", {"status": status}, _load)


def list_alerts(limit: int = 100) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            rows = db.execute(
                select(AlertLog).order_by(AlertLog.id.desc()).limit(limit)).scalars().all()
            return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                           "stock_name": r.stock_name,
                                           "alert_type": r.alert_type, "severity": r.severity,
                                           "message": r.message, "action": r.action,
                                           "signal": r.signal, "pushed": r.pushed,
                                           "source": r.source,
                                           "created_at": str(r.created_at)} for r in rows])

    return _dbq("alert", {"limit": limit}, _load)


def list_reviews(code: str | None = None, limit: int = 50) -> list[dict]:
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(ReviewResult).order_by(ReviewResult.id.desc())
            if code:
                stmt = stmt.where(ReviewResult.stock_code == code)
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
                                           "created_at": str(r.created_at)}
                                          for r in rows])

    return _dbq("review", {"code": code, "limit": limit}, _load)


def get_review(review_id: int) -> ReviewResult | None:
    with SessionLocal() as db:
        return db.get(ReviewResult, review_id)


def list_sell_decisions(holding_id: int, limit: int = 10) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(SellDecision).where(SellDecision.holding_id == holding_id)
            .order_by(SellDecision.id.desc()).limit(limit)).scalars().all()
        return _backfill_stock_names([{"id": r.id, "stock_code": r.stock_code,
                                       "stock_name": r.stock_name,
                                       "decision": r.decision,
                                       "created_at": str(r.created_at)} for r in rows])


# ==================== 私有知识库（人工录入，Agent 启动自动检索注入） ====================

def knowledge_version() -> tuple[int, int]:
    """知识库变更感知（数量 + 最大ID），供 LLM 缓存键使用"""
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(PrivateKnowledge)) or 0
        max_id = db.scalar(select(func.max(PrivateKnowledge.id))) or 0
        return int(count), int(max_id)


def add_knowledge(title: str, content: str, agent_tag: str = "all") -> int:
    with SessionLocal() as db:
        row = PrivateKnowledge(title=title, content=content, agent_tag=agent_tag)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_knowledge(agent_tag: str | None = None) -> list[PrivateKnowledge]:
    with SessionLocal() as db:
        stmt = select(PrivateKnowledge).order_by(PrivateKnowledge.id.desc())
        if agent_tag:
            stmt = stmt.where(PrivateKnowledge.agent_tag == agent_tag)
        return list(db.execute(stmt).scalars().all())


def delete_knowledge(knowledge_id: int) -> bool:
    with SessionLocal() as db:
        row = db.get(PrivateKnowledge, knowledge_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


# ==================== 卖出决策（SellAgent 输出，仅供参考） ====================

def insert_sell_decision(holding_id: int, stock_code: str, stock_name: str, decision: dict) -> int:
    with SessionLocal() as db:
        row = SellDecision(holding_id=holding_id, stock_code=stock_code,
                           stock_name=stock_name, decision=decision)
        db.add(row)
        db.commit()
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


def get_sell_decisions_by_code(stock_code: str, limit: int = 20) -> list[SellDecision]:
    with SessionLocal() as db:
        return list(db.execute(
            select(SellDecision).where(SellDecision.stock_code == stock_code)
            .order_by(SellDecision.id.desc()).limit(limit)).scalars().all())


# ==================== 策略闭环建议（复盘进化Agent 输出，人工审核后生效） ====================

def insert_agent_suggestion(review_id: int, target_agent: str, rule_name: str,
                            current_value: str, suggested_value: str,
                            reason: str, evidence: str,
                            target_kind: str = "profile",
                            rule_type: str = "soft", priority: str = "medium",
                            problem_desc: str = "", rule_text: str = "",
                            expected_effect: str = "", risk_note: str = "",
                            file_path: str = "", insert_position: str = "",
                            suggestion_source: str = "llm") -> int:
    with SessionLocal() as db:
        row = AgentSuggestion(review_id=review_id, target_agent=target_agent, rule_name=rule_name,
                              current_value=current_value, suggested_value=suggested_value,
                              reason=reason, evidence=evidence,
                              target_kind=target_kind, status="pending",
                              rule_type=rule_type, priority=priority,
                              problem_desc=problem_desc, rule_text=rule_text,
                              expected_effect=expected_effect, risk_note=risk_note,
                              file_path=file_path, insert_position=insert_position,
                              suggestion_source=suggestion_source)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def get_agent_suggestion(suggestion_id: int) -> AgentSuggestion | None:
    with SessionLocal() as db:
        return db.get(AgentSuggestion, suggestion_id)


def get_agent_suggestions(review_id: int | None = None,
                          status: str | None = None) -> list[AgentSuggestion]:
    with SessionLocal() as db:
        stmt = select(AgentSuggestion).order_by(AgentSuggestion.id.desc())
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

def get_active_rules() -> list[dict]:
    """生效中规则列表（agent_call 注入数据源；采纳/回滚后 _invalidate 失效）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            rows = db.execute(
                select(RuleChange).where(RuleChange.status == "active")
                .order_by(RuleChange.id)).scalars().all()
            return [{"id": r.id, "target_agent": r.target_agent, "rule_type": r.rule_type,
                     "rule_name": r.rule_name, "rule_text": r.rule_text} for r in rows]

    return _dbq("rule_change", {"active": 1}, _load)


def rule_version() -> str:
    """生效规则内容指纹（count+max_id）→ 入 LLM 缓存键：
    采纳/回滚后指纹变化，当日 LLM 缓存自动失效（同 _knowledge_version 语义）"""
    def _load() -> list:
        with SessionLocal() as db:
            cnt = db.execute(select(func.count()).select_from(RuleChange)
                             .where(RuleChange.status == "active")).scalar() or 0
            max_id = db.execute(select(func.max(RuleChange.id))).scalar() or 0
            return [{"count": int(cnt), "max_id": int(max_id or 0)}]

    rows = _dbq("rule_change", {"ver": 1}, _load)
    row = rows[0] if rows else {}
    return f"{row.get('count', 0)}:{row.get('max_id', 0)}"


def list_rule_changes(status: str | None = None, target_agent: str | None = None,
                      suggestion_id: int | None = None, limit: int = 50) -> list[dict]:
    """规则变更记录轻量列表（记录页数据源，不含长文本；详情按需单查）"""
    def _load() -> list[dict]:
        with SessionLocal() as db:
            stmt = select(RuleChange).order_by(RuleChange.id.desc()).limit(limit)
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
                     "created_at": str(r.created_at),
                     "rollback_time": r.rollback_time} for r in rows]

    return _dbq("rule_change", {"status": status, "agent": target_agent,
                                "suggestion_id": suggestion_id, "limit": limit}, _load)


def get_rule_change(rule_change_id: int) -> dict | None:
    """规则变更完整详情（变更前后对比/回滚原因/落地元数据，供记录页展开）"""
    def _load() -> list:
        with SessionLocal() as db:
            r = db.get(RuleChange, rule_change_id)
            if r is None:
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
                     "created_at": str(r.created_at)}]

    rows = _dbq("rule_change", {"detail": rule_change_id}, _load)
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
        )
        db.add(change)
        sug.status = "approved"
        db.commit()
        db.refresh(change)
        _invalidate("rule_change")
        return change.id


def rollback_rule_change(rule_change_id: int, reason: str) -> bool:
    """一键回滚：status=active → rolled_back + 原因/时间留痕；返回是否成功"""
    with SessionLocal() as db:
        row = db.get(RuleChange, rule_change_id)
        if row is None or row.status != "active":
            return False
        row.status = "rolled_back"
        row.rollback_reason = reason.strip()
        row.rollback_time = _now().strftime("%Y-%m-%d %H:%M")
        db.commit()
        _invalidate("rule_change")
        return True


# ==================== 监控信号历史（ReviewAgent 复盘聚合用） ====================

def get_alerts_by_code(stock_code: str, limit: int = 50) -> list[AlertLog]:
    with SessionLocal() as db:
        return list(db.execute(
            select(AlertLog).where(AlertLog.stock_code == stock_code)
            .order_by(AlertLog.id.desc()).limit(limit)).scalars().all())


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
    norm = _normalize_seat(seat)
    for p in list_hot_money_profiles():
        p_norm = _normalize_seat(p.get("seat_code") or "")
        if p_norm and (p_norm in norm or norm in p_norm):
            return p
    return None


def _normalize_seat(seat: str) -> str:
    """席位名停用词归一化（模糊匹配辅助，非市场判断）"""
    for word in ("股份有限公司", "有限责任公司", "证券营业部", "营业部", "证券", "分公司"):
        seat = seat.replace(word, "")
    return seat.strip()


# ================= 龙虎榜原始流水（lhb_original_flow，口径硬隔离） =================

def insert_lhb_flows(rows: list[dict]) -> int:
    """批量插入龙虎榜流水（rows: trade_date/stock_code/stock_name/lhb_type/
    disclosure_reason/seat_name/buy_amt/sell_amt/net_buy/confidence/source）"""
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
                source=r.get("source", "eastmoney")))
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


# ==================== 经验沉淀闭环（pending → worker → experience → review_log → 检索注入） ====================

def add_pending_experience(task_id, stage, summary, artifacts_ref) -> int:
    """热路径经验沉淀写入：单行 INSERT，零分析。失败由调用方静默降级（不阻塞主任务）。"""
    with SessionLocal() as db:
        row = PendingExperience(task_id=task_id, stage=stage, summary=summary,
                                artifacts_ref=artifacts_ref, status="pending")
        db.add(row)
        db.commit()
        _invalidate("pending_experience")
        return row.id


def list_pending_experience(status=None, stage=None, limit=50) -> list:
    """待处理队列只读列表（最新在前）"""
    with SessionLocal() as db:
        stmt = select(PendingExperience)
        if status:
            stmt = stmt.where(PendingExperience.status == status)
        if stage:
            stmt = stmt.where(PendingExperience.stage == stage)
        stmt = stmt.order_by(PendingExperience.id.desc()).limit(limit)
        rows = db.execute(stmt).scalars().all()
        return [_pending_row(r) for r in rows]


def _pending_row(r) -> dict:
    return dict(id=r.id, task_id=r.task_id, stage=r.stage, summary=r.summary,
                artifacts_ref=r.artifacts_ref, status=r.status, error=r.error,
                created_at=str(r.created_at))


def claim_pending_batch(batch_size=20) -> list:
    """原子认领下一批 pending：逐行 UPDATE ... WHERE id=? AND status='pending'（防并发双跑）。
    返回认领成功行的 dict 列表；并发下重复执行不会重复消费。"""
    with SessionLocal() as db:
        pending = db.execute(
            select(PendingExperience).where(PendingExperience.status == "pending")
            .order_by(PendingExperience.id).limit(batch_size)).scalars().all()
        claimed = []
        for row in pending:
            res = db.execute(
                PendingExperience.__table__.update()
                .where(PendingExperience.id == row.id,
                       PendingExperience.status == "pending")
                .values(status="processing"))
            if res.rowcount == 1:
                claimed.append(_pending_row(row))
        if claimed:
            db.commit()
            _invalidate("pending_experience")
        return claimed


def release_pending(id, error=None) -> None:
    """处理完成：标 done + 可选 error（失败也标 done，error 记录原因，不残留 processing）"""
    with SessionLocal() as db:
        row = db.execute(select(PendingExperience).where(PendingExperience.id == id)
                         ).scalar_one_or_none()
        if row is None:
            return
        row.status = "done"
        row.error = error
        db.commit()
        _invalidate("pending_experience")


def watchdog_reset_stale_processing(older_than_hours=2.0) -> int:
    """看门狗：processing 超时（默认 2h）复位为 pending，防 Worker 崩溃卡死队列。返回复位条数"""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    with SessionLocal() as db:
        rows = db.execute(
            select(PendingExperience).where(
                PendingExperience.status == "processing",
                PendingExperience.created_at < cutoff)).scalars().all()
        for row in rows:
            row.status = "pending"
            row.error = "watchdog_timeout"
        if rows:
            db.commit()
            _invalidate("pending_experience")
        return len(rows)


def pending_backlog_count() -> int:
    """待处理队列积压数（Digest 积压触发判断）"""
    with SessionLocal() as db:
        return db.execute(
            select(func.count()).select_from(PendingExperience)
            .where(PendingExperience.status == "pending")).scalar_one()


def insert_experience(title, body, stage, tags, impact, confidence,
                      auto_merged=0, source_pending_id=None, status="pending_review") -> int:
    """插入沉淀经验；FTS 触发器自动同步索引。返回 experience.id"""
    tags_json = json.dumps(tags, ensure_ascii=False) if isinstance(tags, (list, tuple)) else tags
    with SessionLocal() as db:
        row = Experience(title=title, body=body, stage=stage, tags=tags_json,
                         impact=impact, confidence=float(confidence),
                         auto_merged=auto_merged, source_pending_id=source_pending_id,
                         status=status)
        db.add(row)
        db.commit()
        _invalidate("experience")
        return row.id


def list_experience(status=None, stage=None, auto_merged=None, limit=50) -> list:
    """经验库列表（最新在前）"""
    with SessionLocal() as db:
        stmt = select(Experience)
        if status:
            stmt = stmt.where(Experience.status == status)
        if stage:
            stmt = stmt.where(Experience.stage == stage)
        if auto_merged is not None:
            stmt = stmt.where(Experience.auto_merged == auto_merged)
        stmt = stmt.order_by(Experience.id.desc()).limit(limit)
        rows = db.execute(stmt).scalars().all()
        return [_exp_row(r) for r in rows]


def get_experience(id) -> dict:
    """单条经验（含来源 pending 摘要，供 UI/审核展示）"""
    with SessionLocal() as db:
        row = db.execute(select(Experience).where(Experience.id == id)).scalar_one_or_none()
        if row is None:
            return None
        out = _exp_row(row)
        if row.source_pending_id:
            pend = db.execute(select(PendingExperience).where(
                PendingExperience.id == row.source_pending_id)).scalar_one_or_none()
            if pend:
                out["source_summary"] = pend.summary
                out["source_task_id"] = pend.task_id
        return out


def _exp_row(r) -> dict:
    return dict(id=r.id, title=r.title, body=r.body, stage=r.stage, tags=r.tags,
                impact=r.impact, confidence=r.confidence, auto_merged=r.auto_merged,
                source_pending_id=r.source_pending_id, status=r.status,
                created_at=str(r.created_at),
                last_reviewed_at=str(r.last_reviewed_at) if r.last_reviewed_at else None)


def update_experience_status(id, status, reviewer=None, action=None, note=None) -> None:
    """状态流转 + 写 review_log（同事务）；last_reviewed_at 刷新"""
    with SessionLocal() as db:
        row = db.execute(select(Experience).where(Experience.id == id)).scalar_one_or_none()
        if row is None:
            return
        row.status = status
        row.last_reviewed_at = _now()
        if action and reviewer:
            db.add(ReviewLog(experience_id=id, action=action, reviewer=reviewer, note=note))
        db.commit()
        _invalidate("experience")
        _invalidate("review_log")


def experience_version() -> str:
    """经验版本感知（e{count}:{max_id}），供 LLM 缓存键追加，经验变更后缓存自动失效"""
    with SessionLocal() as db:
        count = db.execute(select(func.count()).select_from(Experience)).scalar_one()
        max_id = db.execute(select(func.max(Experience.id))).scalar_one()
        return f"e{count}:{max_id or 0}"


def write_review_log(experience_id, action, reviewer, note=None) -> None:
    """独立审核留痕（auto_merge/rollback 等）"""
    with SessionLocal() as db:
        db.add(ReviewLog(experience_id=experience_id, action=action,
                         reviewer=reviewer, note=note))
        db.commit()
        _invalidate("review_log")


def start_worker_run() -> int:
    """Worker 运行记录开始，返回 run_id"""
    with SessionLocal() as db:
        row = WorkerRun(status="running")
        db.add(row)
        db.commit()
        return row.id


def finish_worker_run(run_id, processed_count, status, error=None) -> None:
    """Worker 运行记录结束（ended_at/processed_count/status/error）"""
    with SessionLocal() as db:
        row = db.execute(select(WorkerRun).where(WorkerRun.id == run_id)).scalar_one_or_none()
        if row is None:
            return
        row.ended_at = _now()
        row.processed_count = processed_count
        row.status = status
        row.error = error
        db.commit()


def search_experience(stage=None, tags=None, query=None, k=5, status="active") -> list:
    """经验检索注入：SQLite 用 FTS5 MATCH（rank 相关度），中文整串匹配差时自动降级 LIKE；
    MySQL 模式直接 LIKE 检索（标注检索精度降级）。仅取 status 指定的经验。"""
    if settings.db_backend != "sqlite":
        return _search_experience_like(stage, tags, query, k, status)
    if query and str(query).strip():
        params: dict = {"status": status, "k": int(k)}
        sql = ("SELECT e.* FROM experience_fts f JOIN experience e ON e.id=f.rowid "
               "WHERE e.status=:status")
        if stage:
            sql += " AND e.stage=:stage"
            params["stage"] = stage
        sql += " AND experience_fts MATCH :query ORDER BY rank LIMIT :k"
        params["query"] = str(query)
        try:
            with SessionLocal() as db:
                rows = db.execute(text(sql), params).mappings().all()
                if rows:
                    return [_exp_map_row(r) for r in rows]
        except Exception:  # noqa: BLE001 FTS 语法/整串匹配失败 → 降级 LIKE
            logger.warning("FTS5 检索失败（降级 LIKE）: %s", str(query)[:60])
    return _search_experience_like(stage, tags, query, k, status)


def _search_experience_like(stage=None, tags=None, query=None, k=5, status="active") -> list:
    """LIKE 兜底检索（FTS 不可用/未命中；MySQL 降级模式）"""
    with SessionLocal() as db:
        stmt = select(Experience).where(Experience.status == status)
        if stage:
            stmt = stmt.where(Experience.stage == stage)
        if tags:
            stmt = stmt.where(Experience.tags.like(f"%{tags}%"))
        if query and str(query).strip():
            kw = f"%{str(query)}%"
            stmt = stmt.where(Experience.title.like(kw) | Experience.body.like(kw))
        stmt = stmt.order_by(Experience.id.desc()).limit(k)
        rows = db.execute(stmt).scalars().all()
        return [_exp_row(r) for r in rows]


def _exp_map_row(r) -> dict:
    """FTS JOIN 原始行映射（RowMapping → 统一 dict）"""
    return dict(id=r["id"], title=r["title"], body=r["body"], stage=r["stage"],
                tags=r["tags"], impact=r["impact"], confidence=r["confidence"],
                auto_merged=r["auto_merged"], source_pending_id=r["source_pending_id"],
                status=r["status"], created_at=str(r["created_at"]),
                last_reviewed_at=str(r["last_reviewed_at"]) if r["last_reviewed_at"] else None)


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
