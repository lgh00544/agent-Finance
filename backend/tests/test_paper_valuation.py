from datetime import datetime, timedelta

import pytest

from app.db import repo
from app.db.session import init_db
from app.services import paper_valuation


@pytest.fixture(scope="module", autouse=True)
def ready():
    init_db()


def test_quote_time_is_not_replaced_with_fetch_time():
    now = datetime(2026, 9, 9, 10, 0)
    assert paper_valuation.quote_state({"price": 10}, now) == "time_unknown"
    assert paper_valuation.quote_state({"price": 10, "time": "2026-09-09 09:00:00"}, now) == "stale"
    assert paper_valuation.quote_state({"price": 10, "time": "2026-09-09 10:01:00"}, now) == "stale"
    assert paper_valuation.quote_state({"price": float("nan")}, now) == "unavailable"


def test_total_pnl_includes_realized_cash(monkeypatch):
    account = repo.create_paper_account("估值收益测试", 10000)
    value = repo.get_paper_account(account["id"])
    value.cash = 11000
    monkeypatch.setattr(repo, "get_paper_account", lambda _: value)
    result = paper_valuation.account_view(account["id"], refresh=False)
    assert result["pnl_amount"] == 1000
    assert result["pnl_pct"] == 10


def test_partial_or_stale_quotes_do_not_invent_equity(monkeypatch):
    account = repo.create_paper_account("部分行情测试", 10000)
    positions = [{"stock_code": code, "shares": 100, "avg_price": 10} for code in ("600001", "600002")]
    monkeypatch.setattr(repo, "list_paper_positions", lambda *a, **k: positions)
    repo.upsert_paper_quotes(account["id"], [{"stock_code": "600001", "price": 12,
                                            "quote_time": datetime.now().isoformat(), "status": "ok"}])
    result = paper_valuation.account_view(account["id"], refresh=False)
    assert result["positions"][0]["pnl_amount"] == 200
    assert result["positions"][1]["market_value"] is None
    assert result["equity"] is None
    repo.upsert_paper_quotes(account["id"], [{"stock_code": "600001", "price": 12,
                                            "quote_time": (datetime.now() - timedelta(hours=1)).isoformat()}])
    stale = paper_valuation.account_view(account["id"], refresh=False)["positions"][0]
    assert stale["quote_status"] == "stale"
    assert stale["current_price"] == 12
    assert stale["market_value"] == 1200
    assert stale["quote_reference_only"] is True


def test_quote_fallback_preserves_provenance(monkeypatch):
    from app.datasource import fallback

    class Source:
        def fetch_tencent_quotes_batch(self, codes):
            return {"600001": {"price": 12, "time": datetime.now().isoformat(), "volume": 1000, "source": "tencent"}}

        def fetch_spot_quotes_batch(self, codes):
            assert codes == ["600002"]
            return {"600002": {"price": 13, "source": "eastmoney_batch"}}

    monkeypatch.setattr(fallback, "get_datasource", lambda: Source())
    quotes, errors = paper_valuation.fetch_quotes(["600001", "600002"])
    assert quotes["600001"]["volume"] == 1000
    assert paper_valuation.quote_state(quotes["600002"]) == "time_unknown"
    assert not errors


@pytest.mark.parametrize("failure", ["empty", "exception", "time_unknown"])
def test_failed_refresh_retains_last_fact_for_reference_only(monkeypatch, failure):
    from app.services import paper_execution, paper_monitor

    account = repo.create_paper_account(f"历史估值 {failure}", 10000)
    positions = [{"stock_code": "600001", "shares": 100, "avg_price": 10}]
    monkeypatch.setattr(repo, "list_paper_positions", lambda *a, **k: positions)
    fact_time = (datetime.now() - timedelta(minutes=2)).isoformat()
    repo.upsert_paper_quotes(account["id"], [{
        "stock_code": "600001", "price": 12, "quote_time": fact_time,
        "source": "tencent", "status": "ok", "snapshot": {"volume": 1000, "change_pct": 1},
    }])

    def failed(_codes):
        if failure == "exception":
            raise RuntimeError("provider offline")
        return ({"600001": {"price": 99, "source": "undated"}} if failure == "time_unknown" else {}), []

    monkeypatch.setattr(paper_valuation, "fetch_quotes", failed)
    result = paper_valuation.account_view(account["id"])
    position = result["positions"][0]
    assert position["current_price"] == 12
    assert position["market_value"] == 1200
    assert position["pnl_amount"] == 200
    assert position["pnl_pct"] == 20
    assert position["quote_source"] == result["quote_source"] == "tencent"
    assert position["fact_as_of"] == result["valuation_as_of"] == fact_time
    assert position["quote_time"] == fact_time
    assert position["quote_reference_only"] is result["quote_reference_only"] is True
    assert position["quote_notice"] == result["quote_notice"] == "行情已过期，仅供参考"
    assert position["quote_status"] == result["quote_status"] == "stale"
    assert result["equity"] == 11200
    cached = repo.list_paper_quotes(account["id"], None)[0]
    assert cached["status"] != "ok"
    assert paper_valuation.quote_state(cached) != "ok"
    assert paper_monitor._quote_problem(cached, datetime.now().date().isoformat(), "live_paper")
    monkeypatch.setattr(paper_execution, "live_session_open", lambda _: True)
    assert paper_execution._live_quote_block(position, datetime.now().date().isoformat()) == "quote_stale_or_time_missing"
    assert not repo.list_paper_executions(account["id"])

    # A repeated failed refresh must not replace the saved factual snapshot.
    again = paper_valuation.account_view(account["id"])
    assert again["positions"][0]["current_price"] == 12
    assert again["positions"][0]["fact_as_of"] == fact_time
    monkeypatch.setattr(paper_valuation, "fetch_quotes", lambda _: ({"600001": {
        "price": 13, "time": datetime.now().isoformat(), "source": "tencent"}}, []))
    recovered = paper_valuation.account_view(account["id"])
    assert recovered["positions"][0]["current_price"] == 13
    assert recovered["quote_status"] == "ok"
    assert recovered["quote_reference_only"] is False


@pytest.mark.parametrize("quote", [{}, {"price": 12}, {"price": 12, "time": "2099-09-09 10:00:00"}])
def test_without_historical_facts_valuation_stays_unavailable(monkeypatch, quote):
    account = repo.create_paper_account("无历史有效事实", 10000)
    monkeypatch.setattr(repo, "list_paper_positions", lambda *a, **k: [
        {"stock_code": "600001", "shares": 100, "avg_price": 10}])
    monkeypatch.setattr(paper_valuation, "fetch_quotes", lambda _: ({"600001": quote}, []))
    result = paper_valuation.account_view(account["id"])
    assert result["positions"][0]["current_price"] is None
    assert result["market_value"] is result["equity"] is result["pnl_amount"] is None
    assert result["valuation_as_of"] is None
    assert result["quote_reference_only"] is False


def test_recovers_only_live_execution_quote_facts(monkeypatch):
    from app.db.models import PaperExecution
    from app.db.session import SessionLocal

    account = repo.create_paper_account("历史成交行情恢复", 10000)
    fact_time = (datetime.now() - timedelta(days=1)).isoformat()
    newer_time = (datetime.now() - timedelta(hours=1)).isoformat()
    with SessionLocal() as db:
        for index, (code, mode, quote) in enumerate([
            ("600001", "live_paper", {"price": 12, "time": fact_time, "source": "tencent"}),
            ("600001", "historical_replay", {"price": 99, "time": newer_time, "source": "replay"}),
            ("600002", "live_paper", {"price": 88, "source": "undated"}),
        ]):
            db.add(PaperExecution(account_id=account["id"], execution_key=f"valuation:{account['id']}:{index}",
                                  stock_code=code, side="buy", status="filled", requested_price=10,
                                  trade_date=fact_time[:10],
                                  metadata_json={"mode": mode, "facts": {"quote": quote}}))
        db.commit()
    monkeypatch.setattr(repo, "list_paper_positions", lambda *a, **k: [
        {"stock_code": code, "shares": 100, "avg_price": 10} for code in ("600001", "600002")])
    monkeypatch.setattr(paper_valuation, "fetch_quotes", lambda _: ({}, []))
    result = paper_valuation.account_view(account["id"])
    assert result["positions"][0]["current_price"] == 12
    assert result["positions"][0]["fact_as_of"] == fact_time
    assert result["positions"][0]["quote_status"] == "stale"
    assert result["positions"][1]["current_price"] is None
    assert result["equity"] is None


def test_stale_batch_fact_survives_undated_single_fallback(monkeypatch):
    from app.datasource import fallback

    fact_time = (datetime.now() - timedelta(hours=1)).isoformat()

    class Source:
        def fetch_tencent_quotes_batch(self, codes):
            return {"600001": {"price": 12, "time": fact_time, "source": "tencent"}}

        def fetch_spot_quote(self, code):
            return {"price": 99, "source": "undated"}

    monkeypatch.setattr(fallback, "get_datasource", lambda: Source())
    quotes, _errors = paper_valuation.fetch_quotes(["600001"])
    assert quotes["600001"]["price"] == 12
    assert quotes["600001"]["source"] == "tencent"
