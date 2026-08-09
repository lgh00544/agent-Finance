"""建仓计划量化计算层（LLM 输出 → 可执行数值计划，纯计算零 LLM 调用）

【核心原则】所有数值基于账户真实可用资金、C1/C2 风控红线、标的评级，精确可落地：
- 单票仓位上限按评级分级：A 级 30% / B 级 20% / C 级 10%（C1 红线，仅 B+ 可生成故实际 A/B）；
- C2 总仓位上限 60%：账户可用资金 = 总资产×60% − 当前持仓市值（不足自动缩减各档金额）；
- 股数一律 100 股整数倍（A 股一手），金额/价格 2 位小数；
- 初始止损 = max(LLM 止损, C3 成本×0.92)（更严为准，跌破无条件离场）；
- 盈亏比 = (止盈−成本) / (成本−止损)，不足 3:1 → 仓位自动降档并标注风险；
- 建仓后预计总仓位 = (当前市值 + 计划投入) / 总资产 × 100%，不突破 C2。

【接入】position.py llm_plan 落库前调用，结果写入 detail.quant，展示层直接读取。
"""
import logging
import re
import time

from app.core.config import settings
from app.services import holding_view

logger = logging.getLogger(__name__)

# 分级单票仓位上限（C1 红线，规格硬性规则：A 级 30% / B 级 20% / C 级 10%）
GRADE_CAP_PCT = {"A": 0.30, "B": 0.20, "C": 0.10}
C2_TOTAL_CAP = 0.60          # C2 总仓位上限 60%
BREAKEVEN_MIN = 3.0          # 盈亏比硬性要求 ≥3:1
REDUCE_FACTOR = 0.7          # 盈亏比不足时仓位自动降低比例
LOT = 100                    # A 股一手 100 股


def _round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _lots(amount: float, price: float) -> int:
    """金额按价格换算股数，向下取整到 100 股整数倍（A 股一手规则）"""
    if not amount or not price or price <= 0:
        return 0
    return int(amount / price / LOT) * LOT


def _zone_mid(price_zone: str) -> float | None:
    """价格区间字符串（如 61.5-62.5）→ 中值价；解析失败返回 None"""
    nums = re.findall(r"\d+\.?\d*", str(price_zone or ""))
    if len(nums) >= 2:
        try:
            lo, hi = float(nums[0]), float(nums[1])
            return (lo + hi) / 2
        except (TypeError, ValueError):
            return None
    if len(nums) == 1:
        try:
            return float(nums[0])
        except (TypeError, ValueError):
            return None
    return None


def _account_snapshot() -> tuple[float, float]:
    """账户快照：(总资产, 当前持仓市值)；行情失败降级市值 0，不阻塞量化"""
    total = float(settings.total_capital or 0)
    market_value = 0.0
    try:
        view = holding_view.build_holding_view()
        market_value = sum((r.get("market_value") or 0.0) for r in (view.get("rows") or []))
    except Exception as exc:  # noqa: BLE001 市值获取失败降级 0
        logger.warning("账户持仓市值获取失败（按 0 处理）: %s", exc)
    return total, market_value


def quantify(code: str, name: str, grade: str, output_batches: list,
             stop_loss: float, take_profit: float, latest_close: float,
             latest_date: str = "") -> dict:
    """LLM 输出 → 量化计划（detail.quant 结构）。

    output_batches: [{tranche, price_zone, ratio_pct, trigger_note}]（LLM 分批明细）
    返回全部数值化字段：当前价/单票上限金额与股数/可用资金/初始止损/止盈/盈亏比/
    分档金额股数累计占比/建仓后预计总仓位/降档与风险标注。
    """
    price = float(latest_close or 0)
    total_capital, market_value = _account_snapshot()

    cap_pct = GRADE_CAP_PCT.get(grade, 0.20)
    # 单票投入上限：评级分级 cap × 总资产，受可用资金（C2 约束）限制
    position_amount = total_capital * cap_pct
    available = max(0.0, total_capital * C2_TOTAL_CAP - market_value)
    reduced = False
    notes: list[str] = []
    if position_amount > available:
        position_amount = available
        notes.append("账户可用资金不足（C2 总仓约束），计划金额已自动缩减")

    # 成本基准：第一档价格区间中值（优先）或当前价
    cost_ref = price
    if output_batches:
        mid = _zone_mid(str((output_batches[0] or {}).get("price_zone") or ""))
        if mid:
            cost_ref = mid
    # 初始止损：C3（成本×0.92）与 LLM 止损取更严（价位更高者）
    c3_stop = _round2(cost_ref * 0.92) if cost_ref > 0 else None
    llm_stop = float(stop_loss or 0)
    initial_stop = max(c3_stop or 0, llm_stop) or 0
    initial_stop = _round2(initial_stop) or c3_stop
    tp = _round2(float(take_profit or 0))

    # 盈亏比：(止盈−成本)/(成本−止损)；不足 3:1 → 仓位自动降档并标注
    breakeven = None
    if tp and cost_ref > 0 and initial_stop and cost_ref > initial_stop:
        breakeven = round((tp - cost_ref) / (cost_ref - initial_stop), 2)
    if breakeven is not None and breakeven < BREAKEVEN_MIN:
        position_amount = round(position_amount * REDUCE_FACTOR, 2)
        reduced = True
        notes.append(f"盈亏比 {breakeven}:1 不足 3:1，仓位已自动降低至 {REDUCE_FACTOR * 100:.0f}%"
                     "并请重点跟踪止损纪律")

    # 分档买入明细：金额/股数/累计占比（比例归一化，防 LLM 比例和不等于 100%）
    total_ratio = sum(float(b.get("ratio_pct") or 0) for b in output_batches) or 1.0
    batches = []
    cum_pct = 0.0
    for b in output_batches:
        ratio = float(b.get("ratio_pct") or 0) / total_ratio
        amt = _round2(position_amount * ratio)
        zone = str(b.get("price_zone") or "")
        mid = _zone_mid(zone) or price
        shares = _lots(amt, mid)
        cum_pct = round(cum_pct + ratio * 100, 1)
        batches.append({
            "tranche": b.get("tranche"), "price_zone": zone,
            "trigger_note": str(b.get("trigger_note") or ""),
            "amount": amt, "shares": shares, "cum_pct": cum_pct,
        })

    total_shares = sum(x["shares"] for x in batches)
    total_amount = _round2(sum(x["amount"] or 0 for x in batches))
    expected_total_pct = _round2((market_value + (total_amount or 0)) / total_capital * 100) \
        if total_capital > 0 else None

    return {
        "current_price": _round2(price),
        "price_date": latest_date or time.strftime("%Y-%m-%d"),
        "total_capital": _round2(total_capital),
        "available_capital": _round2(available),
        "position_cap_pct": cap_pct * 100,
        "position_amount": _round2(position_amount),
        "position_shares": _lots(position_amount, price) if price > 0 else 0,
        "initial_stop": initial_stop,
        "c3_stop": c3_stop,
        "take_profit": tp,
        "breakeven_ratio": breakeven,
        "breakeven_ok": breakeven is not None and breakeven >= BREAKEVEN_MIN,
        "expected_total_pct": expected_total_pct,
        "reduced": reduced,
        "batches": batches,
        "total_shares": total_shares,
        "total_amount": total_amount,
        "notes": notes,
    }
