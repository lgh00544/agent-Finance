"""D' 板块级前瞻：纯代码计算延续、退潮、追高风险与切换候选。"""
import logging
import queue
import threading
import time

from app.core.config import settings
from app.db import repo

logger = logging.getLogger(__name__)
TOP_N = 10
HORIZONS = ("t1", "t3", "t5")


def _clamp(value):
    return max(0.0, min(1.0, float(value)))


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _top(rows):
    return [r["sector_name"] for r in rows[:TOP_N]]


def _history(name, days=10):
    return repo.list_sector_daily_history(name, days)


def _streak(hist):
    count = 0
    for row in reversed(hist):
        if row.get("rank_no", TOP_N + 1) <= 5:
            count += 1
        else:
            break
    return count


def _causal_context(trade_date: str, sector_name: str) -> dict:
    """读取已落库归因；旧日期只作背景，不能在缺失当日归因时修正评分。"""
    current = next(
        (item for item in repo.list_sector_launch_by_date(trade_date)
         if item.get("sector_name") == sector_name),
        None,
    )
    if current is not None:
        evidence = current.get("evidence") or {}
        caps = evidence.get("confidence_caps") or {}
        confidence = current.get("confidence")
        if confidence is None:
            confidence = caps.get("final_confidence")
        try:
            confidence = _clamp(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None
        return {
            "causal_missing": False,
            "source_trade_date": trade_date,
            "confidence": confidence,
            "reason_tags": current.get("reason_tags") or "",
            "evidence": evidence,
        }

    background = None
    for date in repo.list_sector_daily_dates(limit=30):
        if date == trade_date:
            continue
        candidate = next(
            (item for item in repo.list_sector_launch_by_date(date)
             if item.get("sector_name") == sector_name),
            None,
        )
        if candidate is not None:
            background = (date, candidate)
            break
    return {
        "causal_missing": True,
        "source_trade_date": background[0] if background else None,
        "confidence": None,
        "reason_tags": "",
        "evidence": (background[1].get("evidence") or {}) if background else {},
        "background_available": background is not None,
    }


def _apply_causal_adjustment(continuation, chase, causal):
    if continuation is None or not causal or causal.get("causal_missing"):
        return continuation, chase, None
    confidence = causal.get("confidence")
    if confidence is None:
        return continuation, chase, None
    if confidence >= 0.75:
        return _clamp(continuation + 0.05), chase, 0.05
    if confidence < 0.45:
        return _clamp(continuation - 0.05), _clamp(chase + 0.05), -0.05
    return continuation, chase, 0.0


def _score(row, hist, previous, boxes, regime, causal=None):
    name = row["sector_name"]
    top10_freq = sum(1 for r in hist if r.get("rank_no", 99) <= 10) / 10
    streak = _streak(hist)
    volume = row.get("volume_ratio")
    volume_term = _clamp(1 - abs(float(volume) - 1)) if volume is not None else None
    box_pct = (boxes.get(name) or {}).get("box60_pct")
    box = float(box_pct) / 100 if box_pct is not None else None
    high_box = 1 if box is not None and box >= 0.7 else 0
    historical_up = _mean([r.get("up_count") for r in hist[-10:]]) or 1
    breadth = _clamp(((_mean([row.get("up_count")]) or 0) / historical_up) - 1)
    continuation = None
    if volume_term is not None and box is not None:
        continuation = _clamp(0.35 * top10_freq + 0.20 * volume_term +
                              0.20 * _clamp(streak / 5) + 0.15 * breadth +
                              0.10 * (1 - high_box))
    streak_ge_5 = 1 if streak >= 5 else 0
    prev_volume = previous.get("volume_ratio") if previous else None
    volume_fade = 1 if volume is not None and prev_volume not in (None, 0) and volume / prev_volume < 0.8 else 0
    rank_drop = _clamp((row.get("rank_no", 10) - (previous or {}).get("rank_no", row.get("rank_no", 10))) / 10)
    exhaustion = _clamp(0.40 * high_box + 0.30 * streak_ge_5 +
                        0.20 * volume_fade + 0.10 * rank_drop)
    surge = _clamp(float(row.get("change_pct") or 0) / 10)
    chase = _clamp(0.5 * surge + 0.3 * (1 - top10_freq) + 0.2 * high_box)
    technical_continuation = continuation
    continuation, chase, causal_adjustment = _apply_causal_adjustment(
        continuation, chase, causal)
    mainline = regime.get("current_regime") == "mainline"
    fading = regime.get("regime_stage") in ("diverge", "fade") and (
        not regime.get("evidence", {}).get("leader_streak_sector") or
        regime["evidence"].get("leader_streak_sector") != name)
    top10_two_days = len(hist) >= 2 and all(r.get("rank_no", 99) <= 10 for r in hist[-2:])
    expanding = (volume is not None and prev_volume is not None and volume > prev_volume)
    switch = bool(box is not None and box < 0.7 and top10_two_days and expanding and fading)
    bias = "continue" if continuation is not None and continuation >= 0.6 and exhaustion < 0.6 else (
        "switch" if switch else "fade" if exhaustion >= 0.6 else "uncertain")
    sector_tag = "none"
    if switch and continuation is not None and continuation >= 0.5 and streak >= 2:
        sector_tag = "mainline_seed"
    elif exhaustion >= 0.6:
        sector_tag = "fade_warn"
    elif regime.get("regime_stage") == "accelerate" and chase >= 0.5:
        sector_tag = "accelerate_warn"
    elif exhaustion < 0.4 and continuation is not None and continuation >= 0.5 and box is not None and box < 0.6:
        sector_tag = "low_buy"
    elif chase >= 0.6 and top10_freq < 0.3 and streak < 2:
        sector_tag = "one_day_fly"
    return {
        "sector_name": name, "rank_no": row["rank_no"], "stage": regime.get("regime_stage", "unknown"),
        "continuation_prob": continuation, "exhaustion_risk": exhaustion,
        "chase_risk": chase, "switch_candidate": switch,
        "regime": regime.get("current_regime", "unknown"), "forward_bias": bias,
        "sector_tag": sector_tag,
        "evidence": {"top10_freq_10d": top10_freq, "streak": streak,
                     "volume_ratio": volume, "box_position_60d": box,
                     "breadth_expansion": breadth, "mainline_fading": fading,
                     "data_insufficient": len(hist) < 10 or not hist,
                     "technical_continuation_prob": technical_continuation,
                     "causal_missing": bool(causal.get("causal_missing")) if causal else False,
                     "causal_adjustment": causal_adjustment,
                     "causal_confidence": causal.get("confidence") if causal else None,
                     "causal_source_trade_date": causal.get("source_trade_date") if causal else None},
        "mainline": mainline,
    }


def _fetch_boxes(names: list[str]) -> dict:
    """箱位是辅助标注；数据源慢/卡住时降级为空，不能阻塞 D' 主结果落库。"""
    result_q: queue.Queue[tuple[dict | None, Exception | None]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            from app.datasource.akshare_source import AkshareSource
            result_q.put((AkshareSource().fetch_board_box_positions(names), None))
        except Exception as exc:  # noqa: BLE001
            result_q.put((None, exc))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    try:
        boxes, error = result_q.get(timeout=max(0.1, float(settings.datasource_timeout)))
    except queue.Empty:
        logger.warning("板块前瞻箱位获取超时，降级为空箱位")
        return {}
    if error is not None:
        logger.warning("板块前瞻箱位获取失败（标注缺失）: %s", error)
        return {}
    return boxes or {}


def run_sector_forward(trade_date: str | None = None) -> dict:
    """读取 C' 结构结果，按 D' 硬公式计算 top10 三窗口前瞻并落库。"""
    today = trade_date or time.strftime("%Y-%m-%d")
    regime = repo.get_sector_regime_forecast(today)
    rows = repo.list_sector_daily_by_date(today)[:TOP_N]
    if not rows:
        return {"success": False, "trade_date": today, "count": 0, "error": "无全板块日快照"}
    if not regime:
        return {"success": False, "trade_date": today, "count": 0, "error": "行情结构预测不存在"}
    names = [r["sector_name"] for r in rows]
    boxes = _fetch_boxes(names)
    forecasts = []
    for row in rows:
        hist = _history(row["sector_name"], 10)
        previous = hist[-2] if len(hist) >= 2 else None
        causal = _causal_context(today, row["sector_name"])
        score = _score(row, hist, previous, boxes, regime, causal)
        emotion_only = "emotion_only" in {
            tag.strip() for tag in str(causal.get("reason_tags") or "").split(",")
        }
        for horizon in HORIZONS:
            bias = score["forward_bias"]
            if horizon == "t3":
                bias = "diverge" if score["exhaustion_risk"] >= 0.6 else bias
            elif horizon == "t5":
                bias = ("new_mainline_switch" if score["switch_candidate"] else
                        "fade" if score["exhaustion_risk"] >= 0.6 else
                        "mainline_confirm" if bias == "continue" else
                        "invalid_rotation" if regime["current_regime"] == "rotation" else "uncertain")
            if emotion_only:
                if score["sector_tag"] in {"mainline_seed", "low_buy"}:
                    score["sector_tag"] = "one_day_fly"
                if horizon in {"t3", "t5"} and bias in {"continue", "mainline_confirm"}:
                    bias = "uncertain"
            forecasts.append({**score, "trade_date": today, "forward_bias": bias,
                              "forecast_horizon": horizon})
    count = repo.upsert_sector_forward_forecast(forecasts)
    return {"success": True, "trade_date": today, "count": count,
            "regime": regime.get("current_regime")}
