"""
MonitorAgent 持仓监控 - LangGraph 节点（每持仓执行一次）
【刚性代码逻辑】实时行情/新闻拉取、纯数学指标、告警去重、飞书推送、落库
【交由模型推理的业务逻辑】趋势破坏/支撑压力/突发利空识别、持有/减仓/清仓建议（全部在 LLM）
流转：collect_quote → llm_signal → push_alert
"""
import logging
import time

from app.agents.common import agent_call
from agent_prompts import monitor_prompt
from app.agents.schemas import MonitorOutput
from app.cache import cache
from app.core.config import settings
from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.db.models import Holding
from app.graph.state import StockAgentState
from app.services.feishu import push_alert
from app.services.indicator import compute_indicators

logger = logging.getLogger(__name__)


def collect_quote(state: StockAgentState) -> StockAgentState:
    """节点1：拉取持仓实时行情与最新新闻【刚性代码逻辑】"""
    code = state["stock_code"]
    source = AkshareSource()
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    kline = source.fetch_daily_kline(code, _days_ago(30), today)
    indicators = compute_indicators(kline)

    news_rows: list[dict] = []
    try:
        news_df = source.fetch_news(code)
        for _, row in news_df.head(10).iterrows():
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            repo.add_news(code, state.get("stock_name") or "", title,
                          str(row.get("content") or ""), str(row.get("source") or ""),
                          str(row.get("url") or ""), str(row.get("published_at") or ""))
            news_rows.append({"title": title, "published_at": str(row.get("published_at") or "")})
    except Exception as exc:  # noqa: BLE001 新闻失败不阻塞监控
        logger.warning("监控新闻拉取失败 %s: %s", code, exc)

    state["tech_index"] = indicators
    state["news_report"] = news_rows
    state["trace"] = [*state.get("trace", []), f"行情聚合: {indicators.get('latest_date')}"]
    return state


def llm_signal(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 信号研判"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    holding = repo.get_holding(state["holding_id"]) if state.get("holding_id") else None

    if holding is None:
        state["error"] = f"持仓不存在: {state.get('holding_id')}"
        return state

    holding_info = (
        f"【持仓信息】{name}({code})\n"
        f"建仓日期: {holding.entry_date} | 成本价: {holding.entry_price} | 持仓股数: {holding.shares}\n"
        f"参考止损: {holding.stop_loss} | 参考止盈: {holding.take_profit} | 目标仓位: {holding.target_pct}%"
    )
    indicators = state.get("tech_index") or {}
    quote_data = {
        "最新指标": {k: v for k, v in indicators.items() if k != "recent_klines"},
        "近期K线": indicators.get("recent_klines", [])[-15:],
    }
    news_context = "\n".join(
        f"{n.get('published_at')} {n.get('title')}" for n in (state.get("news_report") or [])) or "（无）"

    # 盘中监控 LLM 调用节流（短 TTL 缓存）
    cache_key = f"{code}:{today}:{time.strftime('%H')}"
    output = agent_call(
        agent="monitor",
        cache_key=cache_key,
        system_prompt=monitor_prompt.SYSTEM_PROMPT,
        user_prompt=monitor_prompt.build_user_prompt(
            holding_info, _compact(quote_data), news_context),
        schema=MonitorOutput,
        ttl_seconds=max(60, settings.monitor_llm_cache_minutes * 60),
    )

    state["holding_signal"] = output.model_dump()
    state["stage"] = "holding_monitor"
    state["trace"] = [*state.get("trace", []),
                      f"信号: {output.action}({output.severity}) {output.alert_type}"]
    return state


def push_alert_node(state: StockAgentState) -> StockAgentState:
    """节点3：告警去重 + 飞书推送 + 落库【刚性代码逻辑】"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    signal = state.get("holding_signal") or {}

    if not signal:
        return state

    # 所有信号落库（面板可见）；推送按严重度与去重控制
    pushed = False
    if signal.get("action") != "hold" or signal.get("severity") in ("warning", "critical"):
        dedup_key = f"{code}:{signal.get('alert_type', 'unknown')}:{today}"
        if not cache.alert_deduplicated(dedup_key, ttl_seconds=86400):
            pushed = push_alert(name, code, signal.get("alert_type", "监控"),
                                signal.get("severity", "info"),
                                signal.get("message", ""), signal.get("action", "hold"))
        else:
            logger.info("告警去重命中，跳过推送: %s", dedup_key)

    repo.insert_alert(code, name, signal.get("alert_type", "常规跟踪"),
                      signal.get("severity", "info"), signal.get("message", ""),
                      signal.get("action", "hold"), signal, pushed)
    return state


def _compact(data) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
