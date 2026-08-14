"""持仓止盈/仓位管理计算服务（独立计算模块，不侵入 MonitorAgent 扫描循环）

【规则来源】完全复用现有风控体系（知识库红线 + 既有代码同口径，不新增自定义规则）：
- C1 单票仓位上限 30%、C2 总仓位上限 60%（知识库红线，默认值可经 settings 调整）；
- C3 硬止损 = 加权成本 × 0.92（与 routes 加仓/成本修正联动口径一致，跌破无条件离场）；
- 分档锁利：第一止盈位触发 → 减仓 1/3 锁利 + 止损上移至成本价；第二止盈位触发 →
  再减仓 1/3 + 止损上移至第一止盈位；剩余 1/3 移动止盈（MA5，高位标的 MA10），跌破清仓；
- 波段操作：跌破 MA10 且量能放大 → 先行减半；回调支撑位且缩量 → 可加仓（禁止追高）。

【同源同步】行情/参考止损止盈/市值全部来自 build_holding_view()（持仓监控页同一函数），
技术指标来自 compute_indicators()（MonitorAgent 同源指标层）——两边展示 100% 一致。

【计算】纯数学计算，零 LLM 调用；K线不可用（网络/数据源失败）时降级为固定比例区间估算。
【留痕】计算结果写入 ai_reasoning_trace（source_module='position_monitor'），纠察 Agent 可追溯。
【缓存】按 代码+日期 缓存 10 分钟（cache 抽象层），手动刷新时 force=True 击穿。
【告警】「接近止盈 / 止盈触发」由独立通道去重写入 alert_log（cache.alert_deduplicated），
不修改 MonitorAgent 扫描循环。
"""
import json
import logging
import time

from sqlalchemy import select

from app.cache import cache
from app.datasource.fallback import get_datasource
from app.db import repo
from app.db.models import NewsArticle
from app.db.session import SessionLocal
from app.services import holding_view, reasoning_trace
from app.services.indicator import compute_indicators

logger = logging.getLogger(__name__)

# ==================== 风控红线（知识库规则，代码同口径） ====================
C1_SINGLE_CAP = 0.30      # C1 单票仓位上限（知识库红线默认 30%）
C2_TOTAL_CAP = 0.60       # C2 总仓位上限（知识库红线默认 60%）
C3_STOP_PCT = 0.92        # C3 硬止损线 = 成本 × 0.92（与 routes 同口径）
TP1_PCT = 0.10            # 第一止盈位保守参考：成本 + 8%~10%（取与前期高点较低值）
TP1_FLOOR_PCT = 0.08      # 第一止盈位下限（成本 + 8%）
TP2_EXT = 0.618           # 第二止盈位波段目标：黄金分割扩展位 0.618
TP_NEAR_PCT = 0.03        # 接近止盈/止损阈值：现价距点位 ≤3%
TRAILING_ENABLE_PNL_PCT = 5.0   # 移动止盈启用门槛：持仓浮盈超过 5% 后启用
TRAILING_DRAWBACK_PCT = 0.92    # 移动止盈线 = 持仓期最高价 × 0.92（从最高点回撤 8% 止盈）
_CACHE_TTL = 600          # 计算结果缓存 10 分钟（与行情缓存同量级）
_TRACE_MODULE = "position_monitor"
_ANOMALY_KEYS = ("异动", "涨停", "跌停", "利好", "利空", "大单", "减持", "增持",
                 "停牌", "重组", "中标", "预增", "预亏", "龙虎榜")


# ==================== 核心计算（纯函数，可单测） ====================

def _round2(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None


def calc_trailing_stop(entry_price: float, high_price: float | None,
                       current_price: float | None) -> float | None:
    """移动止盈线（批次1 · 纯函数，可单测）：持仓浮盈超过 5% 后启用，
    移动止盈线 = 持仓期最高价 × 0.92（从最高点回撤 8% 止盈），且不低于成本价（保底不亏）；
    浮盈不足 5% 或数据缺失返回 None（沿用原固定止盈，不启用移动止盈）。

    entry_price: 加权成本价；high_price: 持仓期最高价（NULL/0 时按当前价基准）；
    current_price: 当前价。"""
    try:
        entry = float(entry_price)
        high = float(high_price or 0.0)
        price = float(current_price or 0.0)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or high <= 0 or price <= 0:
        return None
    pnl_pct = (price - entry) / entry * 100
    if pnl_pct < TRAILING_ENABLE_PNL_PCT:
        return None
    return round(max(high * TRAILING_DRAWBACK_PCT, entry), 2)


def compute_plan(row: dict, ind: dict) -> dict:
    """单只持仓的止盈/仓位计划（纯数学计算）。

    row: build_holding_view() 的持仓行（含 current_price/stop_loss/take_profit/市值等）
    ind: compute_indicators() 结果；空 dict 表示 K线不可用（降级模式）
    """
    code = row["stock_code"]
    name = row["stock_name"]
    cost = float(row.get("entry_price") or 0.0)
    shares = int(row.get("shares") or 0)
    price = row.get("current_price")
    plan_sl = float(row.get("stop_loss") or 0.0)       # 参考止损（人工/计划/默认风控 已补全）
    plan_tp = float(row.get("take_profit") or 0.0)     # 参考止盈（同上）
    market_value = row.get("market_value")

    degraded = not ind
    if degraded or cost <= 0 or price is None or price <= 0:
        # 降级：固定比例区间估算（无 K线/无行情时不给点位，避免误导）
        tp1 = _round2(cost * (1 + TP1_PCT)) if cost > 0 else None
        tp2 = _round2(cost * (1 + 0.25)) if cost > 0 else None
        ma5 = ma10 = support = None
        volume_ratio = None
    else:
        high = float(ind.get("high_20d") or ind.get("high_60d") or (cost * 1.15))
        low = float(ind.get("low_20d") or ind.get("low_60d") or (cost * 0.90))
        ma5 = _round2(ind.get("ma5"))
        ma10 = _round2(ind.get("ma10"))
        volume_ratio = _round2(ind.get("volume_ratio_5"))
        # 第一止盈位（保守锁利）= min(近期前高压力位, 成本+10%)，且不低于成本+8%
        tp1 = min(high, cost * (1 + TP1_PCT))
        if tp1 < cost * (1 + TP1_FLOOR_PCT):
            tp1 = cost * (1 + TP1_FLOOR_PCT)
        # 第二止盈位（波段目标）= 黄金分割扩展位与前期重要压力位共振
        fib = high + (high - low) * TP2_EXT
        tp2 = max(fib, high)
        support = _round2(low)   # 波段低点支撑（加仓前提）
        tp1, tp2 = _round2(tp1), _round2(tp2)

    # 止损体系：初始 C3 硬止损（成本×0.92）；手动/计划止损更严格（价位更高）时以更严为准，
    # 更宽松（价位更低）时硬线兜底——任何情况下不得突破 C3 红线
    c3_hard = _round2(cost * C3_STOP_PCT) if cost > 0 else None
    current_stop = (round(max(plan_sl, c3_hard), 2) if (plan_sl and c3_hard) else
                    (c3_hard or (round(plan_sl, 2) if plan_sl else None)))
    # 阶梯止损上移：到达第一止盈位后 → 成本价；到达第二止盈位后 → 第一止盈位
    ladder_stop_1 = _round2(cost) if cost > 0 else None
    ladder_stop_2 = tp1

    # 移动止盈线：默认 MA5；高位标的（现价显著高于 MA20）切换 MA10
    trailing_line = ma5
    if not degraded and ma10 and ind.get("ma20"):
        if price > float(ind["ma20"]) * 1.20:
            trailing_line = ma10
    trailing_note = ("移动止盈线绑定 10 日均线（高位标的，随股价上移）"
                     if trailing_line is not None and trailing_line != ma5 else
                     "移动止盈线绑定 5 日均线，随股价上涨自动上移")

    # 状态标签判定（规格二.3）：接近止损 > 减仓预警 > 接近止盈 > 持有观察
    status, status_tone = "持有观察", "info"
    if price is not None and price > 0:
        if current_stop and price <= current_stop * (1 + TP_NEAR_PCT):
            status, status_tone = "接近止损", "err"
        elif ma10 and price < ma10:
            status, status_tone = "减仓预警", "err"
        elif tp1 and price >= tp1 * (1 - TP_NEAR_PCT):
            status, status_tone = "接近止盈", "warn"

    # 仓位指引（C1 单票 / C2 总仓 红线）
    single_pct = None
    if market_value is not None and row.get("total_capital"):
        single_pct = round(market_value / row["total_capital"] * 100, 1)
    c1_ok = single_pct is not None and single_pct <= C1_SINGLE_CAP * 100
    # 加仓条件：回调支撑位且缩量 → 可加仓至 C1 上限；追高（现价高于 MA5×1.03）禁止
    add_condition = None
    if not degraded and support and price:
        if price <= support * 1.03 and (volume_ratio is None or volume_ratio < 1.0):
            cap_shares = None
            if row.get("total_capital"):
                cap_shares = int(C1_SINGLE_CAP * row["total_capital"] / price / 100) * 100
            add_condition = (f"回调至支撑位 {support} 元且量能萎缩（量比 {volume_ratio or '—'}），"
                             f"可加仓至单票仓位上限 30%"
                             + (f"（约 {cap_shares:,} 股）" if cap_shares else ""))
        elif price >= (ma5 or 0) * 1.03:
            add_condition = "现价高于 5 日均线 3% 以上（追高风险），暂不建议加仓"
    # 波段减仓：跌破 MA10 且量能放大 → 先行减半
    reduce_condition = None
    if not degraded and ma10 and price:
        if price < ma10 and (volume_ratio is None or volume_ratio > 1.2):
            reduce_condition = f"已跌破 MA10（{ma10}）且量能放大（量比 {volume_ratio}），先行减仓一半"
        elif price < ma10:
            reduce_condition = f"已跌破 MA10（{ma10}），关注量能是否放大决定是否减半"

    return {
        "stock_code": code, "stock_name": name, "holding_id": row.get("id"),
        "cost": _round2(cost), "shares": shares, "current_price": price,
        "single_pct": single_pct, "c1_cap_pct": C1_SINGLE_CAP * 100,
        "c1_ok": c1_ok,
        "c2_cap_pct": C2_TOTAL_CAP * 100,
        "tp1": tp1, "tp2": tp2, "tp1_note": "触发减仓 1/3 锁利，止损上移至成本价",
        "tp2_note": "触发再减仓 1/3，剩余仓位移动止盈持有",
        "trailing_line": trailing_line, "trailing_note": trailing_note,
        "c3_stop": c3_hard, "current_stop": current_stop,
        "ladder_stop_1": ladder_stop_1, "ladder_stop_2": ladder_stop_2,
        "support": support, "ma5": ma5, "ma10": ma10, "volume_ratio": volume_ratio,
        "status": status, "status_tone": status_tone,
        "add_condition": add_condition, "reduce_condition": reduce_condition,
        "degraded": degraded,
        "calc_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ==================== 异动联动（K229 异动标记，复用新闻真源表） ====================

def _recent_anomaly(stock_code: str) -> bool:
    """当日该股新闻标题是否含异动类关键词（大额买卖/利好利空等）"""
    today = time.strftime("%Y-%m-%d")
    try:
        with SessionLocal() as db:
            rows = db.execute(
                select(NewsArticle.title)
                .where(NewsArticle.stock_code == stock_code,
                       NewsArticle.published_at.like(f"{today}%"))
                .limit(10)).scalars().all()
        return any(k in (t or "") for t in rows for k in _ANOMALY_KEYS)
    except Exception as exc:  # noqa: BLE001 异动标记失败不阻塞主流程
        logger.warning("异动标记查询失败 %s: %s", stock_code, exc)
        return False


# ==================== 留痕（source_module='position_monitor'） ====================

def _trace_plan(plan: dict) -> None:
    """止盈/仓位计算结果写入推理留痕表（异步 worker，不阻塞页面）"""
    try:
        reasoning_trace.submit({
            "stock_code": plan["stock_code"], "stock_name": plan["stock_name"],
            "source_module": _TRACE_MODULE,
            "generate_date": time.strftime("%Y-%m-%d"),
            "fact_basis": json.dumps(
                {"cost": plan["cost"], "shares": plan["shares"],
                 "current_price": plan["current_price"],
                 "single_pct": plan["single_pct"],
                 "c1_cap_pct": plan["c1_cap_pct"], "c2_cap_pct": plan["c2_cap_pct"],
                 "ma5": plan["ma5"], "ma10": plan["ma10"],
                 "volume_ratio": plan["volume_ratio"]}, ensure_ascii=False),
            "technical_reasoning": (
                f"第一止盈位 {plan['tp1']}（min(前期高点, 成本+10%)，锁利 1/3）；"
                f"第二止盈位 {plan['tp2']}（黄金分割 0.618 与前期压力共振）；"
                f"移动止盈线 {plan['trailing_line']}；支撑位 {plan['support']}"),
            "capital_reasoning": "",
            "fundamental_reasoning": "",
            "risk_reasoning": f"C3 硬止损 {plan['c3_stop']}（成本×0.92）；"
                              f"当前生效止损 {plan['current_stop']}；"
                              f"状态标签：{plan['status']}",
            "rule_refs": "C1 单票仓位上限 30% / C2 总仓位上限 60% / C3 硬止损 成本×0.92 / "
                         "分档锁利与移动止盈 / 波段减仓（跌破 MA10 且量能放大）",
            "final_conclusion": json.dumps(plan, ensure_ascii=False),
            "confidence": 0.0,
            "data_source": "build_holding_view 行情（与持仓监控同源） + compute_indicators 指标",
            "ext_info": json.dumps(
                {"degraded": plan["degraded"], "calc_time": plan["calc_time"]},
                ensure_ascii=False),
        })
    except Exception as exc:  # noqa: BLE001 留痕失败不阻塞主流程
        logger.warning("止盈计划留痕失败 %s: %s", plan.get("stock_code"), exc)


# ==================== 告警通道（接近止盈/止盈触发，独立去重，不改监控循环） ====================

def _check_tp_alerts(plan: dict) -> None:
    """到达止盈位主动提示：现价 ≥ TP1 → 「止盈触发」；现价距 TP1 ≤3% → 「接近止盈」。
    与止损告警同等展示级别，按 代码+日期 去重（当日只推一次）。"""
    price, tp1 = plan.get("current_price"), plan.get("tp1")
    if not price or not tp1:
        return
    today = time.strftime("%Y-%m-%d")
    label = f"{plan['stock_code']} {plan['stock_name']}"
    if price >= tp1:
        if not cache.alert_deduplicated(f"takeprofit:{plan['stock_code']}:{today}:hit", 86400):
            repo.insert_alert(
                plan["stock_code"], plan["stock_name"], "止盈触发", "warning",
                f"{label} 现价 {price} 已到达第一止盈位 {tp1}：触发减仓 1/3 锁利，"
                f"止损上移至成本价 {plan.get('ladder_stop_1')}；"
                f"第二止盈位 {plan.get('tp2')}（黄金分割与前期压力共振）",
                "reduce", {"confidence": 80, "plan_tp1": tp1,
                           "plan_tp2": plan.get("tp2")}, False)
    elif price >= tp1 * (1 - TP_NEAR_PCT):
        if not cache.alert_deduplicated(f"takeprofit:{plan['stock_code']}:{today}:near", 86400):
            repo.insert_alert(
                plan["stock_code"], plan["stock_name"], "接近止盈", "info",
                f"{label} 现价 {price} 距第一止盈位 {tp1} ≤3%：准备按分档锁利执行减仓，"
                f"止损同步上移至成本价",
                "hold", {"confidence": 80, "plan_tp1": tp1,
                         "plan_tp2": plan.get("tp2")}, False)


# ==================== 对外入口 ====================

def build_plans(force: bool = False, trace: bool = True, check_alerts: bool = True) -> dict:
    """全部持仓的止盈/仓位计划（与持仓监控页 100% 同源）。

    force=True 击穿缓存（手动刷新）；结果按 代码+日期 缓存 10 分钟；
    默认顺带写留痕 + 检查接近止盈/止盈触发告警（独立通道，不改监控循环）。
    """
    view = holding_view.build_holding_view()
    rows = view.get("rows") or []
    if not rows:
        return {"rows": [], "quote_time": view.get("quote_time"),
                "quote_error": view.get("quote_error"), "total_capital": 0}

    total_capital = float(view.get("total_capital") or 0)
    total_market_value = sum((r.get("market_value") or 0.0) for r in rows)
    today = time.strftime("%Y-%m-%d")
    source = get_datasource()
    plans = []
    for r in rows:
        code = r["stock_code"]
        cache_key = f"takeprofit:{code}:{today}"
        cached = None if force else cache.get(cache_key)
        if cached is not None:
            try:
                plan = json.loads(cached)
            except (ValueError, TypeError):
                plan = None
            if plan and plan.get("stock_code") == code:
                plans.append(plan)
                continue
        # K线指标（MonitorAgent 同源；失败降级为固定比例估算）
        ind = {}
        try:
            kline = source.fetch_daily_kline(code, time.strftime("%Y-%m-%d",
                                                                 time.localtime(time.time() - 90 * 86400)), today)
            ind = compute_indicators(kline)
        except Exception as exc:  # noqa: BLE001 K线失败降级
            logger.warning("止盈计划 K线获取失败 %s: %s", code, exc)
        plan = compute_plan({**r, "total_capital": total_capital}, ind)
        plan["anomaly"] = _recent_anomaly(code)
        plan["total_pct"] = round(total_market_value / total_capital * 100, 1) \
            if total_capital > 0 else None
        cache.set(cache_key, json.dumps(plan, ensure_ascii=False),
                  _CACHE_TTL)
        if trace:
            _trace_plan(plan)
        if check_alerts:
            _check_tp_alerts(plan)
        plans.append(plan)
    return {"rows": plans, "quote_time": view.get("quote_time"),
            "quote_error": view.get("quote_error"), "total_capital": total_capital}
