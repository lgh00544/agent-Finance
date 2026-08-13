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
        repo.upsert_market_intel(
            date_key, output.phase, output.core_conflict, output.risk_appetite,
            output.volume_signal or {}, output.operative_meaning or {},
            output.next_day_watch or {}, output.summary, raw)
        state["market_intel"] = {
            "trade_date": date_key, "phase": output.phase,
            "core_conflict": output.core_conflict, "risk_appetite": output.risk_appetite,
            "volume_signal": output.volume_signal or {},
            "operative_meaning": output.operative_meaning or {},
            "next_day_watch": output.next_day_watch or {},
            "summary": output.summary,
        }
        logger.info("市场研判完成: %s（%s，风险偏好 %s）",
                    date_key, output.phase, output.risk_appetite)
    except Exception as exc:  # noqa: BLE001 研判失败降级：标注 error 不抛断
        logger.warning("市场研判失败: %s", exc)
        state["error"] = f"市场研判失败: {exc}"
    return state
