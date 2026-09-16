import pandas as pd


def _last_rows(df: pd.DataFrame, n: int) -> pd.DataFrame | None:
    if df is None or len(df) < n:
        return None
    cols = ["open", "close", "high", "low"]
    if not set(cols).issubset(df.columns):
        return None
    out = df[cols].tail(n).apply(pd.to_numeric, errors="coerce")
    return None if out.isna().any().any() else out


def is_hammer(df: pd.DataFrame) -> bool:
    rows = _last_rows(df, 1)
    if rows is None:
        return False
    o, c, h, l = rows.iloc[-1]
    body, full = abs(c - o), h - l
    return full > 0 and l <= min(o, c) - 2 * body and h - max(o, c) <= body and body < full / 3


def is_bullish_engulfing(df: pd.DataFrame) -> bool:
    rows = _last_rows(df, 2)
    if rows is None:
        return False
    prev, cur = rows.iloc[-2], rows.iloc[-1]
    return prev.close < prev.open and cur.close > cur.open and cur.open <= prev.close and cur.close >= prev.open


def is_morning_star(df: pd.DataFrame) -> bool:
    rows = _last_rows(df, 3)
    if rows is None:
        return False
    first, middle, last = rows.iloc[-3], rows.iloc[-2], rows.iloc[-1]
    first_body, middle_body = abs(first.close - first.open), abs(middle.close - middle.open)
    return (first.close < first.open and first_body > middle_body * 2 and middle_body <= (first.high - first.low) / 3
            and last.close > last.open and last.close >= (first.open + first.close) / 2)


def is_shooting_star(df: pd.DataFrame) -> bool:
    rows = _last_rows(df, 1)
    if rows is None:
        return False
    o, c, h, l = rows.iloc[-1]
    body = abs(c - o)
    return h - max(o, c) >= 2 * body and min(o, c) - l <= body


def is_bearish_engulfing(df: pd.DataFrame) -> bool:
    rows = _last_rows(df, 2)
    if rows is None:
        return False
    prev, cur = rows.iloc[-2], rows.iloc[-1]
    return prev.close > prev.open and cur.close < cur.open and cur.open >= prev.close and cur.close <= prev.open
