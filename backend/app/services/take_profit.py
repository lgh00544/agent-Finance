"""持仓止盈/仓位管理计算服务（独立计算模块，不侵入 MonitorAgent 扫描循环）

【规则来源】完全复用现有风控体系（知识库红线 + 既有代码同口径，不新增自定义规则）：
- 分级单票仓位上限（GRADE_POSITION_CAP，A 级 30%）与 C2 总仓位上限 60%
  （C2_TOTAL_POSITION_CAP）——S-4 后唯一源在 core.config（L0 红线，不可经 settings 覆盖）；
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
from app.core import clock
from datetime import timedelta
import json
import logging
import time

from sqlalchemy import select

from app.cache import cache
from app.core.config import C2_TOTAL_POSITION_CAP, C3_STOP_FACTOR, GRADE_POSITION_CAP
from app.datasource.fallback import get_datasource
from app.db import repo
from app.db.models import NewsArticle
from app.db.session import SessionLocal
from app.services import holding_view, reasoning_trace, kline_store
from app.services.feishu import push_alert
from app.services.indicator import compute_indicators

logger = logging.getLogger(__name__)

# ==================== 风控红线（唯一源 core.config，S-4） ====================
C1_SINGLE_CAP = GRADE_POSITION_CAP["A"]      # 分级单票仓位上限（A 级 30%，仅 B+ 可建仓）
C2_TOTAL_CAP = C2_TOTAL_POSITION_CAP / 100  # C2 总仓位上限 60%（比例）
C3_STOP_PCT = C3_STOP_FACTOR                # C3 硬止损线 = 成本 × 0.92（与 routes 同口径）
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

    # 移动止盈线（确定性告警用，S-1）：持仓期最高价 × 0.92，保底成本价；
    # 浮盈 < TRAILING_ENABLE_PNL_PCT 或 high_price 缺失 → None（不启用）
    high_price = float(row.get("high_price") or 0.0) or None
    trailing_stop = calc_trailing_stop(cost, high_price, price) if cost > 0 else None

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
                             f"可加仓至单票仓位上限 {C1_SINGLE_CAP * 100:.0f}%"
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
        "trailing_stop": trailing_stop, "high_price": _round2(high_price),
        "c3_stop": c3_hard, "current_stop": current_stop,
        "ladder_stop_1": ladder_stop_1, "ladder_stop_2": ladder_stop_2,
        "support": support, "ma5": ma5, "ma10": ma10, "volume_ratio": volume_ratio,
        "status": status, "status_tone": status_tone,
        "add_condition": add_condition, "reduce_condition": reduce_condition,
        "degraded": degraded,
        "calc_time": clock.now_str(),
    }


# ==================== 异动联动（K229 异动标记，复用新闻真源表） ====================

def _recent_anomaly(stock_code: str) -> bool:
    """当日该股新闻标题是否含异动类关键词（大额买卖/利好利空等）"""
    today = clock.today()
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
            "generate_date": clock.today(),
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
            "rule_refs": f"分级单票仓位上限 A 级 {C1_SINGLE_CAP * 100:.0f}% / "
                         f"C2 总仓位上限 {C2_TOTAL_CAP * 100:.0f}% / "
                         f"C3 硬止损 成本×{C3_STOP_PCT} / "
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


# ==================== 确定性风控告警通道（止损/移动止盈/止盈，先于 LLM，S-1/S-11） ====================

def _deterministic_alert(code: str, name: str, today: str, kind: str,
                         alert_type: str, severity: str, message: str, action: str,
                         signal: dict) -> bool:
    """确定性告警唯一落库/推送通道（零 LLM）：**投递成功后才置去重位**（S-11）。

    - 去重键 = 代码:类型:日期；先 cache.alert_seen 只读探测，未投递过才推；
    - delivered / not_configured（未配置任何推送通道）视为已处理并置位；
      failed 不置位 → 下一轮扫描自动重试（feishu.push_alert 内含重试与升级留痕）；
    - 无论是否推送成功都落 alert_log（面板可见），push_channel/push_result 留痕。
    返回 True 表示本次新落库一条告警。
    """
    dedup_key = f"{code}:{kind}:{today}"
    if cache.alert_seen(dedup_key):
        return False
    result = push_alert(name, code, alert_type, severity, message, action)
    outcome = str(result.get("result") or "failed")
    if outcome in ("delivered", "not_configured"):
        cache.alert_mark(dedup_key, 86400)
    else:
        logger.warning("确定性告警投递失败（下一轮自动重试）%s/%s: %s",
                       code, kind, result)
    repo.insert_alert(code, name, alert_type, severity, message, action, signal,
                      outcome == "delivered", source="risk_deterministic",
                      push_channel=str(result.get("channel") or "none"),
                      push_result=outcome)
    return True


def _check_tp_alerts(plan: dict) -> None:
    """确定性风控告警（止盈/止损/移动止盈）：先于任何 LLM 研判直接落库并推送。

    触发条件全部是程序计算事实，与 MonitorAgent 扫描循环解耦：
    1) 止损：现价 ≤ max(C3 硬止损, 参考/计划止损) → 「触及止损」critical/exit；
    2) 移动止盈：现价 ≤ 移动止盈线（持仓期最高价×0.92，浮盈 ≥5% 才启用，保底成本）
       → 「移动止盈触发」critical/reduce。注：模块既定语义是「**跌破**移动止盈线」
       （剩余仓位锁利离场，见 calc_trailing_stop 与分档锁利说明），
       故此处判定方向为 price ≤ trailing_stop，而非 price ≥；
    3) 止盈：现价 ≥ 第一止盈位 TP1 → 「止盈触发」warning/reduce；
       现价距 TP1 ≤ TP_NEAR_PCT → 「接近止盈」info/hold。
    三条互斥（按风险优先级取第一条命中），去重范式见 _deterministic_alert。
    """
    code = plan.get("stock_code")
    if not code:
        return
    name = plan.get("stock_name") or code
    price = plan.get("current_price")
    if not price or price <= 0:
        return
    today = clock.today()
    label = f"{code} {name}" if name != code else code

    # 1) 止损：C3 硬止损与计划/参考止损取更严（价位更高）者
    c3_stop, plan_stop = plan.get("c3_stop"), plan.get("current_stop")
    stop_line = max([v for v in (c3_stop, plan_stop) if v]) if (c3_stop or plan_stop) else None
    if stop_line and price <= stop_line:
        _deterministic_alert(
            code, name, today, "stop", "触及止损", "critical",
            f"{label} 现价 {price} 已触及止损线 {stop_line}"
            f"（C3 硬止损 {c3_stop}，当前参考止损 {plan_stop}）：跌破无条件离场，禁止补仓摊薄",
            "exit", {"confidence": 95, "stop_line": stop_line, "c3_stop": c3_stop,
                     "plan_stop": plan_stop})
        return

    # 2) 移动止盈：跌破移动止盈线（最高价×0.92，保底成本）→ 锁利离场
    trailing_stop = plan.get("trailing_stop")
    if trailing_stop and price <= trailing_stop:
        _deterministic_alert(
            code, name, today, "trailing", "移动止盈触发", "critical",
            f"{label} 现价 {price} 已跌破移动止盈线 {trailing_stop}"
            f"（持仓期最高价 {plan.get('high_price')}×{TRAILING_DRAWBACK_PCT}，保底成本价）"
            f"：剩余仓位锁利离场",
            "reduce", {"confidence": 85, "trailing_stop": trailing_stop,
                       "high_price": plan.get("high_price")})
        return

    # 3) 止盈：到达第一止盈位 / 接近第一止盈位
    tp1 = plan.get("tp1")
    if not tp1:
        return
    if price >= tp1:
        _deterministic_alert(
            code, name, today, "takeprofit_hit", "止盈触发", "warning",
            f"{label} 现价 {price} 已到达第一止盈位 {tp1}：触发减仓 1/3 锁利，"
            f"止损上移至成本价 {plan.get('ladder_stop_1')}；"
            f"第二止盈位 {plan.get('tp2')}（黄金分割与前期压力共振）",
            "reduce", {"confidence": 80, "plan_tp1": tp1, "plan_tp2": plan.get("tp2")})
    elif price >= tp1 * (1 - TP_NEAR_PCT):
        _deterministic_alert(
            code, name, today, "takeprofit_near", "接近止盈", "info",
            f"{label} 现价 {price} 距第一止盈位 {tp1} ≤{TP_NEAR_PCT * 100:.0f}%："
            f"准备按分档锁利执行减仓，止损同步上移至成本价",
            "hold", {"confidence": 80, "plan_tp1": tp1, "plan_tp2": plan.get("tp2")})


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
    today = clock.today()
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
                # 缓存命中也要跑确定性告警（S-1）：止盈/止损/移动止盈按本轮现价判定，
                # 不受 10 分钟计划缓存节流；去重键保证同一触发当日只落一条。
                # 计划点位（C3/参考止损/TP1）由成本推出，与缓存同源；只把现价换成最新行情。
                if check_alerts:
                    _check_tp_alerts({**plan, "current_price": r.get("current_price")})
                plans.append(plan)
                continue
        # K线指标（MonitorAgent 同源；失败降级为固定比例估算）
        ind = {}
        try:
            kline = source.fetch_daily_kline(code, (clock.now() - timedelta(days=90)).strftime("%Y-%m-%d"), today)
            ind = compute_indicators(kline)
        except kline_store.MixedAdjustError as exc:  # noqa: BLE001 复权口径漂移：指标不可用，降级不阻塞
            logger.warning("止盈计划 K线复权口径漂移（MixedAdjustError）%s: %s", code, exc)
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
