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


def test_second_source_status_dynamic():
    """第二源状态动态（K227 零网络）：sina_fetched=True → available=True 双源标注；False → 旧标注"""
    ss_t = dts.second_source_status(sina_fetched=True)
    assert ss_t["available"] is True
    assert "双源" in ss_t["annotation"] and "东财金额" in ss_t["annotation"]
    ss_f = dts.second_source_status(sina_fetched=False)
    assert ss_f["available"] is False
    assert "仅东财可用" in ss_f["annotation"] and "采信待第二源" in ss_f["annotation"]
    # 无参默认向后兼容（jobs.py/hot_money.py 不传参 → 旧标注）
    assert dts.second_source_status()["available"] is False
    assert dts.second_source_status()["annotation"] == ss_f["annotation"]


def test_fetch_and_merge_dual_listed_verified(monkeypatch):
    """双源在榜：东财金额行 confidence 升级 0.9 + multi_source_verified=True；金额以东财为准"""
    class _FakeAk:
        def stock_lhb_detail_daily_sina(self, date=None):
            return pd.DataFrame([
                {"股票代码": "601138", "股票名称": "工业富联", "指标": "日涨幅偏离值达7%"},
            ])
    monkeypatch.setattr(dts, "ak", _FakeAk())
    _, stocks = dts.DragonTigerSource().fetch_and_merge("2026-08-07")
    em_row = stocks[stocks["source"] == "eastmoney"].iloc[0]
    assert em_row["stock_code"] == "601138"
    assert em_row["confidence"] == 0.9
    assert bool(em_row["multi_source_verified"]) is True  # pandas bool 列回 np.bool_，用 bool() 归一
    assert em_row["net_buy"] == 40000000.0  # 金额以东财为准，不被新浪覆盖
    sina_row = stocks[stocks["source"] == "sina"].iloc[0]
    assert "net_buy" not in sina_row or pd.isna(sina_row.get("net_buy"))  # 新浪无金额列


def test_fetch_and_merge_sina_only_degrades(monkeypatch):
    """仅新浪在榜（无金额，仅上榜确认）：confidence 0.55、multi_source_verified 不置"""
    class _FakeAk:
        def stock_lhb_detail_daily_sina(self, date=None):
            return pd.DataFrame([
                {"股票代码": "000001", "股票名称": "平安银行", "指标": "日涨幅偏离值达7%"},
            ])
    monkeypatch.setattr(dts, "ak", _FakeAk())
    _, stocks = dts.DragonTigerSource().fetch_and_merge("2026-08-07")
    sina_row = stocks[stocks["source"] == "sina"].iloc[0]
    assert sina_row["stock_code"] == "000001"
    assert sina_row["confidence"] == 0.55
    assert bool(sina_row["multi_source_verified"]) is False
    assert "net_buy" not in sina_row or pd.isna(sina_row.get("net_buy"))
    # 东财独享行不受影响（保持 0.8，不置核验标志）
    em_row = stocks[stocks["source"] == "eastmoney"].iloc[0]
    assert em_row["confidence"] == 0.8
    assert bool(em_row["multi_source_verified"]) is False


def test_fetch_dragon_tiger_persists_multi_source_flag(monkeypatch):
    """落库：双源在榜标的 multi_source_verified=True 写入 lhb_flows 并随查询返回"""
    from app.db import repo
    from app.db.session import init_db

    class _FakeAk:
        def stock_lhb_detail_daily_sina(self, date=None):
            return pd.DataFrame([
                {"股票代码": "601138", "股票名称": "工业富联", "指标": "日涨幅偏离值达7%"},
            ])
    monkeypatch.setattr(dts, "ak", _FakeAk())
    init_db()
    dts.fetch_dragon_tiger("2026-08-13")
    rows = repo.list_lhb_flows(trade_date="2026-08-13")
    verified = [r for r in rows if r.get("multi_source_verified")]
    assert verified, "双源在榜标的应持久化 multi_source_verified=True"
