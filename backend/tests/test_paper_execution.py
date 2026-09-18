"""模拟账本最小闭环：规则在代码层验证，且不污染真实 Holding。"""
import pytest
import pandas as pd

from app.db import repo
from app.db.models import Holding
from app.db.session import SessionLocal, init_db
from app.services import paper_execution


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _facts(price=10.0, change_pct=0.0, tradeable=True):
    row = {"stock_code": "688901", "stock_name": "模拟测试股", "is_tradeable": int(tradeable),
           "current_price": price, "detail": {}}
    candidate = {"id": 99001, "stock_code": "688901", "stock_name": "模拟测试股",
                 "snapshot": {"price": price, "change_pct": change_pct, "fact_as_of": "2026-09-08"}}
    return {"tradeable": [row], "candidates": {"688901": candidate},
            "scores": {"688901": {"id": 99002, "grade": "A"}},
            "plans": {"688901": {"id": 99003, "status": "accepted", "total_pct": 50,
                                    "batches": [{"ratio": 1}], "stop_loss": 8, "take_profit": 12}}}


def test_paper_buy_lot_t1_and_sell_without_real_holding():
    with SessionLocal() as db:
        real_before = db.query(Holding).count()
    account = repo.create_paper_account("测试模拟账户", 100_000, "current_gate")
    result = paper_execution.run(account["id"], "2026-09-08", facts=_facts())
    assert result["filled"] == 1
    assert result["executions"][0]["shares"] == 5000
    assert result["executions"][0]["source_label"] == "AI模拟"

    same_day = paper_execution.run(account["id"], "2026-09-08", facts=_facts(),
                                   requested_sides={"688901": "sell"})
    assert same_day["rejected"] == 1
    assert same_day["executions"][0]["reject_reason"] == "t_plus_one_or_no_lot"

    next_day = paper_execution.run(account["id"], "2026-09-09", facts=_facts(),
                                   requested_sides={"688901": "sell"})
    assert next_day["filled"] == 1
    assert next_day["executions"][0]["stamp_tax"] > 0

    with SessionLocal() as db:
        assert db.query(Holding).count() == real_before


def test_paper_limit_up_and_idempotency():
    account = repo.create_paper_account("测试涨停账户", 100_000, "current_gate")
    facts = _facts(change_pct=20.0)
    result = paper_execution.run(account["id"], "2026-09-10", facts=facts)
    assert result["rejected"] == 1
    assert result["executions"][0]["reject_reason"] == "limit_up"
    again = paper_execution.run(account["id"], "2026-09-10", facts=facts)
    assert again["executions"][0]["id"] == result["executions"][0]["id"]


def test_candidate_pool_variant_fills_without_plan_or_tradeable_gate():
    account = repo.create_paper_account("候选池研究账户", 33_960.64, "candidate_pool")
    facts = _facts(price=34.4)
    facts["tradeable"][0]["is_tradeable"] = 0
    facts["plans"] = {}
    result = paper_execution.run(account["id"], "2026-09-10", facts=facts)
    assert result["filled"] == 1
    assert result["executions"][0]["strategy_variant"] == "candidate_pool"
    assert result["executions"][0]["shares"] == 100


def test_paper_future_fact_is_rejected():
    account = repo.create_paper_account("未来数据隔离账户", 100_000, "current_gate")
    facts = _facts()
    facts["candidates"]["688901"]["snapshot"]["fact_as_of"] = "2026-09-11"
    result = paper_execution.run(account["id"], "2026-09-10", facts=facts)
    assert result["rejected"] == 1
    assert result["executions"][0]["reject_reason"] == "future_data"


def test_paper_nested_future_observation_is_rejected():
    account = repo.create_paper_account("嵌套未来数据隔离账户", 100_000, "current_gate")
    facts = _facts()
    facts["candidates"]["688901"]["detail"] = {
        "quote": {"observed_at": "2026-09-11 09:35:00"},
    }
    result = paper_execution.run(account["id"], "2026-09-10", facts=facts)
    assert result["rejected"] == 1
    assert result["executions"][0]["reject_reason"] == "future_data"
    assert "candidate.detail.quote.observed_at" in result["executions"][0]["metadata"]["future_fields"]


def test_paper_buy_fee_budget_shortfall_is_recorded_as_rejection():
    account = repo.create_paper_account("费用预算账户", 10, "current_gate")
    result = paper_execution.run(account["id"], "2026-09-12", facts=_facts(price=10.0))
    assert result["filled"] == 0
    assert result["rejected"] == 1
    assert result["executions"][0]["reject_reason"] == "cash_or_plan_position_too_small"


def test_paper_review_requires_audit_before_shadow():
    account = repo.create_paper_account("测试复盘账户", 10_000, "current_gate")
    rid = repo.create_paper_review(account["id"], "688901", "模拟测试股", "2026-09-10", {"pnl_pct": -1})
    with pytest.raises(ValueError, match="必须先通过 AI 审核"):
        repo.mark_paper_shadow(rid)
    audited = repo.audit_paper_review(rid, "pass", "事实范围、费用和未来数据隔离完整")
    assert audited["audit_status"] == "passed"
    assert repo.mark_paper_shadow(rid)["shadow_status"] == "pending"


def test_paper_account_can_pause_and_resume():
    account = repo.create_paper_account("暂停账户", 10_000, "current_gate")
    paused = repo.update_paper_account_status(account["id"], "paused")
    assert paused["status"] == "paused"
    active = repo.update_paper_account_status(account["id"], "active")
    assert active["status"] == "active"


def test_sell_after_leaving_pool_and_partial_trace():
    account = repo.create_paper_account("离池减仓测试", 100_000)
    paper_execution.run(account["id"], "2026-09-08", facts=_facts())
    facts = {"contexts": {"688901": {"id": 123, "facts": {"fact_as_of": "2026-09-09"}}},
             "sell_decisions": {"688901": {"action": "partial", "reduce_ratio": 0.5}}}
    out = paper_execution.run(account["id"], "2026-09-09", facts=facts,
                              requested_sides={"688901": "sell"},
                              quote_facts={"688901": {"price": 11, "change_pct": 0.8, "fact_as_of": "2026-09-09"}})
    event = out["executions"][0]
    assert event["status"] == "filled"
    assert event["shares"] == 2500
    assert event["metadata"]["context_id"] == 123
    assert repo.list_paper_positions(account["id"])[0]["shares"] == 2500
    review = repo.list_paper_reviews(account["id"])[0]
    assert review["content"]["exit_execution"]["id"] == event["id"]
    assert "pnl_amount" in review["content"]


def test_sub_one_percent_is_not_a_limit():
    assert paper_execution._limit_block("buy", "600001", {"price": 10, "change_pct": 0.8}) == ""
    assert paper_execution._limit_block("buy", "600001", {"price": 10, "change_pct": 5, "name": "ST测试"}) == "limit_up"


def test_reopened_position_has_new_t1_date():
    account = repo.create_paper_account("重开仓测试", 100_000)
    for day, side in (("2026-09-08", "buy"), ("2026-09-09", "sell"), ("2026-09-10", "buy")):
        paper_execution.run(account["id"], day, facts=_facts(), requested_sides={"688901": side})
    out = paper_execution.run(account["id"], "2026-09-10", facts=_facts(), requested_sides={"688901": "sell"})
    assert out["executions"][0]["reject_reason"] == "t_plus_one_or_no_lot"
    assert repo.list_paper_positions(account["id"])[0]["opened_trade_date"] == "2026-09-10"


def test_live_market_closed_is_not_filled(monkeypatch):
    account = repo.create_paper_account("非交易时段测试", 100_000)
    monkeypatch.setattr(paper_execution, "live_session_open", lambda _: False)
    facts = {**_facts(), "mode": "live_paper", "contexts": {"688901": {"id": 123}}}
    result = paper_execution.run(account["id"], "2026-09-08", facts=facts,
                                 quote_facts={"688901": {"price": 10}})
    assert result["filled"] == 0
    assert result["executions"][0]["reject_reason"] == "market_closed"


def test_live_paper_records_latest_market_context(monkeypatch):
    account = repo.create_paper_account("最新市况留痕测试", 100_000)
    monkeypatch.setattr(repo, "get_latest_market_condition", lambda: {
        "trade_date": "2026-09-08", "total_score": 45, "band": "进取期",
        "cap": 30, "dims": {"breadth": 9}, "summary": "上涨扩散",
    })
    monkeypatch.setattr(paper_execution, "_live_quote_block", lambda *_: "")
    facts = {**_facts(), "mode": "live_paper",
             "contexts": {"688901": {"id": 123, "facts": {"fact_as_of": "2026-09-08"}}}}
    out = paper_execution.run(account["id"], "2026-09-08", facts=facts,
                              quote_facts={"688901": {"price": 10, "change_pct": 0,
                                                       "volume": 1000,
                                                       "fact_as_of": "2026-09-08"}})
    assert out["market_context"]["total_score"] == 45
    assert out["executions"][0]["metadata"]["facts"]["market_context"]["band"] == "进取期"


def test_paper_market_sync_adds_relative_strength_only_on_live_rotation(monkeypatch):
    from app.datasource import fallback

    class Source:
        def fetch_index_spot(self):
            return pd.DataFrame({"code": ["sh000001", "sz399001"], "change_pct": [1.0, 1.2]})

        def fetch_spot_universe(self):
            return pd.DataFrame({"code": ["600001", "600002"], "price": [10.0, 8.0],
                                 "change_pct": [2.0, 1.3]})

    monkeypatch.setattr(fallback, "get_datasource", lambda: Source())
    today = paper_execution.date.today().isoformat()
    rows, context = paper_execution._paper_market_sync(
        today, [],
        {"600001": {"stock_name": "强势股"}, "600002": {"stock_name": "普通股"}},
        {"600001": {"id": 1}, "600002": {"id": 2}},
    )
    assert [row["stock_code"] for row in rows] == ["600001"]
    assert context["status"] == "rotation_candidates"


def test_paper_market_sync_freezes_historical_facts():
    rows, context = paper_execution._paper_market_sync(
        "2026-09-08", [], {"600001": {}}, {"600001": {"id": 1}})
    assert rows == []
    assert context["status"] == "historical_or_frozen"


def test_live_buy_gate_records_missing_facts_without_touching_replay():
    missing, metadata = paper_execution._live_buy_gate(
        {"price": 10, "fact_as_of": "2026-09-18"},
        {"facts": {"get_daily_kline": {"rows": [{"close": 10}]},
                   "get_news": {"news": []}}},
        {"band": "进取期"}, "2026-09-18")
    assert missing == []
    assert metadata["live_buy_gate"]["fact_as_of"] == "2026-09-18"
    missing, metadata = paper_execution._live_buy_gate(
        {"price": 10, "fact_as_of": "2026-09-18"}, {}, {}, "2026-09-18")
    assert set(missing) == {"technical_kline", "news_announcement", "market_context"}
    assert metadata["live_buy_gate"]["context_hash"]


def test_live_buy_missing_facts_is_rejected_and_audited(monkeypatch):
    account = repo.create_paper_account("实时复核闸门账户", 100_000, "candidate_pool")
    monkeypatch.setattr(paper_execution, "_live_quote_block", lambda *_: "")
    today = paper_execution.date.today().isoformat()
    facts = {**_facts(), "mode": "live_paper", "market_context": {"band": "进取期"},
             "contexts": {"688901": {"id": 123, "facts": {"fact_as_of": today}}}}
    out = paper_execution.run(
        account["id"], today, facts=facts,
        quote_facts={"688901": {"price": 10, "volume": 1000,
                                 "change_pct": 0, "fact_as_of": today}})
    event = out["executions"][0]
    assert event["status"] == "rejected"
    assert event["reject_reason"] == "live_buy_facts_missing"
    assert set(event["metadata"]["live_buy_gate"]["missing"]) == {
        "technical_kline", "news_announcement"}


def test_candidate_pool_uses_candidate_universe_for_non_tradeable_grade():
    account = repo.create_paper_account("候选池全集测试", 100_000, "candidate_pool")
    facts = _facts(price=10.0)
    facts["tradeable"] = []
    result = paper_execution.run(account["id"], "2026-09-12", facts=facts)
    assert result["filled"] == 1
    assert result["executions"][0]["shares"] == 1000
    position = repo.list_paper_positions(account["id"])[0]
    assert position["metadata"]["control_plan"]["version"] == "candidate-pool-control-v1"


def test_candidate_pool_lifecycle_control_and_review():
    account = repo.create_paper_account("候选池生命周期测试", 100_000, "candidate_pool")

    opened = paper_execution.run(account["id"], "2026-09-08", facts=_facts(price=10.0))
    assert opened["filled"] == 1
    assert opened["executions"][0]["side"] == "buy"

    added = paper_execution.run(account["id"], "2026-09-09", facts=_facts(price=10.5))
    assert added["filled"] == 1
    assert added["executions"][0]["side"] == "buy"
    assert added["executions"][0]["metadata"]["lifecycle_reason"] == "candidate_pool_add"

    first_take = paper_execution.run(account["id"], "2026-09-10", facts=_facts(price=10.81))
    assert first_take["filled"] == 1
    assert first_take["executions"][0]["side"] == "sell"
    assert first_take["executions"][0]["shares"] == 500

    trailing = paper_execution.run(account["id"], "2026-09-11", facts=_facts(price=10.1))
    assert trailing["filled"] == 1
    assert trailing["executions"][0]["metadata"]["lifecycle_reason"] == "trailing_stop"
    assert repo.list_paper_positions(account["id"])[0]["status"] == "exited"
    reviews = repo.list_paper_reviews(account["id"])
    assert reviews and reviews[0]["execution_id"] == trailing["executions"][0]["id"]

    again = paper_execution.run(account["id"], "2026-09-11", facts=_facts(price=10.1))
    assert again["filled"] == 0
