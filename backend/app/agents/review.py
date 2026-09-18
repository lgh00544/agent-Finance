"""
ReviewAgent 卖出复盘 - LangGraph 节点
【刚性代码逻辑】读取建仓计划/交易记录/全程行情，计算盈亏与持仓天数的客观数值
【交由模型推理的业务逻辑】逻辑兑现度对比、盈亏归因、经验教训、筛选偏好微调（全部在 LLM）
流转：collect_review → llm_review；建议驳回后由 llm_rethink_suggestion 驱动重思考迭代
"""
import logging
import json
import time
from datetime import date
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


def _day_text(value: object, fallback: str = "") -> str:
    """将日期/时间值归一为 YYYY-MM-DD；异常值返回 fallback。"""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "")[:10]
    try:
        date.fromisoformat(text)
    except ValueError:
        return fallback
    return text


def _in_period(value: object, start_date: str, end_date: str) -> bool:
    day = _day_text(value)
    return bool(day) and start_date <= day <= end_date


def _active_rule_context() -> str:
    """把全部目标 Agent 的生效规则作为去重/归因材料提供给 ReviewAgent。"""
    try:
        rules = repo.get_active_rules()
    except Exception as exc:  # noqa: BLE001 规则读取失败不阻塞复盘主链路
        logger.warning("复盘读取生效规则失败（跳过规则去重材料）: %s", exc)
        return ""
    if not rules:
        return ""
    return (
        "\n\n【各目标 Agent 已生效规则（仅用于去重与归因）】\n"
        + json.dumps(
            [{"target_agent": r.get("target_agent"), "rule_name": r.get("rule_name"),
              "rule_text": r.get("rule_text")} for r in rules],
            ensure_ascii=False)
    )


def collect_review(state: StockAgentState) -> StockAgentState:
    """节点1：聚合复盘所需全部原始数据【刚性代码逻辑】"""
    holding = repo.get_holding(state["holding_id"]) if state.get("holding_id") else None
    if holding is None:
        state["error"] = f"持仓不存在: {state.get('holding_id')}"
        return state
    code = holding.stock_code
    state["stock_code"] = code
    state["stock_name"] = holding.stock_name

    entry_date = _day_text(holding.entry_date, _today())
    all_trades = repo.get_trades(holding.id)
    all_sells = [t for t in all_trades if t.side == "sell"]
    # 退出日以最后一笔卖出成交日为准；旧数据没有卖出流水时退回本次任务日期。
    exit_date = max((_day_text(t.trade_date) for t in all_sells), default="")
    if not exit_date:
        exit_date = _day_text(state.get("trade_date"), _today())
    if exit_date < entry_date:
        exit_date = entry_date
    # 同一持仓的原始流水也限定在生命周期内，避免异常补录污染客观口径。
    trades = [t for t in all_trades if _in_period(t.trade_date, entry_date, exit_date)]
    sells = [t for t in trades if t.side == "sell"]
    buys = [t for t in trades if t.side == "buy"]

    # 客观数值：持仓天数 = 末次卖出日 - 首次买入日；盈亏：exited 用总成本口径（治建仓流水缺失漏计底仓），cost 缺失回退 Σ卖−Σ买
    hold_days = 0
    pnl_pct = 0.0
    pnl_caliber = ""  # 口径回退标注（进 trace）
    if sells and buys:
        def _d(s: str) -> date:
            return date.fromisoformat(_day_text(s))

        hold_days = (_d(sells[-1].trade_date) - _d(buys[0].trade_date)).days
        sell_amount = sum(t.amount for t in sells)
        cost = holding.cost
        if holding.status == "exited" and cost and cost > 0:
            pnl_pct = round((sell_amount - cost) / cost * 100, 2)
        else:
            buy_amount = sum(t.amount for t in buys)
            if buy_amount > 0:
                pnl_pct = round((sell_amount - buy_amount) / buy_amount * 100, 2)
                pnl_caliber = "（cost 缺失，回退 Σ卖−Σ买 口径）"

    plan = repo.get_plan(getattr(holding, "plan_id", None))
    plan_binding = "holding.plan_id" if plan is not None else "missing"
    if plan is None and not getattr(holding, "plan_id", None):
        plan, plan_binding = repo.get_plan_for_entry(code, holding.entry_date)
    # 复盘只读取入场时点已存在的评分版本，禁止把退出后重评分带入历史结论。
    score_row = repo.get_latest_score(code, as_of=entry_date)

    # 全链路落地表现聚合：持仓期间监控信号历史 + 卖出决策记录（各 Agent 输出方案的客观记录）
    alerts = repo.get_alerts_by_code(code, limit=30,
                                     start_date=entry_date, end_date=exit_date)
    alerts = [a for a in alerts
              if _in_period(getattr(a, "created_at", None), entry_date, exit_date)]
    signal_rows = [{"date": a.created_at.strftime("%Y-%m-%d %H:%M"), "type": a.alert_type,
                    "severity": a.severity, "action": a.action, "message": a.message} for a in alerts]
    # 游资信号历史（留痕 source_module='hot_money'）：失败标的回溯当时游资信号的成败依据
    import json as _json

    # 先在仓储层按退出日截断，再做入场日过滤；否则历史复盘可能被近 10 条未来留痕占满。
    hm_traces = repo.list_traces(code=code, module="hot_money", limit=10,
                                 end_date=exit_date)
    hm_traces = [t for t in hm_traces
                 if _in_period(t.get("generate_date"), entry_date, exit_date)]
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
    sell_decisions = repo.get_sell_decisions_by_code(
        code, limit=10, holding_id=holding.id,
        start_date=entry_date, end_date=exit_date)
    sell_decisions = [s for s in sell_decisions
                      if _in_period(getattr(s, "created_at", None), entry_date, exit_date)]
    sell_rows = [{"date": s.created_at.strftime("%Y-%m-%d %H:%M"),
                  "action": (s.decision or {}).get("action"),
                  "confidence": (s.decision or {}).get("confidence"),
                  "reasons": (s.decision or {}).get("reasons", [])} for s in sell_decisions]

    source = get_datasource()
    # 行情查询边界与持仓生命周期一致，避免退出后的 K 线泄露到复盘统计。
    kline = source.fetch_daily_kline(code, entry_date, exit_date)

    # 持仓期间行情统计（客观数值）
    if (kline is not None and hasattr(kline, "empty") and not kline.empty
            and "date" in kline.columns):
        kline_days = kline["date"].map(_day_text)
        series = kline[(kline_days >= entry_date) & (kline_days <= exit_date)].copy()
        series["_review_day"] = kline_days.loc[series.index]
        series = series.sort_values("_review_day")
    else:
        series = kline.iloc[0:0] if kline is not None else []
    price_stats = {}
    if hasattr(series, "empty") and not series.empty:
        price_stats = {
            "period_high": float(series["high"].max()),
            "period_low": float(series["low"].min()),
            "exit_day_close": float(series["close"].iloc[-1]),
            "exit_day_change_pct": float(series["change_pct"].iloc[-1]),
        }

    state["exit_suggest"] = {
        "holding": {"entry_date": entry_date, "exit_date": exit_date,
                    "entry_price": holding.entry_price,
                    "shares": holding.shares, "stop_loss": holding.stop_loss,
                    "take_profit": holding.take_profit, "note": holding.note},
        "trades": [{"side": t.side, "price": t.price, "shares": t.shares,
                    "amount": t.amount, "trade_date": t.trade_date} for t in trades],
        "plan": {"plan_id": plan.id if plan else None,
                 "binding": plan_binding,
                 "rationale": plan.rationale if plan else "",
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
        "portfolio_attribution": _portfolio_attribution(code, pnl_pct, exit_date),
        # 周期复利 + 组合归因（批次H）：历史多次操作汇总 + 组合曲线/贡献者/最大拖累者（复盘顶部事实）
        # 组合当前视角无法证明历史时点；历史复盘明确返回缺失状态，避免把今天的持仓
        # 曲线或周期统计伪装成退出日已经知道的事实。
        "cycle_attribution": (_cycle_attribution(code)
                               if exit_date >= _today()
                               else {"status": "not_reconstructed", "as_of": exit_date}),
        "portfolio_curve": (_portfolio_curve_summary()
                             if exit_date >= _today()
                             else {"status": "not_reconstructed", "as_of": exit_date}),
    }
    state["trace"] = [*state.get("trace", []),
                      f"复盘数据聚合: 持有{hold_days}天 盈亏{pnl_pct}%{pnl_caliber} 信号{len(signal_rows)}条 "
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


def _cycle_attribution(code: str) -> dict | None:
    """批次H：该股历史多次操作的周期复利汇总（参考权重；失败返回 None 不阻塞复盘）"""
    try:
        from app.services.track_verify import build_stock_cycle_attribution
        return build_stock_cycle_attribution(code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("周期复利读取失败（跳过注入）: %s", exc)
        return None


def _portfolio_curve_summary() -> dict:
    """批次H：组合归因摘要（曲线 + 贡献者 + 最大拖累者；失败返回空结构不阻塞复盘）"""
    try:
        from app.services.track_verify import build_portfolio_attribution
        return build_portfolio_attribution(30)
    except Exception as exc:  # noqa: BLE001
        logger.warning("组合归因读取失败（跳过注入）: %s", exc)
        return {"portfolio_curve": [], "contributors": [], "drag_analysis": None}


def llm_review(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 复盘 + 落库 + 偏好回流"""
    if state.get("error"):
        return state
    data = state["exit_suggest"]
    code = state["stock_code"]
    name = state.get("stock_name") or code
    # 复盘的业务日期必须来自事实包的最后卖出日；任务提交日期只是调度元数据。
    exit_date = str((data.get("holding") or {}).get("exit_date") or
                    state.get("trade_date") or time.strftime("%Y-%m-%d"))[:10]

    existing = repo.get_review_for_holding_exit(state["holding_id"], exit_date)
    if existing is not None:
        state["stage"] = "exit_review"
        state["review_id"] = existing.id
        state["trace"] = [*state.get("trace", []),
                          f"复盘已存在: review_id={existing.id}，跳过重复生成"]
        return state

    # 历史驳回记录注入：反映用户真实偏好，避免再次提出同类建议
    reject_section = review_prompt.build_reject_history_section(
        repo.get_review_reject_history(code, limit=10))
    review_data = "【复盘数据】（客观数值与原始记录）\n" + json.dumps(data, ensure_ascii=False, default=str)
    if reject_section:
        review_data += "\n\n" + reject_section
    review_data += _active_rule_context()

    output = agent_call(
        agent="review",
        cache_key=f"{code}:{data['holding'].get('entry_date')}:{exit_date}",
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
        code, name, state["holding_id"], exit_date,
        int(data.get("hold_days", 0)), float(data.get("pnl_pct", 0.0)),
        output.plan_vs_actual, output.lesson, stored_feedback,
    )
    # 偏好回流：先留在待审核状态；人工采纳后才注入后续 Discover/Score prompt
    repo.upsert_preference(output.feedback, source_review_id=review_id, status="pending")
    # 策略闭环：各 Agent 优化建议落库为 pending，必须人工审核确认后才生效
    # （v2 一键采纳落地信息随建议持久化：rule_text/rule_type/priority/落地元数据）
    suggestion_count = 0
    for item in output.agent_suggestions:
        sid = repo.insert_agent_suggestion(
            review_id, item.target_agent, item.rule_name,
            item.current_value, item.suggested_value, item.reason, item.evidence,
            target_kind=item.target_kind,
            rule_type=item.rule_type, priority=item.priority,
            problem_desc=item.problem_desc, rule_text=item.rule_text,
            expected_effect=item.expected_effect, risk_note=item.risk_note,
            file_path=item.file_path, insert_position=item.insert_position,
            dedupe=True)
        suggestion_count += int(bool(sid))
    # 游资复盘闭环留痕：失败标的回溯游资信号结论（source_module='hot_money_review'，
    # 只留痕不改任何配置；无游资信号可回溯时 LLM 输出 null 跳过）
    hm_reviewed = False
    if getattr(output, "hot_money_review", None):
        reasoning_trace.trace_hot_money_review(code, name, exit_date,
                                               dict(output.hot_money_review))
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
    original_text += _active_rule_context()

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
    # 新一轮反馈仍需人工采纳；保留旧版本以便审计和回溯。
    repo.upsert_preference(stored_feedback, source_review_id=review_id, status="pending")
    logger.info("建议重思考 %s: 第%s版（原因: %s）", row.stock_code, new_iteration, reject_reason)
    return {"iteration": new_iteration, "feedback": stored_feedback,
            "profile_suggestion": stored_feedback.get("profile_suggestion")}


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def paper_review_cycle(facts: dict) -> dict:
    """Review a frozen paper snapshot; do not invoke collect_review or live repos."""
    from app.services.paper_analysis import review_cycle

    return review_cycle(facts)
