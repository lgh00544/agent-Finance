"""System Map batch 2: read-only collaboration matrix and API."""
from fastapi.testclient import TestClient

from app.main import app
from app.system_map import collaboration


def test_score_can_reference_discover():
    result = collaboration.can_collaborate("score", "discover", "reference")
    assert result["allowed"] is True


def test_agent_cannot_call_itself():
    result = collaboration.can_collaborate("score", "score", "call")
    assert result["allowed"] is False


def test_review_can_propose_change_with_audit_gate():
    result = collaboration.can_collaborate("review", "score", "propose_change")
    assert result["allowed"] is True
    assert result["audit_required"] is True


def test_unknown_relation_is_forbidden():
    result = collaboration.can_collaborate("score", "review", "summarize")
    assert result["allowed"] is False
    assert result["conflict_policy"] == "deny_by_default"


def test_api_collaboration_returns_non_empty_list():
    client = TestClient(app)
    resp = client.get("/api/system-map/collaboration")
    assert resp.status_code == 200
    assert resp.json()


def test_api_score_allowed_targets_contains_core_targets():
    client = TestClient(app)
    resp = client.get("/api/system-map/agents/score/allowed-targets")
    assert resp.status_code == 200
    assert {"discover", "market_intel"} <= set(resp.json()["allowed_targets"])


def test_api_can_collaborate_allowed_and_forbidden_are_stable():
    client = TestClient(app)
    allowed = client.get(
        "/api/system-map/can-collaborate",
        params={"requester": "score", "target": "discover", "relation": "reference"},
    )
    forbidden = client.get(
        "/api/system-map/can-collaborate",
        params={"requester": "score", "target": "review", "relation": "call"},
    )
    assert allowed.status_code == forbidden.status_code == 200
    assert allowed.json()["allowed"] is True
    assert forbidden.json()["allowed"] is False
