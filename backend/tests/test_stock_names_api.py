"""GET /api/stocks/names 只读批量补名接口（不触网：数据源 mock）：
1. 正常返回 {code: name}；name 为空或等于代码的项丢弃（缺省键）
2. 空 codes / 非 6 位代码过滤 / 上限 50
3. 数据源异常 → 返回 {} 不报错（前端静默降级为「名称待补」）
"""
import pytest

from app.api import routes


class _FakeDS:
    def __init__(self, quotes):
        self._quotes = quotes

    def fetch_spot_quotes_batch(self, codes):
        return self._quotes


def _patch_ds(monkeypatch, quotes):
    import app.datasource.fallback as fallback

    monkeypatch.setattr(fallback, "get_datasource", lambda: _FakeDS(quotes))


def test_stock_names_ok(monkeypatch):
    """正常补名：名=代码/空名的项丢弃"""
    _patch_ds(monkeypatch, {
        "600519": {"code": "600519", "name": "贵州茅台", "price": None},
        "000001": {"code": "000001", "name": "", "price": None},
        "999999": {"code": "999999", "name": "999999", "price": None},
    })
    assert routes.stock_names("600519,000001,999999") == {"600519": "贵州茅台"}


def test_stock_names_empty_codes():
    assert routes.stock_names("") == {}
    assert routes.stock_names(",,,") == {}


def test_stock_names_filters_bad_codes(monkeypatch):
    """非 6 位代码过滤，不触发数据源"""
    import app.datasource.fallback as fallback

    def _boom():
        raise AssertionError("无有效代码不应调用数据源")

    monkeypatch.setattr(fallback, "get_datasource", lambda: _boom())
    assert routes.stock_names("abc,6005,12345678901") == {}


def test_stock_names_exception_returns_empty(monkeypatch):
    """数据源异常（断路器/限流）→ 返回 {} 不报错"""

    class _Boom:
        def fetch_spot_quotes_batch(self, codes):
            raise ConnectionError("数据源不可达")

    import app.datasource.fallback as fallback

    monkeypatch.setattr(fallback, "get_datasource", lambda: _Boom())
    assert routes.stock_names("600519") == {}


def test_stock_names_dedupe_and_limit(monkeypatch):
    """去重 + 超 50 个只取前 50：数据源收到的 codes 数应 ≤ 50 且无重复"""
    codes = "600001,600001," + ",".join(f"60{i:04d}" for i in range(55))
    import app.datasource.fallback as fallback

    seen = {}

    class _Rec:
        def fetch_spot_quotes_batch(self, codes):
            seen["codes"] = codes
            return {}

    monkeypatch.setattr(fallback, "get_datasource", lambda: _Rec())
    routes.stock_names(codes)
    assert len(seen["codes"]) <= 50
    assert len(seen["codes"]) == len(set(seen["codes"]))
