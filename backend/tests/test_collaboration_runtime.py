"""Batch 11: runtime collaboration guard for internal Agent calls."""
from pathlib import Path

from app.agents import agentic_tools
from app.services import chat_handlers as ch
from app.system_map import collaboration


def test_check_collaboration_allows_explicit_reference_relation():
    result = collaboration.check_collaboration("score", "discover", "reference")
    assert result["allowed"] is True
    assert result["caller"] == "score"
    assert result["target"] == "discover"
    assert result["unknown"] is False


def test_dispatch_allows_explicit_internal_call(monkeypatch):
    called = {"n": 0}
    monkeypatch.setitem(ch._HANDLERS, "monitor",
                        lambda params, hint: called.update(n=called["n"] + 1) or "ok")
    result = ch.dispatch("内部监控", "monitor", {"_caller_agent": "chat_entry"}, "", "ou_rt")
    assert result == "ok"
    assert called["n"] == 1


def test_default_forbidden_relation_is_rejected_and_target_not_executed(monkeypatch):
    called = {"n": 0}
    monkeypatch.setitem(ch._HANDLERS, "review",
                        lambda params, hint: called.update(n=called["n"] + 1) or "should-not-run")
    result = ch.dispatch("内部复盘", "review", {
        "_caller_agent": "score",
        "_target_agent": "review",
        "_relation": "call",
    }, "", "ou_rt")
    assert "协作调用被拒绝" in result
    assert "caller=score" in result and "target=review" in result
    assert "reason=" in result
    assert called["n"] == 0


def test_unknown_caller_is_rejected():
    result = collaboration.check_collaboration("unknown_agent", "score", "call")
    assert result["allowed"] is False
    assert result["unknown_caller"] is True
    assert result["default_denied"] is True


def test_unknown_target_is_rejected_and_not_executed(monkeypatch):
    called = {"n": 0}
    monkeypatch.setitem(ch._HANDLERS, "score",
                        lambda params, hint: called.update(n=called["n"] + 1) or "should-not-run")
    result = ch.dispatch("内部评分", "score", {
        "_caller_agent": "review",
        "_target_agent": "not_registered",
        "_relation": "call",
    }, "", "ou_rt")
    assert "协作调用被拒绝" in result
    assert "target=not_registered" in result
    assert called["n"] == 0


def test_user_direct_dispatch_without_internal_marker_still_runs(monkeypatch):
    called = {"n": 0}
    monkeypatch.setitem(ch._HANDLERS, "review",
                        lambda params, hint: called.update(n=called["n"] + 1) or "user-ok")
    result = ch.dispatch("最新复盘", "review", {}, "", "ou_user")
    assert result == "user-ok"
    assert called["n"] == 1


def test_long_task_rejection_does_not_submit_queue(monkeypatch):
    submitted = {"n": 0}
    monkeypatch.setattr(ch.task_queue, "submit",
                        lambda *args, **kwargs: submitted.update(n=submitted["n"] + 1))
    result = ch.dispatch("内部评分", "score", {
        "_caller_agent": "review",
        "_target_agent": "score",
        "_relation": "call",
    }, "", "ou_rt")
    assert "协作调用被拒绝" in result
    assert submitted["n"] == 0


def test_readonly_react_tool_is_not_intercepted(monkeypatch):
    monkeypatch.setattr(agentic_tools.repo, "get_sector_regime_forecast",
                        lambda trade_date: {"trade_date": trade_date, "regime": "test"})
    result = agentic_tools.TOOL_FUNCS["get_sector_regime"]("2026-09-01")
    assert result["regime"]["trade_date"] == "2026-09-01"


def test_no_auto_trading_endpoint_or_order_function_names():
    route_text = "\n".join(getattr(route, "path", "") for route in ch.feishu_bridge.app.routes) \
        if hasattr(ch.feishu_bridge, "app") else ""
    source = (Path("backend/app/services/chat_handlers.py").read_text(encoding="utf-8")
              + Path("backend/app/system_map/collaboration.py").read_text(encoding="utf-8")).lower()
    forbidden = ["auto_order", "auto_trade", "place_order", "submit_order",
                 "cancel_order", "execute_trade", "自动下单"]
    assert not any(term in route_text.lower() for term in forbidden)
    assert not any(f"def {term}" in source for term in forbidden if term.isascii())
