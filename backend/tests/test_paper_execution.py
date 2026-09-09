"""模拟账本最小闭环：规则在代码层验证，且不污染真实 Holding。"""
import pytest

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
