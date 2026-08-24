"""
PortfolioSentinel 组合哨兵 - LangGraph 单节点（交易时段每 10 分钟 + 手动触发）
【定位】与 MonitorAgent 平行运行的独立 Agent（零耦合，不共享节点、不互相调用）：
- MonitorAgent = 个股盘中哨兵（逐只看行情，3 分钟一次）
- PortfolioSentinel = 组合级风控哨兵（全局看板块/组合/时间，10 分钟一次）
【刚性代码逻辑】批量行情/板块行情/持仓天数/组合盈亏/集中度（纯数学）
【交由模型推理的业务逻辑】板块退潮检测、时间止损评估、组合风险解读（全部在 LLM，LIGHT 模型）
流转：portfolio_sentinel_node（collect → agent_call(LIGHT) → 落库推送）
数据纪律：各数据段独立 try/except，缺失字段标注「数据不足」绝不编造；无持仓正常跳过不报错。
"""
import logging
import re
import time
from datetime import datetime

from agent_prompts import portfolio_sentinel_prompt
from app.agents.common import ModelLevel, agent_call
from app.agents.schemas import PortfolioSentinelOutput
from app.cache import cache
from app.datasource.fallback import get_datasource
from app.db import repo
from app.graph.state import StockAgentState
from app.services.feishu import push_alert

logger = logging.getLogger(__name__)

_DEFAULT_HOLD_PERIOD_DAYS = 14   # 持仓周期偏好缺失时默认 14 天（参考权重）
_DRAWDOWN_THRESHOLD_PCT = -3.0   # 组合总盈亏 < -3% 触发回撤预警（参考权重）
_CONCENTRATION_THRESHOLD = 0.40  # 同板块持仓合计占总市值 > 40% 触发集中度预警（参考权重）
_TTL_SECONDS = 600               # 巡检 LLM 缓存 10 分钟（与巡检频率同节奏）
_ALERT_SOURCE = "portfolio_sentinel"  # alert_log.source 标记（复用现有 alert 表）


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _hold_days(entry_date) -> int:
    """持仓天数（entry_date 非法时返回 0，LLM 侧按数据不足处理）"""
    try:
        return (datetime.strptime(_today(), "%Y-%m-%d")
                - datetime.strptime(str(entry_date)[:10], "%Y-%m-%d")).days
    except (TypeError, ValueError):
        return 0


def _pref_hold_days() -> int:
    """从个人交易偏好档案提取持仓周期偏好（天）；提取不到默认 14 天"""
    try:
        content = repo.get_trade_profile_content() or {}
    except Exception:  # noqa: BLE001 偏好读取失败不阻塞巡检
        return _DEFAULT_HOLD_PERIOD_DAYS
    text = str(content.get("持仓周期偏好") or "")
    m = re.search(r"(\d+)\s*(天|日|周|个月|月)", text)
    if not m:
        return _DEFAULT_HOLD_PERIOD_DAYS
    n = int(m.group(1))
    unit = m.group(2)
    if unit in ("周",):
        return n * 7
    if unit in ("个月", "月"):
        return n * 30
    return n


def _stock_sector_map(codes: list[str]) -> dict[str, str]:
    """持仓股 → 所属板块（fetch_stock_info 行业字段，86400 缓存）；失败跳过标注数据不足"""
    source = get_datasource()
    out: dict[str, str] = {}
    for code in codes:
        try:
            info = source.fetch_stock_info(code)
            sector = str(info.get("行业") or "").strip()
            if sector:
                out[code] = sector
        except Exception as exc:  # noqa: BLE001 单只行业归属失败不阻塞整体
            logger.warning("组合哨兵 持仓 %s 行业归属获取失败: %s", code, exc)
    return out


def _board_match(board_df, sector: str) -> dict:
    """板块行情表中匹配持仓行业（board_name 与行业名双向子串匹配，命中首个）；
    量比/涨跌幅字段缺失如实标注 None（不编造）。返回 {change_pct, volume_ratio}"""
    if board_df is None or board_df.empty or "board_name" not in board_df.columns:
        return {"change_pct": None, "volume_ratio": None}
    for _, r in board_df.iterrows():
        name = str(r.get("board_name") or "")
        if not name:
            continue
        if sector in name or name in sector:
            return {"change_pct": _safe_float(r.get("change_pct")),
                    "volume_ratio": _safe_float(r.get("volume_ratio"))}
    return {"change_pct": None, "volume_ratio": None}


def _safe_float(v) -> float | None:
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


def collect_portfolio_data() -> dict | None:
    """组合哨兵原始数据聚合【刚性代码逻辑】只打包客观数据，研判全部由 LLM 完成。

    各数据段独立 try/except：单段失败不影响整体（缺失字段标注「数据不足」）；
    无持仓返回 None（调用方正常跳过，不报错）。"""
    holdings = repo.get_active_holdings()
    if not holdings:
        return None
    today = _today()
    source = get_datasource()
    codes = [h.stock_code for h in holdings]

    # 1) 持仓批量行情（全持仓一次获取；数据源内部已做逐只兜底）
    quotes: dict[str, dict] = {}
    try:
        quotes = source.fetch_spot_quotes_batch(codes)
    except Exception as exc:  # noqa: BLE001 批量行情失败不阻塞整体
        logger.warning("组合哨兵批量行情失败: %s", exc)

    # 2) 行业板块行情（一次拉全量再过滤，不做逐板块请求）
    board_df = None
    try:
        board_df = source.fetch_industry_spot()
    except Exception as exc:  # noqa: BLE001 板块失败标注缺失
        logger.warning("组合哨兵板块行情失败: %s", exc)

    # 3) 持仓股板块归属（行业字段）
    sector_map = _stock_sector_map(codes)

    # 4) 组合数学（纯数学：市值/盈亏/集中度/持仓天数）
    hold_rows: list[dict] = []
    sector_mv: dict[str, float] = {}
    total_cost = 0.0
    total_mv = 0.0
    for h in holdings:
        quote = quotes.get(h.stock_code) or {}
        price = quote.get("price")
        cost = float(h.cost or (h.entry_price or 0) * (h.shares or 0))
        total_cost += cost
        mv = pnl_pct = None
        if price is not None and price > 0:
            mv = round(float(price) * (h.shares or 0), 2)
            pnl_pct = (round((float(price) - h.entry_price) / h.entry_price * 100, 2)
                       if h.entry_price and h.entry_price > 0 else None)
            total_mv += mv
            sector = sector_map.get(h.stock_code, "")
            if sector:
                sector_mv[sector] = sector_mv.get(sector, 0.0) + mv
        hold_rows.append({
            "stock_code": h.stock_code, "stock_name": h.stock_name,
            "sector": sector_map.get(h.stock_code, "（数据不足）"),
            "entry_date": h.entry_date, "holding_days": _hold_days(h.entry_date),
            "entry_price": h.entry_price, "current_price": price,
            "change_pct": quote.get("change_pct"), "pnl_pct": pnl_pct,
            "market_value": mv,
        })

    total_pnl_pct = (round((total_mv - total_cost) / total_cost * 100, 2)
                     if total_cost > 0 else None)
    drawdown_alert = (total_pnl_pct is not None
                      and total_pnl_pct < _DRAWDOWN_THRESHOLD_PCT)
    max_sector_pct = None
    if total_mv > 0 and sector_mv:
        top = max(sector_mv.items(), key=lambda kv: kv[1])
        max_sector_pct = round(top[1] / total_mv * 100, 1)
    concentration_alert = (max_sector_pct is not None
                           and max_sector_pct > _CONCENTRATION_THRESHOLD * 100)

    # 5) 持仓板块行情（涨跌幅/量比；缺失标注 None，不编造）
    sector_boards: dict[str, dict] = {}
    for code, sector in sector_map.items():
        sector_boards[sector] = _board_match(board_df, sector)

    return {
        "trade_date": today,
        "hold_period_days": _pref_hold_days(),
        "holdings": hold_rows,
        "portfolio": {"total_cost": round(total_cost, 2),
                      "total_mv": round(total_mv, 2),
                      "total_pnl_pct": total_pnl_pct,
                      "max_sector_pct": max_sector_pct,
                      "drawdown_alert": drawdown_alert,
                      "concentration_alert": concentration_alert},
        "sector_boards": sector_boards,
    }


def raw_to_text(raw: dict) -> str:
    """原始数据 → 文本（缺失字段明确标注「数据不足」，供 LLM 研判）"""
    lines = [f"交易日期: {raw.get('trade_date')}",
             f"持仓周期偏好（天数）: {raw.get('hold_period_days')}（超过一半未启动即触发时间止损评估）"]
    p = raw.get("portfolio") or {}
    lines.append(f"组合总盈亏 %: {p.get('total_pnl_pct') or '（数据不足）'} "
                 f"（口径：Σ市值-Σ成本）/Σ成本；组合总市值: {p.get('total_mv')}")
    lines.append(f"最大板块持仓占比 %: {p.get('max_sector_pct') or '（数据不足）'}；"
                 f"回撤预警: {'触发（<-3%）' if p.get('drawdown_alert') else '未触发'}；"
                 f"集中度预警: {'触发（>40%）' if p.get('concentration_alert') else '未触发'}")
    lines.append("\n【持仓明细】代码 名称 板块 持仓天数 成本 现价 当日涨跌幅% 浮盈亏%")
    for r in raw.get("holdings") or []:
        lines.append(
            f"{r['stock_code']} {r['stock_name']} {r['sector']} "
            f"持仓{r['holding_days']}天 成本{r['entry_price']} 现价{r['current_price'] or '—'} "
            f"当日{r['change_pct'] or '—'}% 浮盈{r['pnl_pct'] or '—'}%")
    lines.append("\n【板块行情】（量比/涨跌幅缺失 = 数据源未提供，不得编造）")
    for sector, b in (raw.get("sector_boards") or {}).items():
        lines.append(f"{sector}: 涨跌幅 {b.get('change_pct') or '（数据不足）'}% "
                     f"量比 {b.get('volume_ratio') or '（数据不足）'}")
    return "\n".join(lines)


def portfolio_sentinel_node(state: StockAgentState) -> StockAgentState:
    """组合哨兵节点：聚合客观数据 → LLM 组合研判（LIGHT）→ 告警落库 + 飞书推送。
    无持仓直接跳过（正常状态不报错）；失败仅打 warning 标注 state.error，不抛断。"""
    today = state.get("trade_date") or _today()
    try:
        raw = collect_portfolio_data()
        if raw is None:
            state["portfolio_sentinel"] = {"trade_date": today, "skipped": True,
                                           "reason": "无持仓，组合哨兵跳过"}
            logger.info("组合哨兵跳过（无持仓）: %s", today)
            return state
        output = agent_call(
            agent="portfolio_sentinel",
            cache_key=f"portfolio_sentinel:{today}:{int(time.time() // 600)}",
            system_prompt=portfolio_sentinel_prompt.SYSTEM_PROMPT,
            user_prompt=portfolio_sentinel_prompt.build_user_prompt(raw_to_text(raw)),
            schema=PortfolioSentinelOutput,
            ttl_seconds=_TTL_SECONDS,
            model_level=ModelLevel.LIGHT,
        )
        result = output.model_dump()
        state["portfolio_sentinel"] = {"trade_date": today, **result}
        _persist_alerts(raw, result, today)
        logger.info("组合哨兵完成: %s 板块预警 %s 条 / 时间止损 %s 条 / 组合回撤 %s / 集中度 %s",
                    today, len(result["sector_alerts"]), len(result["time_stop_alerts"]),
                    result["portfolio_risk"]["drawdown_alert"],
                    result["portfolio_risk"]["concentration_alert"])
    except Exception as exc:  # noqa: BLE001 组合哨兵失败降级：标注 error 不抛断
        logger.warning("组合哨兵失败: %s", exc)
        state["error"] = f"组合哨兵失败: {exc}"
    return state


def _persist_alerts(raw: dict, result: dict, today: str) -> None:
    """告警落库（alert_log，source='portfolio_sentinel'）+ 有告警推飞书汇总（当日去重）。
    所有告警落库供面板展示；飞书仅推一条汇总（去重：当日同类只推一次）。"""
    alerts: list[dict] = []

    def _severity(level: str) -> str:
        return {"高": "critical", "中": "warning"}.get(level, "info")

    for a in result.get("sector_alerts") or []:
        alerts.append({"stock_code": a["stock_code"], "stock_name": a["stock_name"],
                       "alert_type": "组合哨兵-板块退潮", "severity": _severity(a["alert_level"]),
                       "action": "review",
                       "message": f"{a['stock_name']}({a['stock_code']}) 所属板块「{a['sector']}」"
                                  f"退潮预警（{a['alert_level']}）：板块涨跌幅 "
                                  f"{a.get('sector_change_pct') or '数据不足'}%，量比 "
                                  f"{a.get('sector_volume_ratio') or '数据不足'}。{a['reason']}",
                       "signal": a})
    for a in result.get("time_stop_alerts") or []:
        alerts.append({"stock_code": a["stock_code"], "stock_name": a["stock_name"],
                       "alert_type": "组合哨兵-时间止损", "severity": "warning",
                       "action": "review",
                       "message": f"{a['stock_name']}({a['stock_code']}) 持仓 {a['holding_days']} 天"
                                  f"（浮盈 {a.get('pnl_pct') or '数据不足'}%）横盘，"
                                  f"结论：{a['verdict']}。{a['reason']}",
                       "signal": a})
    risk = result.get("portfolio_risk") or {}
    if risk.get("drawdown_alert"):
        alerts.append({"stock_code": "PORTFOLIO", "stock_name": "组合",
                       "alert_type": "组合哨兵-组合回撤", "severity": "critical",
                       "action": "review",
                       "message": f"组合总盈亏 {risk.get('total_pnl_pct')}%（< -3%）触发回撤预警，"
                                  f"建议降低仓位、暂缓加仓。",
                       "signal": risk})
    if risk.get("concentration_alert"):
        alerts.append({"stock_code": "PORTFOLIO", "stock_name": "组合",
                       "alert_type": "组合哨兵-集中度", "severity": "warning",
                       "action": "review",
                       "message": f"同板块持仓合计占总市值 {risk.get('max_sector_pct')}%（> 40%）"
                                  f"触发集中度预警，建议分散持仓。",
                       "signal": risk})

    for al in alerts:
        repo.insert_alert(al["stock_code"], al["stock_name"], al["alert_type"],
                          al["severity"], al["message"], al["action"], al["signal"],
                          pushed=False, source=_ALERT_SOURCE)

    # 汇总落库 + 有告警才推飞书（当日去重）
    if alerts:
        n_alert = len(alerts)
        summary_msg = (f"组合哨兵 · {today}：共 {n_alert} 项告警\n"
                       f"总评估：{result.get('overall_assessment') or ''}\n"
                       + "\n".join(a["message"][:60] for a in alerts[:5]))
        dedup_key = f"portfolio_sentinel:summary:{today}"
        pushed = False
        if not cache.alert_deduplicated(dedup_key, ttl_seconds=86400):
            pushed = push_alert("组合哨兵", "PORTFOLIO", "组合风控告警", "warning",
                                summary_msg, "review")
        repo.insert_alert("PORTFOLIO", "组合哨兵", "组合哨兵-汇总", "warning",
                          summary_msg, "review",
                          {"overall_assessment": result.get("overall_assessment"),
                           "alert_count": n_alert}, pushed=pushed, source=_ALERT_SOURCE)
        if pushed:
            logger.info("组合哨兵飞书推送成功: %s（%s 项告警）", today, n_alert)
    else:
        # 无告警：落一条 info 级巡检记录（面板可回溯），不推飞书
        repo.insert_alert("PORTFOLIO", "组合哨兵", "组合哨兵-巡检", "info",
                          f"组合哨兵巡检完成（{today}）：无告警。"
                          f"组合总盈亏 {risk.get('total_pnl_pct') or '数据不足'}%，"
                          f"最大板块占比 {risk.get('max_sector_pct') or '数据不足'}%",
                          "hold", {"overall_assessment": result.get("overall_assessment")},
                          pushed=False, source=_ALERT_SOURCE)
