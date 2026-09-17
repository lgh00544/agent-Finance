from app.factors.data_adapter import DataAdapter, factor, num
from app.services.factor_registry import register


@register
def f01_ma20_deviate(data: DataAdapter, code: str):
    close = num(data.indicators.get("latest_close"))
    ma20 = num(data.indicators.get("ma20"))
    if close is None or ma20 in (None, 0):
        return factor(None, "data_missing:close_or_ma20")
    value = max(-0.5, min(0.5, (close - ma20) / ma20))
    return factor(value, quantile=data.quantile("f01", value))


@register
def f02_macd_state(data: DataAdapter, code: str):
    dif, dea = num(data.indicators.get("macd_dif")), num(data.indicators.get("macd_dea"))
    if dif is None or dea is None:
        return factor(None, "data_missing:macd")
    return factor("金叉" if dif > dea else "死叉" if dif < dea else "中性")


@register
def f03_20d_return(data: DataAdapter, code: str):
    values = [num(r.get("close")) for r in data.kline_rows()]
    values = [v for v in values if v is not None]
    if len(values) <= 20 or values[-21] == 0:
        return factor(None, "data_missing:close_20d")
    value = values[-1] / values[-21] - 1
    return factor(value, quantile=data.quantile("f03", value))


@register
def f04_volume_ratio(data: DataAdapter, code: str):
    value = num(data.indicators.get("volume_ratio_5"))
    if value is None:
        volumes = [num(r.get("volume")) for r in data.kline_rows()]
        volumes = [v for v in volumes if v is not None]
        value = volumes[-1] / sum(volumes[-5:]) * 5 if len(volumes) >= 5 and sum(volumes[-5:]) else None
    return factor(value, "ok" if value is not None else "data_missing:volume", data.quantile("f04", value) if value is not None else None)


@register
def f05_wyckoff_phase(data: DataAdapter, code: str):
    value = data.find("wyckoff_phase", "stock_type")
    return factor(value, "ok" if value is not None else "data_missing:wyckoff_phase")
