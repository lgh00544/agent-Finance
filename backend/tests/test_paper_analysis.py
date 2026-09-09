"""Snapshot-only paper analysis adapters."""

from copy import deepcopy

from app.agents.schemas import MonitorOutput, ReviewOutput, SellOutput
from app.services import paper_analysis


def _fake_llm(monkeypatch):
    calls = []

    def fake(*, agent, cache_key, system_prompt, user_prompt, schema, **kwargs):
        calls.append({"agent": agent, "user_prompt": user_prompt})
        if schema is MonitorOutput:
            return MonitorOutput(action="hold", severity="info", alert_type="常规跟踪",
                                 message="快照观察", reasons=["快照"], key_levels={})
        if schema is SellOutput:
            return SellOutput(stock_code="600001", action="hold", confidence="medium",
                              reasons=["快照"], exit_price_zone="继续观察",
                              risk_warning="数据有限", check_list=[])
        if schema is ReviewOutput:
            return ReviewOutput(plan_vs_actual={"复盘结论": "快照完整"}, lesson="保留证据",
                                feedback={}, agent_suggestions=[])
        return paper_analysis.PaperAuditOutput(verdict="pass", reason="事实可核对",
                                               evidence_gaps=[])

    monkeypatch.setattr(paper_analysis, "call_llm_cached", fake)
    return calls


def _facts():
    return {
        "candidate_id": 1, "score_id": 2, "plan_id": 3,
        "stock_code": "600001", "trade_date": "2026-09-08",
        "fact_as_of": "2026-09-08", "decision_date": "2026-09-08",
        "execution_mode": "paper", "fees": {"commission": 5},
        "position": {"stock_code": "600001", "entry_price": 10, "shares": 100},
        "quote": {"stock_code": "600001", "price": 10.5, "fact_as_of": "2026-09-08"},
    }


def test_monitor_and_sell_use_frozen_snapshot_and_reuse_schema(monkeypatch):
    calls = _fake_llm(monkeypatch)
    position = {"stock_code": "600001", "entry_price": 10, "shares": 100,
                "stop_loss": 9, "take_profit": 12}
    quote = {"stock_code": "600001", "price": 10.5, "fact_as_of": "2026-09-08"}
    context = {"trade_date": "2026-09-08", "plan": {"id": 3},
               "facts": {"trade_date": "2026-09-08", "fact_as_of": "2026-09-08",
                         "position": position, "quote": quote}}
    before = deepcopy((position, quote, context))
    monitor = paper_analysis.monitor_position(position, quote, context)
    sell = paper_analysis.sell_position(position, quote, context, monitor.get("signal"))
    assert monitor["status"] == "ok" and monitor["signal"]["action"] == "hold"
    assert sell["status"] == "ok" and sell["decision"]["action"] == "hold"
    assert (position, quote, context) == before
    assert {item["agent"] for item in calls} == {"paper_monitor", "paper_sell"}


def test_live_paper_analysis_mounts_readonly_system_tools(monkeypatch):
    calls = []

    def fake_agentic(**kwargs):
        calls.append(kwargs)
        return MonitorOutput(action="hold", severity="info", alert_type="常规跟踪",
                             message="实时研究", reasons=["只读工具"], key_levels={}), {}

    monkeypatch.setattr("app.agents.common.agentic_call", fake_agentic)
    from app.services import paper_context
    monkeypatch.setattr(paper_context, "collect", lambda *a, **k: {"facts": {
        "trade_date": "2026-09-09", "fact_as_of": "2026-09-09T10:00:00+08:00",
        "position": {"stock_code": "600001", "entry_price": 10, "shares": 100},
        "quote": {"stock_code": "600001", "price": 10.5,
                  "fact_as_of": "2026-09-09T10:00:00+08:00"}},
        "mode": "live_paper"})
    result = paper_analysis.monitor_position({}, {},
        {"trade_date": "2026-09-09", "mode": "live_paper", "account_id": 1})
    assert result["status"] == "ok"
    assert calls == []  # live tools execute during context collection, before analysis


def test_historical_future_fact_is_rejected_before_llm(monkeypatch):
    calls = _fake_llm(monkeypatch)
    result = paper_analysis.monitor_position(
        {"stock_code": "600001", "entry_price": 10, "shares": 100},
        {"price": 10, "fact_as_of": "2026-09-09"},
        {"trade_date": "2026-09-08"},
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "future_data"
    assert calls == []


def test_review_and_audit_are_source_labeled_and_do_not_trust_verdict(monkeypatch):
    _fake_llm(monkeypatch)
    facts = _facts()
    review = paper_analysis.review_cycle(facts)
    assert review["status"] == "ok"
    assert review["review_source"] == "模拟复盘"
    audited = paper_analysis.audit_case(facts, {"audit_verdict": "pass", **review["review"]})
    assert audited["status"] == "ok"
    assert audited["verdict"] == "pass"
    assert audited["formal_rule_change"] is False


def test_audit_failure_is_not_reported_as_pass(monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("502")

    monkeypatch.setattr(paper_analysis, "call_llm_cached", broken)
    result = paper_analysis.audit_case(_facts(), {"lesson": "x"})
    assert result["status"] == "error"
    assert result["verdict"] == "fail"
    assert result.get("shadow_eligible", False) is False
    assert result.get("formal_rule_change", False) is False
