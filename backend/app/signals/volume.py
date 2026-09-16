from app.services.signal_registry import evaluate, register


@register("s21", "volume_breakout", "量价", "buy", {"window": 20, "ratio": 1.5})
def s21_volume_breakout(features, kline, code):
    """创 20 日新高 且 成交量 ≥ 5 日均量 × 1.5"""
    return evaluate(features, kline, ("latest_close", "donchian_upper_20", "volume_ratio_5"),
                    lambda f: f["latest_close"] > f["donchian_upper_20"] and f["volume_ratio_5"] >= 1.5)


@register("s22", "shrink_pullback", "量价", "sell", {"ratio": 0.7})
def s22_shrink_pullback(features, kline, code):
    """当日下跌 且 成交量 ≤ 5 日均量 × 0.7（缩量回调）"""
    return evaluate(features, kline, ("change_pct", "volume_ratio_5"),
                    lambda f: f["change_pct"] < 0 and f["volume_ratio_5"] <= 0.7)
