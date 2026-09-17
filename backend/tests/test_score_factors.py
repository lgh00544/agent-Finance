import pandas as pd
import pytest

from app.factors import factor_registry
from app.factors.data_adapter import DataAdapter, latest


def _adapter(**overrides):
    kline = [{"close": 10 + i * 0.1, "volume": 100 + i, "date": f"2026-08-{i + 1:02d}"} for i in range(25)]
    base = {
        "kline": kline,
        "indicators": {"latest_close": 12.4, "ma20": 12, "volume_ratio_5": 1.2,
                       "macd_dif": 1, "macd_dea": 0.5, "wyckoff_phase": "吸筹"},
        "financial": [{"pe": 20, "pb": 2, "ps": 4, "profit_yoy": 10, "roe": 18,
                       "gross_margin": 40, "ocf": 20, "revenue": 100, "debt_ratio": 30}],
        "fund_flow": [{"main_net_inflow": 5, "amount": 100}],
        "news": [{"title": "政策支持行业业绩预增", "content": ""}],
        "sectors": [{"board_name": "测试行业", "sector_5d": 5, "sector_fund": 3,
                     "rotation_pos": "启动", "sector_crowd": 40}],
        "quote": {"pe_dynamic": 20, "pb": 2, "ps": 4, "amount": 100,
                  "north_flow_5d": 1, "dragon_tiger_count_30d": 2,
                  "margin_balance_change_5d": 3},
        "hot_money": {"direction": "买入", "level": "一线"},
        "extra": {"industry": "测试行业", "market_5d": 2, "wyckoff_phase": "吸筹",
                  "quantiles": {f"f{i:02d}": 60 for i in (1, 3, 4, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23)}},
    }
    base.update(overrides)
    return DataAdapter(code="600000", **base)


@pytest.mark.parametrize("definition", factor_registry.list_active())
def test_all_25_factors_normal(definition):
    result = definition.func(_adapter(), "600000")
    assert result.reason
    assert result.value is not None


def test_registry_has_25_active_factors():
    assert len(factor_registry.list_active()) == 25
    assert factor_registry.get("f01") is not None


def test_f01_extreme_is_capped():
    result = factor_registry.get("f01").func(_adapter(indicators={"latest_close": 100, "ma20": 1}), "600000")
    assert result.value == 0.5


def test_adapter_source_exception_is_missing():
    class Broken:
        def fetch_daily_kline(self, *args):
            raise RuntimeError("source down")
    result = factor_registry.get("f03").func(DataAdapter(source=Broken(), code="600000"), "600000")
    assert result.value is None and result.reason.startswith("data_missing:")


def test_all_missing_still_returns_results():
    data = DataAdapter(code="600000")
    results = [f.func(data, "600000") for f in factor_registry.list_active()]
    assert len(results) == 25 and all(r.value is None or r.reason for r in results)


def test_single_missing_has_explicit_reason():
    result = factor_registry.get("f13").func(_adapter(fund_flow=[]), "600000")
    assert result.value is None and result.reason == "data_missing:main_inflow_or_amount"


def test_quantile_is_derived_from_peer_values():
    result = factor_registry.get("f09").func(
        _adapter(extra={"quantile_values": {"f09": [10, 20, 30]}}), "600000")
    assert result.quantile == pytest.approx(66.67)


def test_latest_picks_newest_by_date_not_position():
    """「最新一期」按日期字段最大值判定：降序（数据源实际）/升序/无日期字段三种输入。"""
    older = {"report_date": "2001-03-31", "roe": None}
    newer = {"report_date": "2026-06-30", "roe": 4.69}
    assert latest([newer, older])["roe"] == 4.69     # 降序：数据源实际序，不可取 [-1]
    assert latest([older, newer])["roe"] == 4.69      # 升序
    assert latest([]) == {}
    # 资金流用 date 字段，同样是「最新在前」
    assert latest([{"date": "2026-04-17", "main_net_inflow": 1},
                   {"date": "2026-04-30", "main_net_inflow": 2}])["main_net_inflow"] == 2
    # 无可用日期字段（如 sector_rows 板块快照）→ 保留原行为 items[-1]
    assert latest([{"board_name": "甲"}, {"board_name": "乙"}])["board_name"] == "乙"


def test_data_adapter_accepts_dataframes():
    result = factor_registry.get("f01").func(
        _adapter(kline=pd.DataFrame(_adapter().kline_rows())), "600000")
    assert result.value is not None
