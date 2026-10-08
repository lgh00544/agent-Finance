"""持仓红线扫描（批次G）：C1/C2/C3/C4 + K139 SOP + K226 派发期 + K189 对倒 —— 纯计算事实层。

设计纪律：
- 只做数学计算 + 复用 D 派发期 / E 资本视图已落缓存，不落库、不研判（LLM 一票否决）；
- K139/K226 为参考权重（非死条件）；缺数据字段显式 null，不补 0、不补均值（前端显示「—」/灰徽章）；
- C1/C2/C3 阈值是 L0 红线（sir 钦定），本模块只读不改。
"""
from app.core import clock
from datetime import timedelta
import json
import logging
import time

from app.cache import cache
from app.core.config import (
    C1_CONCENTRATION_CAP, C2_INTRADAY_DRAWDOWN_PCT, C3_STOP_FACTOR, settings,
)
from app.db import repo
from app.services import kline_store

logger = logging.getLogger(__name__)

# ---------- L0 红线阈值（sir 钦定，不可改；S-4 后唯一源在 core.config） ----------
C1_CAP_PCT = C1_CONCENTRATION_CAP           # C1：单只占总资产上限 %（集中度告警）
C2_DRAWDOWN_PCT = C2_INTRADAY_DRAWDOWN_PCT  # C2：单票日内回撤触发线 %（相对成本）
C3_FACTOR = C3_STOP_FACTOR                  # C3：止损 = 成本 × 0.92

# ---------- 参考权重（非死条件） ----------
K139_TRAILING_FACTOR = 0.5     # K183 移动止盈 = 成本 + (现价 - 成本) × 0.5
K226_STRONG_PHASE = 4          # 末跌期/触底期 → 强派发（≈3 主体减仓）
K226_MED_PHASE = 2             # 砸盘期/反弹期 → 中等派发（≈2 主体减仓）；phase<2 → 无


def _num(v) -> float | None:
    """安全转 float；None/空/NaN → None（缺数据显式 null）"""
    if v is None:
        return None
    try:
        f = float(v)
        return f if f == f else None  # NaN → None
    except (TypeError, ValueError):
        return None


def account_total_asset() -> float:
    """账户总资产：有券商基线（OCR 确认保存）用真实值，否则用配置总资金（估算）。

    E-14 分母口径标注：本函数是 C1 集中度占比（c1_cap_pct）的**唯一**分母来源，
    Agent 与路由同源，避免口径漂移；与 holding_view 的 target_pct 分母（固定配置基准
    settings.total_capital，不读券商基线）不是同一把尺子，跨页面对比占比前先确认分母。"""
    try:
        baseline = repo.get_latest_account_baseline()
        if baseline:
            asset = _num(baseline.get("total_asset"))
            if asset is not None and asset > 0:
                return asset
    except Exception:  # noqa: BLE001 基线读失败降级配置总资金
        pass
    return float(getattr(settings, "total_capital", 0) or 0)


def _read_cache_json(key: str) -> dict | None:
    """读 JSON 缓存；缺失/坏 JSON → None（不抛错不伪造）"""
    raw = cache.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _k139_stage(price: float, cost: float) -> tuple[str, str]:
    """K139 SOP 持盈不持亏：现价相对成本分档 → (stage, next_action)。参考权重，判断在 LLM。"""
    if price <= cost * C3_FACTOR:
        return "跌破C3", "跌破清仓"
    if price < cost:
        return "试探仓", "持有观察"
    if price >= cost * 1.10:
        return "+10%减仓", "减仓锁利"
    if price >= cost * 1.05:
        return "+5%减仓", "减仓锁利"
    return "持有观察", "持有观察"


def _k226_level(dist: dict | None) -> tuple[int | None, str | None]:
    """K226 派发主体：复用 D 派发期 phase（>=2 触发）。phase 缺失 → 显式 null。"""
    phase = _num(dist.get("phase")) if dist else None
    if phase is None:
        return None, None
    if phase >= K226_STRONG_PHASE:
        return 3, "强派发"
    if phase >= K226_MED_PHASE:
        return 2, "中等派发"
    return 0, "无"


def _compute_row(h: dict, price, low, total_asset: float, trade_date: str) -> dict:
    code = str(h.get("stock_code") or "").strip()
    # 每股成本：以 entry_price（平均建仓成本）为准；缺时用「当前总成本 ÷ 当前股数」折算。
    # S-5 后 holding.cost 恒等于 entry_price × shares（减仓/清仓事务内重算），该回退
    # 与 entry_price 同值；历史脏数据（减仓未重算 cost）也不会再放大每股成本。
    cost = _num(h.get("entry_price"))
    shares = _num(h.get("shares"))
    if cost is None and h.get("cost") is not None and shares and shares > 0:
        cost = _num(h["cost"]) / shares
    high_price = _num(h.get("high_price"))
    price = _num(price)
    low = _num(low)

    # C1 单只占比 = 当前价 × 股数 / 总资产（缺总资产/行情 → null）
    # E-14 分母标注：total_asset 来自 account_total_asset()（有券商基线取真实总资产，
    # 否则取配置总资金 settings.total_capital）；与 holding_view 的市值权重（恒用配置
    # 基准本金）口径不同，两者只在无券商基线时数值一致。
    c1_cap_pct = c1_alert = None
    if price is not None and shares is not None and total_asset > 0:
        c1_cap_pct = round(price * shares / total_asset * 100, 1)
        c1_alert = bool(c1_cap_pct > C1_CAP_PCT)

    # C2 单票日内回撤 = (low - cost)/cost；≤ -30% 触发（缺 low/成本 → null）
    c2_alert = c2_drawdown_pct = None
    if low is not None and cost and cost > 0:
        c2_drawdown_pct = round((low - cost) / cost * 100, 1)
        c2_alert = bool(c2_drawdown_pct <= -C2_DRAWDOWN_PCT)

    # C3 止损 = 成本 × 0.92；当前价 ≤ C3 触发
    c3_stop_loss = round(cost * C3_FACTOR, 2) if cost and cost > 0 else None
    c3_alert = bool(price is not None and c3_stop_loss is not None and price <= c3_stop_loss)

    # C4 突破持仓期最高价（high_price 缺失 → null，不伪造 False）
    c4_high_break = None
    if price is not None and high_price and high_price > 0:
        c4_high_break = bool(price >= high_price)

    # 浮动盈亏 %
    pnl_pct = round((price - cost) / cost * 100, 2) if (price is not None and cost and cost > 0) else None

    # K139 SOP 持盈不持亏（缺行情/成本 → stage 显式 null）
    k139 = {"trailing_stop": None, "stage": None, "next_action": None}
    if price is not None and cost and cost > 0:
        k139 = {
            "trailing_stop": round(cost + (price - cost) * K139_TRAILING_FACTOR, 2),
            "stage": _k139_stage(price, cost)[0],
            "next_action": _k139_stage(price, cost)[1],
        }

    # K226 派发期主体 / K189 对倒：复用 D/E 已落缓存；缺失 → null 不伪造
    dist = _read_cache_json(f"distribution_phase:{trade_date}:{code}")
    k226_count, k226_level = _k226_level(dist)
    cv = _read_cache_json(f"capital_view:{trade_date}:{code}")
    k189 = None
    if cv is not None and cv.get("wash_suspect") is not None:
        k189 = bool(cv["wash_suspect"])

    return {
        "stock_code": code,
        "stock_name": h.get("stock_name") or code,
        "c1_cap_pct": c1_cap_pct,
        "c1_alert": c1_alert,
        "c2_alert": c2_alert,
        "c2_drawdown_pct": c2_drawdown_pct,
        "c3_stop_loss": c3_stop_loss,
        "c3_alert": c3_alert,
        "c4_high_break": c4_high_break,
        "pnl_pct": pnl_pct,
        "k139_sop": k139,
        "k226_subject_count": k226_count,
        "k226_alert_level": k226_level,
        "k189_wash_suspect": k189,
    }


def compute_red_line(holdings: list, prices: dict, total_asset: float,
                     trade_date: str | None = None, lows: dict | None = None) -> list[dict]:
    """按持仓逐行扫描，返回每只持仓的红线事实行（缺数据字段显式 null）。

    - holdings: [{stock_code, entry_price|cost, shares, high_price}]（每股成本以 entry_price 优先）
    - prices:   {code: 现价 float} 或 {code: {"price":.., "low":..}}（low 也可经 lows 单独传）
    - lows:     {code: 当日最低价}；缺 low 时 C2 → null
    """
    trade_date = trade_date or clock.today()
    lows = lows or {}
    rows = []
    for h in holdings:
        code = str(h.get("stock_code") or "").strip()
        pv = prices.get(code)
        if isinstance(pv, dict):
            price = pv.get("price")
            low = pv.get("low") if lows.get(code) is None else lows[code]
        else:
            price = pv
            low = lows.get(code)
        rows.append(_compute_row(h, price, low, total_asset, trade_date))
    return rows


# ==================== 确定性告警通道（越限先于 LLM 落库 + 推送，S-1/S-11） ====================

# 越限字段 → (告警类型, 严重度, 建议动作)；文案由 _red_line_message 生成
_RED_LINE_ALERT_RULES = (
    ("c3_alert", "红线C3-硬止损", "critical", "exit"),
    ("c2_alert", "红线C2-日内回撤", "critical", "exit"),
    ("c1_alert", "红线C1-集中度", "warning", "reduce"),
    ("c4_high_break", "红线C4-突破前高", "info", "hold"),
)


def _red_line_message(row: dict, flag: str) -> str:
    """越限文案：全部取自本次扫描的事实值，缺数据显式「—」，不编造（K227）"""
    code = row.get("stock_code")

    def _v(key):
        value = row.get(key)
        return "—" if value is None else value

    if flag == "c3_alert":
        return (f"{code} 现价已跌破 C3 硬止损 {_v('c3_stop_loss')}"
                f"（成本×{C3_FACTOR}）：跌破无条件离场，禁止补仓摊薄")
    if flag == "c2_alert":
        return (f"{code} 日内最低价回撤 {_v('c2_drawdown_pct')}%"
                f"（≤-{C2_DRAWDOWN_PCT}% 触发线）：单票日内回撤越限")
    if flag == "c1_alert":
        return (f"{code} 单只占总资产 {_v('c1_cap_pct')}%"
                f"（> {C1_CAP_PCT}% 集中度上限）：集中度越限，建议减仓分散")
    return (f"{code} 现价突破持仓期最高价：C4 突破（参考权重，非死条件）")


def emit_red_line_alerts(rows: list, trade_date: str | None = None) -> dict:
    """红线越限结果落库（alert_log, source='red_line'）+ 推送（确定性通道，先于 LLM）。

    去重范式与 take_profit 一致：**投递成功后才置去重位**（S-11）——
    cache.alert_seen 只读探测，未投递过才推；push_alert 结果 delivered/not_configured
    视为已处理并置位，failed 不置位 → 下一轮扫描自动重试（附重试/升级见 feishu.push_alert）。
    单条失败只记日志，不抛不阻塞扫描。返回 {"emitted", "deduplicated", "failed"}。
    """
    from app.services.feishu import push_alert

    trade_date = trade_date or clock.today()
    emitted = deduplicated = failed = 0
    for row in rows or []:
        code = str(row.get("stock_code") or "")
        if not code:
            continue
        name = row.get("stock_name") or code
        for flag, alert_type, severity, action in _RED_LINE_ALERT_RULES:
            if not row.get(flag):
                continue
            dedup_key = f"redline:{code}:{flag}:{trade_date}"
            if cache.alert_seen(dedup_key):
                deduplicated += 1
                continue
            message = _red_line_message(row, flag)
            result = push_alert(name, code, alert_type, severity, message, action)
            outcome = str(result.get("result") or "failed")
            if outcome in ("delivered", "not_configured"):
                cache.alert_mark(dedup_key, 86400)
            else:
                failed += 1
                logger.warning("红线告警投递失败（下一轮自动重试）%s %s: %s",
                               code, flag, result)
            try:
                repo.insert_alert(code, name, alert_type, severity, message, action,
                                  {"red_line": flag, "row": row},
                                  outcome == "delivered", source="red_line",
                                  push_channel=str(result.get("channel") or "none"),
                                  push_result=outcome)
            except Exception as exc:  # noqa: BLE001 单条落库失败不阻塞其余
                failed += 1
                logger.warning("红线告警落库失败 %s/%s: %s", code, flag, exc)
                continue
            emitted += 1
    return {"emitted": emitted, "deduplicated": deduplicated, "failed": failed}


def scan_red_line(trade_date: str | None = None, *, emit: bool = True) -> dict:
    """全持仓红线扫描唯一入口：GET /red_line_check 与 red_line_job 共用同一条链路。

    - 输入与持仓监控页 100% 同源（holding_view.build_holding_view）；
    - 当日 low 逐只取日 K 最新一根，失败则不收录（C2 → null，不伪造）；
    - emit=True 时越限结果落 alert_log（source='red_line'）并推送。
    返回 {"rows", "trade_date", "total_asset", "quote_time", "alerts"}。
    """
    from app.datasource.fallback import get_datasource
    from app.services import holding_view

    trade_date = trade_date or clock.today()
    view = holding_view.build_holding_view()
    view_rows = view.get("rows") or []
    start = (clock.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    source = get_datasource()
    holdings, lows = [], {}
    for r in view_rows:
        code = r.get("stock_code")
        # A-12：high_price 已由 repo.list_holdings 直接返回（含列迁移兜底），
        # build_holding_view 用 {**r, ...} 原样透传 → 不再逐只 repo.get_holding 回查
        # （消除每轮扫描的 N+1 查询）；旧数据缺列 → None → C4 显式 null，不伪造 False。
        holdings.append({"stock_code": code, "stock_name": r.get("stock_name"),
                         "entry_price": r.get("entry_price"), "cost": r.get("cost"),
                         "shares": r.get("shares"), "high_price": r.get("high_price")})
        if not code:
            continue
        try:
            kl = source.fetch_daily_kline(code, start, trade_date)
            if kl is not None and not kl.empty:
                lows[code] = float(kl.iloc[-1]["low"])
        except kline_store.MixedAdjustError as exc:  # noqa: BLE001 复权口径漂移：low 兜底不可用，C2 → null 不伪造
            logger.warning("红线扫描·当日 low 复权口径漂移（MixedAdjustError）%s: %s", code, exc)
        except Exception as exc:  # noqa: BLE001 单只失败不影响其余
            logger.warning("红线扫描·当日 low 取数失败 %s: %s", code, exc)
    prices = {r["stock_code"]: r["current_price"] for r in view_rows
              if r.get("current_price") is not None}
    total_asset = account_total_asset()
    rows = compute_red_line(holdings, prices, total_asset,
                            trade_date=trade_date, lows=lows)
    return {"rows": rows, "trade_date": trade_date, "total_asset": total_asset,
            "quote_time": view.get("quote_time"),
            "alerts": emit_red_line_alerts(rows, trade_date) if emit else None}
