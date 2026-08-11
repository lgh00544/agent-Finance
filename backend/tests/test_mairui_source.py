"""麦蕊智数增强数据源测试（不触网：requests 全部 mock）：
1. 数据源工厂：默认关闭返回 akshare（行为与之前完全一致）/ 启用返回降级包装
2. 麦蕊取数解析（股东户数/成交分布 → 对齐 akshare 标准字段）
3. 配额超限/字段缺失 → 回退不抛异常；当日缓存不二次请求
4. 降级包装：主源 akshare 优先，失败/空 → 麦蕊备源补齐；基础数据仅走主源
注意：每个用例使用独立股票代码，避免当日缓存键串扰。
"""
import pandas as pd
import pytest

from app.core.config import settings
from app.datasource.akshare_source import AkshareSource
from app.datasource.fallback import FallbackSource, get_datasource
from app.datasource.mairui_source import MairuiSource, _parse_change_pct


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _mock_get(monkeypatch, responder):
    """responder(url) -> 返回体（list / str 配额标记 / 抛异常）
    麦蕊走共享 HTTP 会话（http_client._session.get），mock 会话而非 requests.get"""
    from app.datasource.http_client import _session

    monkeypatch.setattr(
        _session, "get",
        lambda url, params=None, headers=None, timeout=None, **kw: responder(url))


# ==================== 数据源工厂（默认关闭零开销） ====================

def test_get_datasource_default_returns_akshare(monkeypatch):
    monkeypatch.setattr(settings, "mairui_enable", False)
    assert isinstance(get_datasource(), AkshareSource)


def test_get_datasource_enabled_returns_fallback(monkeypatch):
    monkeypatch.setattr(settings, "mairui_enable", True)
    monkeypatch.setattr(settings, "mairui_licence", "test-licence")
    assert isinstance(get_datasource(), FallbackSource)


def test_get_datasource_enabled_without_licence_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "mairui_enable", True)
    monkeypatch.setattr(settings, "mairui_licence", "")
    assert isinstance(get_datasource(), AkshareSource)


# ==================== 股东户数解析（/hscp/gdbh） ====================

def test_shareholder_detail_parse(monkeypatch):
    calls = []
    _mock_get(monkeypatch, lambda url: (calls.append(url), _FakeResp(
        [{"jzrq": "2026-07-31", "gdhs": "12345", "bh": "下降3.2%"}]))[1])
    out = MairuiSource().fetch_shareholder_detail("600520")
    assert out["report_date"] == "2026-07-31"
    assert out["holder_count"] == "12345"
    assert out["holder_change_pct"] == -3.2
    assert settings.mairui_licence in calls[0]  # 证书拼在 URL 末尾


def test_shareholder_change_parse_variants():
    assert _parse_change_pct("下降3.2%") == -3.2
    assert _parse_change_pct("上升1.5%") == 1.5
    assert _parse_change_pct("-2.1") == -2.1
    assert _parse_change_pct("减少0.8%") == -0.8
    assert _parse_change_pct(None) is None
    assert _parse_change_pct("暂无变化") is None


def test_shareholder_quota_exceeded_returns_empty(monkeypatch):
    _mock_get(monkeypatch, lambda url: _FakeResp("101"))
    assert MairuiSource().fetch_shareholder_detail("600521") == {}


def test_shareholder_failure_returns_empty(monkeypatch):
    def _boom(url):
        raise ConnectionError("网络不可达")

    _mock_get(monkeypatch, _boom)
    assert MairuiSource().fetch_shareholder_detail("600522") == {}


# ==================== 成交分布 → 标准资金流列（/hsmy/lscjt） ====================

def _lscjt_rows(days=10):
    """模拟最近 N 天成交分布（麦蕊拼音字段）：超大单/大单/小单净流入 + 主力=超大+大（纯算术）"""
    rows = []
    for i in range(days):
        rows.append({"t": f"2026-07-{25 + i:02d}",
                     "cddjlr": 1e7 + i * 1e7, "ddjlr": -5e6 + i * 2e6,
                     "xdjlr": -2e7})
    return rows


def test_fund_flow_builds_standard_columns(monkeypatch):
    _mock_get(monkeypatch, lambda url: _FakeResp(_lscjt_rows()))
    df = MairuiSource().fetch_fund_flow("600530")
    assert list(df.columns) == ["date", "super_large_net", "large_net",
                                "medium_net", "small_net", "main_net_inflow"]
    assert len(df) == 10
    # 主力净流入 = 超大单 + 大单（逐日纯算术）；最后一日 i=9: 超大单=1e7+9*1e7=1e8, 大单=-5e6+9*2e6=1.3e7
    assert df.iloc[-1]["super_large_net"] == pytest.approx(1e8)
    assert df.iloc[-1]["large_net"] == pytest.approx(1.3e7)  # 不得误命中「超大单」列（子串匹配回归）
    assert df.iloc[-1]["main_net_inflow"] == pytest.approx(1e8 + 1.3e7)
    # 近3/5/10日主力累计（与 _enrich_candidate_data 的 tail 求和口径一致）
    assert df["main_net_inflow"].tail(3).sum() == pytest.approx(
        sum((1e8 + 1.3e7, 9e7 + 1.1e7, 8e7 + 9e6)))
    assert df["super_large_net"].iloc[0] == 1e7


def test_fund_flow_unparseable_fields_returns_empty(monkeypatch):
    _mock_get(monkeypatch, lambda url: _FakeResp(
        [{"日期": "2026-08-04", "主力净额": 123.0}]))  # 字段名完全对不上
    assert MairuiSource().fetch_fund_flow("600531").empty


def test_fund_flow_quota_exceeded_returns_empty(monkeypatch):
    _mock_get(monkeypatch, lambda url: _FakeResp("101"))
    assert MairuiSource().fetch_fund_flow("600532").empty


# ==================== 当日缓存（同日同标的不二次请求） ====================

def test_same_day_cache_no_second_request(monkeypatch):
    counter = {"n": 0}

    def _responder(url):
        counter["n"] += 1
        return _FakeResp(_lscjt_rows())

    _mock_get(monkeypatch, _responder)
    src = MairuiSource()
    src.fetch_fund_flow("600540")
    src.fetch_fund_flow("600540")
    assert counter["n"] == 1


# ==================== 降级包装（主源 akshare 优先 → 麦蕊备源补齐） ====================

class _FakePrimary(AkshareSource):
    """测试主源：不触网，只记录被调用；fund_flow_ok=False 模拟主源资金流缺失"""

    def __init__(self, fund_flow_ok=True):
        self.fund_flow_calls = []
        self.shareholder_calls = []
        self.fund_flow_ok = fund_flow_ok

    def fetch_trade_calendar(self):
        return ["2026-08-04"]

    def fetch_fund_flow(self, code):
        self.fund_flow_calls.append(code)
        if not self.fund_flow_ok:
            return pd.DataFrame()
        return pd.DataFrame({"date": ["2026-08-04"], "main_net_inflow": [1.0]})

    def fetch_shareholder_detail(self, code):
        self.shareholder_calls.append(code)
        return {"holder_change_pct": -3.2}


def test_fallback_akshare_ok_skips_mairui(monkeypatch):
    """主源 akshare 有资金流 → 直接用，麦蕊备源不调用（节省配额）"""
    counter = {"n": 0}

    def _responder(url):
        counter["n"] += 1
        return _FakeResp(_lscjt_rows())

    _mock_get(monkeypatch, _responder)
    primary = _FakePrimary()
    wrapper = FallbackSource(primary, MairuiSource())
    df = wrapper.fetch_fund_flow("600560")
    assert not df.empty and primary.fund_flow_calls == ["600560"]
    assert counter["n"] == 0  # 麦蕊零调用


def test_fallback_akshare_empty_then_mairui(monkeypatch):
    """主源 akshare 返回空 → 麦蕊备源补齐（主源优先、备源兜底）"""
    _mock_get(monkeypatch, lambda url: _FakeResp(_lscjt_rows()))
    primary = _FakePrimary(fund_flow_ok=False)
    wrapper = FallbackSource(primary, MairuiSource())
    df = wrapper.fetch_fund_flow("600561")
    assert not df.empty and df.iloc[-1]["super_large_net"] == pytest.approx(1e8)  # 来自麦蕊
    assert primary.fund_flow_calls == ["600561"]


def test_fallback_akshare_fail_then_mairui(monkeypatch):
    """主源 akshare 抛异常 → 麦蕊备源补齐，不中断主链路"""
    _mock_get(monkeypatch, lambda url: _FakeResp(_lscjt_rows()))

    class _Boom(_FakePrimary):
        def fetch_fund_flow(self, code):
            raise ConnectionError("akshare 网络不可达")

    wrapper = FallbackSource(_Boom(), MairuiSource())
    df = wrapper.fetch_fund_flow("600562")
    assert not df.empty  # 麦蕊兜底成功


def test_fallback_both_empty_returns_empty(monkeypatch):
    """双源均无资金流 → 返回空表（上层标注当日不可用，不携带历史/占位值）"""
    _mock_get(monkeypatch, lambda url: _FakeResp([]))  # 麦蕊也为空
    primary = _FakePrimary(fund_flow_ok=False)
    wrapper = FallbackSource(primary, MairuiSource())
    assert wrapper.fetch_fund_flow("600563").empty


def test_fallback_basic_data_only_primary(monkeypatch):
    """基础数据（交易日历）仅走主源，不调用麦蕊（节省配额）"""
    counter = {"n": 0}

    def _responder(url):
        counter["n"] += 1
        return _FakeResp(_lscjt_rows())

    _mock_get(monkeypatch, _responder)
    primary = _FakePrimary()
    wrapper = FallbackSource(primary, MairuiSource())
    assert wrapper.fetch_trade_calendar() == ["2026-08-04"]
    assert counter["n"] == 0  # 麦蕊零调用
