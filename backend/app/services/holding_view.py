"""持仓列表只读视图：加载实时行情、补全风控参考值与目标仓位【刚性代码逻辑】。

职责边界：
- 只做数据加载与数学计算（实时价 → 市值/盈亏；参考价补全），不落库、不做任何研判；
- 不修改任何持仓/计划记录，去重合并由前端展示层完成（原始数据完整保留）；
- 行情失败时字段为 None（前端显示警示，不伪造 0 值）。
"""
import logging
import time

from app.core.config import settings
from app.datasource.akshare_source import get_datasource
from app.db import repo

logger = logging.getLogger(__name__)


def _quote_map(spot_df) -> dict[str, float]:
    """spot 快照 → {代码: 最新价}；无价/非正价（停牌、异常）不收录"""
    result: dict[str, float] = {}
    for _, row in spot_df.iterrows():
        code = str(row.get("code") or "").strip()
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if code and price > 0:
            result[code] = price
    return result


def _fetch_holding_quotes(codes: list[str]) -> tuple[dict[str, float], str, str | None]:
    """持仓价三级取数（任一成功即返回）：①腾讯批量 → ②DB快照 → ③全市场快照。

    返回 (quotes, source, error)；source ∈ 'tencent'/'snapshot'/'universe'；
    全失败 return ({}, "universe", error)。只取数 + 降级，不做任何研判。"""
    # ① 腾讯批量（首选：N 只 = 1 次 HTTP，实测 0.56s，不占东财反爬额度）
    try:
        quotes = get_datasource().fetch_tencent_batch(codes)
        if quotes:
            return quotes, "tencent", None
    except Exception as exc:  # noqa: BLE001 降级不阻塞
        logger.warning("持仓行情·腾讯批量失败: %s", exc)
    # ② DB 快照兜底（10 分钟内，秒回；跨进程共享定时快照）
    try:
        snapshot = repo.get_quote_snapshot(within_minutes=10)
        if snapshot is not None and not snapshot.empty:
            return _quote_map(snapshot), "snapshot", None
    except Exception as exc:  # noqa: BLE001
        logger.warning("持仓行情·DB快照读取失败: %s", exc)
    # ③ 全市场快照（原逻辑；akshare 挂返回空但不阻塞）
    try:
        quotes = _quote_map(get_datasource().fetch_spot_universe())
        return quotes, "universe", None
    except Exception as exc:  # noqa: BLE001
        logger.warning("持仓行情·全市场快照失败: %s", exc)
        return {}, "universe", f"行情获取失败：{exc}"


def _round2(value: float) -> float:
    return round(value, 2)


def build_holding_view() -> dict:
    """持仓列表视图：原始记录 + 实时行情 + 参考止损/止盈 + 目标仓位%。

    返回 {rows, quote_time, quote_error}：rows 为 repo 原始记录基础上追加
    current_price/market_value/pnl_amount/pnl_pct/stop_loss_source/take_profit_source，
    并补全 stop_loss/take_profit（人工设置优先 → 关联建仓计划 → 默认风控比例）。
    """
    now_min = time.strftime("%Y-%m-%d %H:%M")
    rows = repo.list_holdings(status="holding")
    if not rows:
        return {"rows": [], "quote_time": now_min, "quote_error": None,
                "total_capital": settings.total_capital}

    quote_error = None
    source = ""
    quotes: dict[str, float] = {}
    # 三级取数：腾讯批量 → DB 快照 → 全市场快照（任一成功即返回，全失败不阻塞列表）
    quotes, source, quote_error = _fetch_holding_quotes([r["stock_code"] for r in rows])

    plan_rows = repo.list_plans(limit=500)
    plans = {p["id"]: p for p in plan_rows}
    latest_plan_by_code: dict[str, dict] = {}
    for p in plan_rows:  # list_plans 按 id 倒序，首见即最新
        latest_plan_by_code.setdefault(p["stock_code"], p)

    out = []
    for r in rows:
        code = r["stock_code"]
        price = quotes.get(code)
        shares = r.get("shares") or 0
        entry_price = r.get("entry_price") or 0
        market_value = pnl_amount = pnl_pct = None
        if price is not None:
            market_value = _round2(price * shares)
            pnl_amount = _round2((price - entry_price) * shares)
            if entry_price > 0:
                pnl_pct = _round2((price - entry_price) / entry_price * 100)

        stop_loss, sl_src = _reference_price(
            r.get("stop_loss"), entry_price, plans.get(r.get("plan_id")),
            latest_plan_by_code.get(code), settings.default_stop_loss_pct, True)
        take_profit, tp_src = _reference_price(
            r.get("take_profit"), entry_price, plans.get(r.get("plan_id")),
            latest_plan_by_code.get(code), settings.default_take_profit_pct, False)

        target_pct = None
        if market_value is not None and settings.total_capital > 0:
            target_pct = round(market_value / settings.total_capital * 100, 1)

        out.append({**r, "current_price": price, "market_value": market_value,
                    "pnl_amount": pnl_amount, "pnl_pct": pnl_pct,
                    "stop_loss": stop_loss, "stop_loss_source": sl_src,
                    "take_profit": take_profit, "take_profit_source": tp_src,
                    "target_pct": target_pct})
    return {"rows": out, "quote_time": now_min, "quote_error": quote_error,
            "source": source, "total_capital": settings.total_capital}


def build_account_summary() -> dict:
    """账户核心资产摘要（双数据路径，纯数学计算，不落库不研判）：

    - 有账户基准（OCR 截图人工确认保存）：总资产/可用资金/仓位占比直接用券商真实值；
    - 无基准：总资产 = TOTAL_CAPITAL + Σ持仓盈亏（估算，前端标注「估算」）；
    - 总持仓成本/总盈亏金额/比例始终按持仓 + 最新市价实时计算；
    - 行情整体失败且有持仓时，与市价相关的项返回 None（前端显示「—」+ 标注，不伪造 0）。
    """
    view = build_holding_view()
    rows = view["rows"]

    total_cost = sum(float(r.get("cost") or 0) for r in rows)
    mv_known = any(r.get("market_value") is not None for r in rows)
    market_value = sum(float(r.get("market_value") or 0) for r in rows
                       if r.get("market_value") is not None)
    pnl = sum(float(r.get("pnl_amount") or 0) for r in rows
              if r.get("pnl_amount") is not None)

    baseline = repo.get_latest_account_baseline()
    source = "baseline" if baseline else "estimate"

    if not rows or mv_known:
        if baseline:
            total_asset = float(baseline["total_asset"])
            available_cash = float(baseline["available_cash"])
            position_pct = float(baseline["position_pct"])
        else:
            total_asset = settings.total_capital + pnl
            available_cash = total_asset - market_value
            position_pct = market_value / total_asset * 100 if total_asset > 0 else 0.0
        base = total_asset - pnl
        pnl_pct = pnl / base * 100 if base > 0 else 0.0
        return {"total_asset": _round2(total_asset), "total_cost": _round2(total_cost),
                "market_value": _round2(market_value), "pnl_amount": _round2(pnl),
                "pnl_pct": _round2(pnl_pct), "position_pct": _round2(position_pct),
                "available_cash": _round2(available_cash), "source": source,
                "baseline": baseline, "quote_time": view["quote_time"],
                "quote_error": view["quote_error"]}

    # 行情整体失败且存在持仓：市价相关项不展示（前端显示「—」并标注失败原因）
    return {"total_asset": float(baseline["total_asset"]) if baseline else None,
            "total_cost": _round2(total_cost), "market_value": None, "pnl_amount": None,
            "pnl_pct": None, "position_pct": float(baseline["position_pct"]) if baseline else None,
            "available_cash": float(baseline["available_cash"]) if baseline else None,
            "source": source, "baseline": baseline,
            "quote_time": view["quote_time"], "quote_error": view["quote_error"]}


def _reference_price(manual, entry_price, plan_by_id, plan_by_code,
                     default_pct: float, is_stop: bool) -> tuple[float, str]:
    """参考价补全链：人工设置 → 关联建仓计划（plan_id 精确）→ 该股最新计划 → 成本×默认风控比例"""
    def _positive(v) -> bool:
        try:
            return v is not None and float(v) > 0
        except (TypeError, ValueError):
            return False

    if _positive(manual):
        return round(float(manual), 2), "手动设置"
    plan = plan_by_id or plan_by_code
    if plan and _positive(plan.get("stop_loss" if is_stop else "take_profit")):
        return round(float(plan["stop_loss" if is_stop else "take_profit"]), 2), "建仓计划"
    if entry_price > 0:
        factor = (1 - default_pct / 100) if is_stop else (1 + default_pct / 100)
        return _round2(entry_price * factor), f"默认风控 {default_pct:g}%"
    return 0.0, ""
