"""Batch 6: private knowledge metadata, filtering, and lifecycle guards."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect

from app.agents.common import knowledge_section
from app.agents import agentic_tools
from app.db import repo
from app.db.models import PrivateKnowledge
from app.db.session import SessionLocal, init_db
from app.services.vector_store import get_vector_store


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    init_db()


def test_private_knowledge_metadata_columns_are_migrated_idempotently():
    with SessionLocal() as db:
        columns = {column["name"] for column in inspect(db.bind).get_columns("private_knowledge")}
    assert {
        "source_type", "methodology_type", "market_scope", "scenario_tags",
        "evidence_level", "valid_from", "valid_to", "status", "risk_note",
    } <= columns


def test_old_add_knowledge_call_keeps_defaults():
    kid = repo.add_knowledge("批6旧调用", "旧调用内容", "discover")
    try:
        row = repo.list_knowledge("discover")[0]
        assert row.id == kid
        assert row.source_type == "manual"
        assert row.methodology_type == "general"
        assert row.market_scope == "all"
        assert row.scenario_tags == []
        assert row.evidence_level == "unverified"
        assert row.status == "active"
        assert row.risk_note == ""
    finally:
        repo.delete_knowledge(kid)


def test_list_knowledge_supports_metadata_filters():
    common = {"source_type": "external", "methodology_type": "tactic",
              "market_scope": "sector", "scenario_tags": ["breakout", "mainline"],
              "evidence_level": "reviewed", "risk_note": "仅供参考"}
    ids = [
        repo.add_knowledge("批6过滤命中", "过滤内容A", "score", **common),
        repo.add_knowledge("批6过滤排除", "过滤内容B", "score",
                           source_type="manual", methodology_type="risk",
                           market_scope="stock", scenario_tags=["drawdown"]),
        repo.add_knowledge("批6其它 Agent", "过滤内容C", "monitor", **common),
    ]
    try:
        assert [r.id for r in repo.list_knowledge(
            "score", status="active", source_type="external",
            methodology_type="tactic", market_scope="sector", scenario_tag="breakout",
        )] == [ids[0]]
        assert [r.id for r in repo.list_knowledge("score", scenario_tag="drawdown")] == [ids[1]]
    finally:
        for kid in ids:
            repo.delete_knowledge(kid)


def test_search_knowledge_defaults_to_active_and_agent_or_all():
    ids = [
        repo.add_knowledge("批6 active 专属", "active score 内容", "score"),
        repo.add_knowledge("批6 active 通用", "active all 内容", "all"),
        repo.add_knowledge("批6 archived", "archived 内容", "score", status="archived"),
        repo.add_knowledge("批6 other Agent", "monitor 内容", "monitor"),
    ]
    try:
        titles = {row["title"] for row in get_vector_store().search_knowledge("score", top_k=20)}
        assert {"批6 active 专属", "批6 active 通用"} <= titles
        assert "批6 archived" not in titles
        assert "批6 other Agent" not in titles
    finally:
        for kid in ids:
            repo.delete_knowledge(kid)


def test_search_knowledge_supports_scenario_and_methodology_filters():
    ids = [
        repo.add_knowledge("批6场景命中", "场景过滤内容", "score",
                           scenario_tags=["mainline"], methodology_type="tactic"),
        repo.add_knowledge("批6场景排除", "另一个场景内容", "score",
                           scenario_tags=["drawdown"], methodology_type="risk"),
    ]
    try:
        rows = get_vector_store().search_knowledge(
            "score", top_k=20, scenario_tags=["mainline"], methodology_type="tactic",
        )
        assert [row["title"] for row in rows] == ["批6场景命中"]
    finally:
        for kid in ids:
            repo.delete_knowledge(kid)


def test_knowledge_section_does_not_inject_archived_or_expired_docs(monkeypatch):
    future = datetime.now() + timedelta(days=1)
    docs = [
        {"id": 1, "title": "active", "content": "可注入", "status": "active"},
        {"id": 2, "title": "archived", "content": "不可注入", "status": "archived"},
        {"id": 3, "title": "expired", "content": "不可注入", "status": "expired"},
        {"id": 4, "title": "future", "content": "不可注入", "valid_from": future},
    ]
    monkeypatch.setattr("app.services.vector_store.get_vector_store",
                        lambda: type("S", (), {
                            "search_knowledge": lambda self, agent, top_k=5: docs,
                        })())
    monkeypatch.setattr(repo, "bump_knowledge_hits", lambda ids: len(ids))
    text, selected = knowledge_section("score")
    assert "active" in text and "可注入" in text
    assert "archived" not in text and "expired" not in text and "future" not in text
    assert [item["id"] for item in selected] == [1]


def test_react_stock_knowledge_tool_still_uses_search_related(monkeypatch):
    calls = {}
    monkeypatch.setattr(agentic_tools, "get_vector_store", lambda: type("S", (), {
        "search_related": lambda self, code, query, top_k: calls.update(
            {"code": code, "query": query, "top_k": top_k}) or [
                {"title": "资料", "summary": "摘要"}
            ],
    })())
    result = agentic_tools._search_knowledge("600519", "趋势", 3)
    assert calls == {"code": "600519", "query": "趋势", "top_k": 3}
    assert result["hits"][0]["标题"] == "资料"
