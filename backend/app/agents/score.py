"""
ScoreAgent 多维打分 - LangGraph 节点
【刚性代码逻辑】数据聚合（行情/财务/资金流/新闻）、纯数学指标计算、落库
【交由模型推理的业务逻辑】五维评分、A/B/C 分级、风险清单（全部在 LLM）
流转：collect_data → llm_score
"""
import logging
import time

from app.agents.common import agent_call
from agent_prompts import score_prompt
from app.agents.schemas import ScoreOutput
from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.indicator import compute_indicators
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_KLINE_DAYS = 250  # 约一年交易日


def collect_data(state: StockAgentState) -> StockAgentState:
    """节点1：聚合个股全部原始数据【刚性代码逻辑】"""
    code = state["stock_code"]
    source = AkshareSource()
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    # 行情与指标
    kline = source.fetch_daily_kline(code, _days_ago(_KLINE_DAYS), today)
    indicators = compute_indicators(kline)

    # 财务（最近4期）
    financial = source.fetch_financial(code)
    fin_rows = financial.head(4).to_dict(orient="records") if not financial.empty else []

    # 资金流（最近10日；东财接口不稳定，失败不阻塞打分）
    ff_rows = []
    try:
        fund_flow = source.fetch_fund_flow(code)
        ff_rows = fund_flow.tail(10).to_dict(orient="records") if not fund_flow.empty else []
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

    state["basic_info"] = {"stock_code": code, "trade_date": today,
                           "industry_spot": industry_rows}
    state["tech_index"] = indicators
    state["finance_data"] = fin_rows
    state["news_report"] = news_rows
    state["fund_flow_rows"] = ff_rows
    state["risk_notice"] = []
    state["trace"] = [*state.get("trace", []),
                      f"聚合完成: K线{len(kline)}行 财务{len(fin_rows)}期 资金流{len(ff_rows)}日 新闻{len(news_rows)}条"]
    return state


def llm_score(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 五维打分 + 落库"""
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
    }

    output = agent_call(
        agent="score",
        cache_key=f"{code}:{today}",
        system_prompt=score_prompt.SYSTEM_PROMPT,
        user_prompt=score_prompt.build_user_prompt(_compact(data_pack), preference_text),
        schema=ScoreOutput,
        ttl_seconds=86400,
    )

    repo.upsert_score(
        code, name, today, float(output.score), output.grade,
        {d.name: {"score": d.score, "comment": d.comment} for d in output.dimensions},
        output.risk_list,
    )
    state["score_result"] = output.model_dump()
    state["risk_notice"] = output.risk_list
    state["stage"] = "score"
    state["trace"] = [*state.get("trace", []),
                      f"打分完成: {output.score}分 {output.grade}级 风险{len(output.risk_list)}条"]
    logger.info("评分完成 %s: %s分 %s级", code, output.score, output.grade)
    return state


def _compact(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
