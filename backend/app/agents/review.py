"""
ReviewAgent 卖出复盘 - LangGraph 节点
【刚性代码逻辑】读取建仓计划/交易记录/全程行情，计算盈亏与持仓天数的客观数值
【交由模型推理的业务逻辑】逻辑兑现度对比、盈亏归因、经验教训、筛选偏好微调（全部在 LLM）
流转：collect_review → llm_review；建议驳回后由 llm_rethink_suggestion 驱动重思考迭代
"""
import logging
import time
from hashlib import md5

from app.agents.common import ModelLevel, agent_call
from agent_prompts import review_prompt
from app.agents.schemas import ReviewOutput
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services import reasoning_trace
from app.agents.portfolio_sentinel import read_portfolio_overview

logger = logging.getLogger(__name__)


def collect_review(state: StockAgentState) -> StockAgentState:
    """节点1：聚合复盘所需全部原始数据【刚性代码逻辑】"""
    holding = repo.get_holding(state["holding_id"]) if state.get("holding_id") else None
    if holding is None:
        state["error"] = f"持仓不存在: {state.get('holding_id')}"
        return state
    code = holding.stock_code
    state["stock_code"] = code
    state["stock_name"] = holding.stock_name

    trades = repo.get_trades(holding.id)
    sells = [t for t in trades if t.side == "sell"]
    buys = [t for t in trades if t.side == "buy"]

    # 客观数值：持仓天数 = 末次卖出日 - 首次买入日；盈亏 = 卖出额 - 买入额（简化口径）
    hold_days = 0
    pnl_pct = 0.0
    if sells and buys:
        from datetime import date

        def _d(s: str) -> date:
            return date.fromisoformat(s)

        hold_days = (_d(sells[-1].trade_date) - _d(buys[0].trade_date)).days
        buy_amount = sum(t.amount for t in buys)
        sell_amount = sum(t.amount for t in sells)
        if buy_amount > 0:
            pnl_pct = round((sell_amount - buy_amount) / buy_amount * 100, 2)

    plan = repo.get_latest_plan(code)
    score_row = repo.get_latest_score(code)

    # 全链路落地表现聚合：持仓期间监控信号历史 + 卖出决策记录（各 Agent 输出方案的客观记录）
    alerts = repo.get_alerts_by_code(code, limit=30)
    signal_rows = [{"date": a.created_at.strftime("%Y-%m-%d %H:%M"), "type": a.alert_type,
                    "severity": a.severity, "action": a.action, "message": a.message} for a in alerts]
    # 游资信号历史（留痕 source_module='hot_money'）：失败标的回溯当时游资信号的成败依据
    import json as _json

    hm_traces = repo.list_traces(code=code, module="hot_money", limit=10)
    hm_signals = []
    for t in hm_traces:
        try:
            concl = _json.loads(t.get("final_conclusion") or "{}")
        except (ValueError, TypeError):
            concl = {}
        try:
            cap = _json.loads(t.get("capital_reasoning") or "{}")
        except (ValueError, TypeError):
            cap = {}
        hm_signals.append({
            "generate_date": t.get("generate_date"),
            "seat": cap.get("seat_name") or "", "actor": cap.get("actor") or "",
            "net_buy": cap.get("lhb_1d_net_buy"),
            "multi_source_verified": bool(concl.get("multi_source_verified")),
            "confidence": concl.get("confidence"),
            "risk_note": t.get("risk_reasoning") or "",
        })
    sell_decisions = repo.get_sell_decisions_by_code(code, limit=10)
    sell_rows = [{"date": s.created_at.strftime("%Y-%m-%d %H:%M"),
                  "action": (s.decision or {}).get("action"),
                  "confidence": (s.decision or {}).get("confidence"),
                  "reasons": (s.decision or {}).get("reasons", [])} for s in sell_decisions]

    source = get_datasource()
    kline = source.fetch_daily_kline(code, holding.entry_date.replace("-", "")[:4] + "0101", _today())

    # 持仓期间行情统计（客观数值）
    series = kline[kline["date"] >= holding.entry_date]
    price_stats = {}
    if not series.empty:
        price_stats = {
            "period_high": float(series["high"].max()),
            "period_low": float(series["low"].min()),
            "exit_day_close": float(series["close"].iloc[-1]),
            "exit_day_change_pct": float(series["change_pct"].iloc[-1]),
        }

    state["exit_suggest"] = {
        "holding": {"entry_date": holding.entry_date, "entry_price": holding.entry_price,
                    "shares": holding.shares, "stop_loss": holding.stop_loss,
                    "take_profit": holding.take_profit, "note": holding.note},
        "trades": [{"side": t.side, "price": t.price, "shares": t.shares,
                    "amount": t.amount, "trade_date": t.trade_date} for t in trades],
        "plan": {"rationale": plan.rationale if plan else "",
                 "batches": plan.batches if plan else [],
                 "stop_loss": plan.stop_loss if plan else 0,
                 "take_profit": plan.take_profit if plan else 0},
        "score": {"score": score_row.score if score_row else None,
                  "grade": score_row.grade if score_row else None,
                  "risk_list": score_row.risk_list if score_row else []},
        "monitor_signals": signal_rows,
        "sell_decisions": sell_rows,
        "hot_money_signals": hm_signals,  # 游资信号历史（复盘闭环回溯依据，无数据为空列表）
        "hold_days": hold_days,
        "pnl_pct": pnl_pct,
        "price_stats": price_stats,
        "portfolio_attribution": _portfolio_attribution(
            code, pnl_pct, state.get("trade_date") or time.strftime("%Y-%m-%d")),
    }
    state["trace"] = [*state.get("trace", []),
                      f"复盘数据聚合: 持有{hold_days}天 盈亏{pnl_pct}% 信号{len(signal_rows)}条 "
                      f"卖出决策{len(sell_rows)}条 游资信号{len(hm_signals)}条"]
    return state


def _portfolio_attribution(code: str, pnl_pct: float | None, trade_date: str) -> dict:
    """该笔交易对组合 P&L 的贡献分解（batch F 组合联动）：{contrib_pct, alpha, drawdown_contrib}。

    - contrib_pct：该股自身盈亏%（对组合收益的直接贡献，参考权重）
    - alpha      ：该股盈亏扣除市场β后的超额（= pnl_pct − 市场成分 system）
    - drawdown_contrib：该股对组合回撤的贡献（pnl<0 时为 pnl，否则 0）
    组合概览缺失（无快照/无沪深300）→ 对应字段 None + missing_data，不编造（K223 事实为先）。
    """
    po = read_portfolio_overview(trade_date)
    decomp = (po.get("drawdown_decomp") or {}) if isinstance(po.get("drawdown_decomp"), dict) else {}
    system = decomp.get("system")
    missing: list[str] = []
    if pnl_pct is None:
        missing.append("pnl_pct")
    if system is None:
        missing.append("csi300_index")
    return {
        "contrib_pct": pnl_pct,          # 该股对组合收益的贡献%（未做权重调整的简化口径，参考权重）
        "alpha": round(pnl_pct - system, 2) if (pnl_pct is not None and system is not None) else None,
        "drawdown_contrib": round(pnl_pct, 2) if (pnl_pct is not None and pnl_pct < 0) else 0.0,
        "missing_data": missing,
    }


def llm_review(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 复盘 + 落库 + 偏好回流"""
    if state.get("error"):
        return state
    data = state["exit_suggest"]
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    import json

    # 历史驳回记录注入：反映用户真实偏好，避免再次提出同类建议
    reject_section = review_prompt.build_reject_history_section(
        repo.get_review_reject_history(code, limit=10))
    review_data = "【复盘数据】（客观数值与原始记录）\n" + json.dumps(data, ensure_ascii=False, default=str)
    if reject_section:
        review_data += "\n\n" + reject_section

    output = agent_call(
        agent="review",
        cache_key=f"{code}:{data['holding'].get('entry_date')}:{today}",
        system_prompt=review_prompt.SYSTEM_PROMPT,
        user_prompt=review_prompt.build_user_prompt(review_data),
        schema=ReviewOutput,
        ttl_seconds=86400,
        model_level=ModelLevel.DEEP,
    )

    # profile_suggestion 随 feedback 持久化（供前端一键采纳/驳回）
    stored_feedback = dict(output.feedback)
    if output.profile_suggestion is not None:
        stored_feedback["profile_suggestion"] = output.profile_suggestion.model_dump()

    review_id = repo.insert_review(
        code, name, state["holding_id"], today,
        int(data.get("hold_days", 0)), float(data.get("pnl_pct", 0.0)),
        output.plan_vs_actual, output.lesson, stored_feedback,
    )
    # 偏好回流：feedback 写入档案，注入后续 Discover/Score prompt
    repo.upsert_preference(output.feedback, source_review_id=review_id)
    # 策略闭环：各 Agent 优化建议落库为 pending，必须人工审核确认后才生效
    # （v2 一键采纳落地信息随建议持久化：rule_text/rule_type/priority/落地元数据）
    suggestion_count = 0
    for item in output.agent_suggestions:
        repo.insert_agent_suggestion(
            review_id, item.target_agent, item.rule_name,
            item.current_value, item.suggested_value, item.reason, item.evidence,
            target_kind=item.target_kind,
            rule_type=item.rule_type, priority=item.priority,
            problem_desc=item.problem_desc, rule_text=item.rule_text,
            expected_effect=item.expected_effect, risk_note=item.risk_note,
            file_path=item.file_path, insert_position=item.insert_position)
        suggestion_count += 1
    # 游资复盘闭环留痕：失败标的回溯游资信号结论（source_module='hot_money_review'，
    # 只留痕不改任何配置；无游资信号可回溯时 LLM 输出 null 跳过）
    hm_reviewed = False
    if getattr(output, "hot_money_review", None):
        reasoning_trace.trace_hot_money_review(code, name, today, dict(output.hot_money_review))
        hm_reviewed = True
    state["stage"] = "exit_review"
    state["trace"] = [*state.get("trace", []),
                      f"复盘完成: review_id={review_id} 优化建议{suggestion_count}条(待人工审核)"
                      + (f" 游资信号回溯已留痕（{output.hot_money_review.get('classification') or ''}）"
                         if hm_reviewed else " 游资信号回溯无")]
    logger.info("复盘完成 %s: review_id=%s 建议%s条 游资回溯%s", code, review_id,
                suggestion_count, "已留痕" if hm_reviewed else "无")
    return state


def llm_rethink_suggestion(review_id: int, reject_reason: str) -> dict:
    """建议驳回重思考（用户驱动，绕过缓存）：
    结合原始复盘结论 + 驳回原因 + 历史迭代轨迹，重新生成调整后的优化建议并回写待审核"""
    import json

    row = repo.get_review(review_id)
    if row is None:
        raise ValueError(f"复盘记录不存在: {review_id}")

    repo.append_review_iteration(review_id, reject_reason)
    new_iteration = row.suggest_iteration + 1
    history = [{"iteration": h.get("iteration"), "suggestion": h.get("suggestion"),
                "reject_reason": h.get("reject_reason")} for h in (row.suggest_history or [])]

    original_text = json.dumps({
        "plan_vs_actual": row.plan_vs_actual,
        "lesson": row.lesson,
        "feedback": row.feedback,
        "suggest_iteration": row.suggest_iteration,
    }, ensure_ascii=False, default=str)

    output = agent_call(
        agent="review",
        cache_key=f"reviewrethink:{review_id}:{new_iteration}:{md5(reject_reason.encode('utf-8')).hexdigest()[:8]}",
        system_prompt=review_prompt.SYSTEM_PROMPT,
        user_prompt=review_prompt.build_rethink_user_prompt(original_text, reject_reason, history),
        schema=ReviewOutput,
        ttl_seconds=1,  # 用户驱动的重思考：不进当日缓存，每次驳回都重新推理
        model_level=ModelLevel.DEEP,
    )

    stored_feedback = dict(output.feedback)
    if output.profile_suggestion is not None:
        stored_feedback["profile_suggestion"] = output.profile_suggestion.model_dump()
    repo.apply_rethink_suggestion(review_id, stored_feedback, new_iteration)
    logger.info("建议重思考 %s: 第%s版（原因: %s）", row.stock_code, new_iteration, reject_reason)
    return {"iteration": new_iteration, "feedback": stored_feedback,
            "profile_suggestion": stored_feedback.get("profile_suggestion")}


def _today() -> str:
    return time.strftime("%Y-%m-%d")
