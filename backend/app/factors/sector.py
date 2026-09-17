from app.factors.data_adapter import DataAdapter, factor, num
from app.services.factor_registry import register


def _sector_value(data: DataAdapter, *keys):
    row = data.sector()
    for key in keys:
        value = num(row.get(key)) if isinstance(row, dict) else None
        if value is not None:
            return value
    return data.number(*keys)


@register
def f22_sector_strength(data: DataAdapter, code: str):
    sector_5d = _sector_value(data, "sector_5d", "change_pct_5d")
    market_5d = data.number("market_5d", "market_change_5d")
    if sector_5d is None or market_5d in (None, 0):
        return factor(None, "data_missing:sector_or_market_5d")
    value = sector_5d / market_5d
    return factor(value, quantile=data.quantile("f22", value))


@register
def f23_sector_fund(data: DataAdapter, code: str):
    value = _sector_value(data, "sector_fund", "sector_main_inflow", "main_net_inflow")
    return factor(value, "ok" if value is not None else "data_missing:sector_fund", data.quantile("f23", value) if value is not None else None)


@register
def f24_rotation_pos(data: DataAdapter, code: str):
    row = data.sector()
    value = row.get("rotation_pos") if row else data.find("rotation_pos")
    return factor(value, "ok" if value is not None else "data_missing:rotation_pos")


@register
def f25_sector_crowd(data: DataAdapter, code: str):
    row = data.sector()
    value = num(row.get("sector_crowd", row.get("crowd"))) if row else data.number("sector_crowd", "crowd")
    return factor(value, "ok" if value is not None else "data_missing:sector_crowd")
