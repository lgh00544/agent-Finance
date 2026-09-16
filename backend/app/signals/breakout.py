from app.services.signal_registry import evaluate, register


@register("s12", "breakout_20d", "突破", "buy", {"window": 20})
def s12_breakout_20d(features, kline, code):
    """收盘突破 20 日高点（唐奇安上轨）"""
    return evaluate(features, kline, ("latest_close", "donchian_upper_20"),
                    lambda f: f["latest_close"] > f["donchian_upper_20"])


@register("s13", "breakdown_20d", "突破", "sell", {"window": 20})
def s13_breakdown_20d(features, kline, code):
    """收盘跌破 20 日低点（唐奇安下轨）"""
    return evaluate(features, kline, ("latest_close", "donchian_lower_20"),
                    lambda f: f["latest_close"] < f["donchian_lower_20"])


@register("s14", "breakout_55d", "突破", "buy", {"window": 55})
def s14_breakout_55d(features, kline, code):
    """收盘突破 55 日高点（海龟系统）"""
    return evaluate(features, kline, ("latest_close", "donchian_upper_55"),
                    lambda f: f["latest_close"] > f["donchian_upper_55"])


@register("s15", "breakdown_55d", "突破", "sell", {"window": 55})
def s15_breakdown_55d(features, kline, code):
    """收盘跌破 55 日低点（海龟系统）"""
    return evaluate(features, kline, ("latest_close", "donchian_lower_55"),
                    lambda f: f["latest_close"] < f["donchian_lower_55"])
