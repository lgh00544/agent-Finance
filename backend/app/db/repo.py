"""
数据仓库层：Agent 落库/读取的统一入口（幂等 upsert）
【刚性代码逻辑】只做数据存取，不含任何市场判断。
"""
import hashlib
import json
import logging
from typing import Any, Callable

from sqlalchemy import delete, func, select, text

from app.cache import cache
from app.core.config import settings
from app.db.models import (
    AccountBaseline, AgentPreference, AgentSuggestion, AiReasoningTrace, AlertLog, Holding,
    MarketCondition, NewsArticle, PositionPlan, PrivateKnowledge, ReviewResult,
    SellDecision, StockCandidate, StockScore, TradeProfile, TradeRecord, _now,
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


# ==================== 市况评分（v2.0 Discover 前置步骤） ====================

def upsert_market_condition(trade_date: str, total_score: int, dims: dict,
                            cap: int, summary: str) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(MarketCondition).where(MarketCondition.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = MarketCondition(trade_date=trade_date)
            db.add(row)
        row.total_score, row.dims, row.cap, row.summary = total_score, dims, cap, summary
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
                batches: list, stop_loss: float, take_profit: float, rationale: str) -> int:
    with SessionLocal() as db:
        row = PositionPlan(stock_code=stock_code, stock_name=stock_name, plan_date=plan_date,
                           total_pct=total_pct, batches=batches, stop_loss=stop_loss,
                           take_profit=take_profit, rationale=rationale)
        db.add(row)
        db.commit()
        db.refresh(row)
        _invalidate("plan")
        # 推理留痕：position 分批区间/止损止盈/总仓 + 建仓逻辑说明
        reasoning_trace.trace_plan(stock_code, stock_name, plan_date, total_pct,
                                   batches, stop_loss, take_profit, rationale, row.id)
        return row.id


def insert_alert(stock_code: str, stock_name: str, alert_type: str, severity: str,
                 message: str, action: str, signal: dict, pushed: bool) -> int:
    with SessionLocal() as db:
        row = AlertLog(stock_code=stock_code, stock_name=stock_name, alert_type=alert_type,
                       severity=severity, message=message, action=action, signal=signal, pushed=pushed)
        db.add(row)
        db.commit()
        db.refresh(row)
        _invalidate("alert")
        # 推理留痕：monitor 信号研判（signal 全量含 reasons/risks/key_levels）
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
                     "detail": r.detail or {}, "created_at": str(r.created_at)} for r in rows]

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
                            target_kind: str = "profile") -> int:
    with SessionLocal() as db:
        row = AgentSuggestion(review_id=review_id, target_agent=target_agent, rule_name=rule_name,
                              current_value=current_value, suggested_value=suggested_value,
                              reason=reason, evidence=evidence,
                              target_kind=target_kind, status="pending")
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


def update_agent_suggestion_status(suggestion_id: int, status: str) -> AgentSuggestion | None:
    """人工审核动作：approved / rejected（严格禁止系统自动修改，仅人工调用）"""
    with SessionLocal() as db:
        row = db.get(AgentSuggestion, suggestion_id)
        if row is None:
            return None
        row.status = status
        db.commit()
        db.refresh(row)
        return row


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


def list_chat_messages(agent: str, limit: int = 50) -> list[dict]:
    """某 Agent 的对话历史（最新在前）"""
    from app.db.models import AgentChatMessage

    with SessionLocal() as db:
        stmt = (select(AgentChatMessage)
                .where(AgentChatMessage.agent == agent)
                .order_by(AgentChatMessage.id.desc())
                .limit(min(limit, 200)))
        rows = list(db.execute(stmt).scalars().all())
    return [{"id": r.id, "agent": r.agent, "role": r.role, "message_type": r.message_type,
             "content": r.content, "verdict": r.verdict, "knowledge_id": r.knowledge_id,
             "meta": r.meta or {}, "created_at": str(r.created_at)}
            for r in rows]
