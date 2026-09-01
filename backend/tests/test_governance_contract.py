"""Batch 10 governance contract tests.

These tests pin the governance boundaries across system map, collaboration,
rules, knowledge shadow, memory curator, and read-only ReAct tools.
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.agents import agentic_tools
from app.agents.common import dynamic_rules_section, knowledge_section
from app.api.routes import AdoptSuggestionBody, adopt_agent_suggestion, approve_agent_suggestion
from app.db import repo
from app.db.models import AgentSuggestion, Experience, KnowledgeShadowHit
from app.db.session import SessionLocal, init_db
from app.main import app
from app.services import memory_curator
from app.system_map import collaboration


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    init_db()


def _cleanup(knowledge_ids=None, experience_ids=None, suggestion_ids=None):
    knowledge_ids = [int(i) for i in (knowledge_ids or []) if i]
    experience_ids = [int(i) for i in (experience_ids or []) if i]
    suggestion_ids = [int(i) for i in (suggestion_ids or []) if i]
    with SessionLocal() as db:
        if knowledge_ids:
            db.execute(delete(KnowledgeShadowHit).where(
                KnowledgeShadowHit.knowledge_id.in_(knowledge_ids)))
        if experience_ids:
            db.execute(delete(Experience).where(Experience.id.in_(experience_ids)))
        if suggestion_ids:
            db.execute(delete(AgentSuggestion).where(AgentSuggestion.id.in_(suggestion_ids)))
        db.commit()
    for kid in knowledge_ids:
        repo.delete_knowledge(kid)


def test_system_map_readonly_endpoints_return_registry_shapes():
    client = TestClient(app)
    summary = client.get("/api/system-map")
    agents = client.get("/api/system-map/agents")
    tools = client.get("/api/system-map/tools")
    workflows = client.get("/api/system-map/workflows")
    assert summary.status_code == agents.status_code == tools.status_code == workflows.status_code == 200
    assert summary.json()["agents_count"] >= 1
    assert any(item["agent_id"] == "score" for item in agents.json())
    assert any(item["tool_id"] == "search_knowledge" for item in tools.json())
    assert any(item["workflow_id"] == "score" for item in workflows.json())


def test_collaboration_defaults_forbidden_and_allowed_is_explicit():
    forbidden = collaboration.can_collaborate("score", "review", "call")
    allowed = collaboration.can_collaborate("score", "discover", "reference")
    assert forbidden["allowed"] is False
    assert forbidden["conflict_policy"] == "deny_by_default"
    assert allowed["allowed"] is True
    assert "discover" in collaboration.list_allowed_targets("score")


def test_dynamic_rules_section_is_agent_scoped(monkeypatch):
    monkeypatch.setattr(repo, "get_active_rules", lambda: [
        {"target_agent": "score", "rule_type": "soft", "rule_text": "score 专属规则"},
        {"target_agent": "discover", "rule_type": "soft", "rule_text": "discover 专属规则"},
        {"target_agent": "all", "rule_type": "soft", "rule_text": "all 通用规则"},
        {"target_agent": "", "rule_type": "soft", "rule_text": "legacy 空目标规则"},
    ])
    section = dynamic_rules_section("score")
    assert "score 专属规则" in section
    assert "all 通用规则" in section
    assert "legacy 空目标规则" in section
    assert "discover 专属规则" not in section


def test_agent_suggestion_requires_audit_pass_for_approve_and_adopt():
    profile_sid = repo.insert_agent_suggestion(
        0, "score", "批10_profile_gate", "old", "new", "reason", "evidence",
        target_kind="profile")
    prompt_sid = repo.insert_agent_suggestion(
        0, "score", "批10_prompt_gate", "old", "new", "reason", "evidence",
        target_kind="prompt", rule_text="批10 测试规则")
    try:
        with pytest.raises(HTTPException) as approve_exc:
            approve_agent_suggestion(profile_sid)
        with pytest.raises(HTTPException) as adopt_exc:
            adopt_agent_suggestion(prompt_sid, AdoptSuggestionBody())
        assert approve_exc.value.status_code == 409
        assert adopt_exc.value.status_code == 409
    finally:
        _cleanup(suggestion_ids=[profile_sid, prompt_sid])


def test_knowledge_section_excludes_shadow_archived_and_expired():
    text, selected = knowledge_section("score", docs=[
        {"id": 1, "title": "active", "content": "正式可注入", "status": "active"},
        {"id": 2, "title": "shadow", "content": "shadow 不可注入", "status": "shadow"},
        {"id": 3, "title": "archived", "content": "archived 不可注入", "status": "archived"},
        {"id": 4, "title": "expired", "content": "expired 不可注入", "status": "expired"},
    ])
    assert "正式可注入" in text
    assert "不可注入" not in text
    assert [item["id"] for item in selected] == [1]


def test_knowledge_shadow_hit_does_not_change_knowledge_status():
    kid = repo.add_knowledge("批10 shadow contract", "shadow 观察", "score", status="shadow")
    try:
        repo.record_knowledge_shadow_hit(
            kid, "score", "810001", "治理合同", "2026-09-01",
            query="观察", shadow_bias="unknown")
        repo.refresh_knowledge_shadow_outcomes()
        rows = [row for row in repo.list_knowledge(status="shadow") if row.id == kid]
        assert rows and rows[0].status == "shadow"
    finally:
        _cleanup(knowledge_ids=[kid])


def test_memory_curator_dry_run_is_readonly_and_api_write_requires_confirm():
    eid = repo.insert_experience(
        "批10 curator dryrun", "到期经验", "选股", ["批10"], "low", 0.9,
        auto_merged=1, status="active")
    with SessionLocal() as db:
        row = db.get(Experience, eid)
        row.expires_at = datetime.now() - timedelta(days=1)
        db.commit()
    try:
        result = memory_curator.run_curator(dry_run=True, limit=50)
        assert any(action.get("id") == eid for action in result["actions"])
        assert repo.get_experience(eid)["status"] == "active"
        resp = TestClient(app).post("/api/experience/curator/run",
                                    json={"dry_run": False, "confirm": False, "limit": 10})
        assert resp.status_code == 400
    finally:
        _cleanup(experience_ids=[eid])


def test_agentic_tools_are_dual_registered_and_fail_as_error(monkeypatch):
    tool_names = {item["function"]["name"] for item in agentic_tools.TOOLS}
    assert tool_names == set(agentic_tools.TOOL_FUNCS)
    monkeypatch.setattr(agentic_tools.repo, "get_sector_regime_forecast",
                        lambda trade_date: (_ for _ in ()).throw(RuntimeError("boom")))
    result = agentic_tools.TOOL_FUNCS["get_sector_regime"]("2026-09-01")
    assert "error" in result


def test_professional_tools_do_not_trigger_full_recompute(monkeypatch):
    monkeypatch.setattr(agentic_tools.repo, "get_sector_regime_forecast",
                        lambda trade_date: {"trade_date": trade_date, "regime": "test"})
    sector = agentic_tools.TOOL_FUNCS["get_sector_regime"]("2026-09-01")
    assert sector["regime"]["trade_date"] == "2026-09-01"

    monkeypatch.setattr(agentic_tools.cache, "get", lambda key: None)
    monkeypatch.setattr(agentic_tools.repo, "get_capital_stats", lambda code, date: {
        "stock_code": code, "trade_date": date, "coordination": "test",
    })
    capital = agentic_tools.TOOL_FUNCS["get_capital_view"]("810001", "2026-09-01")
    assert capital["capital_view"]["stock_code"] == "810001"


def test_no_auto_trading_endpoint_or_order_function_names():
    route_text = "\n".join(getattr(route, "path", "") for route in app.routes).lower()
    source = (Path("backend/app/api/routes.py").read_text(encoding="utf-8")
              + Path("backend/app/agents/agentic_tools.py").read_text(encoding="utf-8")).lower()
    forbidden = [
        "auto_order", "auto_trade", "place_order", "submit_order",
        "cancel_order", "execute_trade", "自动下单",
    ]
    assert not any(term in route_text for term in forbidden)
    assert not any(f"def {term}" in source for term in forbidden if term.isascii())
