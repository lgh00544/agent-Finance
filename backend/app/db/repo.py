"""
数据仓库层：Agent 落库/读取的统一入口（幂等 upsert）
【刚性代码逻辑】只做数据存取，不含任何市场判断。
"""
import logging
from typing import Any

from sqlalchemy import func, select

from app.db.models import (
    AgentPreference, AgentSuggestion, AlertLog, Holding, NewsArticle, PositionPlan,
    PrivateKnowledge, ReviewResult, SellDecision, StockCandidate, StockScore,
    TradeProfile, TradeRecord,
)
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _json(value: Any) -> Any:
    return value if value is not None else None


def upsert_candidate(stock_code: str, stock_name: str, trade_date: str, rank: int,
                     reasons: list, risk_notice: list, snapshot: dict) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(StockCandidate).where(
                StockCandidate.stock_code == stock_code, StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            row = StockCandidate(stock_code=stock_code, stock_name=stock_name, trade_date=trade_date)
            db.add(row)
        row.rank, row.reasons, row.risk_notice, row.snapshot = rank, reasons, risk_notice, snapshot
        db.commit()


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


def insert_plan(stock_code: str, stock_name: str, plan_date: str, total_pct: float,
                batches: list, stop_loss: float, take_profit: float, rationale: str) -> int:
    with SessionLocal() as db:
        row = PositionPlan(stock_code=stock_code, stock_name=stock_name, plan_date=plan_date,
                           total_pct=total_pct, batches=batches, stop_loss=stop_loss,
                           take_profit=take_profit, rationale=rationale)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def insert_alert(stock_code: str, stock_name: str, alert_type: str, severity: str,
                 message: str, action: str, signal: dict, pushed: bool) -> int:
    with SessionLocal() as db:
        row = AlertLog(stock_code=stock_code, stock_name=stock_name, alert_type=alert_type,
                       severity=severity, message=message, action=action, signal=signal, pushed=pushed)
        db.add(row)
        db.commit()
        db.refresh(row)
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
    with SessionLocal() as db:
        stmt = select(StockCandidate).order_by(StockCandidate.trade_date.desc(), StockCandidate.rank)
        if date:
            stmt = stmt.where(StockCandidate.trade_date == date)
        rows = db.execute(stmt.limit(limit)).scalars().all()
        return [{"stock_code": r.stock_code, "stock_name": r.stock_name,
                 "trade_date": r.trade_date, "rank": r.rank,
                 "reasons": r.reasons, "risk_notice": r.risk_notice,
                 "created_at": str(r.created_at)} for r in rows]


def list_scores(code: str | None = None, date: str | None = None, limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(StockScore).order_by(StockScore.trade_date.desc())
        if code:
            stmt = stmt.where(StockScore.stock_code == code)
        if date:
            stmt = stmt.where(StockScore.trade_date == date)
        rows = db.execute(stmt.limit(limit)).scalars().all()
        return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "trade_date": r.trade_date, "score": r.score, "grade": r.grade,
                 "detail": r.detail, "risk_list": r.risk_list,
                 "created_at": str(r.created_at)} for r in rows]


def list_plans(code: str | None = None, limit: int = 50) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(PositionPlan).order_by(PositionPlan.id.desc())
        if code:
            stmt = stmt.where(PositionPlan.stock_code == code)
        rows = db.execute(stmt.limit(limit)).scalars().all()
        return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "plan_date": r.plan_date, "status": r.status, "total_pct": r.total_pct,
                 "batches": r.batches, "stop_loss": r.stop_loss, "take_profit": r.take_profit,
                 "rationale": r.rationale, "created_at": str(r.created_at)} for r in rows]


def list_holdings(status: str | None = None) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(Holding).order_by(Holding.id.desc())
        if status:
            stmt = stmt.where(Holding.status == status)
        rows = db.execute(stmt).scalars().all()
        return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "entry_date": r.entry_date, "entry_price": r.entry_price, "shares": r.shares,
                 "cost": r.cost, "stop_loss": r.stop_loss, "take_profit": r.take_profit,
                 "target_pct": r.target_pct, "status": r.status, "plan_id": r.plan_id,
                 "note": r.note, "created_at": str(r.created_at)} for r in rows]


def list_alerts(limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(select(AlertLog).order_by(AlertLog.id.desc()).limit(limit)).scalars().all()
        return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "alert_type": r.alert_type, "severity": r.severity, "message": r.message,
                 "action": r.action, "signal": r.signal, "pushed": r.pushed,
                 "created_at": str(r.created_at)} for r in rows]


def list_reviews(code: str | None = None, limit: int = 50) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(ReviewResult).order_by(ReviewResult.id.desc())
        if code:
            stmt = stmt.where(ReviewResult.stock_code == code)
        rows = db.execute(stmt.limit(limit)).scalars().all()
        return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "exit_date": r.exit_date, "hold_days": r.hold_days, "pnl_pct": r.pnl_pct,
                 "plan_vs_actual": r.plan_vs_actual, "lesson": r.lesson, "feedback": r.feedback,
                 "suggest_status": r.suggest_status, "reject_reason": r.reject_reason,
                 "suggest_iteration": r.suggest_iteration, "suggest_history": r.suggest_history or [],
                 "created_at": str(r.created_at)}
                for r in rows]


def get_review(review_id: int) -> ReviewResult | None:
    with SessionLocal() as db:
        return db.get(ReviewResult, review_id)


def list_sell_decisions(holding_id: int, limit: int = 10) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(SellDecision).where(SellDecision.holding_id == holding_id)
            .order_by(SellDecision.id.desc()).limit(limit)).scalars().all()
        return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
                 "decision": r.decision, "created_at": str(r.created_at)} for r in rows]


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
