"""indicator.py 纯数学正确性测试（用已知序列验证，不测任何信号结论）"""
import numpy as np
import pandas as pd
import pytest

from app.services.indicator import atr, compute_indicators, macd, rsi, sma


def make_df(closes, highs=None, lows=None):
    n = len(closes)
    highs = highs or [c + 1 for c in closes]
    lows = lows or [c - 1 for c in closes]
    return pd.DataFrame({
        "date": [f"2026-01-{i+1:02d}" for i in range(n)],
        "open": closes, "close": closes, "high": highs, "low": lows,
        "volume": [10000] * n, "amount": [1e7] * n, "change_pct": [0.5] * n,
    })


def test_sma_known_values():
    s = pd.Series(range(1, 11), dtype=float)
    out = sma(s, 3)
    assert out.iloc[2] == pytest.approx(2.0)   # (1+2+3)/3
    assert out.iloc[9] == pytest.approx(9.0)   # (8+9+10)/3
    assert np.isnan(out.iloc[0])


def test_macd_structure():
    s = pd.Series(np.linspace(10, 20, 60), dtype=float)  # 单调上涨
    dif, dea, hist = macd(s)
    assert len(dif) == len(s)
    # 单调上涨时 DIF 应为正
    assert dif.iloc[-1] > 0


def test_rsi_uptrend_near_100():
    s = pd.Series(np.linspace(10, 20, 40), dtype=float)
    r = rsi(s)
    assert r.iloc[-1] > 95  # 连续上涨 RSI 应接近 100


def test_atr_simple():
    # 三根K线高低点恒差 2，ATR 应收敛到 2
    closes = [10.0, 10.5, 11.0, 11.5]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    out = atr(df["high"], df["low"], df["close"], window=3)
    assert out.iloc[-1] == pytest.approx(2.0, abs=0.01)


def test_compute_indicators_complete():
    closes = list(np.linspace(10, 20, 80))
    df = make_df(closes)
    ind = compute_indicators(df)
    assert ind["latest_close"] == pytest.approx(20.0)
    assert ind["ma5"] == pytest.approx(np.mean(closes[-5:]))
    assert ind["ma20"] == pytest.approx(np.mean(closes[-20:]))
    for key in ["ma5", "ma10", "ma20", "ma60", "macd_dif", "macd_dea", "macd_hist",
                "rsi14", "atr14", "high_20d", "low_20d", "high_60d", "low_60d",
                "volume_ratio_5", "change_pct_1d", "change_pct_5d"]:
        assert key in ind, f"缺少指标 {key}"
        assert not isinstance(ind[key], float) or not np.isnan(ind[key]), f"{key} 不应为 NaN"
    assert len(ind["recent_klines"]) == 30
    # make_df 中 high=close+1 / low=close-1
    assert ind["high_20d"] == pytest.approx(np.max(closes[-20:]) + 1)
    assert ind["low_20d"] == pytest.approx(np.min(closes[-20:]) - 1)


def test_compute_indicators_empty():
    assert compute_indicators(pd.DataFrame()) == {}
