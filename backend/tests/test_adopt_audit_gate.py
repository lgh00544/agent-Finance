"""Batch 5: adoption endpoints require AuditAgent pass or explicit override."""
import pytest
from fastapi import HTTPException

from app.api.routes import (
    AdoptSuggestionBody,
    ApproveSuggestionBody,
    adopt_agent_suggestion,
    adopt_review_suggestion,
    approve_agent_suggestion,
)
from app.db import repo
from app.db.models import AgentSuggestion, RuleChange
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean_tables():
    with SessionLocal() as db:
        db.query(RuleChange).delete()
        db.query(AgentSuggestion).delete()
        db.commit()
    repo._invalidate("rule_change")
    yield


def _make_suggestion(*, target_kind="profile", rule_type="soft", audit_verdict="pending",
                     rule_name="批5测试规则", rule_text="批5测试规则正文：满足条件后再执行。"):
    rid = repo.insert_review(
        "600701", "批5测试股", 1, "2026-08-01", 10, 3.2,
        {"入场逻辑": "回踩企稳"}, "批5测试教训", {},
    )
    sid = repo.insert_agent_suggestion(
        review_id=rid, target_agent="score", rule_name=rule_name,
        current_value="旧值", suggested_value="新值", reason="测试理由", evidence="测试证据",
        target_kind=target_kind, rule_type=rule_type, priority="high",
        rule_text=rule_text if target_kind != "profile" else "",
        file_path="agent_prompts/score.py",
    )
    if audit_verdict != "pending":
        repo.update_agent_suggestion_audit(sid, audit_verdict, 1, None)
    return sid


def test_pending_profile_cannot_approve_by_default():
    sid = _make_suggestion()
    with pytest.raises(HTTPException) as exc:
        approve_agent_suggestion(sid)
    assert exc.value.status_code == 409
    assert "审核状态" in exc.value.detail


def test_failed_rule_cannot_adopt_by_default():
    sid = _make_suggestion(target_kind="prompt", audit_verdict="fail")
    with pytest.raises(HTTPException) as exc:
        adopt_agent_suggestion(sid, AdoptSuggestionBody())
    assert exc.value.status_code == 409
    assert "fail" in exc.value.detail


def test_passed_profile_can_approve_and_updates_profile():
    name = "批5通过偏好"
    sid = _make_suggestion(audit_verdict="pass", rule_name=name)
    result = approve_agent_suggestion(sid)
    assert result["applied"] == "profile"
    assert repo.get_agent_suggestion(sid).status == "approved"
    assert repo.get_trade_profile_content()[name] == "新值"


def test_passed_rule_can_adopt_and_creates_rule_change():
    sid = _make_suggestion(target_kind="prompt", audit_verdict="pass",
                           rule_name="批5通过规则")
    result = adopt_agent_suggestion(sid, AdoptSuggestionBody())
    assert result["adopted"] is True
    assert repo.get_rule_change(result["rule_change_id"])["status"] == "active"


def test_hard_rule_still_requires_confirm_after_audit_pass():
    sid = _make_suggestion(target_kind="prompt", rule_type="hard", audit_verdict="pass",
                           rule_name="批5硬规则")
    with pytest.raises(HTTPException) as exc:
        adopt_agent_suggestion(sid, AdoptSuggestionBody())
    assert exc.value.status_code == 400
    assert "确认" in exc.value.detail


def test_override_requires_non_empty_reason():
    sid = _make_suggestion()
    with pytest.raises(HTTPException) as exc:
        approve_agent_suggestion(sid, ApproveSuggestionBody(override_audit=True))
    assert exc.value.status_code == 400
    assert "override_reason" in exc.value.detail


def test_override_with_reason_is_allowed_and_recorded():
    sid = _make_suggestion(target_kind="prompt", rule_name="批5覆盖规则")
    result = adopt_agent_suggestion(
        sid,
        AdoptSuggestionBody(override_audit=True, override_reason="人工确认该建议仅用于本轮观察"),
    )
    assert result["adopted"] is True
    note = repo.get_agent_suggestion(sid).conflict_note
    assert "审核 override" in note and "本轮观察" in note


def test_legacy_review_adopt_is_marked_without_audit_claim():
    rid = repo.insert_review(
        "600702", "批5旧入口测试股", 1, "2026-08-01", 10, 2.0,
        {"入场逻辑": "测试"}, "测试教训",
        {"profile_suggestion": {"field": "批5旧入口偏好", "value": "旧入口值"}},
    )
    result = adopt_review_suggestion(rid)
    assert result["legacy_adopt"] is True
    assert "不具备" in result["warning"]
