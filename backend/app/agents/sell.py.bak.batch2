"""
SellAgent 卖出决策 - LangGraph 节点（每持仓执行一次，人工按需触发）
【刚性代码逻辑】持仓/行情/监控信号/建仓计划聚合、纯数学指标、盈亏客观数值、落库
【交由模型推理的业务逻辑】卖出时机、减仓/清仓判断、卖出价位区间（全部在 LLM）
流转：collect_sell_input → llm_sell
"""
import json
import logging
import time

from app.agents.common import ModelLevel, agent_call
from agent_prompts import sell_prompt
from app.agents.schemas import SellOutput
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
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
    }

    output = agent_call(
        agent="sell",
        cache_key=f"selldec:{code}:{today}",
        system_prompt=sell_prompt.SYSTEM_PROMPT,
        user_prompt=sell_prompt.build_user_prompt(
            holding_info, signals_text, plan_info, json.dumps(quote_pack, ensure_ascii=False, default=str)),
        schema=SellOutput,
        ttl_seconds=86400,
        model_level=ModelLevel.DEEP,
    )

    repo.insert_sell_decision(state["holding_id"], code, name, output.model_dump())
    state["sell_decision"] = output.model_dump()
    state["stage"] = "sell_decision"
    state["trace"] = [*state.get("trace", []),
                      f"卖出决策完成: {output.action}({output.confidence})"]
    logger.info("卖出决策完成 %s: %s(%s)", code, output.action, output.confidence)
    return state


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
