"""The paper coordinator must never enter real trading write paths."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.services import paper_monitor


@pytest.fixture
def sandbox(monkeypatch):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    state = {"alerts": [], "contexts": [], "executions": [], "research": [], "refresh": []}
    state["date"] = now.date().isoformat()
    position = {"id": 7, "account_id": 1, "stock_code": "600001", "shares": 1000,
                "available_shares": 1000, "avg_price": 10,
                "opened_trade_date": (now.date() - timedelta(days=1)).isoformat()}
    quote = {"stock_code": "600001", "price": 9, "status": "ok",
             "quote_time": now.isoformat(), "fact_as_of": now.isoformat(), "source": "test"}
    state.update(position=position, quote=quote)
    monkeypatch.setattr(paper_monitor.repo, "get_paper_account", lambda _: SimpleNamespace(status="active"))
    monkeypatch.setattr(paper_monitor.repo, "list_paper_positions", lambda *a, **k: [position])
    monkeypatch.setattr(paper_monitor.repo, "list_paper_quotes", lambda *a, **k: [quote])
    monkeypatch.setattr(paper_monitor.repo, "list_paper_contexts", lambda *a, **k: [])
    monkeypatch.setattr(paper_monitor.paper_valuation, "refresh_account",
                        lambda aid: state["refresh"].append(aid) or {"source": "test"})

    def collect(*args, **kwargs):
        state["research"].append(kwargs)
        return {"id": 10, "facts": {"mode": kwargs["mode"]}, "tool_trace": [{"tool": "get_news"}]}

    def context(*args):
        state["contexts"].append(args)
        return 20

    def alert(*args):
        state["alerts"].append(args)
        return 30

    def execute(*args, **kwargs):
        state["executions"].append(kwargs)
        return {"filled": 1, "execution_mode": "paper"}

    def real_write(*args, **kwargs):
        raise AssertionError("paper monitoring entered a real write path")

    monkeypatch.setattr(paper_monitor.paper_context, "collect", collect)
    monkeypatch.setattr(paper_monitor.repo, "create_paper_context", context)
    monkeypatch.setattr(paper_monitor.repo, "create_paper_alert", alert)
    monkeypatch.setattr(paper_monitor.paper_execution, "run", execute)
    monkeypatch.setattr(paper_monitor.repo, "insert_holding", real_write)
    monkeypatch.setattr(paper_monitor.repo, "insert_alert", real_write)
    monkeypatch.setattr(paper_monitor.repo, "record_holding_trade", real_write)
    monkeypatch.setattr(paper_monitor.paper_analysis, "monitor_position", lambda *a: {
        "status": "ok", "signal": {"action": "exit", "severity": "critical",
                                    "alert_type": "触及止损", "message": "模拟止损"}})
    monkeypatch.setattr(paper_monitor.paper_analysis, "sell_position", lambda *a: {
        "status": "ok", "decision": {"action": "sell"}})
    return state


def test_paper_monitor_delegates_exit_without_candidate_pool(sandbox):
    result = paper_monitor.run(1, sandbox["date"])
    assert result["monitored"] == 1
    assert result["results"][0]["execution"]["filled"] == 1
    execution = sandbox["executions"][0]
    assert execution["facts"]["contexts"]["600001"]["context_id"] == 20
    assert not execution["facts"].get("tradeable")
    assert execution["requested_sides"] == {"600001": "sell"}
    assert execution["facts"]["sell_decisions"] == {"600001": {"action": "sell"}}
    assert execution["position_facts"][0]["id"] == 7
    assert sandbox["alerts"][0][-1]["context_id"] == 20
    assert sandbox["research"][0]["web_query"].startswith("600001")


def test_paper_partial_decision_retains_ratio(monkeypatch, sandbox):
    monkeypatch.setattr(paper_monitor.paper_analysis, "sell_position", lambda *a: {
        "status": "ok", "decision": {"action": "partial", "reduce_ratio": 0.3}})
    paper_monitor.run(1, sandbox["date"])
    assert sandbox["executions"][0]["facts"]["sell_decisions"]["600001"]["reduce_ratio"] == 0.3


def test_fill_uses_quote_refreshed_after_decision(monkeypatch, sandbox):
    def refresh(account_id):
        sandbox["refresh"].append(account_id)
        if len(sandbox["refresh"]) == 2:
            sandbox["quote"]["price"] = 8.9
        return {"source": "test"}

    monkeypatch.setattr(paper_monitor.paper_valuation, "refresh_account", refresh)
    paper_monitor.run(1, sandbox["date"])
    assert sandbox["contexts"][0][5]["quote"]["price"] == 9
    assert sandbox["executions"][0]["quote_facts"]["600001"]["price"] == 8.9


def test_quote_lost_after_decision_blocks_fill(monkeypatch, sandbox):
    def refresh(account_id):
        sandbox["refresh"].append(account_id)
        if len(sandbox["refresh"]) == 2:
            sandbox["quote"].update(price=None, status="unavailable")
        return {"source": "test"}

    monkeypatch.setattr(paper_monitor.paper_valuation, "refresh_account", refresh)
    result = paper_monitor.run(1, sandbox["date"])
    assert result["results"][0]["status"] == "skipped"
    assert not sandbox["executions"]
    assert sandbox["alerts"][-1][-1]["alert_type"] == "模拟成交行情不可用"


@pytest.mark.parametrize("patch", [{"price": None}, {"price": float("nan")},
                                   {"quote_time": "2020-01-01 10:00:00"},
                                   {"fact_as_of": "2099-01-01"}])
def test_bad_quote_is_recorded_without_llm_or_execution(patch, sandbox):
    sandbox["quote"].update(patch)
    result = paper_monitor.run(1, sandbox["date"])
    assert result["results"][0]["status"] == "skipped"
    assert sandbox["alerts"] and not sandbox["executions"] and not sandbox["research"]


def test_sell_error_keeps_position_and_records_warning(monkeypatch, sandbox):
    monkeypatch.setattr(paper_monitor.paper_analysis, "sell_position", lambda *a: {
        "status": "error", "reason": "llm_unavailable"})
    result = paper_monitor.run(1, sandbox["date"])
    assert result["results"][0]["status"] == "error"
    assert not sandbox["executions"]
    assert sandbox["alerts"][0][-1]["severity"] == "warning"


def test_historical_monitor_uses_only_supplied_snapshot(monkeypatch, sandbox):
    def forbidden(*args, **kwargs):
        raise AssertionError("historical monitoring read live state")

    monkeypatch.setattr(paper_monitor.paper_valuation, "refresh_account", forbidden)
    monkeypatch.setattr(paper_monitor.repo, "list_paper_positions", forbidden)
    monkeypatch.setattr(paper_monitor.repo, "list_paper_quotes", forbidden)
    monkeypatch.setattr(paper_monitor.repo, "list_paper_contexts", forbidden)
    result = paper_monitor.run(1, "2026-09-01", mode="historical_replay", historical_facts={
        "positions": [{**sandbox["position"], "opened_trade_date": "2026-08-31"}],
        "quotes": {"600001": {**sandbox["quote"], "quote_time": "2026-09-01 10:00:00",
                                "fact_as_of": "2026-09-01"}},
        "contexts": {"600001": {"news": [{"published_at": "2026-08-31", "title": "已知公告"}]}},
    })
    assert result["results"][0]["status"] == "ok"
    assert sandbox["research"][0]["mode"] == "historical_replay"
    assert "web_query" not in sandbox["research"][0]
    assert sandbox["executions"][0]["facts"]["mode"] == "historical_replay"


def test_live_monitor_rejects_historical_date(sandbox):
    with pytest.raises(ValueError, match="历史"):
        paper_monitor.run(1, "2001-01-01")
    assert not sandbox["refresh"]


def test_scheduler_paper_monitor_isolates_account_failure(monkeypatch):
    from app.scheduler import jobs

    calls, locks = [], []
    monkeypatch.setattr(jobs, "_in_trading_window", lambda _: True)
    monkeypatch.setattr(jobs.AkshareSource, "fetch_trade_calendar",
                        lambda _: [datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()])
    monkeypatch.setattr(jobs.repo, "list_paper_accounts", lambda **kwargs: [{"id": 1}, {"id": 2}])
    monkeypatch.setattr(jobs.cache, "acquire_lock", lambda *a, **k: True)
    monkeypatch.setattr(jobs.cache, "release_lock", lambda key: locks.append(key))
    monkeypatch.setattr(jobs.cache, "set", lambda *a: None)

    def run(account_id, trade_date):
        calls.append(account_id)
        if account_id == 1:
            raise RuntimeError("模型不可用")

    monkeypatch.setattr(paper_monitor, "run", run)
    monkeypatch.setattr(paper_monitor.paper_execution, "run", lambda *args: None)
    jobs.paper_monitor_job()
    assert calls == [1, 2] and locks == ["paper_monitor"]


def test_scheduler_paper_monitor_pauses_on_unavailable_calendar(monkeypatch):
    from app.scheduler import jobs

    monkeypatch.setattr(jobs, "_in_trading_window", lambda _: True)

    def unavailable(_):
        raise RuntimeError("calendar unavailable")

    def forbidden(*args, **kwargs):
        raise AssertionError("unverified day reached paper execution")

    monkeypatch.setattr(jobs.AkshareSource, "fetch_trade_calendar", unavailable)
    monkeypatch.setattr(jobs.cache, "acquire_lock", forbidden)
    jobs.paper_monitor_job()


def test_close_job_audits_without_backdated_fills(monkeypatch):
    from app.scheduler import jobs
    from app.agents import paper_review

    audited = []
    monkeypatch.setattr(jobs, "_is_trading_day", lambda _: True)
    monkeypatch.setattr(jobs.cache, "acquire_lock", lambda *a, **k: True)
    monkeypatch.setattr(jobs.cache, "release_lock", lambda *a: None)
    monkeypatch.setattr(jobs.cache, "set", lambda *a: None)
    monkeypatch.setattr(jobs.repo, "list_paper_reviews", lambda **k: [
        {"id": 11, "audit_status": "pending"}, {"id": 12, "audit_status": "passed"}])
    monkeypatch.setattr(paper_review, "audit_review", lambda rid: audited.append(rid))

    def forbidden(*args, **kwargs):
        raise AssertionError("post-close job attempted a fill")

    monkeypatch.setattr(paper_monitor.paper_execution, "run", forbidden)
    jobs.paper_execution_job()
    assert audited == [11]
