"""手动持仓操作编辑接口测试（dev SQLite，真实落库；不触网）：
1. 加仓：加权成本重算 + C3 止损（成本×0.92）+ buy 流水留痕
2. 加仓股数非 100 整数倍 → 400（K32-3）
3. 成本修正：cost/C3 联动重算 + adjust 流水留痕（原因进 note）；原因空 → 400
4. 减仓/清仓 exit 补 K32-3 校验；清仓自动触发复盘任务
5. 操作流水接口按时间倒序返回
6. 已平仓/不存在持仓操作 → 404
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api import routes
from app.db import repo
from app.db.models import Holding, TradeRecord
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _holding(entry_price=10.0, shares=1000):
    return repo.insert_holding("600004", "测试股D", "2026-07-01",
                               entry_price, shares, entry_price * shares)


def _get(hid):
    with SessionLocal() as db:
        row = db.get(Holding, hid)
        return row


def _trades(hid):
    with SessionLocal() as db:
        return list(db.execute(
            select(TradeRecord).where(TradeRecord.holding_id == hid)
            .order_by(TradeRecord.id.desc())).scalars().all())


def test_add_shares_weighted_cost_and_c3():
    """加仓：加权成本 / 总股数 / C3=成本×0.92 联动，buy 流水落库"""
    hid = _holding(10.0, 1000)
    result = routes.add_shares(hid, routes.AddSharesBody(
        price=12.0, shares=100, trade_date="2026-08-06", note="回调加仓"))

    new_entry = round((10.0 * 1000 + 12.0 * 100) / 1100, 4)
    assert result["shares"] == 1100
    assert result["cost_price"] == new_entry
    assert result["stop_loss"] == round(new_entry * 0.92, 2)

    row = _get(hid)
    assert row.shares == 1100
    assert row.entry_price == new_entry
    assert row.cost == round(new_entry * 1100, 2)
    assert row.stop_loss == round(new_entry * 0.92, 2)

    t = _trades(hid)
    assert len(t) == 1 and t[0].side == "buy"
    assert t[0].price == 12.0 and t[0].shares == 100
    assert t[0].trade_date == "2026-08-06"


def test_add_shares_rejects_non_multiple_100():
    """K32-3：加仓股数非 100 整数倍 → 400，不落库"""
    hid = _holding(10.0, 1000)
    with pytest.raises(HTTPException) as e:
        routes.add_shares(hid, routes.AddSharesBody(
            price=12.0, shares=50, trade_date="2026-08-06"))
    assert e.value.status_code == 400
    assert _get(hid).shares == 1000


def test_add_shares_404_when_exited():
    """已平仓持仓不可加仓 → 404"""
    hid = _holding(10.0, 1000)
    repo.update_holding(hid, status="exited")
    with pytest.raises(HTTPException) as e:
        routes.add_shares(hid, routes.AddSharesBody(
            price=12.0, shares=100, trade_date="2026-08-06"))
    assert e.value.status_code == 404


def test_adjust_cost_records_adjust_trade():
    """成本修正：cost/C3 联动重算，adjust 流水留痕（原因进 note）"""
    hid = _holding(10.0, 1000)
    result = routes.adjust_cost(hid, routes.CostAdjustBody(
        cost_price=10.5, reason="实盘核对修正"))

    assert result["cost_price"] == 10.5
    assert result["stop_loss"] == round(10.5 * 0.92, 2)

    row = _get(hid)
    assert row.entry_price == 10.5
    assert row.cost == 10500.0
    assert row.stop_loss == round(10.5 * 0.92, 2)

    t = _trades(hid)
    assert len(t) == 1 and t[0].side == "adjust"
    assert "实盘核对修正" in t[0].note


def test_adjust_cost_requires_reason():
    """成本修正原因必填（留痕）→ 400"""
    hid = _holding(10.0, 1000)
    with pytest.raises(HTTPException) as e:
        routes.adjust_cost(hid, routes.CostAdjustBody(cost_price=10.5, reason="  "))
    assert e.value.status_code == 400


def test_exit_rejects_non_multiple_100():
    """K32-3：减仓/清仓股数非 100 整数倍 → 400"""
    hid = _holding(10.0, 1000)
    with pytest.raises(HTTPException) as e:
        routes.exit_holding(hid, routes.ExitBody(
            price=11.0, shares=150, trade_date="2026-08-06"))
    assert e.value.status_code == 400
    assert _get(hid).shares == 1000


def test_exit_full_clears_and_triggers_review(monkeypatch):
    """清仓：股数清零 → status=exited + 自动提交复盘任务"""
    hid = _holding(10.0, 1000)
    submitted = {}
    monkeypatch.setattr(routes, "_submit_task",
                        lambda kind, params: (submitted.update(kind=kind, params=params)
                                              or {"task_id": "t-review"}))
    result = routes.exit_holding(hid, routes.ExitBody(
        price=11.0, shares=1000, trade_date="2026-08-06", note="清仓"))
    assert result["remain_shares"] == 0
    assert result["review_task_id"] == "t-review"
    assert submitted["kind"] == "review"
    assert _get(hid).status == "exited"


def test_trades_desc_order(monkeypatch):
    """操作流水按时间倒序（同秒按 id 倒序），只读"""
    hid = _holding(10.0, 1000)
    monkeypatch.setattr(routes, "_submit_task", lambda kind, params: {"task_id": "t1"})
    routes.add_shares(hid, routes.AddSharesBody(
        price=11.0, shares=100, trade_date="2026-08-05"))
    routes.exit_holding(hid, routes.ExitBody(
        price=11.5, shares=100, trade_date="2026-08-06"))

    trades = routes.holding_trades(hid)
    assert [t["id"] for t in trades] == sorted([t["id"] for t in trades], reverse=True)
    assert [t["side"] for t in trades] == ["sell", "buy"]
    assert trades[0]["trade_date"] == "2026-08-06"
    assert trades[0]["created_at"]
