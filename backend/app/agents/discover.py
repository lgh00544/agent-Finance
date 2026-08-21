"""
DiscoverAgent 潜力发掘 - LangGraph 节点
【刚性代码逻辑】硬过滤（ST/退市/停牌/流动性，客观事实）、指标计算、新闻检索、增量数据采集、落库
【交由模型推理的业务逻辑】市况评分、波段潜力判断、候选理由、风险初判（全部在 LLM）
流转：market_condition → hard_filter → llm_shortlist → enrich_news → enrich_data → llm_final → 落库
"""
import logging

import pandas as pd

from app.agents.common import ModelLevel, agent_call
from agent_prompts import discover_prompt, market_prompt
from app.agents.schemas import DiscoverCandidate, DiscoverOutput, MarketConditionOutput
from app.core.config import market_band_info, settings
from app.datasource.base import DataSource
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_TABLE_COLS = ["code", "name", "price", "change_pct", "amount", "volume_ratio", "turnover_rate",
               "pe_dynamic", "pb", "total_mv", "circ_mv", "pct_change_60d", "pct_change_ytd"]
# 威科夫相对结构列（初选阶段全量计算，随初筛表一并交给 LLM：只看相对位置/形态，不做任何阈值过滤）：
#   dist_52w_high_pct 距52周高点%  /  pos_52w 52周区间位置%  /  ma20_pos_pct·ma60_pos_pct 现价对均线%
#   vol_5_20 5日均量÷20日均量（放/缩量相对变化）  /  pct_change_5d 5日斜率（与 60d 对照判阶段）
_WYCKOFF_COLS = ["dist_52w_high_pct", "pos_52w", "ma20_pos_pct", "ma60_pos_pct",
                 "vol_5_20", "pct_change_5d"]
_TABLE_COLS = [*_TABLE_COLS, *_WYCKOFF_COLS]
# v2.0 增量数据列（候选富化后追加在初筛列之后，随原始数据交给 LLM 研判；
# pct_change_5d/dist_52w_high_pct 已并入初筛威科夫列，此处不重复）
_ENRICH_COLS = ["industry", "intraday_narrow_pct",
                "super_large_net", "large_net", "medium_net", "small_net",
                "main_net_3d", "main_net_5d", "main_net_10d",
                "holder_change_pct", "inst_hold_pct"]
_MONEY_COLS = {"super_large_net", "large_net", "medium_net", "small_net",
               "main_net_3d", "main_net_5d", "main_net_10d"}

# 候选增量采集/新闻检索并行阈值与上限（参考 router._PARALLEL_SCORE 模式；
# 数据源限流器按 kind 全局锁串行化发起频率，并发只重叠网络往返，勿开过高）
_PARALLEL_MIN = 3
_PARALLEL_MAX = 8

# 初筛表金额列统一亿/万压缩（原始整数 10+ 字符/值 → 5 字符内；信息不减，
# 大幅缩减 LLM 输入体积，规避 DeepSeek 长输入偶发空响应，见 README 风险提示）
_MONEY_FMT_COLS = {"amount", "total_mv", "circ_mv"}


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
    source = get_datasource()
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


# ==================== 市况评分（v2.0 前置步骤） ====================

def _market_condition_raw() -> str:
    """市况评分输入原始数据：指数位置/板块结构/资金方向/情绪指标/风险维度
    【刚性代码逻辑】只打包客观数据，五维打分全部由 LLM 完成"""
    source = get_datasource()
    lines = []
    today = _today()
    try:
        idx = source.fetch_index_daily("sh000001", _days_ago(90), today)
        if idx is not None and not idx.empty:
            idx = idx.dropna(subset=["close"]).reset_index(drop=True)
            close = float(idx.iloc[-1]["close"])
            win = idx["close"].tail(60)
            hi60, lo60 = float(win.max()), float(win.min())
            pos = (close - lo60) / (hi60 - lo60) * 100 if hi60 > lo60 else None
            pos_txt = f"{pos:.0f}%" if pos is not None else "（数据不足）"
            lines.append(f"上证指数: 收盘 {close:.2f}，近60日区间位置 {pos_txt}"
                         f"（区间最高 {hi60:.2f} / 最低 {lo60:.2f}）")
            lines.append("上证指数近5日: " + str(idx.tail(5)[["date", "close"]].to_dict(orient="records")))
    except Exception as exc:  # noqa: BLE001 单数据源失败不阻塞
        logger.warning("市况-指数数据失败: %s", exc)
    try:
        board = source.fetch_industry_spot()
        if board is not None and not board.empty and "change_pct" in board.columns:
            board = board.dropna(subset=["change_pct"])
            up_n = int((board["change_pct"] > 0).sum())
            down_n = int((board["change_pct"] < 0).sum())
            lines.append(f"行业板块结构: 共 {len(board)} 个板块，上涨 {up_n} / 下跌 {down_n}")
            lines.append("板块涨幅前5: " + str(board.nlargest(5, "change_pct")[["board_name", "change_pct"]].to_dict(orient="records")))
            lines.append("板块跌幅前5: " + str(board.nsmallest(5, "change_pct")[["board_name", "change_pct"]].to_dict(orient="records")))
    except Exception as exc:  # noqa: BLE001
        logger.warning("市况-板块数据失败: %s", exc)
    try:
        mf = source.fetch_market_fund_flow()
        if mf:
            lines.append("大盘资金流: " + str(mf))
    except Exception as exc:  # noqa: BLE001
        logger.warning("市况-大盘资金流失败: %s", exc)
    try:
        spot = source.fetch_spot_universe()
        if spot is not None and not spot.empty and "change_pct" in spot.columns:
            chg = spot["change_pct"].dropna()
            up_n = int((chg > 0).sum())
            down_n = int((chg < 0).sum())
            flat_n = int((chg == 0).sum())
            lines.append(f"全市场涨跌分布: 上涨 {up_n} / 平盘 {flat_n} / 下跌 {down_n}"
                         f"（涨幅≥9.5% 约 {int((chg >= 9.5).sum())} 家，跌幅≤-9.5% 约 {int((chg <= -9.5).sum())} 家）")
    except Exception as exc:  # noqa: BLE001
        logger.warning("市况-情绪数据失败: %s", exc)
    return "\n".join(lines) if lines else "（市况数据暂不可用）"


def market_condition(state: StockAgentState) -> StockAgentState:
    """节点0：市况评分前置步骤（v2.0）
    【刚性代码逻辑】打包原始数据 → LLM 五维打分 → 代码仅求和（0-50）并按人工档位映射候选池上限 → 落库"""
    date_key = state.get("trade_date", _today())
    total: int | None = None
    try:
        output = agent_call(
            agent="market_condition",
            cache_key=f"market:v2:{date_key}",
            system_prompt=market_prompt.SYSTEM_PROMPT,
            user_prompt=market_prompt.build_user_prompt(_market_condition_raw()),
            schema=MarketConditionOutput,
            ttl_seconds=86400,
            model_level=ModelLevel.DEEP,
        )
        total = output.dim_index + output.dim_sector + output.dim_money \
            + output.dim_sentiment + output.dim_risk
        cap, band = market_band_info(total)
        dims = {"index": output.dim_index, "sector": output.dim_sector,
                "money": output.dim_money, "sentiment": output.dim_sentiment,
                "risk": output.dim_risk}
        state["market_condition"] = {
            "trade_date": date_key, "total_score": total, "band": band, "cap": cap,
            "dims": dims, "summary": output.summary,
        }
        state["market_cap"] = cap
        repo.upsert_market_condition(date_key, total, dims, cap, output.summary)
        logger.info("市况评分 %s 分（%s），候选池上限 %s 只", total, band, cap)
    except Exception as exc:  # noqa: BLE001 市况失败不阻塞主链路，按默认上限继续
        logger.warning("市况评分失败，按默认档位继续: %s", exc)
        cap, band = market_band_info(999)
        state["market_condition"] = None
        state["market_cap"] = cap
    score_txt = f"{total}分" if total is not None else "失败"
    state["trace"] = [*state.get("trace", []),
                      f"市况评分: {score_txt}（候选池上限 {cap} 只）"]
    return state


def _market_note(state: StockAgentState) -> str:
    """市况摘要文本（注入 LLM 提示，告知当日候选池规模约束）"""
    mc = state.get("market_condition")
    if not mc:
        return f"今日市况评分暂不可用，候选池按默认上限 {state.get('market_cap') or 20} 只执行。"
    return (f"今日市况评分 {mc['total_score']} 分（{mc['band']}），"
            f"当日候选池上限 {mc['cap']} 只，市况综述：{mc['summary']}")


def _market_context(source: DataSource) -> str:
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


def _cell_text(col: str, value) -> str:
    """单元格文本：金额列亿/万压缩，其余原样（纯展示格式，不含任何判断）"""
    if value is None:
        return ""
    if col in _MONEY_FMT_COLS:
        return _fmt_money(value)
    return str(value)


def _table_text(records: list[dict]) -> str:
    """数据表压缩为文本（金额列亿/万格式，信息不减体积更小，供 LLM 研判）"""
    if not records:
        return "（无数据）"
    header = ",".join(_TABLE_COLS)
    rows = []
    for r in records:
        vals = [_cell_text(c, r.get(c)) for c in _TABLE_COLS]
        rows.append(",".join(vals))
    return "\n".join([header, *rows])


def _wyckoff_columns(source: DataSource, code: str) -> dict:
    """威科夫相对结构列（单股纯数学，零判断）：距52周高低/区间位置/MA20·MA60相对位置/
    量能相对对比/5日斜率。只喂数据不做过滤；单股失败或样本不足返回空 dict 不阻塞。"""
    out: dict = {}
    try:
        kline = source.fetch_daily_kline(code, _days_ago(400), _today())
        if kline is None or kline.empty:
            return out
        kline = kline.dropna(subset=["close"]).reset_index(drop=True)
        if len(kline) < 6:
            return out
        close = float(kline.iloc[-1]["close"])
        high52 = float(kline["high"].max())
        low52 = float(kline["low"].min())
        out["dist_52w_high_pct"] = round((close / high52 - 1) * 100, 2) if high52 else None
        if high52 > low52:
            out["pos_52w"] = round((close - low52) / (high52 - low52) * 100, 1)
        if len(kline) >= 20:
            ma20 = float(kline["close"].tail(20).mean())
            out["ma20_pos_pct"] = round((close / ma20 - 1) * 100, 2) if ma20 else None
        if len(kline) >= 60:
            ma60 = float(kline["close"].tail(60).mean())
            out["ma60_pos_pct"] = round((close / ma60 - 1) * 100, 2) if ma60 else None
        if "volume" in kline.columns and len(kline) >= 20:
            v5 = float(kline["volume"].tail(5).mean())
            v20 = float(kline["volume"].tail(20).mean())
            out["vol_5_20"] = round(v5 / v20, 2) if v20 else None
        out["pct_change_5d"] = round((close / float(kline.iloc[-6]["close"]) - 1) * 100, 2)
    except Exception as exc:  # noqa: BLE001 单股失败留空，不阻塞
        logger.warning("候选 %s 威科夫列计算失败: %s", code, exc)
    return out


_WYCKOFF_BUDGET = 600  # 威科夫整体超时预算（秒）：东财降级时宁可跳过也不无限等（防卡死 2 小时复现）


def _fill_wyckoff_columns(source: DataSource, universe: list[dict]) -> None:
    """初筛表威科夫列前置：对全部候选补算相对结构列（只喂数据，不做阈值过滤）。
    并发拉日K（限流器按 kind 全局锁控制发起频率，网络往返并行；日K 3600s 缓存
    后续 enrich_data 直接复用，不重复请求）；单股失败留空不阻塞；
    整体超时预算 _WYCKOFF_BUDGET 秒，超时未算完的股打 WARNING 跳过（空结构列继续）。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

    def _work(u: dict) -> tuple[str, dict]:
        code = str(u.get("code") or "")
        return code, _wyckoff_columns(source, code)

    if len(universe) < _PARALLEL_MIN:
        for u in universe:
            u.update(_work(u)[1])
        return
    done = 0
    with ThreadPoolExecutor(max_workers=min(_PARALLEL_MAX, len(universe))) as pool:
        futures = [pool.submit(_work, u) for u in universe]
        try:
            for fut in as_completed(futures, timeout=_WYCKOFF_BUDGET):
                code, cols = fut.result()
                done += 1
                for u in universe:
                    if str(u.get("code")) == code:
                        u.update(cols)
                        break
        except TimeoutError:
            skipped = len(futures) - done
            logger.warning("威科夫列计算整体超时 %ds，已算 %d 只，跳过 %d 只（空结构列继续）",
                           _WYCKOFF_BUDGET, done, skipped)
            pool.shutdown(wait=False, cancel_futures=True)  # 先丢未开始任务，尽快释放线程
    logger.info("威科夫相对结构列计算完成: %s 只", done)


def _merge_universe_fields(shortlist: list[dict], universe: list[dict]) -> None:
    """LLM 初选输出合并全市场快照字段（行情 13 列 + 威科夫列）：
    v3.0 schema 后 LLM 输出不含行情字段，终选表需补全原始数值；
    仅补 LLM 输出缺失的列，不覆盖 LLM 自带字段。"""
    uni_map = {str(u.get("code")): u for u in universe}
    for cand in shortlist:
        u = uni_map.get(str(cand.get("stock_code"))) or {}
        cand["code"] = cand.get("stock_code")
        cand["name"] = cand.get("stock_name")
        for col in _TABLE_COLS:
            if cand.get(col) is None and u.get(col) is not None:
                cand[col] = u.get(col)


def llm_shortlist(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 从初筛表中挑选波段潜力候选
    （初选前为全表补算威科夫相对结构列——只喂数据不做过滤，LLM 才能判断吸筹末期/拉升初期）"""
    universe = state.get("universe") or []
    if not universe:
        return state

    source = get_datasource()
    _fill_wyckoff_columns(source, universe)
    date_key = state.get("trade_date", _today())
    output = agent_call(
        agent="discover",
        cache_key=f"shortlist:v2:{date_key}",
        system_prompt=discover_prompt.SYSTEM_PROMPT,
        user_prompt=discover_prompt.build_user_prompt(
            _table_text(universe), _market_context(source), _market_note(state)),
        schema=DiscoverOutput,
        ttl_seconds=86400,
        # 初选用深度模型：初筛 300 只 × 19 列（含威科夫列）输入约 50k tokens，
        # flash 上下文/输出预算在长输入下必空响应（README 风险提示已记录；
        # 13 列时代已边缘，加威科夫列后 24 连败实测确认）。chat 上下文大 2-4 倍，
        # 初选仅 1 次调用，速度差 1-2 分钟换稳定输出，缓存键按模型隔离不冲突。
        model_level=ModelLevel.DEEP,
    )
    shortlist = [c.model_dump() for c in output.candidates]
    _merge_universe_fields(shortlist, universe)  # 补全行情+威科夫列，终选表复用
    state["shortlist"] = shortlist
    state["trace"] = [*state.get("trace", []),
                      f"LLM 初选: {len(shortlist)}只（威科夫列 {len(_WYCKOFF_COLS)} 项前置）"]
    logger.info("LLM 初选 %s 只: %s", len(shortlist),
                [c["stock_code"] for c in shortlist])
    return state


def enrich_news(state: StockAgentState) -> StockAgentState:
    """节点3：候选股新闻检索（落库 + 向量索引 + 语义检索）【刚性代码逻辑】
    并发拉新闻+add_news 落库（repo 每调用独立 SessionLocal，线程安全）；
    向量索引/语义检索串行执行（Qdrant 共享客户端并发写有风险），先拉完再统一索引。"""
    source = get_datasource()
    vector_store = get_vector_store()
    shortlist = state.get("shortlist") or []

    def _fetch_news(cand: dict) -> tuple[str, list[dict]]:
        code, name = cand["stock_code"], cand["stock_name"]
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
            return code, stored
        except Exception as exc:  # noqa: BLE001 单股新闻失败不阻塞
            logger.warning("候选 %s 新闻拉取失败: %s", code, exc)
            return code, []

    # 并发拉取 + 落库（保持输入顺序）
    fetched: dict[str, list[dict]] = {}
    if len(shortlist) >= _PARALLEL_MIN:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(_PARALLEL_MAX, len(shortlist))) as pool:
            for code, stored in pool.map(_fetch_news, shortlist):
                fetched[code] = stored
    else:
        for cand in shortlist:
            code, stored = _fetch_news(cand)
            fetched[code] = stored

    # 串行：向量索引 + 语义检索（Qdrant 并发写风险，务必串行）
    enrichment: dict[str, list[dict]] = {}
    for cand in shortlist:
        code = cand["stock_code"]
        name = cand["stock_name"]
        try:
            stored = fetched.get(code) or []
            if stored:
                vector_store.index_news(code, stored)
            related = vector_store.search_related(code, f"{name} 业绩 风险 公告 新闻", top_k=5)
            enrichment[code] = related or stored[:5]
        except Exception as exc:  # noqa: BLE001 单股向量检索失败不阻塞
            logger.warning("候选 %s 新闻向量检索失败: %s", code, exc)
            enrichment[code] = fetched.get(code, [])[:5]
    state["enrichment"] = enrichment
    state["trace"] = [*state.get("trace", []), f"新闻检索完成（并行 {len(shortlist)} 只）"]
    return state


# ==================== 候选增量数据采集（v2.0） ====================

def _num(value) -> float | None:
    """宽松数值转换（None/NaN/非法值 → None），纯类型处理"""
    try:
        f = float(value)
        return None if f != f else f  # noqa: PLR0124 NaN 判定
    except (TypeError, ValueError):
        return None


def _fmt_money(value: float | None) -> str:
    """金额友好格式（元 → 亿/万），纯展示格式化，不含任何判断"""
    v = _num(value)
    if v is None:
        return ""
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.1f}万"
    return f"{v:.0f}"


def _enrich_candidate_data(source: DataSource, inst_map: dict,
                           code: str, name: str, trade_date: str) -> dict:
    """候选股增量数据（v2.0）：资金结构/阶段主力动向/股东面/52周区间/盘中涨幅收窄
    资金字段严格当日有效：仅透传 trade_date 当日的资金流；当日无有效数据一律不写入
    （读取层统一标注「当日资金数据暂不可用」，禁止 T-1 及更早历史数据降级填充）。
    【刚性代码逻辑】只做客观数据采集与纯数学计算（累计求和/区间极值/百分比），零判断"""
    out: dict = {}
    try:
        info = source.fetch_stock_info(code)
        out["industry"] = str(info.get("行业") or "") if info else ""
    except Exception as exc:  # noqa: BLE001 单项失败不影响其余字段
        logger.warning("候选 %s 基本信息失败: %s", code, exc)
    try:
        kline = source.fetch_daily_kline(code, _days_ago(400), _today())
        if kline is not None and not kline.empty:
            kline = kline.dropna(subset=["close", "high", "low"]).reset_index(drop=True)
            if len(kline) >= 2:
                close, prev_close = float(kline.iloc[-1]["close"]), float(kline.iloc[-2]["close"])
                high52, low52 = float(kline["high"].max()), float(kline["low"].min())
                out["high_52w"] = round(high52, 2)
                out["low_52w"] = round(low52, 2)
                out["dist_52w_high_pct"] = round((close / high52 - 1) * 100, 2) if high52 else None
                if len(kline) >= 6:
                    out["pct_change_5d"] = round((close / float(kline.iloc[-6]["close"]) - 1) * 100, 2)
                # 盘中涨幅收窄 = 当日最高涨幅 - 收盘涨幅（纯数学，供 LLM 判定脉冲题材）
                out["intraday_narrow_pct"] = round((float(kline.iloc[-1]["high"]) - close) / prev_close * 100, 2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("候选 %s 日K增量失败: %s", code, exc)
    try:
        flow = source.fetch_fund_flow(code)
        if flow is not None and not flow.empty and "date" in flow.columns:
            # 严格当日有效：只取 trade_date 当日资金流；当日无有效数据 → 不写入任何资金字段，
            # 由读取层统一标注「当日资金数据暂不可用」。禁止 T-1 及更早历史数据降级填充。
            today = flow.loc[flow["date"].astype(str).str.slice(0, 10) == trade_date]
            if not today.empty:
                row = today.iloc[-1]
                for col, key in [("super_large_net", "super_large_net"), ("large_net", "large_net"),
                                 ("medium_net", "medium_net"), ("small_net", "small_net")]:
                    if col in flow.columns:
                        v = _num(row.get(col))
                        if v is not None:  # 仅当日有效值落库，None/NaN 视为缺失不携带
                            out[key] = v
                # 阶段主力累计：以「当日」为主锚点的近 3/5/10 日窗口；
                # 当日主力净流入无效则不计算（防历史数据冒充当日累计）
                if "main_net_inflow" in flow.columns and _num(row.get("main_net_inflow")) is not None:
                    vals = flow["main_net_inflow"].dropna().astype(float)
                    out["main_net_3d"] = round(float(vals.tail(3).sum()), 2)
                    out["main_net_5d"] = round(float(vals.tail(5).sum()), 2)
                    out["main_net_10d"] = round(float(vals.tail(10).sum()), 2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("候选 %s 资金流增量失败: %s", code, exc)
    try:
        inst = inst_map.get(code) or {}
        if inst:
            out["inst_hold_pct"] = _num(inst.get("float_pct"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("候选 %s 机构持股失败: %s", code, exc)
    try:
        gdhs = source.fetch_shareholder_detail(code)
        if gdhs.get("holder_change_pct") is not None:
            out["holder_change_pct"] = _num(gdhs.get("holder_change_pct"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("候选 %s 股东户数失败: %s", code, exc)
    return out


def _final_table_text(shortlist: list[dict], data_enrichment: dict) -> str:
    """初选表（13 列）+ 候选增量数据（v2.0 列）合并为一个紧凑文本表"""
    if not shortlist:
        return "（无数据）"
    cols = [*_TABLE_COLS, *_ENRICH_COLS]
    rows = []
    for r in shortlist:
        extra = data_enrichment.get(r.get("code")) or {}
        vals = [_cell_text(c, r.get(c)) for c in _TABLE_COLS]
        for c in _ENRICH_COLS:
            v = extra.get(c)
            if v is None or v == "":
                vals.append("")
            elif c in _MONEY_COLS:
                vals.append(_fmt_money(v))
            else:
                vals.append(str(v))
        rows.append(",".join(vals))
    return "\n".join([",".join(cols), *rows])


def enrich_data(state: StockAgentState) -> StockAgentState:
    """节点3.5：候选股增量数据采集（资金结构/主力动向/股东面/52周区间）
    【刚性代码逻辑】只采集原始数据 + 纯数学计算，不判断；单股失败不阻塞。
    候选 ≥3 只线程池并发（上限 8）：只并行拉数据+计算，不碰 DB/向量库；
    结果按 shortlist 原顺序重建，LLM 看到的行序不变。"""
    source = get_datasource()
    inst_map: dict = {}
    try:
        inst_map = source.fetch_institute_hold_map()
    except Exception as exc:  # noqa: BLE001 机构持股全景失败不阻塞
        logger.warning("机构持股全景拉取失败，跳过: %s", exc)
    shortlist = state.get("shortlist") or []

    def _work(cand: dict) -> tuple[str, dict]:
        code = cand["stock_code"]
        try:
            return code, _enrich_candidate_data(source, inst_map, code,
                                                cand.get("stock_name", ""),
                                                state.get("trade_date", _today()))
        except Exception as exc:  # noqa: BLE001 单股失败不阻塞
            logger.warning("候选 %s 增量数据采集失败: %s", code, exc)
            return code, {}

    enriched: dict[str, dict] = {}
    if len(shortlist) >= _PARALLEL_MIN:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(_PARALLEL_MAX, len(shortlist))) as pool:
            for code, data in pool.map(_work, shortlist):  # map 保持输入顺序
                enriched[code] = data
    else:
        for cand in shortlist:
            code, data = _work(cand)
            enriched[code] = data
    state["data_enrichment"] = enriched
    state["trace"] = [*state.get("trace", []),
                      f"候选增量数据采集完成（并行 {len(shortlist)} 只）"]
    return state


def llm_final(state: StockAgentState) -> StockAgentState:
    """节点4：结合新闻+增量数据 LLM 最终确认 + 落库"""
    shortlist = state.get("shortlist") or []
    enrichment = state.get("enrichment") or {}
    data_enrichment = state.get("data_enrichment") or {}
    if not shortlist:
        return state

    table = _final_table_text(shortlist, data_enrichment)
    news_ctx = []
    for cand in shortlist:
        news = enrichment.get(cand["stock_code"], [])
        news_ctx.append(f"{cand['stock_code']} {cand['stock_name']}: " +
                        ("；".join(f"{n.get('title')}({n.get('published_at')})" for n in news) or "（无相关新闻）"))
    news_text = "\n".join(news_ctx) if news_ctx else "（无）"

    # 游资聚合数据注入（阶段3）：逐候选聚合龙虎榜流水 → 注入文本段（无数据返回空，LLM 保持标中性）
    hm_aggs = {}
    date_key = state.get("trade_date", _today())
    try:
        from app.services import hot_money as hot_money_svc
        for cand in shortlist:
            agg = hot_money_svc.aggregate_for_stock(cand["stock_code"], cand["stock_name"], date_key)
            if agg:
                hm_aggs[cand["stock_code"]] = agg
    except Exception as exc:  # noqa: BLE001 游资数据聚合失败不阻塞挖掘主链路
        logger.warning("游资聚合失败（降级跳过）: %s", exc)
    hm_text = hot_money_svc.build_hot_money_context(hm_aggs, date_key) if hm_aggs else ""

    # 前瞻兑现对照事实注入（第 5 子 Agent 输入切片）：逐候选离组 延续/回归/回吐 判据的客观事实。
    # 纯统计零 LLM（track_verify.build_horizon_context）；空串整段省略（终选退回今日行为，不阻塞）。
    try:
        from app.services.track_verify import build_horizon_context
        horizon_text = build_horizon_context(shortlist, data_enrichment)
    except Exception as exc:  # noqa: BLE001 组装失败降级省略前瞻段，不阻塞终选
        logger.warning("前瞻对照事实组装失败（省略前瞻段）: %s", exc)
        horizon_text = ""

    cap = state.get("market_cap")
    output = agent_call(
        agent="discover_final",
        cache_key=f"final:v2:{date_key}:h{repo.hot_money_fingerprint()}",
        system_prompt=discover_prompt.SYSTEM_PROMPT,
        user_prompt=discover_prompt.build_final_prompt(
            table, news_text, cap=cap, market_note=_market_note(state),
            hot_money_context=hm_text, horizon_context=horizon_text),
        schema=DiscoverOutput,
        ttl_seconds=86400,
        model_level=ModelLevel.DEEP,
    )

    # 市况档位上限（人工映射）：按 LLM 输出优先级客观截断（LLM 输出已按优先级排序）
    final_list = output.candidates
    if cap and len(final_list) > cap:
        final_list = final_list[:cap]

    trade_date = state.get("trade_date", _today())
    candidates = []
    for rank, cand in enumerate(final_list, start=1):
        # 前瞻硬兜底（pydantic schema 无字段间约束，prompt 软约束不够，必须代码硬兜底防 LLM 自作主张）：
        # 回吐 + 清晰度高/中 → 不得「强烈推荐」，强制降档建议关注 + 关注类型观察
        clarity = (cand.horizon_clarity or "").strip()
        if cand.horizon_bias == "回吐" and clarity in ("高", "中") \
                and cand.confidence_tier == "强烈推荐":
            cand.confidence_tier = "建议关注"
            cand.focus_type = "观察"
            logger.warning("[前瞻兜底] %s 回吐+清晰度%s → 强烈推荐降档建议关注",
                           cand.stock_code, clarity)
        item = cand.model_dump()
        candidates.append(item)
        snapshot = next((u for u in state.get("universe") or []
                         if u.get("code") == cand.stock_code), {})
        new_detail = {
            "confidence_tier": cand.confidence_tier, "confidence_pct": cand.confidence_pct,
            "stock_type": cand.stock_type,
            # v3.0 白盒维度归因（主结论）：dimensions 数组 + final_advice 综合评估
            "dimensions": [d.model_dump() for d in cand.dimensions],
            "final_advice": cand.final_advice,
            "macro_view": cand.macro_view, "meso_view": cand.meso_view,
            "micro_view": cand.micro_view, "volume_analysis": cand.volume_analysis,
            "risks": cand.risks, "focus_type": cand.focus_type,
            "tech_view": cand.tech_view, "price_levels": cand.price_levels,
            "position_hint": cand.position_hint,
            "rule_refs": cand.rule_refs,
            # 前瞻兑现三态（第 5 子 Agent 收口；缺则用 schema 默认，禁止静默丢键）
            "horizon_bias": cand.horizon_bias,
            "horizon_clarity": cand.horizon_clarity,
            "horizon_note": cand.horizon_note,
            "enriched": data_enrichment.get(cand.stock_code) or {},
        }
        # 防丢键：防御式 merge，保留既有 detail 中的旧字段（本批次只新增字段，不整 dict 覆盖）。
        # 仅在本函数内封装；不改 repo.upsert_candidate 内部（被 Score/Monitor/ExperienceWorker 共用）。
        existing = repo.get_candidate_detail(cand.stock_code, trade_date) or {}
        detail = {**existing, **new_detail}
        repo.upsert_candidate(cand.stock_code, cand.stock_name, trade_date,
                              rank, [cand.reason], [cand.risk_notice], snapshot, detail)
    # 当日快照替换：删除当日不在本次执行结果中的残留候选，保证当日只保留最新一次执行产物。
    # 结果为空（LLM 无输出/数据源故障）时保留既有快照，防止误清空当日候选造成数据丢失
    if candidates:
        removed = repo.replace_day_candidates({c["stock_code"] for c in candidates}, trade_date)
        if removed:
            logger.info("当日候选快照替换: 清理 %s 只残留", removed)
            state["trace"] = [*state.get("trace", []), f"清理当日残留: {removed}只"]
    else:
        logger.warning("最终确认结果为空，保留当日已有候选快照（防止数据源故障误清空）")
        state["trace"] = [*state.get("trace", []), "终选为空：保留当日已有候选快照"]
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
