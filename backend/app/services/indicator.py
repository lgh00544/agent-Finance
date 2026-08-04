"""
技术指标纯数学计算层
【刚性代码逻辑】所有函数只做数值计算并返回原始数值，绝不包含任何
趋势判断、信号识别、买卖建议。判断全部交由 LLM 完成。
输入统一为 pandas DataFrame，列: date/open/close/high/low/volume。
"""
import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """简单移动平均"""
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, window: int) -> pd.Series:
    """指数移动平均"""
    return close.ewm(span=window, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD：返回 (dif, dea, hist)，均为数值序列"""
    dif = ema(close, fast) - ema(close, slow)
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """相对强弱指标（Wilder 平滑）"""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    # 无下跌段 → rs 无穷大 → RSI=100；全平盘（0/0）→ NaN → 50
    rs = avg_gain / avg_loss
    return (100 - 100 / (1 + rs)).fillna(50.0)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """平均真实波幅"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, adjust=False).mean()


def rolling_extreme(series: pd.Series, window: int) -> pd.Series:
    """滚动窗口最大值（窗口不足返回 NaN）"""
    return series.rolling(window=window, min_periods=window).max()


def _last(df: pd.DataFrame, col: str, n: int = 1) -> float:
    vals = df[col].dropna()
    if len(vals) < n:
        return float("nan")
    return float(vals.iloc[-n])


def _last_date(df: pd.DataFrame) -> str:
    vals = df["date"].dropna()
    return str(vals.iloc[-1]) if len(vals) else ""


def compute_indicators(df: pd.DataFrame) -> dict:
    """计算全部技术指标，返回最新值的数值字典（含最近 30 根 K 线原始数据）。

    返回结构（全部为原始数值，零判断）：
    {
      "latest_close", "latest_date", "ma5", "ma10", "ma20", "ma60",
      "macd_dif", "macd_dea", "macd_hist", "rsi14", "atr14",
      "high_20d", "low_20d", "high_60d", "low_60d", "volume_ratio_5",
      "change_pct_1d", "change_pct_5d", "change_pct_20d", "change_pct_60d",
      "recent_klines": [ {date, open, close, high, low, volume, change_pct} x 最近30 ]
    }
    """
    if df is None or df.empty:
        return {}
    df = df.sort_values("date").reset_index(drop=True)
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]

    dif, dea, hist = macd(close)
    rsi14 = rsi(close)
    atr14 = atr(high, low, close)
    vol_ratio = volume / volume.rolling(window=5, min_periods=5).mean()

    change_pct = df["change_pct"] if "change_pct" in df.columns else df["close"].pct_change() * 100

    def last_val(series: pd.Series, n: int) -> float:
        vals = series.dropna()
        if len(vals) < n:
            return float("nan")
        return float(vals.iloc[-1])

    recent = df.tail(30)[["date", "open", "close", "high", "low", "volume"]].copy()
    recent["change_pct"] = change_pct.tail(30).tolist()

    def _pct(n: int) -> float:
        vals = close.dropna()
        if len(vals) <= n:
            return float("nan")
        return float((vals.iloc[-1] / vals.iloc[-1 - n] - 1) * 100)

    return {
        "latest_date": _last_date(df),
        "latest_close": last_val(close, 1),
        "ma5": last_val(sma(close, 5), 1),
        "ma10": last_val(sma(close, 10), 1),
        "ma20": last_val(sma(close, 20), 1),
        "ma60": last_val(sma(close, 60), 1),
        "macd_dif": last_val(dif, 1),
        "macd_dea": last_val(dea, 1),
        "macd_hist": last_val(hist, 1),
        "rsi14": last_val(rsi14, 1),
        "atr14": last_val(atr14, 1),
        "high_20d": last_val(rolling_extreme(high, 20), 1),
        "low_20d": last_val(-rolling_extreme(-low, 20), 1),
        "high_60d": last_val(rolling_extreme(high, 60), 1),
        "low_60d": last_val(-rolling_extreme(-low, 60), 1),
        "volume_ratio_5": last_val(vol_ratio, 1),
        "change_pct_1d": _pct(1),
        "change_pct_5d": _pct(5),
        "change_pct_20d": _pct(20),
        "change_pct_60d": _pct(60),
        "recent_klines": recent.where(pd.notna(recent), None).to_dict(orient="records"),
    }
