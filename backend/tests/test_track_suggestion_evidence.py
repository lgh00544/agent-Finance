"""Aggregate return anomalies must not force repeated trading restrictions."""
import json

import pytest

from app.agents.schemas import AgentSuggestionItem, TrackVerifyOutput
from app.services import track_verify as tv


def _stats():
    return {"period": "t3", "n": 6, "wins": 2, "win_rate": 33.3,
            "avg_pct": -1.0, "by_rating": {},
            "by_date": {"2026-08-28": {}, "2026-09-01": {}}}


def _anomalies():
    return [{"type": "win_rate_low", "data": {
        "n": 6, "wins": 2, "win_rate": 33.3, "avg_pct": -1.0}}]


def test_aggregate_input_preserves_window_and_evidence_limits():
    payload = json.loads(tv.build_stats_json(_stats(), _anomalies()))
    scope = payload["evidence_scope"]
    assert payload["stats"]["n"] == 6
    assert scope["period"] == "t3"
    assert scope["select_date_start"] == "2026-08-28"
    assert scope["select_date_end"] == "2026-09-01"
    assert scope["selection_dates"] == 2
    assert scope["rating_provenance_verified"] is False
    assert scope["rule_effect_validated"] is False
    assert scope["limitations"]


def test_incomplete_evidence_abstention_does_not_create_fallback(monkeypatch):
    saved = []
    monkeypatch.setattr(tv.repo, "insert_agent_suggestion", lambda *a, **k: saved.append(k))
    out = tv.generate_suggestions(
        _stats(), _anomalies(),
        llm_call=lambda *_: TrackVerifyOutput(summary_note="证据不足，不修改规则"))
    assert saved == []
    assert out["suggestions"] == []
    assert out["fallbacks"] == []
    assert out["summary_note"] == "证据不足，不修改规则"


def test_duplicate_proposal_with_anomaly_does_not_create_another_rule(monkeypatch):
    saved = []
    monkeypatch.setattr(tv.repo, "has_pending_suggestion", lambda name, agent: name == "核对数据")
    monkeypatch.setattr(tv.repo, "insert_agent_suggestion", lambda *a, **k: saved.append(k))
    proposal = AgentSuggestionItem(
        target_agent="discover", target_kind="prompt", rule_name="核对数据",
        current_value="待核实", suggested_value="核对数据", reason="统计异常",
        evidence="6个样本", rule_type="soft", rule_text="说明数据来源")
    out = tv.generate_suggestions(
        _stats(), _anomalies(),
        llm_call=lambda *_: TrackVerifyOutput(agent_suggestions=[proposal]))
    assert saved == []
    assert out["deduped"] == 1
    assert out["fallbacks"] == []


def test_unvalidated_llm_filter_is_blocked(monkeypatch):
    saved = []
    monkeypatch.setattr(tv.repo, "insert_agent_suggestion", lambda *a, **k: saved.append(k))
    proposal = AgentSuggestionItem(
        target_agent="discover", target_kind="prompt", rule_name="硬收紧",
        current_value="当前无", suggested_value="新增门槛", reason="低胜率",
        evidence="汇总统计", rule_type="hard",
        rule_text="若胜率低于40%，量比>1.2且板块共振，否则不纳入正式候选池")
    out = tv.generate_suggestions(
        _stats(), _anomalies(),
        llm_call=lambda *_: TrackVerifyOutput(agent_suggestions=[proposal]))
    assert saved == []
    assert out["suggestions"] == []
    assert out["blocked_unvalidated"] == 1


@pytest.mark.parametrize("anomaly", [
    _anomalies()[0],
    {"type": "consecutive_decline", "data": {"d1": 60, "d2": 40, "d3": 20}},
    {"type": "rating_inversion", "data": {
        "pair": "B<C", "B": {"n": 3, "avg_pct": -2}, "C": {"n": 3, "avg_pct": -1}}},
])
def test_llm_failure_falls_back_to_scoped_diagnostic(monkeypatch, anomaly):
    saved = []

    def insert(*args, **kwargs):
        saved.append({"args": args, **kwargs})
        return 1

    def unavailable(*_):
        raise RuntimeError("offline")

    monkeypatch.setattr(tv.repo, "has_pending_suggestion", lambda *_: False)
    monkeypatch.setattr(tv.repo, "insert_agent_suggestion", insert)
    out = tv.generate_suggestions(_stats(), [anomaly], llm_call=unavailable)
    assert out["suggestions"] == []
    assert len(out["fallbacks"]) == len(saved) == 1
    assert saved[0]["rule_type"] == "soft"
    assert saved[0]["suggestion_source"] == "template"
    assert saved[0]["args"][1] == "discover"
    text = saved[0]["rule_text"]
    assert "T+3" in text and "T+5" not in text
    assert "提高风险过滤权重" not in text
    assert "降低候选池规模" not in text
    assert "不得扩大候选规模" not in text
