"""
PositionAgent 仓位规划 - LangGraph 节点
【刚性代码逻辑】读取评分、大盘 K 线、资金约束、纯数学指标
【交由模型推理的业务逻辑】分批区间/资金配比/止损止盈/市场强弱（全部在 LLM）
流转：collect_plan_input → llm_plan
"""
from app.core import clock
import hashlib
import json
import logging
import time

from app.agents.common import ModelLevel, agent_call
from agent_prompts import position_prompt
from app.agents.schemas import PositionOutput
from app.core.config import (
    C1_CONCENTRATION_CAP, C2_INTRADAY_DRAWDOWN_PCT, C2_TOTAL_POSITION_CAP, C3_STOP_FACTOR,
    GRADE_POSITION_CAP, settings,
)
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.indicator import compute_indicators
from app.services import plan_quant

logger = logging.getLogger(__name__)


def collect_plan_input(state: StockAgentState) -> StockAgentState:
    """节点1：聚合建仓所需全部原始数据【刚性代码逻辑】"""
    code = state["stock_code"]
    source = get_datasource()
    today = state.get("trade_date") or clock.today()

    # 最新评分（数据库为准，经 repo 网关）；S-7：只允许使用不晚于 trade_date 且未过期的
    # 评分（as_of=trade_date），超期一律降级为「未评级」，不由陈旧评级驱动建仓
    score_row, score_meta = repo.get_score_for_position(code, today)
    if score_row is not None and score_meta.get("stale"):
        logger.warning(
            "建仓评分已过期（评分日 %s，距 %s %s 个交易日 > %s 天）→ 降级为未评级: %s",
            score_meta.get("score_date"), today, score_meta.get("age_trading_days"),
            score_meta.get("max_trading_days"), code)

    # 大盘近 60 日
    index_kline = source.fetch_index_daily("sh000001", _days_ago(90), today)

    # 个股近期 K 线与指标
    kline = source.fetch_daily_kline(code, _days_ago(120), today)
    indicators = compute_indicators(kline)

    # S-7：过期/缺失评分统一降级为「未评级」（plan_quant 走 C 级默认档，不按 A/B 放量）
    _stale = bool(score_meta.get("stale") or score_row is None)
    state["score_result"] = {
        "score": float(score_row.score) if score_row else None,
        "grade": "未评级" if _stale else score_row.grade,
        "detail": score_row.detail if score_row else {},
        "risk_list": score_row.risk_list if score_row else [],
        "score_date": score_meta.get("score_date"),
        "as_of": today,
        "stale": _stale,
        "age_trading_days": score_meta.get("age_trading_days"),
    }
    state["basic_info"] = {
        "index_kline": index_kline.tail(60).to_dict(orient="records") if not index_kline.empty else [],
        "indicators": indicators,
        "capital": settings.total_capital,
        "max_single_pct": settings.max_single_position_pct,
        "trade_style": settings.trade_style,
    }
    # K 红线参考（批次G）：C1/C2 软上限 + K192 吸筹末期（建仓前事实参考，非死条件）；失败 None 不阻塞
    red_line_ref = None
    try:
        from app.services.capital_view import compute_capital_view
        _cv = compute_capital_view(code, today)
        # S-4：红线阈值不再写字面量，统一从 core.config 唯一常量源读取
        red_line_ref = {
            "c1_cap_threshold_pct": C1_CONCENTRATION_CAP,
            "c2_drawdown_threshold_pct": -C2_INTRADAY_DRAWDOWN_PCT,
            "c3_stop_loss_factor": C3_STOP_FACTOR,
            "wash_suspect": (bool(_cv.get("wash_suspect"))
                             if _cv and _cv.get("wash_suspect") is not None else None),
            "k192_note": f"建仓按 K192 试探仓：主力成本附近建仓、100 整数倍、C3=成本×{C3_STOP_FACTOR}（吸筹末期待拉升）",
        }
    except Exception as exc:  # noqa: BLE001 红线参考读取失败不阻塞建仓规划
        logger.warning("K 红线参考读取失败（跳过注入）: %s", exc)
    state["basic_info"]["red_line_ref"] = red_line_ref
    state["trace"] = [*state.get("trace", []), "建仓数据聚合完成"]
    return state


def llm_plan(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 生成分批建仓方案 + 落库"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or clock.today()
    info = state.get("basic_info") or {}

    score_info = (
        f"【标的评分】综合 {state['score_result'].get('score')} 分 "
        f"{state['score_result'].get('grade')} 级\n"
        f"五维明细: {state['score_result'].get('detail')}\n"
        f"风险清单: {state['score_result'].get('risk_list')}"
    )
    index_data = _compact(info.get("index_kline", [])[:60])
    capital_constraints = (
        f"总资金: {info.get('capital')} 元；"
        # S-4：单标的仓位上限以 L0 分级红线为准（A 级 30%），不再引用可被 .env 覆盖的
        # 展示用 settings.max_single_position_pct（默认 40%，与 30% 红线自相矛盾）
        f"单标的仓位上限（L0 分级红线）: A 级 {GRADE_POSITION_CAP['A'] * 100:.0f}% / "
        f"B 级 {GRADE_POSITION_CAP['B'] * 100:.0f}% / "
        f"C 级 {GRADE_POSITION_CAP['C'] * 100:.0f}%；"
        f"C2 总仓位上限（L0 红线）: {C2_TOTAL_POSITION_CAP:.0f}%；"
        f"交易风格: {info.get('trade_style')}"
    )
    _rl = info.get("red_line_ref") or {}
    if _rl:
        capital_constraints += (
            f"\n【K 红线参考】C1 单只占比上限 {_rl.get('c1_cap_threshold_pct')}%；"
            f"C2 日内回撤触发线 {_rl.get('c2_drawdown_threshold_pct')}%；"
            f"C3 止损 = 成本 × {_rl.get('c3_stop_loss_factor')}（L0 红线）；"
            f"对倒嫌疑: {_rl.get('wash_suspect') if _rl.get('wash_suspect') is not None else '无数据'}；"
            f"K192 建仓策略: {_rl.get('k192_note')}"
        )
    try:
        from app.services.sector_rotation_pattern import build_regime_context
        regime_context = build_regime_context(today)
    except Exception as exc:  # noqa: BLE001
        logger.warning("行情结构上下文获取失败（跳过注入）: %s", exc)
        regime_context = ""
    if regime_context:
        capital_constraints += f"\n{regime_context}"
    stock_data = _compact(info.get("indicators", {}))
    input_fingerprint = _plan_input_fingerprint(
        code, today, state.get("score_result"),
        {**info, "score_info": score_info, "index_data": index_data,
         "capital_constraints": capital_constraints, "stock_data": stock_data})

    output = agent_call(
        agent="position",
        cache_key=f"{code}:{today}:input:{input_fingerprint}",
        system_prompt=position_prompt.SYSTEM_PROMPT,
        user_prompt=position_prompt.build_user_prompt(
            score_info, index_data, capital_constraints, stock_data),
        schema=PositionOutput,
        ttl_seconds=86400,
        model_level=ModelLevel.DEEP,
    )

    # 新鲜度只描述事实数据，不再用评级推断“实时”。
    # 先固定量化所需的指标快照，再读取日期，避免指标未赋值导致 B/A 计划生成异常。
    indicators = (info or {}).get("indicators") or {}
    grade = (state.get("score_result") or {}).get("grade") or ""
    data_as_of = str(indicators.get("latest_date") or "")
    freshness = _data_freshness(data_as_of, today)
    analysis_generated_at = clock.now_str()
    # 量化计算（纯计算零 LLM）：金额/股数（100 整数倍）/分级 C1 上限/盈亏比/资金缩减
    quant = plan_quant.quantify(
        code, name, grade,
        [b.model_dump() for b in output.batches],
        float(output.stop_loss), float(output.take_profit),
        float(indicators.get("latest_close") or 0),
        str(indicators.get("latest_date") or ""))
    plan_id = repo.insert_plan(
        code, name, today, float(output.total_pct),
        [b.model_dump() for b in output.batches],
        float(output.stop_loss), float(output.take_profit), output.rationale,
        # v3.0 白盒维度归因：dimensions + final_advice + market_regime（顺带落库修复现状丢失）
        detail={"dimensions": [d.model_dump() for d in output.dimensions],
                "final_advice": output.final_advice,
                "market_regime": output.market_regime,
                "freshness": freshness,
                "data_as_of": data_as_of or None,
                "analysis_generated_at": analysis_generated_at,
                "input_fingerprint": input_fingerprint,
                "quant": quant},
        source=state.get("plan_source") or "manual",
    )
    state["position_plan"] = {**output.model_dump(), "plan_id": plan_id}
    state["stage"] = "plan_position"
    state["trace"] = [*state.get("trace", []),
                      f"建仓方案完成: 总仓{output.total_pct}% 止损{output.stop_loss} 止盈{output.take_profit}"]
    logger.info("建仓方案完成 %s: plan_id=%s", code, plan_id)
    return state


def _plan_input_fingerprint(code: str, trade_date: str,
                            score_result: dict | None, basic_info: dict) -> str:
    """动态输入指纹：行情/评分/资金约束变化时，Position LLM 缓存自动换键。"""
    payload = {
        "stock_code": code,
        "trade_date": trade_date,
        "score_result": score_result or {},
        "basic_info": basic_info or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _data_freshness(data_as_of: str, trade_date: str) -> str:
    """返回事实数据状态；daily K 线不宣称盘中实时。"""
    if not data_as_of:
        return "unknown"
    if data_as_of == trade_date:
        return "same_day_as_of"
    return "prior_close"


def _compact(data) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _days_ago(n: int) -> str:
    import datetime

    return (clock.today_date() - datetime.timedelta(days=n)).isoformat()
