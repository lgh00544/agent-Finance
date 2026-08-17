"""盘前快筛 + 候选关联度 + 市况切换（批次4·纯代码检测，无 LLM 调用）

职责边界：【刚性代码逻辑】只读消费既有产出，不做市场判断、不反向调用任何 Agent。
- pre_market_screen(): 盘前集合竞价异常检测（大幅低开/高开/可能停牌），逐条落库 + 合并一条飞书
- candidate_industry_concentration(): 候选行业集中度（只读 detail.enriched.industry）
- market_shift_detect(): 市况切换检测（对比 market_condition 评分/档位/上限 + market_intel 阶段/风险偏好）

阈值（-3%/+5%、集中度 50%、评分差 10）均为参考权重，非死条件。
"""
import logging

from app.datasource.fallback import get_datasource
from app.db import repo
from app.services.feishu import push_alert

logger = logging.getLogger(__name__)

# ==================== 盘前快筛 ====================

_LOW_OPEN_PCT = -3.0   # 竞价跌幅 ≤ -3% → 大幅低开预警（参考权重）
_HIGH_OPEN_PCT = 5.0   # 竞价涨幅 ≥ +5% → 大幅高开提示（参考权重）
_ACTION_LOW = "暂缓买入"    # 低开 action（≤16 字符）
_ACTION_HIGH = "注意追高"   # 高开 action（≤16 字符）
_ACTION_STOP = "注意停牌"   # 停牌 action（≤16 字符）


def _anomaly_pct(a: dict) -> str:
    return f" {a['change_pct']}%" if a.get("change_pct") is not None else ""


def pre_market_screen() -> dict:
    """盘前快筛：取最近一批候选（list_candidate_dates()[0]，**非今日**——今日候选当日 16:10 才生成），
    拉集合竞价行情（force_realtime=True 跳过盘中闸门），检测大幅低开/高开/可能停牌。
    每只异常逐条 insert_alert(source=pre_market) + 多只合并一条飞书；无异常不推送不落库。
    竞价数据整体不可用 → 不报错不推送，日志标注「竞价数据暂不可用」。
    返回 {"checked", "anomalies", "skipped?"}"""
    dates = repo.list_candidate_dates(limit=30)
    if not dates:
        logger.info("盘前快筛跳过：无候选日期")
        return {"checked": 0, "anomalies": [], "skipped": "无候选日期"}
    candidates = repo.list_candidates(dates[0], limit=100)
    if not candidates:
        logger.info("盘前快筛跳过：%s 无候选", dates[0])
        return {"checked": 0, "anomalies": [], "skipped": f"{dates[0]} 无候选"}
    source = get_datasource()
    codes = [c["stock_code"] for c in candidates]
    try:
        quotes = source.fetch_spot_quotes_batch(codes, force_realtime=True)
    except Exception as exc:  # noqa: BLE001 竞价数据整体不可用，不报错不推送
        logger.warning("盘前快筛竞价数据暂不可用: %s", exc)
        return {"checked": len(candidates), "anomalies": [], "skipped": "竞价数据暂不可用"}
    if not quotes:
        logger.warning("盘前快筛竞价数据暂不可用（行情返回为空）")
        return {"checked": len(candidates), "anomalies": [], "skipped": "竞价数据暂不可用"}

    anomalies: list[dict] = []
    for c in candidates:
        code = c["stock_code"]
        quote = quotes.get(code) or {}
        price = quote.get("price")
        change_pct = quote.get("change_pct")
        pre_close = (c.get("snapshot") or {}).get("pre_close")
        if price is None:
            # 行情无该股数据 → 可能停牌
            anomalies.append({"code": code, "name": c["stock_name"], "type": "suspended",
                              "severity": "warning", "action": _ACTION_STOP,
                              "message": "今日可能停牌，集合竞价无数据",
                              "change_pct": None, "price": None, "pre_close": pre_close})
            continue
        if change_pct is None:
            if not pre_close:
                continue  # 昨收也缺失 → 该股跳过判定，不报错
            try:
                change_pct = round((float(price) / float(pre_close) - 1) * 100, 2)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
        if change_pct <= _LOW_OPEN_PCT:
            anomalies.append({"code": code, "name": c["stock_name"], "type": "low_open",
                              "severity": "warning", "action": _ACTION_LOW,
                              "message": (f"集合竞价跌幅 {change_pct}%"
                                          f"（昨收 {pre_close or '—'} → 竞价 {price}），建议今日暂缓"),
                              "change_pct": change_pct, "price": price, "pre_close": pre_close})
        elif change_pct >= _HIGH_OPEN_PCT:
            anomalies.append({"code": code, "name": c["stock_name"], "type": "high_open",
                              "severity": "info", "action": _ACTION_HIGH,
                              "message": f"集合竞价涨幅 {change_pct}%，注意追高风险",
                              "change_pct": change_pct, "price": price, "pre_close": pre_close})
        # 正常波动（-3 ~ +5）→ 不告警

    for a in anomalies:
        repo.insert_alert(a["code"], a["name"], "盘前快筛", a["severity"], a["message"],
                          a["action"],
                          {"pre_market": True, "type": a["type"],
                           "change_pct": a["change_pct"], "price": a["price"],
                           "pre_close": a["pre_close"]},
                          pushed=False, source="pre_market")
    if anomalies:
        items = "；".join(f"{a['code']} {a['name']}{_anomaly_pct(a)}" for a in anomalies)
        summary = (f"【盘前快筛汇总】今日 {len(anomalies)} 只候选异常：{items}，详见告警列表")
        push_alert("盘前快筛", "PRE_MARKET", "盘前快筛", "warning", summary, "关注异常候选")
    return {"checked": len(candidates), "anomalies": anomalies}


# ==================== 候选行业集中度 ====================

def candidate_industry_concentration(date: str | None = None) -> dict:
    """候选行业集中度（只读 detail.enriched.industry）：返回
    {total, groups: [{industry, count, pct, codes}], max_concentration, max_industry, coverage}。
    coverage=有效行业候选占比；有效行业覆盖率 <50% 时前端不展示集中度（防"未分类"误导），
    由调用方据 coverage 决定展示。候选 <3 只/行业全空 → 调用方不展示，本函数照常返回统计。"""
    if not date:
        dates = repo.list_candidate_dates(limit=1)
        if not dates:
            return {"total": 0, "groups": [], "max_concentration": 0.0,
                    "max_industry": "", "coverage": 0.0}
        date = dates[0]
    candidates = repo.list_candidates(date, limit=100)
    total = len(candidates)
    if total == 0:
        return {"total": 0, "groups": [], "max_concentration": 0.0,
                "max_industry": "", "coverage": 0.0}
    counts: dict[str, list[str]] = {}
    for c in candidates:
        industry = str(((c.get("detail") or {}).get("enriched") or {}).get("industry") or "").strip()
        if industry:
            counts.setdefault(industry, []).append(c["stock_code"])
    valid = sum(len(v) for v in counts.values())
    coverage = round(valid / total * 100, 1)
    groups = [
        {"industry": ind, "count": len(codes), "codes": codes,
         "pct": round(len(codes) / total * 100, 1)}
        for ind, codes in sorted(counts.items(), key=lambda kv: len(kv[1]), reverse=True)
    ]
    max_industry = groups[0]["industry"] if groups else ""
    max_concentration = groups[0]["pct"] if groups else 0.0
    return {"total": total, "groups": groups,
            "max_concentration": max_concentration, "max_industry": max_industry,
            "coverage": coverage}


# ==================== 市况切换检测 ====================

_SCORE_SHIFT = 10     # 评分差 ≥10 视为骤变（参考权重）


def market_shift_detect() -> list[dict]:
    """市况切换检测：对比今日与上一期（market_condition 评分/档位/候选池上限 +
    market_intel 阶段/风险偏好），任一显著变化 → 落库一条 + 合并一条飞书。
    两表分别取最近两条，不假设同日对齐；某侧缺失只跳过对应维度，不整体放弃；
    无变化 / 两侧都缺 → 不推送不落库。返回变化维度列表 [{dim, text, data}]。"""
    changes: list[dict] = []

    # 市况评分侧（16:10 生成）
    mc_latest = repo.get_latest_market_condition()
    mc_prev = repo.get_prev_market_condition()
    if mc_latest and mc_prev:
        diff = int(mc_latest["total_score"]) - int(mc_prev["total_score"])
        if abs(diff) >= _SCORE_SHIFT:
            arrow = "↑" if diff > 0 else "↓"
            changes.append({"dim": "评分",
                            "text": f"评分：{mc_prev['total_score']}→{mc_latest['total_score']}"
                                    f"（{arrow}{abs(diff)}）",
                            "data": {"prev": mc_prev["total_score"],
                                     "cur": mc_latest["total_score"], "diff": diff}})
        if (mc_latest["band"] or "") != (mc_prev["band"] or ""):
            changes.append({"dim": "档位",
                            "text": f"档位：{mc_prev['band'] or '—'}→{mc_latest['band'] or '—'}",
                            "data": {"prev": mc_prev["band"], "cur": mc_latest["band"]}})
        if int(mc_latest["cap"] or 0) != int(mc_prev["cap"] or 0):
            changes.append({"dim": "候选池上限",
                            "text": f"候选池上限：{mc_prev['cap'] or '—'}→{mc_latest['cap'] or '—'}",
                            "data": {"prev": mc_prev["cap"], "cur": mc_latest["cap"]}})

    # 市场研判侧（16:20 生成）
    intel_dates = repo.list_market_intel_dates(limit=2)
    mi_today = mi_prev = None
    if len(intel_dates) >= 2:
        mi_today = repo.get_market_intel(intel_dates[0])
        mi_prev = repo.get_market_intel(intel_dates[1])
        if mi_today and mi_prev:
            if (mi_today.get("phase") or "") != (mi_prev.get("phase") or ""):
                changes.append({"dim": "行情阶段",
                                "text": f"行情阶段：{mi_prev.get('phase') or '—'}→"
                                        f"{mi_today.get('phase') or '—'}",
                                "data": {"prev": mi_prev.get("phase"),
                                         "cur": mi_today.get("phase")}})
            if (mi_today.get("risk_appetite") or "") != (mi_prev.get("risk_appetite") or ""):
                changes.append({"dim": "风险偏好",
                                "text": f"风险偏好：{mi_prev.get('risk_appetite') or '—'}→"
                                        f"{mi_today.get('risk_appetite') or '—'}",
                                "data": {"prev": mi_prev.get("risk_appetite"),
                                         "cur": mi_today.get("risk_appetite")}})

    if not changes:
        return []

    if mi_today is None and intel_dates:
        mi_today = repo.get_market_intel(intel_dates[0])
    today_summary = (mi_today or {}).get("summary") or ""
    lines = ["【市况切换】"]
    lines.extend(c["text"] for c in changes)
    if today_summary:
        lines.append(f"综述：{today_summary}")
    message = "\n".join(lines)
    signal = {c["dim"]: c["data"] for c in changes}
    pushed = push_alert("市场", "", "市况切换", "warning", message, "关注市况切换")
    repo.insert_alert("", "市场", "市况切换", "warning", message,
                      "关注市况切换", signal, pushed=pushed, source="market_shift")
    return changes
