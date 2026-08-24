"""
MonitorAgent 持仓监控 - LangGraph 节点（每持仓执行一次）
【刚性代码逻辑】实时行情/新闻拉取、纯数学指标、告警去重、飞书推送、落库
【交由模型推理的业务逻辑】趋势破坏/支撑压力/突发利空识别、持有/减仓/清仓建议（全部在 LLM）
流转：collect_quote → llm_signal → push_alert
"""
import logging
import time

from app.agents.common import ModelLevel, agent_call
from agent_prompts import monitor_prompt
from app.agents.schemas import MonitorOutput
from app.cache import cache
from app.core.config import settings
from app.datasource.base import DataSource, to_float
from app.datasource.fallback import get_datasource
from app.db import repo
from app.db.models import Holding
from app.graph.state import StockAgentState
from app.services.feishu import push_alert
from app.services.indicator import compute_indicators
from app.agents.portfolio_sentinel import read_portfolio_overview

logger = logging.getLogger(__name__)

# LLM 研判不可用时的纯规则兜底阈值（floating loss %）：最硬的一条确定性保命信号
_RULE_FALLBACK_LOSS_PCT = -5.0


def collect_quote(state: StockAgentState) -> StockAgentState:
    """节点1：拉取持仓实时行情（30s 缓存，禁止用过期缓存）与最新新闻【刚性代码逻辑】

    实时价失败时用日K最新收盘兜底并标注「数据暂未更新」；
    止损/止盈距离、盈亏比例、市值基于当次最新价纯数学计算，注入 LLM 上下文。
    """
    code = state["stock_code"]
    source = get_datasource()
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    kline = source.fetch_daily_kline(code, _days_ago(30), today)
    indicators = compute_indicators(kline)

    batch_quote = (state.get("batch_quotes") or {}).get(code)
    if batch_quote and batch_quote.get("price") is not None:
        # 批量预取行情（全持仓一次获取，监控主路径）；与逐只取数同格式同语义
        quote, stale = batch_quote, False
    else:
        quote, stale = _fetch_realtime_quote(source, code, indicators)
    # 移动止盈线（批次1）：持仓期最高价跟踪 + 止盈线计算（纯数学，判断在 LLM；失败降级不阻塞）
    _attach_trailing_stop(quote, state)
    state["real_time"] = quote
    state["quote_stale"] = stale

    news_rows: list[dict] = []
    try:
        news_df = source.fetch_news(code)
        for _, row in news_df.head(10).iterrows():
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            repo.add_news(code, state.get("stock_name") or "", title,
                          str(row.get("content") or ""), str(row.get("source") or ""),
                          str(row.get("url") or ""), str(row.get("published_at") or ""))
            news_rows.append({"title": title, "published_at": str(row.get("published_at") or "")})
    except Exception as exc:  # noqa: BLE001 新闻失败不阻塞监控
        logger.warning("监控新闻拉取失败 %s: %s", code, exc)

    # 游资聚合数据（阶段3：龙虎榜流水聚合；无数据 None，LLM 保持标中性）
    hm_agg = None
    try:
        from app.services import hot_money as hot_money_svc
        hm_agg = hot_money_svc.aggregate_for_stock(code, state.get("stock_name") or "", today)
    except Exception as exc:  # noqa: BLE001 游资聚合失败不阻塞监控
        logger.warning("监控游资聚合失败（降级跳过）: %s", exc)

    state["tech_index"] = indicators
    state["news_report"] = news_rows
    state["hot_money"] = hm_agg
    state["trace"] = [*state.get("trace", []),
                      f"行情聚合: {indicators.get('latest_date')}"
                      + ("（实时价不可用，用日K收盘兜底）" if stale else "")]
    return state


def _attach_trailing_stop(quote: dict, state: StockAgentState) -> None:
    """移动止盈线（批次1）【刚性代码逻辑】：当前价 > 持仓期最高价时更新最高价落库；
    浮盈 ≥5% 时在 quote 上挂 trailing_stop 字段（= 持仓期最高价×0.92，不低于成本价），
    作为数据字段传给 LLM（判断在 LLM，此处零判断）；失败降级跳过不阻塞监控。"""
    try:
        holding = repo.get_holding(state["holding_id"]) if state.get("holding_id") else None
        if holding is None:
            return
        price = quote.get("price")
        high_price = to_float(getattr(holding, "high_price", None), 0.0)
        if price is not None and price > 0:
            if price > high_price:
                repo.update_holding(holding.id, high_price=round(price, 2))
                high_price = price
            from app.services.take_profit import calc_trailing_stop

            quote["trailing_stop"] = calc_trailing_stop(holding.entry_price, high_price, price)
    except Exception as exc:  # noqa: BLE001 移动止盈失败不阻塞监控
        logger.warning("移动止盈线计算失败（降级跳过）: %s", exc)


def _fetch_realtime_quote(source: DataSource, code: str, indicators: dict) -> tuple[dict, bool]:
    """拉取单股实时行情（TTL 30s）；失败用日K最新收盘兜底（上一次有效数据）并返回 stale 标记"""
    try:
        quote = source.fetch_spot_quote(code)
    except Exception as exc:  # noqa: BLE001 实时行情失败不阻塞监控
        logger.warning("实时行情获取失败 %s: %s", code, exc)
        quote = {}
    if quote.get("price") is None:
        # 兜底：日K最新收盘（上一次有效数据，标注「数据暂未更新」）
        kl = indicators.get("recent_klines") or []
        price = float(kl[-1].get("close")) if kl else None
        quote = {"code": code, "name": quote.get("name", ""), "price": price,
                 "change_pct": quote.get("change_pct"), "time": quote.get("time", "")}
        return quote, price is not None
    return quote, False


def _trade_math(price: float | None, holding: Holding | None) -> dict:
    """基于当次最新价程序计算止损/止盈距离、盈亏比例、市值【刚性数学计算，零判断】"""
    if price is None:
        return {"stop_loss_distance_pct": None, "take_profit_distance_pct": None,
                "pnl_pct": None, "market_value": None}
    stop_loss = to_float(holding.stop_loss if holding else 0.0, 0.0)
    take_profit = to_float(holding.take_profit if holding else 0.0, 0.0)
    entry_price = to_float(holding.entry_price if holding else 0.0, 0.0)
    shares = to_float(holding.shares if holding else 0.0, 0.0)
    return {
        "stop_loss_distance_pct": round((stop_loss - price) / price * 100, 2) if stop_loss > 0 else None,
        "take_profit_distance_pct": round((take_profit - price) / price * 100, 2) if take_profit > 0 else None,
        "pnl_pct": round((price - entry_price) / entry_price * 100, 2) if entry_price > 0 else None,
        "market_value": round(price * shares, 2),
    }


def llm_signal(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 信号研判"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    holding = repo.get_holding(state["holding_id"]) if state.get("holding_id") else None

    if holding is None:
        state["error"] = f"持仓不存在: {state.get('holding_id')}"
        return state

    holding_info = (
        f"【持仓信息】{name}({code})\n"
        f"建仓日期: {holding.entry_date} | 成本价: {holding.entry_price} | 持仓股数: {holding.shares}\n"
        f"参考止损: {holding.stop_loss} | 参考止盈: {holding.take_profit} | 目标仓位: {holding.target_pct}%"
    )
    indicators = state.get("tech_index") or {}
    real_time = state.get("real_time") or {}
    stale = bool(state.get("quote_stale"))
    math = _trade_math(real_time.get("price"), holding)
    # 组合联动（batch F）：读组合哨兵告警概览（多键隔离快照），供个股判断参考；无快照为空 dict 不阻断
    po = read_portfolio_overview(today)
    # 派发期判定（batch D）：6 维参考事实（LLM 一票否决）；失败为 None 不阻断
    dist = None
    try:
        from app.services.distribution_phase import compute_distribution_phase
        dist = compute_distribution_phase(code, today)
    except Exception as exc:  # noqa: BLE001
        logger.warning("派发期判定失败（跳过注入）: %s", exc)
    real_time_block = {
        **real_time, **math,
        "数据状态": "实时（TTL 30s 内缓存）" if not stale else "数据暂未更新（实时源不可用，以下为最近一次有效数据）",
    }
    quote_data = {
        "实时行情": real_time_block,
        "最新指标": {k: v for k, v in indicators.items() if k != "recent_klines"},
        "近期K线": indicators.get("recent_klines", [])[-15:],
        # 游资聚合（阶段3）：口径后缀字段 lhb_1d_net_buy/lhb_3d_net_buy，无数据 None
        "游资聚合": state.get("hot_money"),
        # 组合联动（batch F）：组合告警三态色 / 集中度警示 / 板块暴露占比（缺失不注入，避免噪音）
        **({k: po[k] for k in ("portfolio_alert_level", "concentration_warning", "sector_exposure_pct")
           if k in po and po[k] is not None and po[k] != ""}),
        # 派发期判定（batch D）：{phase_label}(置信度) + 6 维原始数据
        "distribution_phase_context": dist,
    }
    news_context = "\n".join(
        f"{n.get('published_at')} {n.get('title')}" for n in (state.get("news_report") or [])) or "（无）"

    # 盘中监控 LLM 调用节流（短 TTL 缓存，与监控频率同节奏）
    cache_key = f"{code}:{today}:{time.strftime('%H')}"
    try:
        output = agent_call(
            agent="monitor",
            cache_key=cache_key,
            system_prompt=monitor_prompt.SYSTEM_PROMPT,
            user_prompt=monitor_prompt.build_user_prompt(
                holding_info, _compact(quote_data), news_context),
            schema=MonitorOutput,
            ttl_seconds=max(60, settings.monitor_llm_cache_minutes * 60),
            model_level=ModelLevel.LIGHT,
        )
    except Exception as exc:  # noqa: BLE001 LLM 不可用 → 规则兜底保命（仅异常分支）
        logger.error("监控 LLM 研判不可用（%s），进入规则兜底分支: %s", exc, code)
        _rule_fallback_alert(code, name, today, math)
        raise

    state["holding_signal"] = output.model_dump()
    state["stage"] = "holding_monitor"
    state["trace"] = [*state.get("trace", []),
                      f"信号: {output.action}({output.severity}) {output.alert_type}"]
    return state


def _rule_fallback_alert(code: str, name: str, today: str, math: dict) -> None:
    """LLM 研判不可用 + 浮亏超硬性止损红线时，推送最硬的一条确定性兜底告警并落库（当日去重）。
    只覆盖「浮亏 ≤ -5%」这一条确定性信号，不做任何复杂判定；复杂研判仍归 LLM。"""
    pnl = math.get("pnl_pct")
    if pnl is None or pnl > _RULE_FALLBACK_LOSS_PCT:
        return
    msg = (f"⚠️ LLM 研判不可用，此为规则兜底预警：{name}({code}) 浮亏 "
           f"{pnl}%（≤{_RULE_FALLBACK_LOSS_PCT}%），触及硬性止损红线。")
    dedup_key = f"{code}:rule_fallback:{today}"
    pushed = False
    if not cache.alert_deduplicated(dedup_key, ttl_seconds=86400):
        pushed = push_alert(name, code, "rule_fallback", "critical", msg, "exit")
    repo.insert_alert(code, name, "rule_fallback", "critical", msg, "exit",
                      {"rule_fallback": True, "pnl_pct": pnl}, pushed=pushed)
    logger.error("监控规则兜底告警落库: %s（浮亏 %s%%，pushed=%s）", code, pnl, pushed)


def push_alert_node(state: StockAgentState) -> StockAgentState:
    """节点3：告警去重 + 飞书推送 + 落库【刚性代码逻辑】"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")
    signal = state.get("holding_signal") or {}

    if not signal:
        return state

    # 所有信号落库（面板可见）；推送按严重度与去重控制
    pushed = False
    if signal.get("action") != "hold" or signal.get("severity") in ("warning", "critical"):
        dedup_key = f"{code}:{signal.get('alert_type', 'unknown')}:{today}"
        if not cache.alert_deduplicated(dedup_key, ttl_seconds=86400):
            pushed = push_alert(name, code, signal.get("alert_type", "监控"),
                                signal.get("severity", "info"),
                                signal.get("message", ""), signal.get("action", "hold"))
            cache.set(f"alert:last:{code}:{today}",
                      f"{signal.get('action')}|{signal.get('severity')}", 86400)
        elif _severity_changed(code, today, signal):
            # 同日同类告警但风险等级/建议发生变化 → 重新推送（30 分钟冷却，防 LLM 波动震荡）
            logger.info("告警等级变化，重新推送: %s %s", code, signal.get("alert_type"))
            pushed = push_alert(name, code, signal.get("alert_type", "监控"),
                                signal.get("severity", "info"),
                                signal.get("message", ""), signal.get("action", "hold"))
            cache.set(f"alert:last:{code}:{today}",
                      f"{signal.get('action')}|{signal.get('severity')}", 86400)
        else:
            logger.info("告警去重命中，跳过推送: %s", dedup_key)

    repo.insert_alert(code, name, signal.get("alert_type", "常规跟踪"),
                      signal.get("severity", "info"), signal.get("message", ""),
                      signal.get("action", "hold"), signal, pushed)
    return state


def _severity_changed(code: str, today: str, signal: dict) -> bool:
    """同日同类告警是否风险等级变化：与当日已推信号比较，且 30 分钟冷却（防震荡）"""
    last = cache.get(f"alert:last:{code}:{today}")
    cur = f"{signal.get('action')}|{signal.get('severity')}"
    if not last or last == cur:
        return False
    return not cache.alert_deduplicated(f"{code}:sevchange:{today}", ttl_seconds=1800)


def _compact(data) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
