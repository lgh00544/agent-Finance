"""候选池可建仓判定（纯事实计算 + 每日落库）

硬性三条件（口径经用户确认）：
  c1 综合评级 ≥ B：唯一读取 stock_score.grade（ScoreAgent 五维权威评分，与建仓 gate run_position
     同源）；无评分返回 None（= 未评级/不可建仓），绝不拿 Discover confidence_tier 冒充评级；
     人工覆盖（candidate_adjust.tier_override）优先于评分，仍只在 A/B/C 内有效。
  c2 当前股价处于建仓计划首仓买入区间：仅已有 position_plan 的标的判定（现价 ∈ batches[0].price_zone
     解析区间）；无方案 → 判不满足并标注「暂无建仓方案，买点未验证」；
  c3 无重大利空/未触发风控红线：候选入库已过 HARD_RULES 一票否决（默认满足），叠加 detail.risks/
     risk_notice 含重大利空类表述 → 不满足并标注。

仅做聚合与标记，不修改任何选股算法/评级权重/风控规则；覆盖（candidate_adjust）只影响展示层判定。
"""
import logging
import re

from app.core.config import (STRICTNESS_FREEZE_NOTE, apply_market_intel_correction,
                             market_band_info, strictness_policy)
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
                    snapshot: dict | None = None,
                    strictness: str = "标准",
                    win_rate_5d: float | None = None) -> dict:
    """单标的可建仓判定（纯函数）：返回 {is_tradeable, label, block_reason, cond_*, plan_exists, price_zone, current_price}。
    strictness 门槛由调用方注入（tier_allowed + extra_checks）；win_rate_5d 为单股历史 T+5 胜率（% 0-100）"""
    policy = strictness_policy.get(strictness, strictness_policy["标准"])
    cond_grade = 1 if tier_effective in policy["tier_allowed"] else 0
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
        reasons.append("未评级/无权威评分（仅观察，不可建仓）" if tier_effective is None
                       else f"评级未达门槛（{strictness}市况仅 {'/'.join(policy['tier_allowed'])} 可建仓）")
    if not cond_risk:
        reasons.append("候选风险含重大利空类表述")
    cond_win, cond_inflow = _strictness_extra_checks(cand, strictness, win_rate_5d, reasons)

    is_tradeable = 1 if (cond_grade and cond_price and cond_risk and cond_win and cond_inflow) else 0
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


def _strictness_extra_checks(cand: dict, strictness: str,
                             win_rate_5d: float | None, reasons: list) -> tuple[int, int]:
    """严格度额外硬校验（extra_checks）：返回 (cond_win, cond_inflow)；阈值不过追加 reason"""
    policy = strictness_policy.get(strictness, strictness_policy["标准"])
    cond_win, cond_inflow = 1, 1
    win_thr = None
    for chk in policy["extra_checks"]:
        if chk.startswith("win_rate_5d>="):
            win_thr = max(win_thr or 0.0, float(chk.split(">=")[1]))
        elif chk.startswith("main_net_5d>="):
            try:
                main5 = float((cand.get("detail") or {}).get("main_net_5d") or 0)
            except (TypeError, ValueError):
                main5 = 0
            if main5 < float(chk.split(">=")[1]):
                cond_inflow = 0
                reasons.append(f"主力净流入不足 {float(chk.split('>=')[1]) / 1e8:.0f} 亿（{strictness}市况）")
    if win_thr is not None and (win_rate_5d is None or win_rate_5d < win_thr):
        cond_win = 0
        reasons.append(f"历史 T+5 胜率不足 {win_thr:.0f}%（{strictness}市况）")
    return cond_win, cond_inflow


def _effective_tier(cand: dict, adjusts: dict, trade_date: str) -> str | None:
    """唯一评级来源（与建仓 gate 同源）：人工覆盖优先 → 否则读该股当日/最近
    stock_score.grade（ScoreAgent 权威评分）；无评分返回 None（= 未评级/不可建仓），
    绝不拿 Discover confidence_tier 冒充评级。"""
    adj = adjusts.get(cand.get("stock_code"))
    if adj and adj.get("tier_override") in ("A", "B", "C"):
        return adj["tier_override"]
    return repo.get_closest_score_grade(cand.get("stock_code") or "", trade_date)


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


_STRICTNESS_FREEZE_LOGGED = False


def _day_strictness(trade_date: str) -> str:
    """当日最终严格度：市况基底（market_cap_bands 4 元组末位）+ MarketIntel 修正；数据缺失退化基底标准"""
    base = "标准"
    mc = repo.get_latest_market_condition()
    if mc:
        base = market_band_info(mc["total_score"])[3]
    return apply_market_intel_correction(base, repo.get_market_intel(trade_date))


def _history_win_rate(stock_code: str) -> float | None:
    """单股历史 T+5 胜率（%）：全部已追踪行中 t5_pct>0 占比；无有效样本返回 None"""
    rows = repo.list_track_verify(limit=1000)
    rows = [r for r in rows if r.get("stock_code") == stock_code and r.get("t5_pct") is not None]
    if not rows:
        return None
    return sum(1 for r in rows if (r.get("t5_pct") or 0) > 0) / len(rows) * 100


def _log_strictness_freeze(trade_date: str, strictness: str) -> None:
    """严格度 mapping 冻结留痕写 review_log（进程内一次；失败不阻塞判定）"""
    global _STRICTNESS_FREEZE_LOGGED
    if _STRICTNESS_FREEZE_LOGGED:
        return
    try:
        repo.write_review_log(None, "strictness_freeze", "system",
                              note=f"{STRICTNESS_FREEZE_NOTE}；当日 {trade_date} 严格度={strictness}")
        _STRICTNESS_FREEZE_LOGGED = True
    except Exception:  # noqa: BLE001 留痕失败不影响主链路
        logger.warning("严格度冻结留痕写入失败")


def ensure_tradeable(trade_date: str) -> int:
    """当日全部候选逐股判定并落库（幂等覆盖，code+date 唯一）；返回判定条数"""
    try:
        rows = repo.list_candidates(date=trade_date, limit=300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("可建仓判定：候选读取失败 %s", exc)
        return 0
    strictness = _day_strictness(trade_date)
    _log_strictness_freeze(trade_date, strictness)
    adjusts = {a["stock_code"]: a for a in repo.list_candidate_adjusts(trade_date)}
    judged = 0
    for cand in rows:
        code = cand.get("stock_code") or ""
        if not code:
            continue
        try:
            snapshot = repo.get_candidate_snapshot(code, trade_date)
            plan = _latest_plan_for(code)
            tier = _effective_tier(cand, adjusts, trade_date)
            res = judge_tradeable(cand, tier, plan, snapshot, strictness, _history_win_rate(code))
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
