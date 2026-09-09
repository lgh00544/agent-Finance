import pytest

from app.services import paper_context


def _frozen():
    return {
        "stock_code": "600001", "trade_date": "2026-09-08",
        "decision_at": "2026-09-08T14:00:00+08:00",
        "fact_as_of": "2026-09-08T14:00:00+08:00",
        "quote": {"price": 10, "fact_as_of": "2026-09-08T14:00:00+08:00"},
        "position": {"shares": 100},
    }


def test_historical_replay_uses_only_frozen_facts(monkeypatch):
    created = {}
    monkeypatch.setattr(paper_context.repo, "create_paper_context",
                        lambda *args: (created.update(facts=args[5]) or 17))
    monkeypatch.setattr(paper_context.agentic_tools, "TOOL_FUNCS",
                        {"get_quote": lambda **kwargs: (_ for _ in ()).throw(AssertionError("live tool"))})
    result = paper_context.collect(1, "600001", "2026-09-08", mode="historical_replay",
                                   historical_facts={"facts": _frozen(),
                                                    "tool_trace": [{"tool": "fixture"}]})
    assert result["id"] == 17
    assert result["facts"]["quote"]["price"] == 10
    assert result["tool_trace"][0]["tool"] == "historical_snapshot"
    assert result["context_hash"]
    assert created["facts"]["quote"]["price"] == 10


def test_historical_replay_rejects_future_or_invalid_timestamps(monkeypatch):
    monkeypatch.setattr(paper_context.repo, "create_paper_context", lambda *args: 1)
    future = _frozen()
    future["quote"]["fact_as_of"] = "2026-09-08T15:01:00+08:00"
    with pytest.raises(ValueError, match="时间校验"):
        paper_context.collect(1, "600001", "2026-09-08", mode="historical_replay",
                              historical_facts={"facts": future})
    invalid = _frozen()
    invalid["fact_as_of"] = "not-a-date"
    with pytest.raises(ValueError, match="时间校验"):
        paper_context.collect(1, "600001", "2026-09-08", mode="historical_replay",
                              historical_facts={"facts": invalid})


def test_live_mode_rejects_past_date(monkeypatch):
    with pytest.raises(ValueError, match="仅可用于今天"):
        paper_context.collect(1, "600001", "2026-09-08", mode="live_paper")


def test_historical_mode_cannot_use_web_or_missing_snapshot():
    with pytest.raises(ValueError, match="必须提供"):
        paper_context.collect(1, "600001", "2026-09-08", mode="historical_replay")
    with pytest.raises(ValueError, match="禁止联网"):
        paper_context.collect(1, "600001", "2026-09-08", mode="historical_replay",
                              historical_facts={"facts": _frozen()}, web_urls=["https://example.com"])
