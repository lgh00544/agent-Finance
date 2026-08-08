"""手动持仓操作「差距补齐」测试（dev SQLite，真实落库；不触网）：
1. 加仓/减仓/清仓/成本修正流水含 before/after_shares（操作前后股数，K223 留痕）
2. record_holding_trade 单事务：失败整体回滚（流水与持仓一致）
3. 已平仓持仓手动触发监控 → 404
4. holding_trades 返回 before/after_shares；旧数据（NULL）兼容
5. 档位标注数据来源：holding_trades 最新 buy/adjust 流水
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
        return db.get(Holding, hid)


def _trades(hid):
    with SessionLocal() as db:
        return list(db.execute(
            select(TradeRecord).where(TradeRecord.holding_id == hid)
            .order_by(TradeRecord.id.desc())).scalars().all())


def test_add_records_before_after_shares():
    """加仓流水：before/after_shares = 1000/1100，与持仓一致"""
    hid = _holding(10.0, 1000)
    routes.add_shares(hid, routes.AddSharesBody(
        price=12.0, shares=100, trade_date="2026-08-06", note="回调加仓"))

    t = _trades(hid)[0]
    assert t.side == "buy"
    assert t.before_shares == 1000 and t.after_shares == 1100
    assert _get(hid).shares == 1100


def test_sell_records_before_after_shares():
    """减仓流水：before/after_shares = 1000/900；清仓 = 1000/0"""
    hid = _holding(10.0, 1000)
    routes.exit_holding(hid, routes.ExitBody(
        price=11.0, shares=100, trade_date="2026-08-06", note="减仓"))
    t = _trades(hid)[0]
    assert t.side == "sell" and t.before_shares == 1000 and t.after_shares == 900

    routes.exit_holding(hid, routes.ExitBody(
        price=11.5, shares=900, trade_date="2026-08-07", note="清仓"))
    t2 = _trades(hid)[0]
    assert t2.before_shares == 900 and t2.after_shares == 0
    assert _get(hid).status == "exited"


def test_adjust_records_before_after_shares():
    """成本修正流水：股数不变（before=after），成本/C3 联动"""
    hid = _holding(10.0, 1000)
    routes.adjust_cost(hid, routes.CostAdjustBody(cost_price=10.5, reason="实盘核对修正"))
    t = _trades(hid)[0]
    assert t.side == "adjust"
    assert t.before_shares == 1000 and t.after_shares == 1000
    assert _get(hid).stop_loss == round(10.5 * 0.92, 2)


def test_record_trade_transaction_rolls_back():
    """单事务：持仓不存在时写入整体回滚（无流水残留）"""
    before = len(_trades(999999))
    with pytest.raises(ValueError):
        repo.record_holding_trade(999999, side="sell", price=10.0, shares=100,
                                  trade_date="2026-08-06", note="x",
                                  before_shares=1000, after_shares=900,
                                  holding_fields={"shares": 900})
    assert len(_trades(999999)) == before  # 无流水写入


def test_monitor_404_when_exited(monkeypatch):
    """已清仓持仓手动触发监控 → 404（监控告警自动停止）"""
    monkeypatch.setattr(routes, "_submit_task", lambda kind, params: {"task_id": "t1"})
    hid = _holding(10.0, 1000)
    routes.exit_holding(hid, routes.ExitBody(
        price=11.0, shares=1000, trade_date="2026-08-06"))
    with pytest.raises(HTTPException) as e:
        routes.trigger_monitor(hid)
    assert e.value.status_code == 404


def test_trades_api_includes_before_after(monkeypatch):
    """holding_trades 接口返回 before/after_shares；旧数据 NULL 兼容"""
    hid = _holding(10.0, 1000)
    monkeypatch.setattr(routes, "_submit_task", lambda kind, params: {"task_id": "t1"})
    routes.add_shares(hid, routes.AddSharesBody(
        price=11.0, shares=100, trade_date="2026-08-05"))

    trades = routes.holding_trades(hid)
    t = trades[0]
    assert t["before_shares"] == 1000 and t["after_shares"] == 1100
    assert "before_shares" in t and "after_shares" in t

    # 旧数据兼容：直接插一条无 before/after 的流水（模拟补列前的历史记录）
    repo.add_trade(hid, "600004", "buy", 10.0, 100, "2026-07-01", "历史建仓")
    trades = routes.holding_trades(hid)
    legacy = [x for x in trades if x.get("before_shares") is None]
    assert legacy and legacy[0]["after_shares"] is None


def test_latest_risk_adjust_trade_source():
    """档位标注数据来源：最新 buy/adjust 流水（created_at 倒序第一条）"""
    hid = _holding(10.0, 1000)
    routes.adjust_cost(hid, routes.CostAdjustBody(cost_price=10.5, reason="实盘核对"))
    routes.add_shares(hid, routes.AddSharesBody(
        price=11.0, shares=100, trade_date="2026-08-06", note="加仓"))

    trades = routes.holding_trades(hid)
    newest = [x for x in trades if x["side"] in ("buy", "adjust")][0]
    assert newest["side"] == "buy" and newest["note"] == "加仓"
    assert newest["created_at"]
