"""G' 下一个风口预测：调用 D' _score() 派生 top10 外候选。"""
import logging
import time

from app.db import repo
from app.services import sector_forward_view

logger = logging.getLogger(__name__)


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def _expected_days(score: dict, row: dict, regime: dict) -> int:
    evidence = score.get("evidence") or {}
    days = 1
    if score.get("switch_candidate"):
        days += 2
    freq = evidence.get("top10_freq_10d") or 0
    days += 2 if freq >= 0.7 else 1 if freq >= 0.5 else 0
    rank = int(row.get("rank_no") or 99)
    days += -1 if 31 <= rank <= 50 else -2 if rank > 50 else 0
    if regime.get("current_regime") == "mainline" and rank > 10:
        days += 1
    if regime.get("current_regime") in ("rotation", "chaos"):
        days -= 1
    return int(_clamp(days, 1, 5))


def _hot_score(score: dict, row: dict) -> float | None:
    evidence = score.get("evidence") or {}
    continuation = score.get("continuation_prob")
    if continuation is None:
        return None
    raw = (0.40 * (1 if score.get("switch_candidate") else 0) +
           0.30 * float(evidence.get("top10_freq_10d") or 0) +
           0.20 * float(continuation) +
           0.10 * (1 - int(row.get("rank_no") or 80) / 80))
    return _clamp(raw)


def _causal_evidence(score: dict, causal: dict | None) -> dict:
    """只输出可回指的归因；没有关系证据时保留空值和待核验项。"""
    causal = causal or {}
    evidence = {
        "causal_missing": bool(causal.get("causal_missing", True)),
        "parent_confidence": None,
        "transmission_distance": None,
        "migration_logic": None,
        "must_verify": [
            "补齐当日板块启动归因",
            "验证资金流向与领涨股持续性",
            "验证产业或政策传导是否真实存在",
        ],
    }
    if not evidence["causal_missing"]:
        parent_confidence = causal.get("confidence")
        causal_chain = (causal.get("evidence") or {}).get("causal_chain") or []
        transmission = (causal.get("evidence") or {}).get("industry_transmission") or []
        evidence.update({
            "parent_confidence": parent_confidence,
            "transmission_distance": len(transmission) if transmission else None,
            "migration_logic": (
                "；".join(str(item) for item in transmission)
                if transmission else None
            ),
            "must_verify": [
                "验证父板块与候选板块的产业或政策关联",
                "验证资金是否从父板块扩散至候选板块",
                "验证候选板块出现持续性盘面确认",
            ],
        })
        if not causal_chain and evidence["migration_logic"] is None:
            evidence["causal_missing"] = True
    return evidence


def judge_next_hot(trade_date: str | None = None) -> dict:
    """预测当前 top10 外、未来 1-3 日最可能进 top5 的前 5 板块。"""
    today = trade_date or time.strftime("%Y-%m-%d")
    regime = repo.get_sector_regime_forecast(today)
    rows = [r for r in repo.list_sector_daily_by_date(today) if 11 <= int(r.get("rank_no") or 0) <= 80]
    if not regime or not rows:
        repo.upsert_sector_next_hot([], trade_date=today)
        return {"success": True, "trade_date": today, "count": 0, "rows": []}
    names = [r["sector_name"] for r in rows]
    try:
        from app.datasource.akshare_source import AkshareSource
        boxes = AkshareSource().fetch_board_box_positions(names)
    except Exception as exc:  # noqa: BLE001
        logger.warning("下一个风口箱位获取失败（标注缺失）: %s", exc)
        boxes = {}
    out = []
    for row in rows:
        hist = repo.list_sector_daily_history(row["sector_name"], 10)
        prev = hist[-2] if len(hist) >= 2 else None
        causal = sector_forward_view._causal_context(today, row["sector_name"])
        score = sector_forward_view._score(row, hist, prev, boxes, regime, causal)
        hot = _hot_score(score, row)
        evidence = {**(score.get("evidence") or {}),
                    "switch_candidate": score.get("switch_candidate"),
                    "current_rank": row.get("rank_no"),
                    "sector_tag": score.get("sector_tag", "none"),
                    **_causal_evidence(score, causal)}
        if hot is None:
            evidence["data_insufficient"] = True
            continue
        if hot >= 0.5:
            out.append({
                "trade_date": today,
                "sector_name": row["sector_name"],
                "rank_no": row["rank_no"],
                "hot_score": hot,
                "expected_horizon_days": _expected_days(score, row, regime),
                "confidence": max(0.2, hot),
                "trigger_evidence": evidence,
            })
    out = sorted(out, key=lambda r: r["hot_score"], reverse=True)[:5]
    for i, row in enumerate(out, 1):
        row["rank_no"] = i
    count = repo.upsert_sector_next_hot(out, trade_date=today)
    return {"success": True, "trade_date": today, "count": count, "rows": out}
