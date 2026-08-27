"""建仓流水补全（A 补数据 + B 兜底）测试：3 例
1. insert_holding 自动产生 buy 流水且金额=entry_price×shares
2. 回填 ensure_opening_trade 幂等不重复插（仿墨龙：缺首笔补 8450）
3. exited 缺流水持仓 review 用总成本口径 → pnl_pct 为负值正确"""
import pandas as pd
import pytest
from sqlalchemy import delete, select

from app.agents import review
from app.db import repo
from app.db.models import Holding, TradeRecord
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _molong_like():
    """仿墨龙：先建仓（自动带补录）→ 删补录模拟存量缺首笔 → 录真实存量 buy（首条 before_shares=1000）"""
    hid = repo.insert_holding("002490", "墨龙", "2026-08-25", 8.394, 2500, 20985.0)
    with SessionLocal() as db:
        db.execute(delete(TradeRecord).where(TradeRecord.holding_id == hid,
                                             TradeRecord.note == "建仓补录"))
        db.commit()
    repo.record_holding_trade(hid, side="buy", price=8.35, shares=500, trade_date="2026-08-25",
                              note="", before_shares=1000, after_shares=1500)
    repo.record_holding_trade(hid, side="buy", price=8.36, shares=1000, trade_date="2026-08-25",
                              note="", before_shares=1500, after_shares=2500)
    return hid


def test_insert_holding_auto_opens_buy_flow():
    """① insert_holding 自动产生开仓 buy 流水，金额=entry_price×shares、note=建仓补录"""
    hid = repo.insert_holding("600000", "测试股", "2026-08-25", 10.0, 200, 2000.0)
    trades = repo.get_trades(hid)
    assert len(trades) == 1
    t = trades[0]
    assert t.side == "buy"
    assert t.note == "建仓补录"
    assert t.amount == pytest.approx(2000.0, abs=0.01)  # 10×200
    assert t.shares == 200
    assert t.price == pytest.approx(10.0)


def test_backfill_idempotent():
    """② 回填幂等：首次补 8450（1000股@8.45），二次运行 0 新增"""
    hid = _molong_like()
    h = repo.get_holding(hid)
    r1 = repo.ensure_opening_trade(h)
    assert r1["applied"] is True
    assert r1["amount"] == pytest.approx(8450.0, abs=0.01)  # cost(20985)−Σbuy(12535)
    assert r1["shares"] == 1000
    assert r1["price"] == pytest.approx(8.45)
    r2 = repo.ensure_opening_trade(h)
    assert r2["applied"] is False
    assert r2["reason"] == "already-backfilled"
    notes = [t for t in repo.get_trades(hid) if t.note == "建仓补录"]
    assert len(notes) == 1


def test_review_pnl_uses_cost_caliber():
    """③ exited 缺流水持仓 review：总成本口径 pnl_pct≈−4.99（不再是 +59%）"""
    hid = _molong_like()
    repo.record_holding_trade(hid, side="sell", price=8.07, shares=800, trade_date="2026-08-26",
                              note="", before_shares=2500, after_shares=1700)
    repo.record_holding_trade(hid, side="sell", price=7.93, shares=1700, trade_date="2026-08-27",
                              note="", before_shares=1700, after_shares=0)
    repo.update_holding(hid, status="exited", shares=0)

    class _FakeSource:
        def fetch_daily_kline(self, code, start, end):
            return pd.DataFrame(columns=["date", "open", "high", "low",
                                         "close", "change_pct", "volume"])

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.agents.review.get_datasource", lambda: _FakeSource())
    try:
        st = review.collect_review({"holding_id": hid, "trade_date": "2026-08-27"})
    finally:
        monkeypatch.undo()
    pnl = st["exit_suggest"]["pnl_pct"]
    assert pnl < 0  # 实亏方向
    assert abs(pnl - (-4.99)) < 0.5  # (19937−20985)/20985×100
