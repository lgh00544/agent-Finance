"""系统地图登记用的模拟执行 Agent 入口。

实际成交规则在 services.paper_execution；本入口只做状态编排，不包含市场判断。
"""
from app.services import paper_execution


def run(state: dict) -> dict:
    account_id = state.get("paper_account_id") or state.get("account_id")
    trade_date = state.get("trade_date")
    if not account_id or not trade_date:
        return {**state, "paper_error": "paper_account_id/trade_date 缺失"}
    result = paper_execution.run(account_id, trade_date,
                                 facts=state.get("paper_facts"),
                                 requested_sides=state.get("requested_sides"))
    return {**state, "paper_execution_result": result}
