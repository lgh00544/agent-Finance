"""System Map batch 1: read-only capability registry and API."""
from fastapi.testclient import TestClient

from app.main import app
from app.system_map import registry


def test_list_agents_contains_core_agents():
    agent_ids = {item["agent_id"] for item in registry.list_agents()}
    assert {"discover", "score", "monitor", "sell", "review"} <= agent_ids


def test_list_tools_contains_readonly_react_tools():
    tool_ids = {item["tool_id"] for item in registry.list_tools()}
    assert {"get_quote", "get_daily_kline", "search_knowledge"} <= tool_ids


def test_list_workflows_contains_key_workflows():
    workflow_ids = {item["workflow_id"] for item in registry.list_workflows()}
    assert {"score", "sell_decision", "market_intel"} <= workflow_ids


def test_api_get_score_agent():
    client = TestClient(app)
    resp = client.get("/api/system-map/agents/score")
    assert resp.status_code == 200
    assert resp.json()["agent_id"] == "score"


def test_api_get_unknown_agent_returns_404():
    client = TestClient(app)
    resp = client.get("/api/system-map/agents/not_exists")
    assert resp.status_code == 404
