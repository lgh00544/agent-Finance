"""Batch 13: read-only governance health aggregation."""
from fastapi.testclient import TestClient

from app.main import app
from app.system_map import health


def test_health_aggregates_real_modules_and_unknown_gaps():
    result = health.get_governance_health()

    assert result["module_count"] == 8
    assert set(result["modules"]) == {
        "system_map",
        "knowledge",
        "shadow",
        "experience_memory",
        "rule_change_audit",
        "collaboration",
        "database_migration",
        "registration_integrity",
    }
    knowledge = result["modules"]["knowledge"]
    assert knowledge["status"] in {"healthy", "attention", "error", "unknown"}
    if knowledge["status"] != "error":
        assert knowledge["counts"]["active"] >= 0
    assert result["modules"]["collaboration"]["counts"]["runtime_rejections"] is None
    assert result["modules"]["collaboration"]["runtime_rejection_stats"]["status"] == "unknown"


def test_health_api_is_read_only_and_returns_module_statuses():
    response = TestClient(app).get("/api/system-map/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"healthy", "attention", "error", "unknown"}
    assert response.json()["module_count"] == 8


def test_health_module_failure_is_error_and_not_healthy(monkeypatch):
    monkeypatch.setattr(health, "_knowledge", lambda: (_ for _ in ()).throw(RuntimeError("knowledge unavailable")))

    result = health.get_governance_health()

    assert result["status"] == "error"
    assert result["complete"] is False
    assert result["modules"]["knowledge"]["status"] == "error"
    assert "knowledge unavailable" in result["modules"]["knowledge"]["last_error"]


def test_health_empty_module_is_unknown_not_healthy(monkeypatch):
    monkeypatch.setattr(health, "_knowledge", lambda: health._module("knowledge", "unknown"))
    for name in ("_system_map", "_shadow", "_experience", "_rules_audit", "_collaboration",
                 "_registration_integrity"):
        monkeypatch.setattr(health, name, lambda name=name: health._module(name, "healthy"))

    result = health.get_governance_health()

    assert result["status"] == "unknown"
    assert result["unknown_modules"] >= 1
    assert result["modules"]["knowledge"]["status"] == "unknown"


def test_health_is_read_only_and_preserves_governance_boundaries():
    source = open(health.__file__, encoding="utf-8").read().lower()
    assert "db.commit" not in source
    assert "db.add(" not in source
    assert "delete(" not in source
    assert "execute_trade" not in source
