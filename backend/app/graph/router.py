"""
图间流转编排：discover→score→position 主链路；monitor 独立轮询；review 独立触发
【刚性代码逻辑】只做流转调度与结果落库，不包含任何市场判断。
"""
import logging
import time

from app.datasource.akshare_source import AkshareSource
from app.graph.graphs import get_graph
from app.graph.state import StockAgentState

logger = logging.getLogger(__name__)


def _new_state(**kwargs) -> StockAgentState:
    base: StockAgentState = {
        "stage": kwargs.get("stage", ""),
        "trace": [],
    }
    base.update(kwargs)
    return base


def run_discover(trade_date: str | None = None) -> StockAgentState:
    """每日潜力股挖掘：硬过滤 → LLM 初选 → 新闻核实 → 最终候选落库"""
    date_key = trade_date or time.strftime("%Y-%m-%d")
    graph = get_graph("discover")
    state = _new_state(trade_date=date_key)
    result = graph.invoke(state)
    logger.info("discover 完成: candidates=%s", len(result.get("candidates") or []))
    return result


def run_score(code: str, stock_name: str = "", trade_date: str | None = None) -> StockAgentState:
    """单股多维打分"""
    graph = get_graph("score")
    state = _new_state(stock_code=code, stock_name=stock_name or code,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_position(code: str, stock_name: str = "", trade_date: str | None = None) -> StockAgentState:
    """单股建仓方案"""
    graph = get_graph("position")
    state = _new_state(stock_code=code, stock_name=stock_name or code,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_monitor(holding_id: int, trade_date: str | None = None) -> StockAgentState:
    """单持仓监控（行情 → LLM 信号 → 去重推送）"""
    from app.db import repo

    holding = repo.get_holding(holding_id)
    if holding is None:
        return _new_state(holding_id=holding_id, error=f"持仓不存在: {holding_id}")
    graph = get_graph("monitor")
    state = _new_state(holding_id=holding_id, stock_code=holding.stock_code,
                       stock_name=holding.stock_name,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_monitor_all(trade_date: str | None = None) -> list[StockAgentState]:
    """批量监控全部持仓"""
    from app.db import repo

    holdings = repo.get_active_holdings()
    results = []
    for h in holdings:
        try:
            results.append(run_monitor(h.id, trade_date))
        except Exception as exc:  # noqa: BLE001 单持仓失败不阻塞其他
            logger.error("监控 %s 失败: %s", h.stock_code, exc)
    logger.info("批量监控完成: %s/%s", len(results), len(holdings))
    return results


def run_sell_decision(holding_id: int, trade_date: str | None = None) -> StockAgentState:
    """单持仓卖出决策（人工按需触发）"""
    from app.db import repo

    holding = repo.get_holding(holding_id)
    if holding is None:
        return _new_state(holding_id=holding_id, error=f"持仓不存在: {holding_id}")
    graph = get_graph("sell")
    state = _new_state(holding_id=holding_id, stock_code=holding.stock_code,
                       stock_name=holding.stock_name,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_review(holding_id: int, trade_date: str | None = None) -> StockAgentState:
    """卖出复盘"""
    graph = get_graph("review")
    state = _new_state(holding_id=holding_id, trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_daily_pipeline(trade_date: str | None = None) -> dict:
    """每日主链路：discover → 对全部候选打分（供面板查看评分）"""
    date_key = trade_date or time.strftime("%Y-%m-%d")
    discover_result = run_discover(date_key)
    scores = []
    for cand in discover_result.get("candidates") or []:
        try:
            res = run_score(cand["stock_code"], cand["stock_name"], date_key)
            scores.append({"code": cand["stock_code"], "score": (res.get("score_result") or {}).get("score")})
        except Exception as exc:  # noqa: BLE001
            logger.error("打分失败 %s: %s", cand["stock_code"], exc)
    return {"candidates": len(discover_result.get("candidates") or []), "scored": len(scores)}
