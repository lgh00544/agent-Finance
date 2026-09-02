"""Batch 16: read-only System Map registration integrity checks."""
from pathlib import Path

from app.agents import agentic_tools
from app.services import agent_chat, chat_handlers
from app.system_map import health, integrity, registry


def _consistent_sources():
    source = integrity._source_snapshot()
    source["registry_agents"] = set(source["agent_meta"]) | set(source["graph_agents"])
    source["intent_targets"] = {
        **source["intent_targets"],
        "synthetic": "score",
    }
    return source


def test_current_sources_are_checked_and_real_drift_is_visible():
    result = integrity.check_system_map_integrity()

    assert result["status"] == "healthy"
    assert result["issues"] == []
    assert result["summary"]["source_count"] == 9


def test_consistent_sources_are_healthy_and_compatibility_nodes_are_valid():
    source = _consistent_sources()
    original = integrity._source_snapshot
    integrity._source_snapshot = lambda: source
    try:
        checked = integrity.check_system_map_integrity()
    finally:
        integrity._source_snapshot = original

    assert checked["status"] == "healthy"
    assert checked["issues"] == []
    assert "chat_entry" in integrity.SYSTEM_NODES
    assert integrity.HANDLER_AGENT_ALIASES["market"] == "market_intel"


def test_market_and_portfolio_agents_are_registered_but_not_chat_agents():
    agents = {item["agent_id"] for item in registry.list_agents()}
    assert {"market_intel", "portfolio_sentinel"} <= agents
    assert "market_intel" not in agent_chat.AGENT_CHAT_META
    assert "portfolio_sentinel" not in agent_chat.AGENT_CHAT_META


def test_agent_registry_without_graph_or_handler_is_detected(monkeypatch):
    source = _consistent_sources()
    source["registry_agents"].add("orphan_agent")
    monkeypatch.setattr(integrity, "_source_snapshot", lambda: source)

    result = integrity.check_system_map_integrity()

    issue = next(item for item in result["issues"] if item["item"] == "orphan_agent")
    assert issue["kind"] == "agent_missing_handler"
    assert issue["severity"] == "error"


def test_unknown_workflow_step_and_entry_are_detected(monkeypatch):
    source = _consistent_sources()
    source["workflows"] = [{
        "workflow_id": "broken", "steps": ["not_a_capability"],
        "allowed_entry_agents": ["not_an_agent"],
    }]
    monkeypatch.setattr(integrity, "_source_snapshot", lambda: source)

    kinds = {item["kind"] for item in integrity.check_system_map_integrity()["issues"]}
    assert {"workflow_unknown_step", "workflow_unknown_entry_agent"} <= kinds


def test_unknown_collaboration_node_and_tool_pairs_are_detected(monkeypatch):
    source = _consistent_sources()
    source["collaboration_rules"] = [{
        "requester_agent": "score", "target_agent": "unknown_node",
        "relation": "reference",
    }]
    source["tools_schema"].add("schema_only")
    source["tool_funcs"].add("function_only")
    monkeypatch.setattr(integrity, "_source_snapshot", lambda: source)

    issues = integrity.check_system_map_integrity()["issues"]
    kinds = {item["kind"] for item in issues}
    assert "collaboration_unknown_node" in kinds
    assert "tool_schema_without_function" in kinds
    assert "tool_function_without_schema" in kinds


def test_unknown_intent_target_and_source_failure_are_not_hidden(monkeypatch):
    source = _consistent_sources()
    source["intent_targets"]["broken"] = "unknown_agent"
    monkeypatch.setattr(integrity, "_source_snapshot", lambda: source)
    result = integrity.check_system_map_integrity()
    assert any(item["kind"] == "intent_unknown_target" for item in result["issues"])
    assert result["status"] == "error"

    monkeypatch.setattr(
        integrity,
        "_source_snapshot",
        lambda: (_ for _ in ()).throw(RuntimeError("registry unavailable")),
    )
    failed = integrity.check_system_map_integrity()
    assert failed["status"] == "error"
    assert failed["issues"][0]["kind"] == "source_read_error"
    assert "registry unavailable" in failed["issues"][0]["actual"]


def test_empty_sources_are_unknown_and_health_remains_read_only(monkeypatch):
    monkeypatch.setattr(integrity, "_source_snapshot", lambda: {})
    result = integrity.check_system_map_integrity()
    assert result["status"] == "unknown"

    monkeypatch.setattr(health.integrity, "check_system_map_integrity", lambda: result)
    observed = health.get_governance_health()
    assert observed["modules"]["registration_integrity"]["status"] == "unknown"

    source = Path(health.__file__).read_text(encoding="utf-8").lower()
    assert "init_db(" not in source
    assert "alter table" not in source
    assert "db.commit" not in source
    assert "execute_trade" not in source


def test_integrity_uses_existing_fact_sources_without_executing_entries():
    assert set(agent_chat.AGENT_CHAT_META) >= {"discover", "score", "review"}
    assert "score" in chat_handlers._INTENT_TARGETS
    assert registry.list_agents()
    assert agentic_tools.TOOLS and agentic_tools.TOOL_FUNCS
