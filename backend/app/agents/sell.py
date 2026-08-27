"""
SellAgent 卖出决策 - LangGraph 节点（每持仓执行一次，人工按需触发）
【刚性代码逻辑】持仓/行情/监控信号/建仓计划聚合、纯数学指标、盈亏客观数值、落库
【交由模型推理的业务逻辑】卖出时机、减仓/清仓判断、卖出价位区间（全部在 LLM）
流转：collect_sell_input → llm_sell
"""
import json
import logging
import time

from app.agents.common import (ModelLevel, agent_call, agentic_call,
                               summarize_agentic_trace)
from app.agents.agentic_tools import _AGENTIC_TOOL_NOTE
from agent_prompts import sell_prompt
from app.agents.schemas import SellOutput
from app.cache import cache
from app.core.config import settings
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services import reasoning_trace
from app.services.indicator import compute_indicators

logger = logging.getLogger(__name__)

_KLINE_DAYS = 120


def collect_sell_input(state: StockAgentState) -> StockAgentState:
    """节点1：聚合卖出决策所需全部原始数据【刚性代码逻辑】"""
    holding = repo.get_holding(state["holding_id"]) if state.get("holding_id") else None
    if holding is None:
        state["error"] = f"持仓不存在: {state.get('holding_id')}"
        return state
    code = holding.stock_code
    state["stock_code"] = code
    state["stock_name"] = holding.stock_name

    source = get_datasource()
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    kline = source.fetch_daily_kline(code, _days_ago(_KLINE_DAYS), today)
    indicators = compute_indicators(kline)

    # 持仓期间监控信号历史（MonitorAgent 历次 LLM 研判，客观记录）
    signals = repo.get_alerts_by_code(code, limit=20)
    signal_rows = [{"date": s.created_at.strftime("%Y-%m-%d %H:%M"), "type": s.alert_type,
                    "severity": s.severity, "action": s.action, "message": s.message}
                   for s in signals]

    # 建仓计划原始记录（入场逻辑与止损止盈参考）
    plan = repo.get_latest_plan(code)

    # 盈亏客观数值（现价基于最近收盘）
    last_close = float(kline["close"].iloc[-1]) if not kline.empty else 0.0
    pnl_pct = round((last_close - holding.entry_price) / holding.entry_price * 100, 2) if holding.entry_price else 0.0

    # 最新新闻标题（尽力而为，失败不阻塞卖出决策）
    news_titles: list[str] = []
    try:
        news_df = source.fetch_news(code)
        news_titles = [str(r.get("title") or "").strip() for _, r in news_df.head(8).iterrows()]
        news_titles = [t for t in news_titles if t]
    except Exception as exc:  # noqa: BLE001
        logger.warning("卖出决策新闻拉取失败 %s: %s", code, exc)

    # 游资聚合数据（阶段3：龙虎榜流水聚合，口径后缀字段；无数据 None，LLM 保持标中性）
    hm_agg = None
    try:
        from app.services import hot_money as hot_money_svc
        hm_agg = hot_money_svc.aggregate_for_stock(code, state.get("stock_name") or "", today)
    except Exception as exc:  # noqa: BLE001 游资聚合失败不阻塞卖出决策
        logger.warning("卖出游资聚合失败（降级跳过）: %s", exc)

    # 组合风险上下文（单向只读 PortfolioSentinel 最近快照；未运行过如实标注不可用，不影响个股独立研判）
    portfolio_risk_context: dict = {"available": False,
                                    "note": "组合数据不可用（PortfolioSentinel 未运行或快照过期）"}
    try:
        _raw = cache.get("portfolio_sentinel:last_risk")
        if _raw:
            _risk = json.loads(_raw) if isinstance(_raw, str) else _raw
            portfolio_risk_context = {"available": True,
                                      "total_pnl_pct": _risk.get("total_pnl_pct"),
                                      "max_sector_pct": _risk.get("max_sector_pct"),
                                      "drawdown_alert": _risk.get("drawdown_alert"),
                                      "concentration_alert": _risk.get("concentration_alert")}
    except Exception as exc:  # noqa: BLE001 组合快照读取失败降级标注不可用，不阻塞卖出决策
        logger.warning("组合风险上下文读取失败（降级标注不可用）: %s", exc)

    # 派发期判定（batch D）：6 维自动判定事实（LLM 一票否决）；失败为 None 不阻断
    distribution_phase_context = None
    try:
        from app.services.distribution_phase import compute_distribution_phase
        _dist = compute_distribution_phase(code, today)
        if _dist:
            distribution_phase_context = {
                "phase": _dist.get("phase"),
                "phase_label": _dist.get("phase_label"),
                "confidence": _dist.get("confidence"),
                "six_dim": _dist.get("six_dim"),
                "missing_data": _dist.get("missing_data") or [],
            }
    except Exception as exc:  # noqa: BLE001 派发期判定失败跳过注入，不阻塞卖出决策
        logger.warning("派发期判定失败（跳过注入）: %s", exc)

    # 资本视图（批次E）：游资三维 + K189 对倒纯代码判定（portfolio_risk_context 后 D 后注入）；失败 None 不阻断
    capital_view_context = None
    try:
        from app.services.capital_view import compute_capital_view
        capital_view_context = compute_capital_view(code, today)
    except Exception as exc:  # noqa: BLE001 资本视图失败跳过注入，不阻塞卖出决策
        logger.warning("资本视图失败（跳过注入）: %s", exc)

    # K139 SOP 触发判定（批次G）：持盈不持亏事实层（参考权重，LLM 一票否决）；失败 None 不阻断
    k139_sop = None
    try:
        from app.services.red_line_check import account_total_asset, compute_red_line
        _kl = indicators.get("recent_klines") or []
        _low = float(_kl[-1].get("low")) if _kl and _kl[-1].get("low") is not None else None
        _red = compute_red_line(
            [{"stock_code": code,
              "entry_price": holding.entry_price,
              "cost": getattr(holding, "cost", None),
              "shares": holding.shares,
              "high_price": getattr(holding, "high_price", None)}],
            {code: last_close},
            account_total_asset(), trade_date=today, lows={code: _low})
        if _red:
            k139_sop = _red[0].get("k139_sop")
    except Exception as exc:  # noqa: BLE001 K139 SOP 失败跳过注入，不阻塞卖出决策
        logger.warning("K139 SOP 触发判定失败（跳过注入）: %s", exc)

    state["sell_input"] = {
        "holding": {"entry_date": holding.entry_date, "entry_price": holding.entry_price,
                    "shares": holding.shares, "stop_loss": holding.stop_loss,
                    "take_profit": holding.take_profit, "target_pct": holding.target_pct,
                    "note": holding.note, "latest_close": last_close, "pnl_pct": pnl_pct},
        "plan": {"rationale": plan.rationale if plan else "",
                 "batches": plan.batches if plan else [],
                 "stop_loss": plan.stop_loss if plan else 0,
                 "take_profit": plan.take_profit if plan else 0},
        "monitor_signals": signal_rows,
        "news_titles": news_titles,
        "hot_money": hm_agg,
        "portfolio_risk_context": portfolio_risk_context,
        "distribution_phase_context": distribution_phase_context,
        "capital_view_context": capital_view_context,
        # K139 SOP 触发判定（批次G）：{trailing_stop, stage, next_action}，参考权重非死条件
        "k139_sop": k139_sop,
    }
    state["tech_index"] = indicators
    state["trace"] = [*state.get("trace", []),
                      f"卖出数据聚合: 现价{last_close} 盈亏{pnl_pct}% 信号{len(signal_rows)}条"]
    return state


def llm_sell(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 卖出决策研判 + 落库"""
    if state.get("error"):
        return state
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    data = state["sell_input"]

    holding_info = (
        f"股票: {name}({code})\n"
        f"建仓日期: {data['holding']['entry_date']} | 成本价: {data['holding']['entry_price']} | "
        f"持仓股数: {data['holding']['shares']} | 现价(最近收盘): {data['holding']['latest_close']} | "
        f"当前盈亏: {data['holding']['pnl_pct']}%\n"
        f"参考止损: {data['holding']['stop_loss']} | 参考止盈: {data['holding']['take_profit']} | "
        f"目标仓位: {data['holding']['target_pct']}%\n"
        f"人工备注: {data['holding']['note'] or '（无）'}"
    )
    signals_text = json.dumps(data["monitor_signals"], ensure_ascii=False, default=str) or "（无监控记录）"
    plan_info = (
        f"建仓逻辑: {data['plan']['rationale'] or '（无）'}\n"
        f"分批方案: {json.dumps(data['plan']['batches'], ensure_ascii=False, default=str)}\n"
        f"计划止损: {data['plan']['stop_loss']} | 计划止盈: {data['plan']['take_profit']}"
    )
    quote_pack = {
        "最新指标": {k: v for k, v in (state.get("tech_index") or {}).items() if k != "recent_klines"},
        "近期K线": (state.get("tech_index") or {}).get("recent_klines", [])[-20:],
        "最新新闻标题": data["news_titles"],
        # 游资聚合（阶段3）：口径后缀字段 lhb_1d_net_buy/lhb_3d_net_buy，无数据 None
        "游资聚合": data.get("hot_money"),
        # K139 SOP 触发判定（批次G）：持盈不持亏事实层（缺失为 None 不注入噪音）
        "【K139 SOP 触发判定】": data.get("k139_sop"),
    }

    # 组合风险上下文 → 文本（只读参考；缺失标注不可用，不影响个股独立研判）
    risk_ctx = data.get("portfolio_risk_context") or {}
    if risk_ctx.get("available"):
        portfolio_risk_text = (
            f"组合总盈亏: {risk_ctx.get('total_pnl_pct') or '数据不足'}% | "
            f"最大板块占比: {risk_ctx.get('max_sector_pct') or '数据不足'}% | "
            f"组合回撤预警: {'触发' if risk_ctx.get('drawdown_alert') else '未触发'} | "
            f"集中度预警: {'触发' if risk_ctx.get('concentration_alert') else '未触发'}"
        )
    else:
        portfolio_risk_text = (risk_ctx.get("note")
                               or "组合数据不可用（PortfolioSentinel 未运行或快照过期）")

    sell_cache_key = f"selldec:{code}:{today}"
    sell_user_prompt = sell_prompt.build_user_prompt(
        holding_info, signals_text, plan_info,
        json.dumps(quote_pack, ensure_ascii=False, default=str),
        portfolio_risk_context=portfolio_risk_text)
    agentic_trace: dict = {}
    if settings.agentic_enable:
        output, agentic_trace = agentic_call(
            agent="sell", cache_key=sell_cache_key,
            system_prompt=_AGENTIC_TOOL_NOTE + sell_prompt.SYSTEM_PROMPT,
            user_prompt=sell_user_prompt,
            schema=SellOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP,
            target_label=f"{name}({code})",
        )
    else:
        output = agent_call(
            agent="sell", cache_key=sell_cache_key,
            system_prompt=sell_prompt.SYSTEM_PROMPT, user_prompt=sell_user_prompt,
            schema=SellOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP,
        )

    decision = output.model_dump()
    if agentic_trace:
        decision["model_thinking"], decision["tool_trace"] = summarize_agentic_trace(agentic_trace)
        # 落库前删两字段：sell_decision 表本体不写 thinking，仅 trace 透传（覆盖 insert 内部空 ext_info 行）
        clean = {k: v for k, v in decision.items() if k not in ("model_thinking", "tool_trace")}
        repo.insert_sell_decision(state["holding_id"], code, name, clean)
        reasoning_trace.trace_sell(code, name, time.strftime("%Y-%m-%d"), decision)
    else:
        repo.insert_sell_decision(state["holding_id"], code, name, decision)
    state["sell_decision"] = decision
    state["stage"] = "sell_decision"
    state["trace"] = [*state.get("trace", []),
                      f"卖出决策完成: {output.action}({output.confidence})"]
    logger.info("卖出决策完成 %s: %s(%s)", code, output.action, output.confidence)
    return state


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
