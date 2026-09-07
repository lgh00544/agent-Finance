"""现实生命周期保护：计划绑定、有效持仓去重、复盘幂等。"""
import pytest
from fastapi import HTTPException

from app.agents import review
from app.api import routes
from app.db import repo
from app.db.session import init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def test_add_holding_rejects_plan_from_other_stock():
    plan_id = repo.insert_plan(
        "601901", "计划股", "2026-09-07", 20.0, [], 9.0, 12.0, "计划",
    )
    with pytest.raises(HTTPException) as exc:
        routes.add_holding(routes.HoldingBody(
            stock_code="601902", stock_name="另一只", entry_date="2026-09-07",
            entry_price=10.0, shares=100, plan_id=plan_id,
        ))
    assert exc.value.status_code == 400
    assert "不属于股票 601902" in str(exc.value.detail)


def test_add_holding_rejects_duplicate_active_code():
    repo.insert_holding("601903", "重复保护", "2026-09-07", 10.0, 100, 1000.0)
    with pytest.raises(HTTPException) as exc:
        routes.add_holding(routes.HoldingBody(
            stock_code="601903", stock_name="重复保护", entry_date="2026-09-07",
            entry_price=10.0, shares=100,
        ))
    assert exc.value.status_code == 409
    assert "请使用加仓/成本修正" in str(exc.value.detail)


def test_review_skips_existing_holding_exit(monkeypatch):
    hid = repo.insert_holding("601904", "复盘幂等", "2026-09-01", 10.0, 100, 1000.0)
    repo.insert_review("601904", "复盘幂等", hid, "2026-09-07", 6, -1.0, {}, "已有", {})
    called = {"llm": False}

    def fail_llm(*args, **kwargs):
        called["llm"] = True
        raise AssertionError("已有复盘不应再次调用模型")

    monkeypatch.setattr(review, "agent_call", fail_llm)
    state = review.llm_review({
        "holding_id": hid,
        "stock_code": "601904",
        "stock_name": "复盘幂等",
        "trade_date": "2026-09-07",
        "exit_suggest": {"holding": {}, "hold_days": 6, "pnl_pct": -1.0},
        "trace": [],
    })
    assert state["review_id"]
    assert "跳过重复生成" in state["trace"][-1]
    assert called["llm"] is False
