from app.services.signal_registry import evaluate, register


@register("s01", "boll_pctb_low", "位置", "buy", {"window": 20, "std": 2.0})
def s01_boll_pctb_low(features, kline, code):
    """布林 %B < 0.05（下轨超卖区）"""
    return evaluate(features, kline, "boll_pctb", lambda f: f["boll_pctb"] < 0.05)


@register("s02", "boll_pctb_high", "位置", "sell", {"window": 20, "std": 2.0})
def s02_boll_pctb_high(features, kline, code):
    """布林 %B > 0.95（上轨超买区）"""
    return evaluate(features, kline, "boll_pctb", lambda f: f["boll_pctb"] > 0.95)


@register("s03", "near_52w_high", "位置", "buy", {"window": 250, "ratio": 0.95})
def s03_near_52w_high(features, kline, code):
    """收盘 ≥ 近 250 日最高价 × 0.95"""
    return evaluate(features, kline, ("latest_close", "high_250d"),
                    lambda f: f["latest_close"] >= f["high_250d"] * 0.95)


@register("s04", "near_52w_low", "位置", "buy", {"window": 250, "ratio": 1.05})
def s04_near_52w_low(features, kline, code):
    """收盘 ≤ 近 250 日最低价 × 1.05"""
    return evaluate(features, kline, ("latest_close", "low_250d"),
                    lambda f: f["latest_close"] <= f["low_250d"] * 1.05)


@register("s05", "stoch_oversold_cross", "位置", "buy", {"n": 9, "k_period": 3, "d_period": 3})
def s05_stoch_oversold_cross(features, kline, code):
    """K < 20 且 K 上穿 D（超卖金叉）"""
    return evaluate(features, kline, ("kdj_k", "kdj_d", "prev_kdj_k", "prev_kdj_d"),
                    lambda f: f["kdj_k"] < 20 and f["prev_kdj_k"] <= f["prev_kdj_d"]
                    and f["kdj_k"] > f["kdj_d"])
