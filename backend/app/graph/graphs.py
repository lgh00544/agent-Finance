"""
LangGraph 图定义：5 个 StateGraph，编译一次全局缓存
【刚性代码逻辑】图结构只描述流转顺序，节点内不包含任何市场判断。
"""
import logging

from langgraph.graph import END, START, StateGraph

from app.agents import discover, monitor, position, review, score, sell
from app.graph.state import StockAgentState

logger = logging.getLogger(__name__)

_graphs: dict[str, object] = {}


def _build_discover() -> StateGraph:
    g = StateGraph(StockAgentState)
    g.add_node("market_condition", discover.market_condition)
    g.add_node("hard_filter", discover.hard_filter)
    g.add_node("llm_shortlist", discover.llm_shortlist)
    g.add_node("enrich_news", discover.enrich_news)
    g.add_node("enrich_data", discover.enrich_data)
    g.add_node("llm_final", discover.llm_final)
    g.add_edge(START, "market_condition")
    g.add_edge("market_condition", "hard_filter")
    g.add_edge("hard_filter", "llm_shortlist")
    g.add_edge("llm_shortlist", "enrich_news")
    g.add_edge("enrich_news", "enrich_data")
    g.add_edge("enrich_data", "llm_final")
    g.add_edge("llm_final", END)
    return g


def _build_score() -> StateGraph:
    g = StateGraph(StockAgentState)
    g.add_node("collect_data", score.collect_data)
    g.add_node("llm_score", score.llm_score)
    g.add_edge(START, "collect_data")
    g.add_edge("collect_data", "llm_score")
    g.add_edge("llm_score", END)
    return g


def _build_position() -> StateGraph:
    g = StateGraph(StockAgentState)
    g.add_node("collect_plan_input", position.collect_plan_input)
    g.add_node("llm_plan", position.llm_plan)
    g.add_edge(START, "collect_plan_input")
    g.add_edge("collect_plan_input", "llm_plan")
    g.add_edge("llm_plan", END)
    return g


def _build_monitor() -> StateGraph:
    g = StateGraph(StockAgentState)
    g.add_node("collect_quote", monitor.collect_quote)
    g.add_node("llm_signal", monitor.llm_signal)
    g.add_node("push_alert_node", monitor.push_alert_node)
    g.add_edge(START, "collect_quote")
    g.add_edge("collect_quote", "llm_signal")
    g.add_edge("llm_signal", "push_alert_node")
    g.add_edge("push_alert_node", END)
    return g


def _build_sell() -> StateGraph:
    g = StateGraph(StockAgentState)
    g.add_node("collect_sell_input", sell.collect_sell_input)
    g.add_node("llm_sell", sell.llm_sell)
    g.add_edge(START, "collect_sell_input")
    g.add_edge("collect_sell_input", "llm_sell")
    g.add_edge("llm_sell", END)
    return g


def _build_review() -> StateGraph:
    g = StateGraph(StockAgentState)
    g.add_node("collect_review", review.collect_review)
    g.add_node("llm_review", review.llm_review)
    g.add_edge(START, "collect_review")
    g.add_edge("collect_review", "llm_review")
    g.add_edge("llm_review", END)
    return g


_BUILDERS = {
    "discover": _build_discover,
    "score": _build_score,
    "position": _build_position,
    "monitor": _build_monitor,
    "sell": _build_sell,
    "review": _build_review,
}


def get_graph(name: str):
    """获取编译后的图（全局缓存）"""
    if name not in _BUILDERS:
        raise KeyError(f"未知图: {name}")
    if name not in _graphs:
        _graphs[name] = _BUILDERS[name]().compile()
        logger.info("图 %s 编译完成", name)
    return _graphs[name]
