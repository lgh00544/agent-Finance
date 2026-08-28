"""
ScoreAgent 六因子透明评分 - LangGraph 节点
【刚性代码逻辑】数据聚合（行情/财务/资金流/新闻 + 候选上下文 + 市况摘要）、纯数学指标计算、
potential_flag 代码层推导、落库
【交由模型推理的业务逻辑】六因子评分、A/B/C 分级、潜力标识自报、交叉验证、风险清单（全部在 LLM）
流转：collect_data → llm_score
"""
import json
import logging
import time

from app.agents.common import (ModelLevel, agent_call, agentic_call,
                               summarize_agentic_trace)
from app.agents.agentic_tools import _AGENTIC_TOOL_NOTE
from agent_prompts import score_prompt
from app.agents.schemas import PrefilterOutput, ScoreOutput
from app.core.config import settings
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.indicator import compute_indicators
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_KLINE_DAYS = 250  # 约一年交易日

# 两段式粗筛系统提示词（独立常量，不改动既有 prompt 文件）
# 注意：必须含字面 "json"，否则 DeepSeek json_object 模式返回 400
_PREFILTER_SYSTEM = (
    "你是 A 股候选池粗筛助手。给你一份候选列表，请你基于候选理由/信心度/关注类型/威科夫阶段/"
    "涨跌幅/量比/换手等字段，挑出值得用深度模型进一步精打评分的一小部分标的。"
    "铁律：宁保守不漏票——你只淘汰明显弱势、无催化、高风险或与用户偏好明显相悖的标的；"
    "拿不准的标的全部保留。请严格以 json（JSON）数据结构化输出来作答："
    "只输出 keep_codes（要精打的 6 位代码数组），reason 字段用一句话说明取舍；"
    "若你认为全部值得精打，keep_codes 输出全部代码，不要偷懒少报。json 输出中不要包含任何多余文本。"
)

# 粗筛 compact 表字段：只取候选/快照已有字段的子集，不新拉数据、不调数据源
_PREFILTER_FIELDS = [
    ("stock_code", "代码"), ("stock_name", "名称"), ("market_cap", "市值"),
    ("industry", "行业"), ("close", "收盘价"), ("change_pct", "涨跌幅%"),
    ("volume_ratio", "量比"), ("turnover_rate", "换手%"), ("stock_type", "威科夫阶段"),
    ("confidence_tier", "信心度"), ("focus_type", "关注类型"), ("reason", "候选理由"),
]


def _compact_prefilter_row(cand: dict) -> dict:
    """构造单只候选紧凑行：仅保留 _PREFILTER_FIELDS 中实际存在的字段（缺失字段省略，不编造）。"""
    out: dict[str, str] = {}
    for key, label in _PREFILTER_FIELDS:
        val = cand.get(key)
        if val not in (None, "", [], {}):
            out[label] = val if not isinstance(val, (list, dict)) else str(val)
    return out


def prefilter_candidates(candidates: list[dict], date_key: str) -> list[dict]:
    """两段式粗筛（仅 settings.score_two_stage=True 时由 router 调用）：低成本 LIGHT 粗筛。

    返回精打名单：keep_codes 与输入候选求交集；空交集（空名单/全不命中）回退全量。
    安全阀 1（防误杀）：keep_codes 为空 → 回退全量精打；
    安全阀 2（防异常）：LLM 调用/校验失败 → 回退全量精打，记 warning。"""
    try:
        rows = [_compact_prefilter_row(c) for c in candidates]
        rows_json = json.dumps(rows, ensure_ascii=False, default=str)
        user_prompt = (
            f"请从以下 {date_key} 候选池（{len(rows)} 只）中粗筛出值得用深度模型精打评分的少量标的。"
            "粗筛原则：宁保守不漏票，淘汰明显弱势/无催化/高风险标的，保留有期望的标的。\n"
            f"候选列表：\n{rows_json}"
        )
        out = agent_call(
            agent="score_prefilter",
            cache_key=f"prefilter:v2:{date_key}:h{repo.hot_money_fingerprint()}",
            system_prompt=_PREFILTER_SYSTEM,
            user_prompt=user_prompt,
            schema=PrefilterOutput,
            ttl_seconds=86400,
            model_level=ModelLevel.LIGHT,
        )
        keep = set(out.keep_codes or [])
        if not keep:
            logger.warning("粗筛空名单（回收全量精打，防误杀）: %s", date_key)
            return candidates
        filtered = [c for c in candidates if c.get("stock_code") in keep]
        if not filtered:
            logger.warning("粗筛名单与输入无交集（回收全量精打）: %s", date_key)
            return candidates
        logger.info("粗筛完成 %s: %s/%s（%s）", date_key, len(filtered), len(candidates),
                    out.reason or "")
        return filtered
    except Exception as exc:  # noqa: BLE001 粗筛失败回退全量（安全阀 2）
        logger.warning("粗筛失败（回收全量精打）: %s", exc)
        return candidates


def collect_data(state: StockAgentState) -> StockAgentState:
    """节点1：聚合个股全部原始数据【刚性代码逻辑】"""
    code = state["stock_code"]
    source = get_datasource()
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    # 行情与指标
    kline = source.fetch_daily_kline(code, _days_ago(_KLINE_DAYS), today)
    indicators = compute_indicators(kline)

    # 财务（最近4期）
    financial = source.fetch_financial(code)
    fin_rows = financial.head(4).to_dict(orient="records") if not financial.empty else []

    # 资金流（严格当日有效：仅透传 trade_date 当日有数据时的近 10 日带日期序列；
    # 当日无资金流 → 不携带任何历史行，LLM 按缺省处理；东财接口不稳定，失败不阻塞打分）
    ff_rows = []
    try:
        fund_flow = source.fetch_fund_flow(code)
        if fund_flow is not None and not fund_flow.empty and "date" in fund_flow.columns:
            today_rows = fund_flow.loc[fund_flow["date"].astype(str).str.slice(0, 10) == today]
            if not today_rows.empty:
                ff_rows = fund_flow.tail(10).to_dict(orient="records")
    except Exception as exc:  # noqa: BLE001
        logger.warning("资金流拉取失败，跳过: %s", exc)

    # 新闻（落库 + 索引）
    news_df = source.fetch_news(code)
    news_rows: list[dict] = []
    for _, row in news_df.head(10).iterrows():
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        content = str(row.get("content") or "")
        is_new = repo.add_news(code, state.get("stock_name") or "", title, content,
                               str(row.get("source") or ""), str(row.get("url") or ""),
                               str(row.get("published_at") or ""))
        news_rows.append({"title": title, "content": content[:300],
                          "published_at": str(row.get("published_at") or "")})
    if news_rows:
        get_vector_store().index_news(code, news_rows)

    # 行业板块行情（全体，供 LLM 判断行业景气；失败不阻塞打分）
    industry_rows = []
    try:
        industry = source.fetch_industry_spot()
        industry_rows = industry.to_dict(orient="records") if not industry.empty else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("行业板块拉取失败，跳过: %s", exc)

    # 游资聚合数据（阶段3：龙虎榜流水聚合，口径后缀字段；无数据 None，LLM 保持标中性）
    hm_agg = None
    try:
        from app.services import hot_money as hot_money_svc
        hm_agg = hot_money_svc.aggregate_for_stock(code, state.get("stock_name") or "", today)
    except Exception as exc:  # noqa: BLE001 游资聚合失败不阻塞打分
        logger.warning("游资聚合失败（降级跳过）: %s", exc)

    state["basic_info"] = {"stock_code": code, "trade_date": today,
                           "industry_spot": industry_rows}
    state["tech_index"] = indicators
    state["finance_data"] = fin_rows
    state["news_report"] = news_rows
    state["fund_flow_rows"] = ff_rows
    state["hot_money"] = hm_agg
    state["risk_notice"] = []

    # ---- v4.0 新增：交叉验证上下文 + 市况摘要 ----
    # 候选上下文（DiscoverAgent 选股理由，供 ScoreAgent 交叉验证）
    discover_ctx = ""
    try:
        cand_ctx = repo.get_candidate_context(code, today)
        if cand_ctx:
            parts = []
            if cand_ctx.get("reasons"):
                parts.append(f"选股理由: {'；'.join(cand_ctx['reasons'])}")
            if cand_ctx.get("confidence_tier"):
                parts.append(f"信心度: {cand_ctx['confidence_tier']}")
            if cand_ctx.get("focus_type"):
                parts.append(f"关注类型: {cand_ctx['focus_type']}")
            if cand_ctx.get("final_advice"):
                parts.append(f"Discover综合评估: {cand_ctx['final_advice']}")
            discover_ctx = " | ".join(parts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("候选上下文获取失败（降级跳过）: %s", exc)

    # 市况摘要（MarketIntel，供主线契合因子参考）
    intel_summary = ""
    try:
        intel = repo.get_latest_market_intel()
        if intel:
            intel_summary = intel.get("summary", "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("MarketIntel 获取失败（降级跳过）: %s", exc)

    regime_context = ""
    try:
        from app.services.sector_rotation_pattern import build_regime_context
        regime_context = build_regime_context(today)
    except Exception as exc:  # noqa: BLE001
        logger.warning("行情结构上下文获取失败（降级跳过）: %s", exc)

    # 因子校准相关性参考（评级重做-C；只读 track_verify 统计，读取失败不阻塞评分）
    factor_calibration = ""
    try:
        from app.services.track_verify import get_factor_calibration
        factor_calibration = get_factor_calibration()
    except Exception as exc:  # noqa: BLE001 读取失败不阻塞评分
        logger.warning("因子校准摘要获取失败（降级跳过）: %s", exc)

    # 派发期判定（batch D）：6 维自动判定事实（LLM 一票否决）；失败为 None 不阻断打分
    distribution_phase_context = None
    try:
        from app.services.distribution_phase import compute_distribution_phase
        distribution_phase_context = compute_distribution_phase(code, today)
    except Exception as exc:  # noqa: BLE001 派发期判定失败跳过注入，不阻塞打分
        logger.warning("派发期判定失败（跳过注入）: %s", exc)

    # 资本视图（批次E）：游资/龙虎榜/资金流三维 + K189 对倒纯代码判定；失败 None 不阻断打分
    capital_view_context = None
    try:
        from app.services.capital_view import compute_capital_view
        capital_view_context = compute_capital_view(code, today)
    except Exception as exc:  # noqa: BLE001 资本视图失败跳过注入，不阻塞打分
        logger.warning("资本视图失败（跳过注入）: %s", exc)

    # 周期复利（批次H）：该股历史多次操作汇总（历史胜率/拖累率 → 资金维度加分/扣分依据）；
    # D 派发期 + E 游资后追加；失败 None 不阻断打分
    cycle_attribution = None
    try:
        from app.services.track_verify import build_stock_cycle_attribution
        cycle_attribution = build_stock_cycle_attribution(code)
    except Exception as exc:  # noqa: BLE001 周期复利失败跳过注入，不阻塞打分
        logger.warning("周期复利读取失败（跳过注入）: %s", exc)

    state["discover_context"] = discover_ctx
    state["market_intel_summary"] = intel_summary
    state["regime_context"] = regime_context
    state["factor_calibration"] = factor_calibration
    state["distribution_phase_context"] = distribution_phase_context
    state["capital_view_context"] = capital_view_context
    state["cycle_attribution"] = cycle_attribution
    state["trace"] = [*state.get("trace", []),
                      f"聚合完成: K线{len(kline)}行 财务{len(fin_rows)}期 资金流{len(ff_rows)}日 新闻{len(news_rows)}条"]
    return state


def llm_score(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 六因子透明评分 + 落库"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    preference = repo.get_latest_preference()
    preference_text = ""
    if preference:
        preference_text = f"偏好: {preference.get('偏好')}；调整方向: {preference.get('调整方向')}"

    data_pack = {
        "基本行情": {k: v for k, v in (state.get("tech_index") or {}).items() if k != "recent_klines"},
        "近期K线": (state.get("tech_index") or {}).get("recent_klines", [])[-20:],
        "财务指标": state.get("finance_data") or [],
        "资金流向": state.get("fund_flow_rows") or [],
        "新闻公告": state.get("news_report") or [],
        "行业板块行情": (state.get("basic_info") or {}).get("industry_spot", [])[:15],
        # 游资聚合（阶段3）：口径后缀字段 lhb_1d_net_buy/lhb_3d_net_buy，无数据 None
        "游资聚合": state.get("hot_money"),
        # 派发期判定（batch D）：6 维 + phase/confidence，供 LLM 单一票否决参考（缺失为 None）
        "distribution_phase_context": state.get("distribution_phase_context"),
        # 资本视图（批次E）：游资/龙虎榜/资金流三维 + K189 对倒 + 30日胜率（缺失为 None）
        "capital_view_context": state.get("capital_view_context"),
        # 周期复利（批次H）：该股历史多次操作汇总（参考权重，缺失为 None 不注入噪音）
        "cycle_attribution": state.get("cycle_attribution"),
    }

    score_cache_key = f"{code}:{today}:v4:h{repo.hot_money_fingerprint()}"
    score_user_prompt = score_prompt.build_user_prompt(
        _compact(data_pack), preference_text,
        discover_context=state.get("discover_context") or "",
        market_intel_summary=state.get("market_intel_summary") or "",
        factor_calibration=state.get("factor_calibration") or "",
    )
    if state.get("regime_context"):
        score_user_prompt = f"{score_user_prompt}\n\n{state['regime_context']}"
    agentic_trace: dict = {}
    if settings.agentic_enable:
        output, agentic_trace = agentic_call(
            agent="score", cache_key=score_cache_key,
            system_prompt=_AGENTIC_TOOL_NOTE + score_prompt.SYSTEM_PROMPT,
            user_prompt=score_user_prompt,
            schema=ScoreOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP,
            target_label=f"{name}({code})",
            # 决策瓶颈：全量6工具 + 8 轮预算（显式示例，等价默认 None）
            tools_allowlist=["get_quote", "get_daily_kline", "get_news",
                             "get_financial", "get_fund_flow", "search_knowledge"],
            max_rounds=8,
        )
    else:
        output = agent_call(
            agent="score", cache_key=score_cache_key,
            system_prompt=score_prompt.SYSTEM_PROMPT, user_prompt=score_user_prompt,
            schema=ScoreOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP,
        )

    # ---- 派发期判定（batch D）：phase≥2 视为派发/砸盘风险，评分上限压至 90 + 追加风险提示 ----
    # 不单独占一维（六因子维度不变），只做总分上限约束；缺失/失败不触发
    _dist = state.get("distribution_phase_context") or {}
    if int(_dist.get("phase") or 0) >= 2:
        output.score = min(output.score, 90)
        _trig = sum(1 for s in (_dist.get("six_dim") or {}).values() if s.get("triggered"))
        _notice = (f"⚠️ 派发期判定: {_dist.get('phase_label') or '派发期'}（6维触发 {_trig} 项），"
                   "评分上限压至 90，追高风险提示")
        if _notice not in output.risk_list:
            output.risk_list.append(_notice)

    # ---- 资本视图（批次E）：加分/减分仿 D 派发期（K189 对倒纯代码判定不交 LLM，减分压上限；
    #      多游资同买仅 +3 加分提示跟买≠必胜；30日无数据不触发）----
    _cv = state.get("capital_view_context") or {}
    if _cv.get("wash_suspect"):
        output.score = min(output.score, 88)
        _notice = ("⚠️ K189 对倒嫌疑（同营业部近5日买卖共存且单次≥1000万），评分上限压至 88")
        if _notice not in output.risk_list:
            output.risk_list.append(_notice)
    elif _cv.get("coordination") == "多游资同买":
        output.score = min(100, output.score + 3)
    # ---- 周期复利（批次H）：历史胜率/拖累率回流 —— 胜率≥60% 资金维度 +5；拖累率≥30% 扣 -10；无历史不动 ----
    _cycle = state.get("cycle_attribution") or {}
    if _cycle.get("win_rate") is not None and _cycle["win_rate"] >= 60.0:
        output.score = min(100, output.score + 5)
        _notice = (f"📈 历史胜率 {_cycle['win_rate']}% ≥ 60%（已了结 "
                   f"{_cycle.get('closed_cycle_count') or 0} 周期），资金维度 +5 分")
        if _notice not in output.risk_list:
            output.risk_list.append(_notice)
    if _cycle.get("drag_rate") is not None and _cycle["drag_rate"] >= 30.0:
        output.score = max(0, output.score - 10)
        _notice = (f"⚠️ 历史拖累率 {_cycle['drag_rate']}% ≥ 30%（已了结 "
                   f"{_cycle.get('closed_cycle_count') or 0} 周期），资金维度 -10 分")
        if _notice not in output.risk_list:
            output.risk_list.append(_notice)
    # ---- v4.0 代码层推导 potential_flag（不信任 LLM 自报；factor 分值为 LLM 判断，flag 为事实换算）----
    _催化 = next((f.score for f in output.factors if f.factor == "催化"), 0)
    _动量 = next((f.score for f in output.factors if f.factor == "动量"), 0)
    output.potential_flag = bool(_催化 >= 7 and _动量 <= 4)

    # v4.0 六因子透明评分：detail 存 factors 列表 + potential_flag + cross_validation_note + final_advice
    detail = {
        "factors": [f.model_dump() for f in output.factors],
        "potential_flag": output.potential_flag,
        "cross_validation_note": output.cross_validation_note,
        "final_advice": output.final_advice,
    }
    # thinking 只进 trace（thinking_summary 透传），detail 业务表保持干净
    repo.upsert_score(
        code, name, today, float(output.score), output.grade,
        detail,
        output.risk_list,
        thinking_summary=(summarize_agentic_trace(agentic_trace) if agentic_trace else None),
    )
    state["score_result"] = output.model_dump()
    state["risk_notice"] = output.risk_list
    state["stage"] = "score"
    state["trace"] = [*state.get("trace", []),
                      f"打分完成: {output.score}分 {output.grade}级 "
                      f"潜力={output.potential_flag} 因子{len(output.factors)}项 风险{len(output.risk_list)}条"]
    logger.info("评分完成 %s: %s分 %s级 潜力=%s", code, output.score, output.grade,
                output.potential_flag)
    return state


def _compact(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
