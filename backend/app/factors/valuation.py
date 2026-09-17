from app.factors.data_adapter import DataAdapter, factor
from app.services.factor_registry import register


def _valuation(data: DataAdapter, fid: str, keys: tuple[str, ...], missing: str):
    value = data.number(*keys)
    if value is None:
        return factor(None, f"data_missing:{missing}")
    return factor(value, quantile=data.quantile(fid, value))


@register
def f09_pe_quantile(data: DataAdapter, code: str):
    return _valuation(data, "f09", ("pe_dynamic", "pe", "市盈率-动态"), "pe")


@register
def f10_pb_quantile(data: DataAdapter, code: str):
    return _valuation(data, "f10", ("pb", "市净率"), "pb")


@register
def f11_peg(data: DataAdapter, code: str):
    pe, growth = data.number("pe_dynamic", "pe"), data.number("growth_rate_pct", "profit_yoy", "revenue_yoy")
    if pe is None or growth in (None, 0):
        return factor(None, "data_missing:pe_or_growth")
    value = pe / growth
    return factor(value, quantile=data.quantile("f11", value))


@register
def f12_ps_quantile(data: DataAdapter, code: str):
    return _valuation(data, "f12", ("ps", "市销率"), "ps")
