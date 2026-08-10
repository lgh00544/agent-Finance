"""游资数据链·步骤二：龙虎榜数据源（mock http_client 东财直连 + akshare 兜底，不触网）"""
import pandas as pd
import pytest

from app.core.config import settings
from app.datasource import dragon_tiger_source as dts


class _FakeResp:
    """东财 datacenter API 假响应：按 reportName 返回对应数据"""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_EM_STOCKS_PAYLOAD = {"result": {"data": [
    {"SECURITY_CODE": "601138", "SECURITY_NAME_ABBR": "工业富联",
     "TRADE_DATE": "2026-08-07 00:00:00", "EXPLANATION": "日涨幅偏离值达7%",
     "BILLBOARD_NET_AMT": 40000000, "BILLBOARD_BUY_AMT": 50000000,
     "BILLBOARD_SELL_AMT": 10000000},
]}}
_EM_SEATS_PAYLOAD = {"result": {"data": [
    {"SECURITY_CODE": "601138", "OPERATEDEPT_NAME": "中信证券股份有限公司上海分公司",
     "BUY": 30000000, "SELL": 10000000, "NET": 20000000},
    {"SECURITY_CODE": "601138", "OPERATEDEPT_NAME": "华鑫证券有限责任公司上海分公司",
     "BUY": 20000000, "SELL": 5000000, "NET": 15000000},
    {"SECURITY_CODE": "000603", "OPERATEDEPT_NAME": "机构专用",
     "BUY": 5000000, "SELL": 0, "NET": 5000000},
]}}


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setattr(settings, "dragon_tiger_enable", True)


@pytest.fixture(autouse=True)
def _fake_http(monkeypatch):
    """mock 东财直连 HTTP（vendored 主路径）"""
    def _fake_get(url, referer=None, params=None, timeout=None, **kw):
        report = (params or {}).get("reportName")
        if report == dts._EM_STOCKS_REPORT:
            return _FakeResp(_EM_STOCKS_PAYLOAD)
        if report == dts._EM_BUY_REPORT:
            return _FakeResp(_EM_SEATS_PAYLOAD)
        if report == dts._EM_SELL_REPORT:
            return _FakeResp({"result": {"data": []}})  # 测试中卖出明细为空
        return _FakeResp({"result": {"data": []}})

    monkeypatch.setattr(dts, "http_get", _fake_get)


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    """隔离席位当日缓存（不同日期 key 天然隔离，测试间不串扰）"""
    yield
    from app.cache import cache
    cache.delete_prefix("lhb:seats:")


def test_fetch_lhb_stocks_eastmoney():
    """东财股票级（vendored 直连）：列规范化 + 净买 float + 口径标记"""
    df = dts.DragonTigerSource().fetch_lhb_stocks("2026-08-07", source="eastmoney")
    assert not df.empty
    assert df.iloc[0]["stock_code"] == "601138"
    assert df.iloc[0]["net_buy"] == 40000000.0
    assert df.iloc[0]["lhb_type"] == "1d" and df.iloc[0]["source"] == "eastmoney"
    assert df.iloc[0]["confidence"] == 0.8


def test_fetch_lhb_stocks_sina(monkeypatch):
    """新浪备源（akshare）：上榜原因列表（无金额列，net_buy 缺省）"""
    class _FakeAk:
        def stock_lhb_detail_daily_sina(self, date=None):
            return pd.DataFrame([
                {"股票代码": "601138", "股票名称": "工业富联", "指标": "日涨幅偏离值达7%"},
            ])

    monkeypatch.setattr(dts, "ak", _FakeAk())
    df = dts.DragonTigerSource().fetch_lhb_stocks("2026-08-07", source="sina")
    assert not df.empty
    assert df.iloc[0]["stock_code"] == "601138"
    assert df.iloc[0]["source"] == "sina"
    assert "net_buy" not in df.columns or pd.isna(df.iloc[0].get("net_buy"))


def test_fetch_lhb_seats():
    """席位级（vendored 东财全量明细 + 按股过滤）"""
    src = dts.DragonTigerSource()
    df = src.fetch_lhb_seats("2026-08-07", "601138", lhb_type="1d")
    assert len(df) == 2
    assert df.iloc[0]["seat_name"] == "中信证券股份有限公司上海分公司"
    assert df.iloc[0]["net_buy"] == 20000000.0  # 东财单位已是元
    assert df.iloc[0]["lhb_type"] == "1d"
    # 其他股票过滤
    df2 = src.fetch_lhb_seats("2026-08-07", "000603", lhb_type="1d")
    assert len(df2) == 1 and df2.iloc[0]["seat_name"] == "机构专用"
    # 3d 暂不支持
    assert src.fetch_lhb_seats("2026-08-07", "601138", lhb_type="3d").empty


def test_fetch_disabled_returns_empty(monkeypatch):
    """开关关闭 → 全部返回空（不抓取）"""
    monkeypatch.setattr(settings, "dragon_tiger_enable", False)
    src = dts.DragonTigerSource()
    assert src.fetch_lhb_stocks("2026-08-07").empty
    assert src.fetch_lhb_seats("2026-08-07", "601138").empty


def test_fetch_failure_degrades(monkeypatch):
    """东财直连失败 → 降级 akshare 兜底；都失败返回空表不抛"""
    def _boom(*a, **k):
        raise ConnectionError("网络不可达")

    monkeypatch.setattr(dts, "http_get", _boom)
    monkeypatch.setattr(dts, "ak", None)  # 无 akshare 兜底
    assert dts.DragonTigerSource().fetch_lhb_stocks("2026-08-07").empty


def test_fetch_and_merge():
    """完整抓取合并：席位级（全量明细）+ 股票级（东财）"""
    seats, stocks = dts.DragonTigerSource().fetch_and_merge("2026-08-07")
    assert len(seats) == 3  # 601138×2 + 000603×1
    assert not stocks.empty and stocks.iloc[0]["source"] == "eastmoney"


def test_fetch_dragon_tiger_lands_db(monkeypatch):
    """fetch_dragon_tiger：拉取 + 落库（独立日期 2026-08-10，避免与其他测试数据串扰）"""
    from app.db import repo
    from app.db.session import init_db

    # akshare 兜底禁网：测试只验证 mock 东财数据链（akshare 是真实网络，交易日连通时
    # 会拉入当日真实龙虎榜行，破坏 4 行精确断言；与上游 HEAD 同源修复）
    monkeypatch.setattr(dts, "ak", None)
    init_db()
    before = len(repo.list_lhb_flows(trade_date="2026-08-10"))
    seats = dts.fetch_dragon_tiger("2026-08-10")
    assert len(seats) == 3
    rows = repo.list_lhb_flows(trade_date="2026-08-10")
    # 本次新增：席位级 3 + 股票级 1（东财）
    assert len(rows) - before == 4
    seat_rows = [r for r in rows if r["seat_name"]]
    assert len(seat_rows) == 3
