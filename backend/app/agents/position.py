"""
PositionAgent 仓位规划 - LangGraph 节点
【刚性代码逻辑】读取评分、大盘 K 线、资金约束、纯数学指标
【交由模型推理的业务逻辑】分批区间/资金配比/止损止盈/市场强弱（全部在 LLM）
流转：collect_plan_input → llm_plan
"""
import logging
import time

from app.agents.common import ModelLevel, agent_call
from agent_prompts import position_prompt
from app.agents.schemas import PositionOutput
from app.core.config import settings
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.indicator import compute_indicators

logger = logging.getLogger(__name__)


def collect_plan_input(state: StockAgentState) -> StockAgentState:
    """节点1：聚合建仓所需全部原始数据【刚性代码逻辑】"""
    code = state["stock_code"]
    source = get_datasource()
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    # 最新评分（数据库为准，经 repo 网关）
    score_row = repo.get_latest_score(code)

    # 大盘近 60 日
    index_kline = source.fetch_index_daily("sh000001", _days_ago(90), today)

    # 个股近期 K 线与指标
    kline = source.fetch_daily_kline(code, _days_ago(120), today)
    indicators = compute_indicators(kline)

    state["score_result"] = {
        "score": float(score_row.score) if score_row else None,
        "grade": score_row.grade if score_row else None,
        "detail": score_row.detail if score_row else {},
        "risk_list": score_row.risk_list if score_row else [],
    }
    state["basic_info"] = {
        "index_kline": index_kline.tail(60).to_dict(orient="records") if not index_kline.empty else [],
        "indicators": indicators,
        "capital": settings.total_capital,
        "max_single_pct": settings.max_single_position_pct,
        "trade_style": settings.trade_style,
    }
    state["trace"] = [*state.get("trace", []), "建仓数据聚合完成"]
    return state


def llm_plan(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 生成分批建仓方案 + 落库"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    info = state.get("basic_info") or {}

    score_info = (
        f"【标的评分】综合 {state['score_result'].get('score')} 分 "
        f"{state['score_result'].get('grade')} 级\n"
        f"五维明细: {state['score_result'].get('detail')}\n"
        f"风险清单: {state['score_result'].get('risk_list')}"
    )
    index_data = _compact(info.get("index_kline", [])[:60])
    capital_constraints = (
        f"总资金: {info.get('capital')} 元；单标的仓位上限: {info.get('max_single_pct')}%；"
        f"交易风格: {info.get('trade_style')}"
    )
    stock_data = _compact(info.get("indicators", {}))

    output = agent_call(
        agent="position",
        cache_key=f"{code}:{today}",
        system_prompt=position_prompt.SYSTEM_PROMPT,
        user_prompt=position_prompt.build_user_prompt(
            score_info, index_data, capital_constraints, stock_data),
        schema=PositionOutput,
        ttl_seconds=86400,
        model_level=ModelLevel.DEEP,
    )

    plan_id = repo.insert_plan(
        code, name, today, float(output.total_pct),
        [b.model_dump() for b in output.batches],
        float(output.stop_loss), float(output.take_profit), output.rationale,
    )
    state["position_plan"] = {**output.model_dump(), "plan_id": plan_id}
    state["stage"] = "plan_position"
    state["trace"] = [*state.get("trace", []),
                      f"建仓方案完成: 总仓{output.total_pct}% 止损{output.stop_loss} 止盈{output.take_profit}"]
    logger.info("建仓方案完成 %s: plan_id=%s", code, plan_id)
    return state


def _compact(data) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
