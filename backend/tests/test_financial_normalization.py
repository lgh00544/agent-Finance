"""财务数据源标准化：字段别名、百分数和最新报告排序。"""

import pandas as pd

from app.datasource import akshare_source
from app.datasource.akshare_source import (AkshareSource, _FINANCIAL_SINA_COLS,
                                          _FINANCIAL_THS_COLS, _normalize_financial)


def test_ths_financial_aliases_numeric_and_newest_first():
    raw = pd.DataFrame([
        {"报告期": "2001-09-30", "营业总收入同比增长率": "2.0%",
         "净利润同比增长率": "-1.0%", "净资产收益率": "0.25%",
         "资产负债率": "63.79%", "销售毛利率": "8.65%"},
        {"报告期": "2026-06-30", "营业总收入同比增长率": "7.92%",
         "净利润同比增长率": "113.11%", "净资产收益率": "3.41%",
         "资产负债率": "62.41%", "销售毛利率": "17.27%"},
    ])

    out = _normalize_financial(raw, _FINANCIAL_THS_COLS)

    assert list(out["report_date"]) == ["2026-06-30", "2001-09-30"]
    assert out.iloc[0]["profit_yoy"] == 113.11
    assert out.iloc[0]["roe"] == 3.41
    assert out.iloc[0]["debt_ratio"] == 62.41


def test_financial_fetch_uses_versioned_cache_and_normalizer(monkeypatch):
    source = AkshareSource()
    captured = {}

    def fake_fetch(scope, func_name, call, ttl_seconds, fallback=None, normalize=None,
                   **kwargs):
        captured["scope"] = scope
        captured["rows"] = normalize(pd.DataFrame([
            {"报告期": "2026-03-31", "净资产收益率": "2.0%"},
            {"报告期": "2026-06-30", "净资产收益率": "3.0%"},
        ]))
        return captured["rows"]

    monkeypatch.setattr(source, "_fetch", fake_fetch)
    result = source.fetch_financial("600150")

    assert captured["scope"] == "fin:v2:600150"
    assert list(result["report_date"]) == ["2026-06-30", "2026-03-31"]
    assert list(result["roe"]) == [3.0, 2.0]


def test_sina_numeric_values_and_missing_markers_remain_compatible():
    raw = pd.DataFrame([
        {"日期": "2026-03-31", "净资产收益率(%)": 2.5,
         "净利润增长率(%)": "--", "销售毛利率(%)": False},
        {"日期": "2026-06-30", "净资产收益率(%)": "3.0%",
         "净利润增长率(%)": "-2.5%", "销售毛利率(%)": 20},
    ])

    out = _normalize_financial(raw, _FINANCIAL_SINA_COLS)

    assert list(out["roe"]) == [3.0, 2.5]
    assert out.iloc[0]["profit_yoy"] == -2.5
    assert out.to_dict(orient="records")[1]["profit_yoy"] is None
    assert out.to_dict(orient="records")[1]["gross_margin"] is None


def test_financial_fallback_calls_sina_with_symbol_kwarg(monkeypatch):
    """主路径（同花顺）失败降级新浪须用 symbol=：写成 stock= 会 TypeError（akshare 1.18.81 签名）。"""
    source = AkshareSource()
    captured, seen = {}, {}

    def fake_fetch(scope, func_name, call, ttl_seconds, fallback=None, normalize=None, **kwargs):
        captured["fallback"] = fallback
        return pd.DataFrame()

    def fake_sina(symbol="600004", start_year="1900"):  # 与 akshare 实际签名一致
        seen["symbol"] = symbol
        return pd.DataFrame([{"日期": "2026-06-30", "净资产收益率(%)": "3.0%",
                              "净利润增长率(%)": "5.0%"}])

    monkeypatch.setattr(source, "_fetch", fake_fetch)
    monkeypatch.setattr(akshare_source.ak, "stock_financial_analysis_indicator", fake_sina)

    source.fetch_financial("600150")
    result = captured["fallback"]()

    assert seen["symbol"] == "600150"
    assert not result.empty and "净资产收益率(%)" in result.columns
