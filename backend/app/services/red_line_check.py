"""持仓红线扫描（批次G）：C1/C2/C3/C4 + K139 SOP + K226 派发期 + K189 对倒 —— 纯计算事实层。

设计纪律：
- 只做数学计算 + 复用 D 派发期 / E 资本视图已落缓存，不落库、不研判（LLM 一票否决）；
- K139/K226 为参考权重（非死条件）；缺数据字段显式 null，不补 0、不补均值（前端显示「—」/灰徽章）；
- C1/C2/C3 阈值是 L0 红线（sir 钦定），本模块只读不改。
"""
import json
import time

from app.cache import cache
from app.core.config import settings
from app.db import repo

# ---------- L0 红线阈值（sir 钦定，不可改） ----------
C1_CAP_PCT = 60.0      # C1：单只占总资产上限 %（超此值触发集中度告警）
C2_DRAWDOWN_PCT = 30.0 # C2：单票日内回撤触发线 %（相对成本，跌破 -30% 触发）
C3_FACTOR = 0.92       # C3：止损 = 成本 × 0.92

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

    供 C1 占比分母；Agent 与路由同源，避免口径漂移。"""
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
    # 每股成本：以 entry_price（平均建仓成本）为准；缺时 cost(总成本)÷股数折算
    cost = _num(h.get("entry_price"))
    shares = _num(h.get("shares"))
    if cost is None and h.get("cost") is not None and shares:
        cost = _num(h["cost"]) / shares
    high_price = _num(h.get("high_price"))
    price = _num(price)
    low = _num(low)

    # C1 单只占比 = 当前价 × 股数 / 总资产（缺总资产/行情 → null）
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
    trade_date = trade_date or time.strftime("%Y-%m-%d")
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
