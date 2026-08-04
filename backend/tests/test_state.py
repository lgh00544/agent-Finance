"""StateGraph 编译与状态流转完整性测试（不触网、不测业务结论）"""
import pytest
from langgraph.graph import END, START, StateGraph

from app.graph.graphs import get_graph
from app.graph.state import StockAgentState

_EXPECTED_NODES = {
    "discover": {"market_condition", "hard_filter", "llm_shortlist",
                 "enrich_news", "enrich_data", "llm_final"},
    "score": {"collect_data", "llm_score"},
    "position": {"collect_plan_input", "llm_plan"},
    "monitor": {"collect_quote", "llm_signal", "push_alert_node"},
    "sell": {"collect_sell_input", "llm_sell"},
    "review": {"collect_review", "llm_review"},
}


def test_all_graphs_compile_with_expected_nodes():
    for name, nodes in _EXPECTED_NODES.items():
        graph = get_graph(name)
        compiled = graph.get_graph()
        node_ids = set(compiled.nodes)  # langchain Graph.nodes 为 id → Node 的 dict
        missing = nodes - node_ids
        assert not missing, f"{name} 图缺少节点: {missing}"


def test_unknown_graph_raises():
    with pytest.raises(KeyError):
        get_graph("no_such_graph")


def test_state_passthrough_and_partial_update():
    """节点只更新自己负责的字段，其余状态自动透传"""
    g = StateGraph(StockAgentState)
    g.add_node("a", lambda s: {**s, "tech_index": {"ma5": 1.0}})
    g.add_node("b", lambda s: {**s, "error": "测试错误"})
    g.add_edge(START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", END)

    out = g.compile().invoke({"stock_code": "600001", "trade_date": "2026-08-03"})
    assert out["stock_code"] == "600001"
    assert out["trade_date"] == "2026-08-03"
    assert out["tech_index"] == {"ma5": 1.0}
    assert out["error"] == "测试错误"


def test_sell_state_keys_survive_merge():
    """回归：sell_input/sell_decision 必须声明在 State 中，
    否则 LangGraph 合并状态时静默丢弃 → llm_sell 读不到输入（曾导致 KeyError）"""
    g = StateGraph(StockAgentState)
    g.add_node("collect", lambda s: {**s, "sell_input": {"holding": {"pnl_pct": -5.2}}})
    g.add_node("llm", lambda s: {**s, "sell_decision": {"action": "sell"}})
    g.add_edge(START, "collect")
    g.add_edge("collect", "llm")
    g.add_edge("llm", END)

    out = g.compile().invoke({"holding_id": 1, "trade_date": "2026-08-03"})
    assert out["sell_input"]["holding"]["pnl_pct"] == -5.2
    assert out["sell_decision"]["action"] == "sell"


def test_state_accumulates_trace():
    """trace 字段按节点顺序追加"""
    g = StateGraph(StockAgentState)
    g.add_node("a", lambda s: {**s, "trace": [*s.get("trace", []), "节点A"]})
    g.add_node("b", lambda s: {**s, "trace": [*s.get("trace", []), "节点B"]})
    g.add_edge(START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", END)

    out = g.compile().invoke({"stock_code": "600002"})
    assert out["trace"] == ["节点A", "节点B"]
