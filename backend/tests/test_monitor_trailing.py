"""MonitorAgent 移动止盈接入测试（批次1）：
1. _attach_trailing_stop：现价 > 持仓期最高价 → 更新最高价落库
2. 浮盈 ≥5% → quote 挂 trailing_stop 字段（= 最高价×0.92，不低于成本）
3. 旧数据 high_price=NULL 降级：首次以当前价为基准
4. 浮盈 <5% → trailing_stop 为 None（沿用原固定止盈）
5. 行情缺失 → 不更新、不挂字段（不编造）
"""
from sqlalchemy import delete

from app.agents import monitor
from app.db import repo
from app.db.models import Holding
from app.db.session import SessionLocal, init_db
import pytest


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(delete(Holding))
        db.commit()


class _Holding:
    """mock 持仓对象（get_holding 返回）"""
    def __init__(self, hid, entry_price, high_price):
        self.id = hid
        self.entry_price = entry_price
        self.high_price = high_price


def _mock_holding(monkeypatch, holding, updated: dict):
    monkeypatch.setattr(monitor.repo, "get_holding", lambda _id: holding)
    monkeypatch.setattr(monitor.repo, "update_holding",
                        lambda hid, **kw: updated.update(kw) or None)
    return updated


def test_updates_high_and_attaches_trailing(monkeypatch):
    """现价 13 > 最高价 12 → 更新最高价；浮盈 30% → 挂 trailing_stop"""
    updated = {}
    _mock_holding(monkeypatch, _Holding(1, 10.0, 12.0), updated)
    quote = {"code": "600519", "price": 13.0, "change_pct": 5.0}
    monitor._attach_trailing_stop(quote, {"holding_id": 1})
    assert updated["high_price"] == 13.0
    assert quote["trailing_stop"] == round(13.0 * 0.92, 2)  # 13×0.92=11.96


def test_null_high_fallback_to_current(monkeypatch):
    """旧数据 high_price=NULL：首次以当前价为基准；浮盈<5% 不启用"""
    updated = {}
    _mock_holding(monkeypatch, _Holding(2, 10.0, None), updated)
    quote = {"code": "600519", "price": 10.4, "change_pct": 1.0}
    monitor._attach_trailing_stop(quote, {"holding_id": 2})
    assert updated["high_price"] == 10.4     # 以当前价为基准写入
    assert quote.get("trailing_stop") is None  # 浮盈 4% → 不启用


def test_below_5pct_attaches_none(monkeypatch):
    """浮盈不足 5%：字段为 None（LLM 见 null 不触发）"""
    updated = {}
    _mock_holding(monkeypatch, _Holding(3, 10.0, 12.0), updated)
    quote = {"code": "600519", "price": 10.4, "change_pct": 1.0}
    monitor._attach_trailing_stop(quote, {"holding_id": 3})
    assert updated == {}                     # 现价未超最高价 → 不更新
    assert quote.get("trailing_stop") is None


def test_missing_price_no_update(monkeypatch):
    """行情缺失（price=None）：不更新最高价、不挂字段"""
    updated = {}
    _mock_holding(monkeypatch, _Holding(4, 10.0, 12.0), updated)
    quote = {"code": "600519", "price": None, "change_pct": None}
    monitor._attach_trailing_stop(quote, {"holding_id": 4})
    assert updated == {}
    assert "trailing_stop" not in quote


def test_no_holding_skips(monkeypatch):
    """无持仓（holding_id 无效）：静默跳过"""
    monkeypatch.setattr(monitor.repo, "get_holding", lambda _id: None)
    quote = {"code": "600519", "price": 13.0}
    monitor._attach_trailing_stop(quote, {"holding_id": 999})
    assert "trailing_stop" not in quote
