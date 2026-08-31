"""只读工具集(ReAct 智能体 PoC 用)。

全部只取数、不写库; 失败返回 {"error": ...} 不中断循环。
TOOLS(OpenAI function schema) + TOOL_FUNCS(name -> 可调用只读函数) 分离, 供 llm/agentic.py 使用。
"""
from __future__ import annotations

import math
import json
import time
from datetime import datetime
from datetime import date, timedelta

from app.cache import cache
from app.datasource.akshare_source import get_datasource
from app.db import repo
from app.services.vector_store import get_vector_store


def _safe(value):
    """递归把 NaN/Inf 等转 None, 保证 JSON 可序列化。"""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


def _wrap(fn):
    """取数工具统一包装: 异常转 error 字典, 保证模型循环不中断。"""
    def inner(*args, **kwargs):
        try:
            return _safe(fn(*args, **kwargs))
        except Exception as exc:  # noqa: BLE001 数据源失败降级不中断
            return {"error": f"{getattr(fn, '__name__', 'tool')} 失败: {exc}"}
    return inner


# ---- 工具实现(全部只读) ----

def _get_quote(code: str) -> dict:
    ds = get_datasource()
    return ds.fetch_spot_quote(code) or {"note": "行情为空"}


def _get_daily_kline(code: str, days: int = 30) -> dict:
    ds = get_datasource()
    end = date.today()
    start = end - timedelta(days=int(days) * 2 + 10)
    df = ds.fetch_daily_kline(code, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
    if df is None or df.empty:
        return {"error": "日K为空"}
    return {"rows": df.tail(int(days)).to_dict(orient="records")}


def _get_news(code: str, limit: int = 8) -> dict:
    ds = get_datasource()
    df = ds.fetch_news(code)
    if df is None or df.empty:
        return {"news": []}
    out = []
    for _, r in df.tail(int(limit)).iterrows():
        item = {str(k): v for k, v in r.items() if isinstance(v, str) and v.strip()}
        out.append(item)
    return {"news": out}


def _get_financial(code: str) -> dict:
    ds = get_datasource()
    df = ds.fetch_financial(code)
    if df is None or df.empty:
        return {"note": "无财务数据"}
    return {"rows": df.tail(6).to_dict(orient="records")}


def _get_fund_flow(code: str) -> dict:
    ds = get_datasource()
    df = ds.fetch_fund_flow(code)
    if df is None or df.empty:
        return {"note": "无资金流数据"}
    return {"rows": df.tail(6).to_dict(orient="records")}


def _search_knowledge(code: str, query: str, top_k: int = 5) -> dict:
    try:
        vs = get_vector_store()
        hits = vs.search_related(code, query, top_k=int(top_k))
    except Exception as exc:  # noqa: BLE001 Qdrant 本地锁冲突等 -> 降级空结果, 不中断循环
        return {"hits": [], "error": f"知识库检索不可用: {exc}"}
    return {"hits": [{"标题": h.get("title"),
                      "摘要": (h.get("summary") or h.get("content") or "")[:120]} for h in hits]}


def _get_sector_regime(trade_date: str = "") -> dict:
    d = trade_date or time.strftime("%Y-%m-%d")
    row = repo.get_sector_regime_forecast(d)
    return {"regime": row} if row else {"regime": None, "note": "no_data", "trade_date": d}


def _get_factor_calibration(period: str = "t5") -> dict:
    from app.services import track_verify

    text = track_verify.get_factor_calibration(period)
    return {"period": period, "text": text[:1200]} if text else {"period": period, "text": "", "note": "no_data"}


def _get_distribution_phase(code: str, trade_date: str = "") -> dict:
    from app.services import distribution_phase

    d = trade_date or time.strftime("%Y-%m-%d")
    result = distribution_phase.compute_distribution_phase(code, d)
    return {"stock_code": code, "trade_date": d, "distribution_phase": result}


def _get_capital_view(code: str, trade_date: str = "") -> dict:
    d = trade_date or time.strftime("%Y-%m-%d")
    raw = cache.get(f"capital_view:{d}:{code}")
    if raw:
        try:
            data = json.loads(raw)
            return {"stock_code": code, "trade_date": d, "capital_view": _compact_capital_view(data)}
        except (TypeError, ValueError):
            pass
    stats = repo.get_capital_stats(code, d)
    if not stats:
        return {"stock_code": code, "trade_date": d, "capital_view": None, "note": "no_data"}
    return {"stock_code": code, "trade_date": d, "capital_view": stats}


def _compact_capital_view(data: dict) -> dict:
    return {
        "stock_code": data.get("stock_code"),
        "trade_date": data.get("trade_date"),
        "coordination": data.get("coordination"),
        "wash_suspect": data.get("wash_suspect"),
        "stats_30d": data.get("stats_30d"),
        "theme_resonance": data.get("theme_resonance"),
        "missing_data": (data.get("missing_data") or [])[:8],
        "recent_actors": (data.get("recent_actors") or [])[:5],
        "source": data.get("source"),
    }


def _get_position_risk(code: str = "") -> dict:
    raw = cache.get("portfolio_sentinel:last_risk")
    if raw:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        if data:
            return {"source": "cache", "risk": data}
    from app.services import take_profit

    plans = take_profit.build_plans(trace=False, check_alerts=False)
    rows = plans.get("rows") or []
    if code:
        rows = [r for r in rows if r.get("stock_code") == code]
    return {"source": "take_profit", "rows": rows[:5], "quote_time": plans.get("quote_time")}


def _get_hot_money_context(code: str, stock_name: str = "", trade_date: str = "") -> dict:
    from app.services import hot_money

    d = trade_date or time.strftime("%Y-%m-%d")
    agg = hot_money.aggregate_for_stock(code, stock_name, d, trace=False)
    text = hot_money.build_hot_money_context({code: agg}, d) if agg else ""
    return {"stock_code": code, "trade_date": d, "aggregate": agg,
            "context": text[:1200], "note": "" if agg else "no_data"}


# ---- 公共注入（agentic 分支统一消费，禁止节点内重抄）----
# 工具引导：提示模型已有只读工具可按需调用核验数据（工具由调用层挂载，本段仅行为约束）
_AGENTIC_TOOL_NOTE = (
    "【只读工具（已挂载，按需调用核验数据）】你已收到聚合数据包，通常足以直接评分；"
    "若某维度数据缺失、过期或需最新确认，可调用只读工具核验/补充：get_quote 实时行情、"
    "get_daily_kline 日K、get_news 新闻公告、get_financial 财务、get_fund_flow 资金流、"
    "search_knowledge 私有知识库检索，以及 get_sector_regime、get_factor_calibration、"
    "get_distribution_phase、get_capital_view、get_position_risk、get_hot_money_context 等专业服务。"
    "新工具仅用于核验或补充缺失维度；返回 error/no_data 时降级处理，不得编造。"
    "数据已充分时直接输出，勿空转调工具。\n\n"
)


# ---- OpenAI function 定义 + 函数注册表 ----

TOOLS = [
    {"type": "function", "function": {
        "name": "get_quote", "description": "查询个股实时行情快照(现价/涨跌幅/成交额/量比等)",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "6位股票代码"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "get_daily_kline", "description": "查询个股近 N 日日K(日期/开盘/收盘/最高/最低/成交量等原始数据)",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"},
            "days": {"type": "integer", "description": "返回最近多少日, 默认30, 上限60"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "get_news", "description": "查询个股最新新闻/公告",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"},
            "limit": {"type": "integer", "description": "返回条数, 默认8"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "get_financial", "description": "查询个股财务指标数据",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "get_fund_flow", "description": "查询个股资金流向数据",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "search_knowledge", "description": "在私有知识库检索与该股相关的历史经验/战法片段",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"},
            "query": {"type": "string", "description": "检索主题, 如 趋势 资金 风险"},
            "top_k": {"type": "integer", "default": 5}}, "required": ["code", "query"]}}},
    {"type": "function", "function": {
        "name": "get_sector_regime", "description": "读取已有行情结构预测，不触发重新计算",
        "parameters": {"type": "object", "properties": {
            "trade_date": {"type": "string", "description": "YYYY-MM-DD, 默认今天"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_factor_calibration", "description": "读取 T+N 因子校准摘要，空数据返回 no_data",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "default": "t5"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_distribution_phase", "description": "计算派发期阶段，只写短期缓存，不写业务表",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}, "trade_date": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "get_capital_view", "description": "读取已有资本视图快照或缓存，不触发资本视图落库计算",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}, "trade_date": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "get_position_risk", "description": "读取组合/持仓风险快照，必要时生成无留痕无告警止盈计划",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "可选股票代码"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_hot_money_context", "description": "读取游资上下文，调用聚合时关闭留痕",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}, "stock_name": {"type": "string"},
            "trade_date": {"type": "string"}}, "required": ["code"]}}},
]

TOOL_FUNCS = {
    "get_quote": _wrap(_get_quote),
    "get_daily_kline": _wrap(_get_daily_kline),
    "get_news": _wrap(_get_news),
    "get_financial": _wrap(_get_financial),
    "get_fund_flow": _wrap(_get_fund_flow),
    "search_knowledge": _wrap(_search_knowledge),
    "get_sector_regime": _wrap(_get_sector_regime),
    "get_factor_calibration": _wrap(_get_factor_calibration),
    "get_distribution_phase": _wrap(_get_distribution_phase),
    "get_capital_view": _wrap(_get_capital_view),
    "get_position_risk": _wrap(_get_position_risk),
    "get_hot_money_context": _wrap(_get_hot_money_context),
}


def select_tools(allowlist: list[str] | None = None):
    """按白名单裁剪工具子集；None/空 = 全量6工具（旧行为零变化）。"""
    if not allowlist:
        return TOOLS, TOOL_FUNCS
    tools = [t for t in TOOLS if t["function"]["name"] in allowlist]
    funcs = {k: v for k, v in TOOL_FUNCS.items() if k in allowlist}
    return tools, funcs
