from app.services.signal_registry import evaluate, register


@register("s06", "macd_golden_daily", "动量", "buy", {"fast": 12, "slow": 26, "signal": 9})
def s06_macd_golden_daily(features, kline, code):
    """DIF 上穿 DEA（日线金叉）"""
    return evaluate(features, kline, ("macd_dif", "macd_dea", "prev_macd_dif", "prev_macd_dea"),
                    lambda f: f["prev_macd_dif"] <= f["prev_macd_dea"] and f["macd_dif"] > f["macd_dea"])


@register("s07", "macd_dead_daily", "动量", "sell", {"fast": 12, "slow": 26, "signal": 9})
def s07_macd_dead_daily(features, kline, code):
    """DIF 下穿 DEA（日线死叉）"""
    return evaluate(features, kline, ("macd_dif", "macd_dea", "prev_macd_dif", "prev_macd_dea"),
                    lambda f: f["prev_macd_dif"] >= f["prev_macd_dea"] and f["macd_dif"] < f["macd_dea"])


@register("s08", "rsi_recover_50", "动量", "buy", {"window": 14, "low": 30, "mid": 50})
def s08_rsi_recover_50(features, kline, code):
    """前值 < 30 且当值上穿 50（超卖修复）"""
    return evaluate(features, kline, ("rsi14", "prev_rsi14"),
                    lambda f: f["prev_rsi14"] < 30 and f["rsi14"] > 50)


@register("s09", "rsi_fall_50", "动量", "sell", {"window": 14, "high": 70, "mid": 50})
def s09_rsi_fall_50(features, kline, code):
    """前值 > 70 且当值下穿 50（超买回落）"""
    return evaluate(features, kline, ("rsi14", "prev_rsi14"),
                    lambda f: f["prev_rsi14"] > 70 and f["rsi14"] < 50)


@register("s10", "ma5_cross_ma20", "动量", "buy", {"fast": 5, "slow": 20})
def s10_ma5_cross_ma20(features, kline, code):
    """MA5 上穿 MA20"""
    return evaluate(features, kline, ("ma5", "ma20", "prev_ma5", "prev_ma20"),
                    lambda f: f["prev_ma5"] <= f["prev_ma20"] and f["ma5"] > f["ma20"])


@register("s11", "ma20_cross_ma60", "动量", "buy", {"fast": 20, "slow": 60})
def s11_ma20_cross_ma60(features, kline, code):
    """MA20 上穿 MA60"""
    return evaluate(features, kline, ("ma20", "ma60", "prev_ma20", "prev_ma60"),
                    lambda f: f["prev_ma20"] <= f["prev_ma60"] and f["ma20"] > f["ma60"])
