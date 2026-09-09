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
    assert paper_valuation.account_view(account["id"], refresh=False)["positions"][0]["quote_status"] == "stale"


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
