"""DiscoverAgent 刚性硬过滤测试（客观条件过滤正确性，不测任何主观结论）"""
import pandas as pd

from app.agents.discover import apply_hard_filter


def make_spot():
    return pd.DataFrame({
        "code": ["600001", "600002", "000003", "300004", "600005", "000006", "688007"],
        "name": ["正常股", "ST风险股", "*ST退市股", "停牌股", "低成交股", "正常股B", "正常股C"],
        "price": [10.0, 3.2, 1.5, 12.0, 8.0, 15.0, 9.0],
        "amount": [5e8, 3e8, 2e8, 4e8, 5e7, 6e8, 1e8],
        "change_pct": [1.2, -2.1, 0.5, 0.0, 0.8, 2.0, -0.5],
        "volume_ratio": [1.5, 2.0, 0.8, 0.0, 1.1, 1.8, 0.9],
        "turnover_rate": [3.0, 4.5, 2.0, 0.0, 1.2, 5.0, 2.2],
        "pe_dynamic": [20.0, None, -5.0, 30.0, 15.0, 25.0, 18.0],
        "pb": [2.0, 1.0, 0.8, 3.0, 1.5, 2.5, 1.9],
        "total_mv": [1e10, 2e9, 1e9, 5e9, 3e9, 1e10, 4e9],
        "circ_mv": [8e9, 1.5e9, 8e8, 4e9, 2e9, 8e9, 3e9],
        "pct_change_60d": [10.0, -5.0, -20.0, 0.0, 3.0, 15.0, 8.0],
        "pct_change_ytd": [5.0, -10.0, -30.0, 0.0, 2.0, 8.0, 4.0],
    })


def test_remove_st_and_delisted():
    df = apply_hard_filter(make_spot(), set(), min_amount=1e8, top_n=100)
    names = df["name"].tolist()
    assert "ST风险股" not in names and "*ST退市股" not in names
    assert "退" not in "".join(names)


def test_remove_suspended():
    df = apply_hard_filter(make_spot(), {"300004"}, min_amount=1e8, top_n=100)
    assert "停牌股" not in df["name"].tolist()


def test_remove_low_amount():
    df = apply_hard_filter(make_spot(), set(), min_amount=1e8, top_n=100)
    assert "低成交股" not in df["name"].tolist()  # 5e7 < 1e8
    assert "正常股C" in df["name"].tolist()       # 恰好 1e8 保留


def test_sort_by_amount_desc():
    df = apply_hard_filter(make_spot(), set(), min_amount=1e8, top_n=100)
    amounts = df["amount"].tolist()
    assert amounts == sorted(amounts, reverse=True)


def test_top_n_limit():
    df = apply_hard_filter(make_spot(), set(), min_amount=1e8, top_n=2)
    assert len(df) == 2


def test_empty_input():
    df = apply_hard_filter(pd.DataFrame(), set(), 1e8, 100)
    assert df is not None
