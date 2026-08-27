"""
MarketIntelAgent 市场研判底座 - LangGraph 节点
【刚性代码逻辑】客观数据聚合（板块量比/大盘连续量比/避险进取归类/板块结构/指数位置/涨跌家数）
【交由模型推理的业务逻辑】阶段定性/核心矛盾/风险偏好/量能信号/操作含义/次日盯盘点（全部在 LLM）

定位：作为全部 agent（discover/score/position/monitor/sell/review/对话）的**参考维度**注入，
不强制改变任何 agent 判级；与 market_condition（打分→候选池上限）并存，不替代。
数据纪律：数据缺失如实标注（不编造量比/资金数字），研判置信度由 LLM 在文本中说明。
"""
import logging
import time
from datetime import datetime, timedelta

from agent_prompts import market_intel_prompt
from app.agents.common import ModelLevel, agent_call
from app.agents.schemas import MarketIntelOutput
from app.datasource.akshare_source import classify_board_groups
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState

logger = logging.getLogger(__name__)


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def collect_market_data() -> dict:
    """市场研判原始数据聚合（【刚性代码逻辑】只打包客观数据，研判全部由 LLM 完成）。

    各数据段独立 try/except：单段失败不影响整体（缺失字段在 raw 中标注「缺失」，
    绝不编造）。"""
    source = get_datasource()
    raw: dict = {"trade_date": _today(), "data_source": "akshare(东财/新浪)"}

    # 1) 上证指数位置 + 近 5 日（60 日区间位置）
    try:
        idx = source.fetch_index_daily("sh000001", _days_ago(90), _today())
        if idx is not None and not idx.empty:
            idx = idx.dropna(subset=["close"]).reset_index(drop=True)
            close = float(idx.iloc[-1]["close"])
            win = idx["close"].tail(60)
            hi60, lo60 = float(win.max()), float(win.min())
            pos = (close - lo60) / (hi60 - lo60) * 100 if hi60 > lo60 else None
            raw["index_close"] = close
            raw["index_pos_60d"] = f"{pos:.0f}%" if pos is not None else "（数据不足）"
            raw["index_recent_5d"] = idx.tail(5)[["date", "close", "change_pct"]].to_dict(
                orient="records") if "change_pct" in idx.columns else None
        else:
            raw["index_recent_5d"] = "（数据缺失）"
    except Exception as exc:  # noqa: BLE001 单数据段失败不阻塞整体
        logger.warning("研判-指数数据失败: %s", exc)
        raw["index_recent_5d"] = "（数据缺失）"

    # 2) 大盘连续量比（近 6 日，成交量比近似）
    try:
        vr = source.fetch_index_volume_ratios(days=6)
        if vr is not None and not vr.empty:
            raw["index_volume_ratios"] = vr.to_dict(orient="records")
        else:
            raw["index_volume_ratios"] = "（数据缺失）"
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-大盘量比失败: %s", exc)
        raw["index_volume_ratios"] = "（数据缺失）"

    # 3) 行业板块行情（涨跌结构 + 量比可用性 + 避险/进取归类）
    board = None
    try:
        board = source.fetch_industry_spot()
        if board is not None and not board.empty and "change_pct" in board.columns:
            board = board.dropna(subset=["change_pct"])
            up_n = int((board["change_pct"] > 0).sum())
            down_n = int((board["change_pct"] < 0).sum())
            raw["board_structure"] = f"共 {len(board)} 个板块，上涨 {up_n} / 下跌 {down_n}"
            show_cols = ["board_name", "change_pct"]
            if "volume_ratio" in board.columns:
                show_cols.append("volume_ratio")
                raw["board_volume_ratio_available"] = True
            else:
                raw["board_volume_ratio_available"] = False  # 数据缺失如实标注
            raw["board_top"] = board.nlargest(5, "change_pct")[show_cols].to_dict(orient="records")
            raw["board_bottom"] = board.nsmallest(5, "change_pct")[show_cols].to_dict(orient="records")
        else:
            raw["board_structure"] = "（数据缺失）"
            raw["board_volume_ratio_available"] = False
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-板块数据失败: %s", exc)
        raw["board_structure"] = "（数据缺失）"
        raw["board_volume_ratio_available"] = False

    # 4) 避险池 vs 进取池 资金归类（纯关键词归类 + 客观聚合）
    try:
        raw["risk_groups"] = classify_board_groups(board)
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-避险进取归类失败: %s", exc)
        raw["risk_groups"] = {"defensive": [], "aggressive": [], "unclassified": [],
                              "stats": {"defensive": None, "aggressive": None,
                                        "note": "归类数据缺失"}}

    # 5) 全市场涨跌家数（情绪）
    try:
        spot = source.fetch_spot_universe()
        if spot is not None and not spot.empty and "change_pct" in spot.columns:
            chg = spot["change_pct"].dropna()
            raw["market_advance_decline"] = {
                "up": int((chg > 0).sum()), "flat": int((chg == 0).sum()),
                "down": int((chg < 0).sum()),
                "up_9pct": int((chg >= 9.5).sum()), "down_9pct": int((chg <= -9.5).sum())}
        else:
            raw["market_advance_decline"] = "（数据缺失）"
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-涨跌家数失败: %s", exc)
        raw["market_advance_decline"] = "（数据缺失）"

    # 6) 隔夜美股（催化传导链数据源；1 次请求，60s 缓存）
    try:
        raw["us_market"] = source.fetch_us_market_overnight()
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-隔夜美股失败: %s", exc)
        raw["us_market"] = {"available": False, "note": "数据缺失"}

    # 7) 主线板块箱位（箱位双视角数据源；涨幅前5 + 进取池涨幅前3，去重限10）
    try:
        top_boards = []
        if raw.get("board_top"):
            top_boards = [b.get("board_name", "") for b in raw["board_top"] if b.get("board_name")]
        rg = raw.get("risk_groups") or {}
        # 修正：classify_board_groups 的 aggressive 是 list[str]（板块名本身），对字符串 .get()
        # 必抛 AttributeError → 整段被 except 捕获静默失效；直接取字符串（isinstance 防御）
        aggressive_boards = [b for b in (rg.get("aggressive") or []) if isinstance(b, str)][:3]
        board_list = list(dict.fromkeys(top_boards + aggressive_boards))[:10]  # 去重限10
        raw["board_box_positions"] = source.fetch_board_box_positions(board_list)
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-板块箱位失败: %s", exc)
        raw["board_box_positions"] = {"note": "数据缺失"}

    # 8) 两市总成交额量倍（量能成色数据源；东财口径，复用现有缓存）
    try:
        raw["market_total_ratio"] = source.fetch_market_total_volume_ratio()
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-两市量倍失败: %s", exc)
        raw["market_total_ratio"] = {"available": False, "note": "数据缺失"}

    # 9) 主线板块内个股抽样（个股三维验证数据源；涨幅前3板块成分股取涨幅前5只）
    try:
        if raw.get("board_top"):
            spot = source.fetch_spot_universe()  # 复用现有快照缓存（60s）
            sample_stocks = []
            for board in raw["board_top"][:3]:
                board_name = board.get("board_name", "")
                if not board_name:
                    continue
                cons = source.fetch_industry_cons(board_name)  # 3600s 缓存
                if cons is None or cons.empty:
                    continue
                code_col = "代码" if "代码" in cons.columns else ("code" if "code" in cons.columns else None)
                if not code_col:
                    continue
                codes = cons[code_col].astype(str).tolist()[:30]  # 每板块取前30只成分股
                if spot is not None and not spot.empty:
                    col_map = {"code": "代码" if "代码" in spot.columns else "code",
                               "name": "名称" if "名称" in spot.columns else "name",
                               "change_pct": "涨跌幅" if "涨跌幅" in spot.columns else "change_pct",
                               "volume_ratio": "量比" if "量比" in spot.columns else "volume_ratio"}
                    board_stocks = spot[spot[col_map["code"]].astype(str).isin(codes)]
                    if not board_stocks.empty and col_map["change_pct"] in board_stocks.columns:
                        top_stocks = board_stocks.nlargest(5, col_map["change_pct"])
                        for _, r in top_stocks.iterrows():
                            sample_stocks.append({
                                "name": str(r.get(col_map["name"], "")),
                                "code": str(r.get(col_map["code"], "")),
                                "change_pct": float(r.get(col_map["change_pct"], 0)),
                                "volume_ratio": float(r.get(col_map["volume_ratio"], 0))
                                if col_map["volume_ratio"] in board_stocks.columns else None,
                            })
            raw["sample_stocks"] = sample_stocks[:5]  # 总共最多5只
        else:
            raw["sample_stocks"] = []
    except Exception as exc:  # noqa: BLE001
        logger.warning("研判-个股抽样失败: %s", exc)
        raw["sample_stocks"] = []

    return raw


def raw_to_text(raw: dict) -> str:
    """原始数据 → 文本（缺失字段明确标注「数据缺失」，供 LLM 研判）"""
    lines = [f"交易日期: {raw.get('trade_date')}"]
    lines.append(f"数据源: {raw.get('data_source')}")

    idx = raw.get("index_recent_5d")
    if isinstance(idx, str):
        lines.append(f"上证指数近5日: {idx}")
    elif isinstance(idx, list):
        lines.append(f"上证指数收盘 {raw.get('index_close')}（近60日位置 {raw.get('index_pos_60d')}）")
        lines.append(f"上证指数近5日: {idx}")

    vr = raw.get("index_volume_ratios")
    lines.append(f"大盘连续量比（成交量比近似口径，近6日）: "
                 f"{vr if isinstance(vr, str) else vr}")

    bs = raw.get("board_structure")
    lines.append(f"行业板块结构: {bs}")
    lines.append(f"板块量比字段可用: "
                 f"{'是' if raw.get('board_volume_ratio_available') else '否（数据缺失，不编造）'}")
    if raw.get("board_top"):
        lines.append(f"板块涨幅前5: {raw['board_top']}")
    if raw.get("board_bottom"):
        lines.append(f"板块跌幅前5: {raw['board_bottom']}")

    rg = raw.get("risk_groups") or {}
    lines.append(f"避险池板块: {rg.get('defensive') or '（无/数据缺失）'} "
                 f"统计: {rg.get('stats', {}).get('defensive')}")
    lines.append(f"进取池板块: {rg.get('aggressive') or '（无/数据缺失）'} "
                 f"统计: {rg.get('stats', {}).get('aggressive')}")

    ad = raw.get("market_advance_decline")
    lines.append(f"全市场涨跌家数: {ad if isinstance(ad, str) else ad}")

    # 隔夜美股
    us = raw.get("us_market") or {}
    if isinstance(us, dict) and us.get("available") is False:
        lines.append("隔夜美股: 数据缺失")
    elif isinstance(us, dict):
        idx_list = us.get("indices") or []
        stk_list = us.get("stocks") or []
        idx_str = "、".join(f"{i.get('name')} {f'{i.get('change_pct'):+.2f}%' if i.get('change_pct') is not None else '数据缺失'}"
                            for i in idx_list)
        stk_str = "、".join(f"{s.get('name')} {f'{s.get('change_pct'):+.2f}%' if s.get('change_pct') is not None else '数据缺失'}"
                            for s in stk_list)
        lines.append(f"隔夜美股({us.get('date', '')}): 指数[{idx_str}]；关键个股[{stk_str}]")

    # 两市量倍
    mtr = raw.get("market_total_ratio") or {}
    if isinstance(mtr, dict) and mtr.get("available") is False:
        lines.append("两市成交额量倍: 数据缺失")
    elif isinstance(mtr, dict):
        lines.append(f"两市成交额量倍: {mtr.get('ratio', '数据缺失')}"
                     f"（{mtr.get('note', '')}，当日约{mtr.get('amount', '数据缺失')}亿）")

    # 板块箱位
    bbp = raw.get("board_box_positions") or {}
    if isinstance(bbp, dict) and bbp.get("note") == "数据缺失":
        lines.append("板块箱位: 数据缺失")
    elif isinstance(bbp, dict):
        box_lines = []
        for bname, bdata in bbp.items():
            if isinstance(bdata, dict):
                box_lines.append(f"{bname}(主箱位{bdata.get('main_box_pct', '缺失')}%"
                                 f"·60日{bdata.get('box60_pct', '缺失')}%)")
        lines.append(f"板块箱位(主箱位/60日箱位): {'、'.join(box_lines) if box_lines else '数据缺失'}")

    # 个股抽样
    ss = raw.get("sample_stocks") or []
    if ss:
        stock_lines = []
        for s in ss:
            vr = f"量比{s.get('volume_ratio')}" if s.get("volume_ratio") else "量比缺失"
            stock_lines.append(f"{s.get('name')}({s.get('code')}) {s.get('change_pct', '缺失')}% {vr}")
        lines.append(f"主线板块个股抽样(涨幅前5): {'、'.join(stock_lines)}")
    else:
        lines.append("主线板块个股抽样: 数据缺失")

    # 段10 板块轮动状态 + 段11 强势板块启动归因（sector_rotation 已落库；缺数据如实「数据缺失」不编造）
    try:
        from app.services.sector_rotation_pattern import get_rotation_daily
        rot = get_rotation_daily()
        st = rot.get("rotation_state")
        if st:
            lines.append(f"板块轮动状态: {st} churn={rot.get('churn_rate')} "
                         f"主线={rot.get('mainline_sector') or '无'}")
        else:
            lines.append("板块轮动状态: 数据缺失")
        launch = rot.get("launch") or []
        top5 = [r["sector_name"] for r in (rot.get("top10") or [])[:5]]
        if launch:
            lmap = {r["sector_name"]: r for r in launch}
            attr_lines = []
            for n in top5:
                lr = lmap.get(n) or {}
                attr_lines.append(f"{n}→tags={lr.get('reason_tags') or '（数据缺失）'}；"
                                  f"{lr.get('reason_text') or '（数据缺失）'}")
            lines.append(f"强势板块启动归因(top5): {'；'.join(attr_lines)}")
        else:
            lines.append("强势板块启动归因: 数据缺失")
    except Exception as exc:  # noqa: BLE001 轮动注入失败不阻塞研判，如实标注缺失
        logger.warning("板块轮动注入失败（标注缺失）: %s", exc)
        lines.append("板块轮动状态: 数据缺失")
        lines.append("强势板块启动归因: 数据缺失")

    return "\n".join(lines)


def market_intel_node(state: StockAgentState) -> StockAgentState:
    """市场研判底座节点：聚合客观数据 → LLM 深度研判（5 大维度）→ 落库 market_intel。
    失败仅打 warning 并标注 state.error，不阻塞其他链路（参考维度）。"""
    date_key = state.get("trade_date", _today())
    try:
        raw = collect_market_data()
        output = agent_call(
            agent="market_intel",
            cache_key=f"market_intel:{date_key}",
            system_prompt=market_intel_prompt.SYSTEM_PROMPT,
            user_prompt=market_intel_prompt.build_user_prompt(raw_to_text(raw)),
            schema=MarketIntelOutput,
            ttl_seconds=86400,
            model_level=ModelLevel.DEEP,
        )
        # 合并新字段到 dict 列（签名不变，不需要改 repo.py；空值防御：字段为空不并入，
        # 避免 prompt 未注入期间写入空 key；getattr 兼容旧格式输出/测试替身缺新字段）
        volume_signal = output.volume_signal or {}
        operative_meaning = output.operative_meaning or {}

        volume_character = getattr(output, "volume_character", "") or ""
        main_structure = getattr(output, "main_structure", {}) or {}
        box_view = getattr(output, "box_view", {}) or {}
        stock_verification = getattr(output, "stock_verification", []) or []

        if volume_character:
            volume_signal["量能成色"] = volume_character
        if main_structure:
            volume_signal["主线结构"] = main_structure
        if box_view:
            operative_meaning["箱位理解"] = box_view
        if stock_verification:
            operative_meaning["个股验证"] = stock_verification

        repo.upsert_market_intel(
            date_key, output.phase, output.core_conflict, output.risk_appetite,
            volume_signal, operative_meaning,
            output.next_day_watch or {}, output.summary, raw)

        # state 同步带上新字段（供链路即时引用）
        state["market_intel"] = {
            "trade_date": date_key, "phase": output.phase,
            "core_conflict": output.core_conflict, "risk_appetite": output.risk_appetite,
            "volume_signal": volume_signal,
            "operative_meaning": operative_meaning,
            "next_day_watch": output.next_day_watch or {},
            "summary": output.summary,
        }
        logger.info("市场研判完成: %s（%s，风险偏好 %s）",
                    date_key, output.phase, output.risk_appetite)
    except Exception as exc:  # noqa: BLE001 研判失败降级：标注 error 不抛断
        logger.warning("市场研判失败: %s", exc)
        state["error"] = f"市场研判失败: {exc}"
    return state
