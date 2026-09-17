from app.factors.data_adapter import DataAdapter, factor
from app.services.factor_registry import register


@register
def f18_roe(data: DataAdapter, code: str):
    value = data.number("roe")
    return factor(value, "ok" if value is not None else "data_missing:roe", data.quantile("f18", value) if value is not None else None)


@register
def f19_gross_margin(data: DataAdapter, code: str):
    value = data.number("gross_margin")
    return factor(value, "ok" if value is not None else "data_missing:gross_margin", data.quantile("f19", value) if value is not None else None)


@register
def f20_ocf_to_revenue(data: DataAdapter, code: str):
    value = data.number("ocf_to_revenue")
    if value is None:
        ocf, revenue = data.number("operating_cash_flow", "ocf", "net_operate_cash_flow"), data.number("revenue", "operating_revenue")
        value = ocf / revenue if ocf is not None and revenue not in (None, 0) else None
    return factor(value, "ok" if value is not None else "data_missing:ocf_or_revenue", data.quantile("f20", value) if value is not None else None)


@register
def f21_debt_ratio(data: DataAdapter, code: str):
    value = data.number("debt_ratio")
    return factor(value, "ok" if value is not None else "data_missing:debt_ratio", data.quantile("f21", value) if value is not None else None)
