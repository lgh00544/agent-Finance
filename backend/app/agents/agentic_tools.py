"""只读工具集(ReAct 智能体 PoC 用)。

全部只取数、不写库; 失败返回 {"error": ...} 不中断循环。
TOOLS(OpenAI function schema) + TOOL_FUNCS(name -> 可调用只读函数) 分离, 供 llm/agentic.py 使用。
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.datasource.akshare_source import get_datasource
from app.services.vector_store import get_vector_store


def _safe(value):
    """递归把 NaN/Inf 等转 None, 保证 JSON 可序列化。"""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
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


# ---- 公共注入（agentic 分支统一消费，禁止节点内重抄）----
# 工具引导：提示模型已有只读工具可按需调用核验数据（工具由调用层挂载，本段仅行为约束）
_AGENTIC_TOOL_NOTE = (
    "【只读工具（已挂载，按需调用核验数据）】你已收到聚合数据包，通常足以直接评分；"
    "若某维度数据缺失、过期或需最新确认，可调用只读工具核验/补充：get_quote 实时行情、"
    "get_daily_kline 日K、get_news 新闻公告、get_financial 财务、get_fund_flow 资金流、"
    "search_knowledge 私有知识库检索。调用后据返回继续推理，证据充分即输出最终 JSON；"
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
]

TOOL_FUNCS = {
    "get_quote": _wrap(_get_quote),
    "get_daily_kline": _wrap(_get_daily_kline),
    "get_news": _wrap(_get_news),
    "get_financial": _wrap(_get_financial),
    "get_fund_flow": _wrap(_get_fund_flow),
    "search_knowledge": _wrap(_search_knowledge),
}


def select_tools(allowlist: list[str] | None = None):
    """按白名单裁剪工具子集；None/空 = 全量6工具（旧行为零变化）。"""
    if not allowlist:
        return TOOLS, TOOL_FUNCS
    tools = [t for t in TOOLS if t["function"]["name"] in allowlist]
    funcs = {k: v for k, v in TOOL_FUNCS.items() if k in allowlist}
    return tools, funcs