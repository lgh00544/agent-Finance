from app.factors.data_adapter import DataAdapter, factor, num
from app.services.factor_registry import register


@register
def f13_main_inflow_pct(data: DataAdapter, code: str):
    inflow = data.number("main_net_inflow", "main_inflow")
    amount = data.number("amount", "turnover_amount", "成交额")
    if inflow is None or amount in (None, 0):
        return factor(None, "data_missing:main_inflow_or_amount")
    value = inflow / amount
    return factor(value, quantile=data.quantile("f13", value))


@register
def f14_north_flow(data: DataAdapter, code: str):
    value = data.number("north_flow_5d", "north_flow")
    return factor(value, "ok" if value is not None else "data_missing:north_flow")


@register
def f15_hot_money_seat(data: DataAdapter, code: str):
    hot = data.hot_money()
    if not hot:
        return factor(None, "data_missing:hot_money_seat")
    direction = hot.get("direction") or hot.get("net_direction")
    if direction is None:
        net = num(hot.get("lhb_1d_net_buy"))
        direction = "买入" if net is not None and net > 0 else "卖出" if net is not None else None
    level = hot.get("level") or hot.get("tier") or hot.get("profile_level")
    value = f"{direction}:{level}" if direction is not None and level else direction
    return factor(value, "ok" if value is not None else "data_missing:hot_money_direction")


@register
def f16_dragon_tiger(data: DataAdapter, code: str):
    value = data.number("dragon_tiger_count_30d", "lhb_count_30d", "count_30d")
    return factor(value, "ok" if value is not None else "data_missing:dragon_tiger_count")


@register
def f17_margin_balance(data: DataAdapter, code: str):
    value = data.number("margin_balance_change_5d", "margin_change_5d", "margin_balance")
    return factor(value, "ok" if value is not None else "data_missing:margin_balance")
