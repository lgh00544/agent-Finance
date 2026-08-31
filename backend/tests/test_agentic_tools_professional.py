"""Batch 7: ReAct wrappers for existing professional read-only services."""
import inspect
import json

from app.agents import agentic_tools
from app.agents.agentic_tools import TOOL_FUNCS, TOOLS, select_tools
from app.system_map import registry


NEW_TOOLS = {
    "get_sector_regime",
    "get_factor_calibration",
    "get_distribution_phase",
    "get_capital_view",
    "get_position_risk",
    "get_hot_money_context",
}


def _tool_names(tools):
    return {item["function"]["name"] for item in tools}


def test_new_tools_registered_in_schema_and_funcs():
    assert NEW_TOOLS <= _tool_names(TOOLS)
    assert NEW_TOOLS <= set(TOOL_FUNCS)


def test_select_tools_respects_allowlist():
    tools, funcs = select_tools(["get_sector_regime"])
    assert _tool_names(tools) == {"get_sector_regime"}
    assert set(funcs) == {"get_sector_regime"}


def test_professional_tools_success_return_json_serializable(monkeypatch):
    from app.services import distribution_phase, hot_money, take_profit, track_verify

    monkeypatch.setattr(agentic_tools.repo, "get_sector_regime_forecast",
                        lambda d: {"trade_date": d, "current_regime": "mainline"})
    monkeypatch.setattr(track_verify, "get_factor_calibration", lambda period="t5": "因子校准摘要")
    monkeypatch.setattr(distribution_phase, "compute_distribution_phase",
                        lambda code, trade_date: {"phase": 2, "trade_date": trade_date})
    monkeypatch.setattr(agentic_tools.cache, "get", lambda key: None)
    monkeypatch.setattr(agentic_tools.repo, "get_capital_stats",
                        lambda code, d: {"stock_code": code, "trade_date": d, "win_rate": 0.5})
    monkeypatch.setattr(take_profit, "build_plans",
                        lambda trace=False, check_alerts=False: {"rows": [{"stock_code": "600519"}]})
    monkeypatch.setattr(hot_money, "aggregate_for_stock",
                        lambda code, name, trade_date, trace=True: {"lhb_date": trade_date, "actor": "A"})
    monkeypatch.setattr(hot_money, "build_hot_money_context",
                        lambda aggs, trade_date: "游资上下文")

    results = [
        TOOL_FUNCS["get_sector_regime"]("2026-08-31"),
        TOOL_FUNCS["get_factor_calibration"]("t5"),
        TOOL_FUNCS["get_distribution_phase"]("600519", "2026-08-31"),
        TOOL_FUNCS["get_capital_view"]("600519", "2026-08-31"),
        TOOL_FUNCS["get_position_risk"]("600519"),
        TOOL_FUNCS["get_hot_money_context"]("600519", "贵州茅台", "2026-08-31"),
    ]
    for result in results:
        json.dumps(result, ensure_ascii=False)


def test_tool_exception_returns_error(monkeypatch):
    monkeypatch.setattr(agentic_tools.repo, "get_sector_regime_forecast",
                        lambda d: (_ for _ in ()).throw(RuntimeError("boom")))
    result = TOOL_FUNCS["get_sector_regime"]("2026-08-31")
    assert "error" in result and "boom" in result["error"]


def test_sector_regime_tool_does_not_call_judge_regime(monkeypatch):
    from app.services import sector_regime

    monkeypatch.setattr(sector_regime, "judge_regime",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call")))
    monkeypatch.setattr(agentic_tools.repo, "get_sector_regime_forecast",
                        lambda d: {"trade_date": d})
    assert TOOL_FUNCS["get_sector_regime"]("2026-08-31")["regime"]["trade_date"] == "2026-08-31"


def test_capital_view_tool_does_not_compute_capital_view(monkeypatch):
    from app.services import capital_view

    monkeypatch.setattr(capital_view, "compute_capital_view",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call")))
    monkeypatch.setattr(agentic_tools.cache, "get", lambda key: None)
    monkeypatch.setattr(agentic_tools.repo, "get_capital_stats",
                        lambda code, d: {"stock_code": code, "trade_date": d})
    result = TOOL_FUNCS["get_capital_view"]("600519", "2026-08-31")
    assert result["capital_view"]["stock_code"] == "600519"


def test_hot_money_tool_passes_trace_false(monkeypatch):
    from app.services import hot_money

    captured = {}
    monkeypatch.setattr(hot_money, "aggregate_for_stock",
                        lambda code, name, trade_date, trace=True: captured.update({"trace": trace}) or {
                            "lhb_date": trade_date,
                        })
    monkeypatch.setattr(hot_money, "build_hot_money_context", lambda aggs, d: "ctx")
    result = TOOL_FUNCS["get_hot_money_context"]("600519", "贵州茅台", "2026-08-31")
    assert captured["trace"] is False
    assert result["context"] == "ctx"


def test_position_risk_tool_disables_trace_and_alerts(monkeypatch):
    from app.services import take_profit

    captured = {}
    monkeypatch.setattr(agentic_tools.cache, "get", lambda key: None)
    monkeypatch.setattr(take_profit, "build_plans",
                        lambda trace=True, check_alerts=True: captured.update({
                            "trace": trace, "check_alerts": check_alerts,
                        }) or {"rows": [{"stock_code": "600519"}, {"stock_code": "000001"}]})
    result = TOOL_FUNCS["get_position_risk"]("600519")
    assert captured == {"trace": False, "check_alerts": False}
    assert result["rows"] == [{"stock_code": "600519"}]


def test_agent_allowlists_include_professional_tools_and_monitor_rounds():
    from app.agents import monitor, score, sell

    score_src = inspect.getsource(score)
    sell_src = inspect.getsource(sell)
    monitor_src = inspect.getsource(monitor)
    for name in ("get_sector_regime", "get_factor_calibration", "get_distribution_phase",
                 "get_capital_view", "get_hot_money_context"):
        assert name in score_src
    for name in ("get_position_risk", "get_distribution_phase", "get_capital_view",
                 "get_hot_money_context"):
        assert name in sell_src
        assert name in monitor_src
    assert "max_rounds=4" in monitor_src


def test_system_map_lists_new_tools():
    tool_ids = {item["tool_id"] for item in registry.list_tools()}
    assert NEW_TOOLS <= tool_ids
