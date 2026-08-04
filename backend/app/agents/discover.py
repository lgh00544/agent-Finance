"""
DiscoverAgent 潜力发掘 - LangGraph 节点
【刚性代码逻辑】硬过滤（ST/退市/停牌/流动性，客观事实）、指标计算、新闻检索、落库
【交由模型推理的业务逻辑】波段潜力判断、候选理由、风险初判（全部在 LLM）
流转：hard_filter → llm_shortlist → enrich_news → llm_final → 落库
"""
import logging

import pandas as pd

from app.agents.common import agent_call
from agent_prompts import discover_prompt
from app.agents.schemas import DiscoverCandidate, DiscoverOutput
from app.core.config import settings
from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_TABLE_COLS = ["code", "name", "price", "change_pct", "amount", "volume_ratio", "turnover_rate",
               "pe_dynamic", "pb", "total_mv", "circ_mv", "pct_change_60d", "pct_change_ytd"]


def apply_hard_filter(spot: pd.DataFrame, suspended_codes: set[str],
                      min_amount: float, top_n: int) -> pd.DataFrame:
    """刚性硬过滤 + 客观排序（纯函数，可单测）【刚性代码逻辑】
    仅依据客观事实：ST/退市名称、停牌名单、成交额阈值；排序按成交额。
    """
    if spot is None or spot.empty:
        return spot
    df = spot.copy()
    df["code"] = df["code"].astype(str).str.zfill(6)
    for col in ["amount", "price", "change_pct", "volume_ratio", "turnover_rate",
                "pe_dynamic", "pb", "total_mv", "circ_mv", "pct_change_60d", "pct_change_ytd"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ---- 刚性过滤（客观事实，无博弈空间）----
    if "name" in df.columns:
        df = df[~df["name"].astype(str).str.contains("ST|退", na=False)]
    if "amount" in df.columns:
        df = df[(df["amount"].notna()) & (df["amount"] >= min_amount)]
    if suspended_codes:
        df = df[~df["code"].isin(suspended_codes)]

    # ---- 客观排序取前 N（按成交额，非主观筛选）----
    if "amount" in df.columns:
        df = df.sort_values("amount", ascending=False)
    df = df.head(top_n)

    return df.where(pd.notna(df), None)


def hard_filter(state: StockAgentState) -> StockAgentState:
    """节点1：刚性硬过滤 + 客观排序【刚性代码逻辑】"""
    source = AkshareSource()
    spot = source.fetch_spot_universe()
    if spot is None or spot.empty:
        state["error"] = "全市场快照拉取失败"
        return state

    suspended_codes: set[str] = set()
    try:
        suspended = source.fetch_suspended()
        if not suspended.empty and "code" in suspended.columns:
            suspended_codes = set(suspended["code"].astype(str).str.zfill(6))
    except Exception as exc:  # noqa: BLE001 停牌表失败不阻塞主链路
        logger.warning("停牌表拉取失败，跳过: %s", exc)

    df = apply_hard_filter(spot, suspended_codes, settings.min_amount, settings.discover_top_n)
    universe = df.to_dict(orient="records")
    state["universe"] = universe
    state["trace"] = [*state.get("trace", []), f"硬过滤: 全市场→{len(universe)}只"]
    logger.info("硬过滤完成: 保留 %s 只", len(universe))
    return state


def _market_context(source: AkshareSource) -> str:
    """大盘 + 行业板块行情摘要（原始数据打包）"""
    lines = []
    try:
        idx = source.fetch_index_daily("sh000001",
                                       _days_ago(30), _today())
        if not idx.empty:
            if "change_pct" not in idx.columns:  # 新浪降级无涨跌幅列，按收盘价补算
                idx["change_pct"] = idx["close"].pct_change() * 100
            last = idx.tail(5)[["date", "close", "change_pct"]].to_dict(orient="records")
            lines.append("上证指数近5日: " + str(last))
    except Exception as exc:  # noqa: BLE001
        logger.warning("大盘数据拉取失败: %s", exc)
    try:
        board = source.fetch_industry_spot()
        if not board.empty and "change_pct" in board.columns:
            board = board.dropna(subset=["change_pct"])
            top = board.nlargest(5, "change_pct")
            bottom = board.nsmallest(5, "change_pct")
            lines.append("行业板块涨幅前5: " + str(top[["board_name", "change_pct"]].to_dict(orient="records")))
            lines.append("行业板块跌幅前5: " + str(bottom[["board_name", "change_pct"]].to_dict(orient="records")))
    except Exception as exc:  # noqa: BLE001
        logger.warning("行业板块拉取失败: %s", exc)
    return "\n".join(lines) if lines else "（市场数据暂不可用）"


def _table_text(records: list[dict]) -> str:
    """数据表压缩为文本（保留全部原始数值，供 LLM 研判）"""
    if not records:
        return "（无数据）"
    header = ",".join(_TABLE_COLS)
    rows = []
    for r in records:
        vals = [str(r.get(c, "") if r.get(c) is not None else "") for c in _TABLE_COLS]
        rows.append(",".join(vals))
    return "\n".join([header, *rows])


def llm_shortlist(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 从初筛表中挑选波段潜力候选"""
    universe = state.get("universe") or []
    if not universe:
        return state

    source = AkshareSource()
    date_key = state.get("trade_date", _today())
    output = agent_call(
        agent="discover",
        cache_key=f"shortlist:{date_key}",
        system_prompt=discover_prompt.SYSTEM_PROMPT,
        user_prompt=discover_prompt.build_user_prompt(
            _table_text(universe), _market_context(source)),
        schema=DiscoverOutput,
        ttl_seconds=86400,
    )
    shortlist = [c.model_dump() for c in output.candidates]
    state["shortlist"] = shortlist
    state["trace"] = [*state.get("trace", []), f"LLM 初选: {len(shortlist)}只"]
    logger.info("LLM 初选 %s 只: %s", len(shortlist),
                [c["stock_code"] for c in shortlist])
    return state


def enrich_news(state: StockAgentState) -> StockAgentState:
    """节点3：候选股新闻检索（落库 + 向量索引 + 语义检索）【刚性代码逻辑】"""
    source = AkshareSource()
    vector_store = get_vector_store()
    enrichment: dict[str, list[dict]] = {}
    for cand in state.get("shortlist") or []:
        code = cand["stock_code"]
        name = cand["stock_name"]
        try:
            news_df = source.fetch_news(code)
            stored = []
            for _, row in news_df.iterrows():
                title = str(row.get("title") or "").strip()
                if not title:
                    continue
                content = str(row.get("content") or "")
                is_new = repo.add_news(code, name, title, content,
                                       str(row.get("source") or ""),
                                       str(row.get("url") or ""),
                                       str(row.get("published_at") or ""))
                if is_new:
                    stored.append({"title": title, "content": content[:500],
                                   "published_at": str(row.get("published_at") or "")})
            if stored:
                vector_store.index_news(code, stored)
            related = vector_store.search_related(code, f"{name} 业绩 风险 公告 新闻", top_k=5)
            enrichment[code] = related or stored[:5]
        except Exception as exc:  # noqa: BLE001 单股新闻失败不阻塞
            logger.warning("候选 %s 新闻检索失败: %s", code, exc)
            enrichment[code] = []
    state["enrichment"] = enrichment
    state["trace"] = [*state.get("trace", []), "新闻检索完成"]
    return state


def llm_final(state: StockAgentState) -> StockAgentState:
    """节点4：结合新闻 LLM 最终确认 + 落库"""
    shortlist = state.get("shortlist") or []
    enrichment = state.get("enrichment") or {}
    if not shortlist:
        return state

    table = _table_text(shortlist)
    news_ctx = []
    for cand in shortlist:
        news = enrichment.get(cand["stock_code"], [])
        news_ctx.append(f"{cand['stock_code']} {cand['stock_name']}: " +
                        ("；".join(f"{n.get('title')}({n.get('published_at')})" for n in news) or "（无相关新闻）"))
    news_text = "\n".join(news_ctx) if news_ctx else "（无）"

    date_key = state.get("trade_date", _today())
    output = agent_call(
        agent="discover_final",
        cache_key=f"final:{date_key}",
        system_prompt=discover_prompt.SYSTEM_PROMPT,
        user_prompt=discover_prompt.build_final_prompt(_table_text(shortlist), news_text),
        schema=DiscoverOutput,
        ttl_seconds=86400,
    )

    trade_date = state.get("trade_date", _today())
    candidates = []
    for rank, cand in enumerate(output.candidates, start=1):
        item = cand.model_dump()
        candidates.append(item)
        snapshot = next((u for u in state.get("universe") or []
                         if u.get("code") == cand.stock_code), {})
        repo.upsert_candidate(cand.stock_code, cand.stock_name, trade_date,
                              rank, [cand.reason], [cand.risk_notice], snapshot)
    state["candidates"] = candidates
    state["stage"] = "discover"
    state["trace"] = [*state.get("trace", []), f"落库候选: {len(candidates)}只"]
    logger.info("候选池落库完成: %s 只", len(candidates))
    return state


def _today() -> str:
    import time

    return time.strftime("%Y-%m-%d")


def _days_ago(n: int) -> str:
    import datetime

    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
