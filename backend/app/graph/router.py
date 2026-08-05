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

# 批量打分并行开关：候选 ≥ 5 只自动切换并行模式（大标的池提速），小于阈值保持串行
_PARALLEL_SCORE_MIN = 5
_PARALLEL_SCORE_MAX = 8


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


def run_monitor(holding_id: int, trade_date: str | None = None,
                batch_quotes: dict[str, dict] | None = None) -> StockAgentState:
    """单持仓监控（行情 → LLM 信号 → 去重推送）"""
    from app.db import repo

    holding = repo.get_holding(holding_id)
    if holding is None:
        return _new_state(holding_id=holding_id, error=f"持仓不存在: {holding_id}")
    graph = get_graph("monitor")
    state = _new_state(holding_id=holding_id, stock_code=holding.stock_code,
                       stock_name=holding.stock_name,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"),
                       batch_quotes=batch_quotes)
    return graph.invoke(state)


def run_monitor_all(trade_date: str | None = None) -> list[StockAgentState]:
    """批量监控全部持仓：行情一次批量预取（全持仓统一获取后再过滤），
    避免逐只循环请求触发数据源限流；单持仓手动监控路径不受影响"""
    from app.db import repo
    from app.datasource.fallback import get_datasource

    holdings = repo.get_active_holdings()
    codes = [h.stock_code for h in holdings]
    batch: dict[str, dict] = {}
    try:
        batch = get_datasource().fetch_spot_quotes_batch(codes) if codes else {}
    except Exception as exc:  # noqa: BLE001 批量预取失败不阻塞监控（逐只路径自动兜底）
        logger.warning("批量行情预取失败，监控走逐只取数: %s", exc)
    results = []
    for h in holdings:
        try:
            results.append(run_monitor(h.id, trade_date, batch))
        except Exception as exc:  # noqa: BLE001 单持仓失败不阻塞其他
            logger.error("监控 %s 失败: %s", h.stock_code, exc)
    logger.info("批量监控完成: %s/%s（批量行情命中 %s/%s）",
                len(results), len(holdings), len(batch), len(codes))
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
    """每日主链路：discover → 对全部候选打分（供面板查看评分）

    批量打分自动切换并行模式：候选 ≥5 只时以线程池并发执行（每只独立走
    run_score 图，同一 prompt/schema，结果与串行一致，提速不降质）；
    候选 <5 只保持单 Agent 串行模式。SQLite 已启用 WAL + busy_timeout，并发安全。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    date_key = trade_date or time.strftime("%Y-%m-%d")
    discover_result = run_discover(date_key)
    candidates = discover_result.get("candidates") or []

    def _score_one(cand: dict) -> dict | None:
        try:
            res = run_score(cand["stock_code"], cand["stock_name"], date_key)
            return {"code": cand["stock_code"],
                    "score": (res.get("score_result") or {}).get("score")}
        except Exception as exc:  # noqa: BLE001 单股失败不阻塞其他
            logger.error("打分失败 %s: %s", cand["stock_code"], exc)
            return None

    scores = []
    if len(candidates) >= _PARALLEL_SCORE_MIN:
        with ThreadPoolExecutor(max_workers=min(_PARALLEL_SCORE_MAX, len(candidates))) as pool:
            futures = [pool.submit(_score_one, cand) for cand in candidates]
            for fut in as_completed(futures):
                item = fut.result()
                if item:
                    scores.append(item)
    else:
        for cand in candidates:
            item = _score_one(cand)
            if item:
                scores.append(item)
    logger.info("批量打分完成: %s/%s（并行模式: %s）", len(scores), len(candidates),
                len(candidates) >= _PARALLEL_SCORE_MIN)
    return {"candidates": len(candidates), "scored": len(scores)}
