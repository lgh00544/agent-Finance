"""经验 Worker / 审核调度的用户上下文隔离回归测试。"""

import sys
import types

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def _no_database_or_cache_writes(monkeypatch):
    from app.db import repo
    from app.scheduler import jobs

    def unexpected_database_access(*_args, **_kwargs):
        raise AssertionError("this unit test must not connect to a database")

    monkeypatch.setattr(repo, "SessionLocal", unexpected_database_access)
    monkeypatch.setattr(jobs.cache, "set", lambda *_args, **_kwargs: None)


def _suggestion(user_id):
    return types.SimpleNamespace(
        id=11, user_id=user_id, review_id=21, target_agent="score",
        audit_verdict="pending", audit_round=0, last_audit_id=None,
    )


def _output():
    return types.SimpleNamespace(
        verdict="pass", confidence=80, support_view="support", dissent_view="dissent",
        boundary_cases="boundary", evidence_refs=["test"],
        model_dump=lambda: {"verdict": "pass"},
    )


def test_experience_worker_job_iterates_active_users(monkeypatch):
    from app.scheduler import jobs

    monkeypatch.setattr(jobs.settings, "multi_user_enabled", True)
    monkeypatch.setattr(jobs.repo, "list_active_users", lambda: [
        {"id": 11, "role": "researcher"}, {"id": 12, "role": "admin"},
    ])
    seen = []
    worker = types.SimpleNamespace(worker_run=lambda **kw: seen.append(kw) or {"ok": True})
    monkeypatch.setitem(sys.modules, "app.services.experience_worker", worker)

    jobs.experience_worker_job(force=True)

    assert [item["user_id"] for item in seen] == [11, 12]
    assert all(item["force"] is True for item in seen)


def test_experience_worker_job_failure_does_not_skip_next_user_or_leak_context(monkeypatch):
    from app.scheduler import jobs
    from app.core.auth import current_user_id, reset_user_context, set_user_context

    monkeypatch.setattr(jobs.settings, "multi_user_enabled", True)
    monkeypatch.setattr(jobs.repo, "list_active_users", lambda: [
        {"id": 11, "role": "researcher"}, {"id": 12, "role": "researcher"},
    ])
    seen = []

    def worker_run(**kw):
        seen.append((kw["user_id"], current_user_id()))
        if kw["user_id"] == 11:
            raise RuntimeError("first user failed")
        return {"ok": True}

    monkeypatch.setitem(sys.modules, "app.services.experience_worker",
                        types.SimpleNamespace(worker_run=worker_run))
    token = set_user_context(99, "admin")
    try:
        jobs.experience_worker_job(force=True)
        assert seen == [(11, 11), (12, 12)]
        assert current_user_id() == 99
    finally:
        reset_user_context(token)


def test_audit_job_failure_does_not_skip_next_user_or_leak_context(monkeypatch):
    from app.scheduler import jobs
    from app.core.auth import current_user_id, reset_user_context, set_user_context

    monkeypatch.setattr(jobs.settings, "multi_user_enabled", True)
    monkeypatch.setattr(jobs.repo, "list_active_users", lambda: [
        {"id": 11, "role": "researcher"}, {"id": 12, "role": "researcher"},
    ])
    seen = []

    def run_pending_audits(**_kw):
        seen.append(current_user_id())
        if current_user_id() == 11:
            raise RuntimeError("first audit failed")
        return {"errors": []}

    monkeypatch.setitem(sys.modules, "app.agents.audit",
                        types.SimpleNamespace(run_pending_audits=run_pending_audits))
    token = set_user_context(99, "admin")
    try:
        jobs.audit_pending_job()
        assert seen == [11, 12]
        assert current_user_id() == 99
    finally:
        reset_user_context(token)


def test_audit_timeout_worker_inherits_context(monkeypatch):
    from app.agents import audit
    from app.core.auth import current_user_id, reset_user_context, set_user_context

    token = set_user_context(77, "researcher")
    try:
        seen = []

        def fn():
            seen.append(current_user_id())

        audit._call_with_timeout(fn, 2)
        assert seen == [77]
    finally:
        reset_user_context(token)


def test_audit_batch_uses_user_cursor(monkeypatch):
    from app.agents import audit
    from app.core.auth import reset_user_context, set_user_context

    monkeypatch.setattr(audit.settings, "multi_user_enabled", True)
    calls = []
    monkeypatch.setattr(audit.repo, "get_config",
                        lambda key, default=None: calls.append(("get", key)) or "7")
    monkeypatch.setattr(audit.repo, "set_config",
                        lambda key, value: calls.append(("set", key, value)))
    monkeypatch.setattr(audit.repo, "list_agent_suggestions_for_audit",
                        lambda cursor, limit, user_id=None: calls.append(
                            ("list", cursor, limit, user_id)) or [])

    token = set_user_context(88, "researcher")
    try:
        result = audit.run_pending_audits(limit=3)
    finally:
        reset_user_context(token)

    assert result["cursor"] == 7
    assert ("get", "audit_cursor.u88.last_id") in calls
    assert ("list", 7, 3, 88) in calls
    assert ("set", "audit_cursor.u88.last_id", "7") in calls


def test_audit_batch_uses_legacy_cursor_when_single_user(monkeypatch):
    from app.agents import audit
    monkeypatch.setattr(audit.settings, "multi_user_enabled", False)
    calls = []
    monkeypatch.setattr(audit.repo, "get_config",
                        lambda key, default=None: calls.append(("get", key)) or "3")
    monkeypatch.setattr(audit.repo, "set_config",
                        lambda key, value: calls.append(("set", key, value)))
    monkeypatch.setattr(audit.repo, "list_agent_suggestions_for_audit",
                        lambda cursor, limit, user_id=None: [])
    audit.run_pending_audits(limit=2)
    assert calls[0] == ("get", "audit_cursor.last_id")
    assert calls[-1][1] == "audit_cursor.last_id"


@pytest.mark.parametrize("role", ["researcher", "admin"])
def test_collect_rejects_cross_user_before_reading_private_rules(monkeypatch, role):
    from app.agents import audit
    from app.core.auth import reset_user_context, set_user_context

    monkeypatch.setattr(audit.settings, "multi_user_enabled", True)
    reads = []
    monkeypatch.setattr(audit.repo, "get_active_rules",
                        lambda *a, **kw: reads.append((a, kw)) or [])
    token = set_user_context(7, role)
    try:
        with pytest.raises((PermissionError, RuntimeError, LookupError, HTTPException)):
            audit.collect_audit(_suggestion(8))
    finally:
        reset_user_context(token)
    assert reads == []


@pytest.mark.parametrize("role", ["researcher", "admin"])
def test_persist_rejects_cross_user_without_writes(monkeypatch, role):
    from app.agents import audit
    from app.core.auth import reset_user_context, set_user_context

    monkeypatch.setattr(audit.settings, "multi_user_enabled", True)
    writes = []
    monkeypatch.setattr(audit.repo, "insert_audit_log",
                        lambda *a, **kw: writes.append((a, kw)) or 101)
    monkeypatch.setattr(audit.repo, "update_agent_suggestion_audit",
                        lambda *a, **kw: writes.append((a, kw)))
    token = set_user_context(7, role)
    try:
        with pytest.raises((PermissionError, RuntimeError, LookupError, HTTPException)):
            audit._persist(_suggestion(8), 1, _output(), 1)
    finally:
        reset_user_context(token)
    assert writes == []


@pytest.mark.parametrize("role", ["researcher", "admin"])
def test_trigger_rejects_cross_user_before_model_or_write(monkeypatch, role):
    from app.agents import audit
    from app.core.auth import reset_user_context, set_user_context

    monkeypatch.setattr(audit.settings, "multi_user_enabled", True)
    suggestion = _suggestion(8)
    # Return the foreign object even if the repository were mis-scoped: the
    # service boundary must reject ownership before using personal model context.
    monkeypatch.setattr(audit.repo, "get_agent_suggestion", lambda *_a, **_kw: suggestion)
    monkeypatch.setattr(audit.repo, "get_agent_suggestion_for_user",
                        lambda *_a, **_kw: suggestion)
    calls = []
    monkeypatch.setattr(audit, "llm_audit", lambda *_a, **_kw: calls.append("llm") or _output())
    monkeypatch.setattr(audit.repo, "insert_audit_log",
                        lambda *_a, **_kw: calls.append("insert") or 101)
    monkeypatch.setattr(audit.repo, "update_agent_suggestion_audit",
                        lambda *_a, **_kw: calls.append("update"))
    token = set_user_context(7, role)
    try:
        with pytest.raises((PermissionError, RuntimeError, LookupError, HTTPException)):
            audit.trigger_audit_for_suggestion(suggestion.id)
    finally:
        reset_user_context(token)
    assert calls == []


def test_same_owner_can_collect_persist_and_trigger_audit(monkeypatch):
    from app.agents import audit
    from app.core.auth import reset_user_context, set_user_context

    monkeypatch.setattr(audit.settings, "multi_user_enabled", True)
    suggestion = _suggestion(7)
    writes = []
    monkeypatch.setattr(audit.repo, "get_active_rules", lambda *a, **kw: [])
    monkeypatch.setattr(audit.repo, "get_agent_suggestion", lambda *a, **kw: suggestion)
    monkeypatch.setattr(audit.repo, "get_agent_suggestion_for_user", lambda *a, **kw: suggestion)
    monkeypatch.setattr(audit, "llm_audit", lambda *_a, **_kw: _output())
    monkeypatch.setattr(audit.repo, "insert_audit_log", lambda *a, **kw: writes.append(kw) or 101)
    monkeypatch.setattr(audit.repo, "update_agent_suggestion_audit", lambda *a, **kw: None)
    token = set_user_context(7, "researcher")
    try:
        assert audit.collect_audit(suggestion)["id"] == suggestion.id
        assert audit._persist(suggestion, 1, _output(), 1) == 101
        assert audit.trigger_audit_for_suggestion(suggestion.id)["audited"] is True
    finally:
        reset_user_context(token)
    assert len(writes) == 2
    assert all(row["user_id"] == 7 for row in writes)
