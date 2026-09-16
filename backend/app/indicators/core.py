"""信号快照聚合层：只 import 指标库函数并组装最新/前值，不定义任何指标算法。"""
from typing import Any

import pandas as pd

from app.services.indicator import (
    atr, boll, compute_indicators, donchian, kdj, macd, rolling_extreme, rsi, sma,
)

_OHLCV = ("close", "high", "low", "volume")

def _last_two(series: pd.Series | None) -> tuple[float | None, float | None]:
    """返回最后两个有效值 (latest, prev)，不足为 None（NaN 安全，快于 dropna）。"""
    arr = series.to_numpy(dtype="float64", na_value=float("nan")) if series is not None else ()
    ok = [i for i, value in enumerate(arr) if value == value]
    return (float(arr[ok[-1]]) if ok else None), (float(arr[ok[-2]]) if len(ok) > 1 else None)

def compute_signal_snapshot(kline_df: pd.DataFrame) -> dict[str, Any]:
    """信号快照：库内 compute_indicators() 字段直接取用 + 新增指标 latest/prev；纯函数、不抛异常。"""
    if kline_df is None or kline_df.empty or not set(_OHLCV).issubset(kline_df.columns):
        return {}
    df = kline_df.sort_values("date") if "date" in kline_df.columns else kline_df.copy()
    df = df.assign(**{c: pd.to_numeric(df[c], errors="coerce") for c in _OHLCV}).dropna(
        subset=list(_OHLCV)).reset_index(drop=True)
    if not (base := compute_indicators(df)):
        return {}
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
    dif, dea, hist = macd(close)
    middle, upper, lower, pctb = boll(close)
    k, d, j = kdj(high, low, close)
    (up20, low20), (up55, low55) = donchian(high, low, 20), donchian(high, low, 55)
    series_map = {
        "ma5": sma(close, 5), "ma10": sma(close, 10), "ma20": sma(close, 20), "ma60": sma(close, 60),
        "macd_dif": dif, "macd_dea": dea, "macd_hist": hist, "rsi14": rsi(close),
        "atr14": atr(high, low, close), "volume_ratio_5": volume / sma(volume, 5),
        "change_pct": df["change_pct"] if "change_pct" in df.columns else None,
        "boll_middle": middle, "boll_upper": upper, "boll_lower": lower, "boll_pctb": pctb,
        "kdj_k": k, "kdj_d": d, "kdj_j": j,
        "donchian_upper_20": up20, "donchian_lower_20": low20,
        "donchian_upper_55": up55, "donchian_lower_55": low55,
        "high_250d": rolling_extreme(high, 250), "low_250d": -rolling_extreme(-low, 250),
    }
    out: dict[str, Any] = dict(base)
    for name, series in series_map.items():
        latest, prev = _last_two(series)
        out.setdefault(name, latest)
        out[f"prev_{name}"] = prev
    if out.get("change_pct") is None:
        out["change_pct"] = base.get("change_pct_1d")
    return out
