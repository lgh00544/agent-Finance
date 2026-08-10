"""候选池可建仓判定（纯事实计算 + 每日落库）

硬性三条件（口径经用户确认）：
  c1 综合评级 ≥ B：候选 detail.confidence_tier 映射（强烈推荐→A、建议关注→B、谨慎观察→C）；
  c2 当前股价处于建仓计划首仓买入区间：仅已有 position_plan 的标的判定（现价 ∈ batches[0].price_zone
     解析区间）；无方案 → 判不满足并标注「暂无建仓方案，买点未验证」；
  c3 无重大利空/未触发风控红线：候选入库已过 HARD_RULES 一票否决（默认满足），叠加 detail.risks/
     risk_notice 含重大利空类表述 → 不满足并标注。

仅做聚合与标记，不修改任何选股算法/评级权重/风控规则；覆盖（candidate_adjust）只影响展示层判定。
"""
import logging
import re

from app.db import repo

logger = logging.getLogger(__name__)

# 置信档位 → 展示评级（与候选池页 TIER_MAP 同款映射，纯展示层）
TIER_MAP = {"强烈推荐": "A", "建议关注": "B", "谨慎观察": "C"}
# 重大利空类表述命中即判 c3 不满足（候选生成时 LLM 已产出 risks/risk_notice 文本）
_NEGATIVE_KEYWORDS = ("重大利空", "立案", "退市", "暴雷", "监管处罚", "风险警示", "重大诉讼", "问询函")


def tier_of(confidence_tier: str) -> str:
    return TIER_MAP.get(confidence_tier or "", "")


def _zone_bounds(price_zone: str) -> tuple[float, float] | None:
    """价格区间字符串（如「现价 23.5~24.0」）→ (lo, hi)；解析失败返回 None。
    复用 plan_quant._zone_mid 的 regex 思路，取前两个数字为区间上下界。"""
    nums = [float(x) for x in re.findall(r"\d+\.?\d*", str(price_zone or ""))]
    if len(nums) >= 2 and nums[0] < nums[1]:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], nums[0]
    return None


def _has_major_negative(cand: dict) -> bool:
    """c3 校验：risks / risk_notice 命中重大利空类表述"""
    risks = [str(x) for x in (cand.get("detail") or {}).get("risks") or []]
    risks += [str(x) for x in (cand.get("risk_notice") or [])]
    text = " ".join(risks).upper()
    return any(kw in text for kw in _NEGATIVE_KEYWORDS)


def _current_price(cand: dict, snapshot: dict | None, plan: dict | None) -> float | None:
    """判定现价：候选当日快照 price 优先 → plan.quant.current_price 兜底"""
    if snapshot:
        try:
            p = snapshot.get("price")
            if p not in (None, "", "0"):
                return float(p)
        except (TypeError, ValueError):
            pass
    if plan:
        try:
            q = float(((plan.get("detail") or {}).get("quant") or {}).get("current_price") or 0)
            if q > 0:
                return q
        except (TypeError, ValueError):
            pass
    return None


def judge_tradeable(cand: dict, tier_effective: str, plan: dict | None,
                    snapshot: dict | None = None) -> dict:
    """单标的可建仓判定（纯函数）：返回 {is_tradeable, label, block_reason, cond_*, plan_exists, price_zone, current_price}"""
    cond_grade = 1 if tier_effective in ("A", "B") else 0
    cond_risk = 0 if _has_major_negative(cand) else 1
    plan_exists = 1 if plan else 0
    current_price = _current_price(cand, snapshot, plan)
    cond_price = 0
    price_zone = ""
    reasons = []
    if plan:
        batches = plan.get("batches") or []
        price_zone = str((batches[0] or {}).get("price_zone") or "")
        bounds = _zone_bounds(price_zone)
        if bounds is None:
            reasons.append("建仓方案首仓区间无法解析")
        elif current_price is None:
            reasons.append("现价缺失，无法判定买点")
        elif bounds[0] <= current_price <= bounds[1]:
            cond_price = 1
        else:
            reasons.append(f"现价 {current_price:.2f} 偏离首仓区间（{price_zone}），买点未到")
    else:
        reasons.append("暂无建仓方案，买点未验证")
    if not cond_grade:
        reasons.append("评级未达 B（C 级仅观察）")
    if not cond_risk:
        reasons.append("候选风险含重大利空类表述")

    is_tradeable = 1 if (cond_grade and cond_price and cond_risk) else 0
    if is_tradeable:
        label = "可建仓"
    elif tier_effective in ("A", "B"):
        label = "建议关注"
    else:
        label = "观察"
    return {"is_tradeable": is_tradeable, "label": label,
            "block_reason": "；".join(reasons) or "",
            "cond_grade": cond_grade, "cond_price": cond_price, "cond_risk": cond_risk,
            "plan_exists": plan_exists, "price_zone": price_zone, "current_price": current_price}


def _effective_tier(cand: dict, adjusts: dict) -> str:
    """人工覆盖优先，否则置信档位映射"""
    adj = adjusts.get(cand.get("stock_code"))
    if adj and adj.get("tier_override") in ("A", "B", "C"):
        return adj["tier_override"]
    return tier_of(((cand.get("detail") or {}).get("confidence_tier") or ""))


def _latest_plan_for(code: str) -> dict | None:
    """最新非 expired 建仓方案（取最近一次，status != expired）"""
    try:
        plans = repo.list_plans(code=code, limit=20)
    except Exception:  # noqa: BLE001 方案读取失败不阻塞判定
        return None
    for p in plans:
        if (p.get("status") or "proposed") != "expired":
            return p
    return None


def ensure_tradeable(trade_date: str) -> int:
    """当日全部候选逐股判定并落库（幂等覆盖，code+date 唯一）；返回判定条数"""
    try:
        rows = repo.list_candidates(date=trade_date, limit=300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("可建仓判定：候选读取失败 %s", exc)
        return 0
    adjusts = {a["stock_code"]: a for a in repo.list_candidate_adjusts(trade_date)}
    judged = 0
    for cand in rows:
        code = cand.get("stock_code") or ""
        if not code:
            continue
        try:
            snapshot = repo.get_candidate_snapshot(code, trade_date)
            plan = _latest_plan_for(code)
            tier = _effective_tier(cand, adjusts)
            res = judge_tradeable(cand, tier, plan, snapshot)
        except Exception as exc:  # noqa: BLE001 单标的异常不阻塞整体
            logger.warning("可建仓判定 %s@%s 失败: %s", code, trade_date, exc)
            res = {"is_tradeable": 0, "label": "建议关注",
                   "block_reason": f"判定异常（{type(exc).__name__}）",
                   "cond_grade": 0, "cond_price": 0, "cond_risk": 0,
                   "plan_exists": 0, "price_zone": "", "current_price": None}
        repo.upsert_candidate_tradeable(
            code, cand.get("stock_name") or "", trade_date, tier,
            res["is_tradeable"], res["label"], res["plan_exists"],
            res["price_zone"], res["current_price"],
            res["cond_grade"], res["cond_price"], res["cond_risk"],
            res["block_reason"], {"effective_tier": tier,
                                  "confidence_tier": (cand.get("detail") or {}).get("confidence_tier"),
                                  "plan_date": _plan_date(plan)})
        judged += 1
    return judged


def _plan_date(plan: dict | None) -> str:
    return str((plan or {}).get("plan_date") or "")


def ensure_if_missing(trade_date: str) -> int:
    """当日缺判定记录时懒补算（幂等）；已有记录直接返回 0 表示无需补算"""
    if repo.has_tradeable_rows(trade_date):
        return 0
    return ensure_tradeable(trade_date)


def plan_candidate_count(trade_date: str) -> int:
    """可自动生成建仓计划的标的数量：effective_tier ∈ A/B 且暂无建仓方案"""
    rows = repo.list_candidate_tradeable(trade_date, limit=300)
    return sum(1 for r in rows
               if r.get("tier") in ("A", "B") and not r.get("plan_exists"))


def tradeable_view(trade_date: str, limit: int = 200) -> dict:
    """当日可建仓视图（前端顶部计数/卡标签/筛选同源）"""
    ensure_if_missing(trade_date)
    rows = repo.list_candidate_tradeable(trade_date, limit=limit)
    count = sum(1 for r in rows if r.get("is_tradeable"))
    return {"date": trade_date, "count": count,
            "plan_candidate_count": plan_candidate_count(trade_date),
            "total": len(rows), "items": rows}
