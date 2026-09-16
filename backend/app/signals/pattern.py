from app.indicators.candle_patterns import (
    is_bearish_engulfing, is_bullish_engulfing, is_hammer, is_morning_star, is_shooting_star,
)
from app.services.signal_registry import SignalResult, ready, register

_OHLC = ("open", "close", "high", "low")


def _pattern(features, kline, detect) -> SignalResult:
    """形态信号统一入口：数据闸门 → OHLC 列检查 → K 线形态判定。"""
    gate = ready(features, kline)
    if gate is not None:
        return gate
    if not set(_OHLC).issubset(kline.columns):
        return SignalResult(hit=False, reason="data_missing:ohlc")
    hit = bool(detect(kline))
    return SignalResult(hit=hit, reason="ok" if hit else "not_triggered")


@register("s16", "cdl_hammer", "形态", "buy", {})
def s16_cdl_hammer(features, kline, code):
    """锤子线：下影 ≥ 2×实体 且 上影 ≤ 实体 且 实体 < 全幅 1/3"""
    return _pattern(features, kline, is_hammer)


@register("s17", "cdl_bullish_engulf", "形态", "buy", {})
def s17_cdl_bullish_engulf(features, kline, code):
    """看涨吞没：前阴后阳，后实体完全包住前实体"""
    return _pattern(features, kline, is_bullish_engulfing)


@register("s18", "cdl_morning_star", "形态", "buy", {})
def s18_cdl_morning_star(features, kline, code):
    """早晨之星：长阴 + 小实体 + 长阳收回首根实体过半"""
    return _pattern(features, kline, is_morning_star)


@register("s19", "cdl_shooting_star", "形态", "sell", {})
def s19_cdl_shooting_star(features, kline, code):
    """射击之星：上影 ≥ 2×实体 且 下影 ≤ 实体"""
    return _pattern(features, kline, is_shooting_star)


@register("s20", "cdl_bearish_engulf", "形态", "sell", {})
def s20_cdl_bearish_engulf(features, kline, code):
    """看跌吞没：前阳后阴，后实体完全包住前实体"""
    return _pattern(features, kline, is_bearish_engulfing)
