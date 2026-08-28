"""D' 板块级前瞻：纯代码计算延续、退潮、追高风险与切换候选。"""
import logging
import time

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


def _score(row, hist, previous, boxes, regime):
    name = row["sector_name"]
    top10_freq = sum(1 for r in hist if r.get("rank_no", 99) <= 10) / 10
    streak = _streak(hist)
    volume = row.get("volume_ratio")
    volume_term = _clamp(1 - abs(float(volume) - 1)) if volume is not None else None
    box_pct = (boxes.get(name) or {}).get("box60_pct")
    box = float(box_pct) / 100 if box_pct is not None else None
    high_box = 1 if box is not None and box >= 0.7 else 0
    breadth = _clamp((_mean([row.get("up_count")]) or 0) /
                     max(_mean([r.get("up_count") for r in hist[-10:]]) or 1) - 1)
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
    mainline = regime.get("current_regime") == "mainline"
    fading = regime.get("regime_stage") in ("diverge", "fade") and (
        not regime.get("evidence", {}).get("leader_streak_sector") or
        regime["evidence"].get("leader_streak_sector") != name)
    top10_two_days = len(hist) >= 2 and all(r.get("rank_no", 99) <= 10 for r in hist[-2:])
    expanding = (volume is not None and prev_volume is not None and volume > prev_volume)
    switch = bool(box is not None and box < 0.7 and top10_two_days and expanding and fading)
    bias = "continue" if continuation is not None and continuation >= 0.6 and exhaustion < 0.6 else (
        "switch" if switch else "fade" if exhaustion >= 0.6 else "uncertain")
    return {
        "sector_name": name, "rank_no": row["rank_no"], "stage": regime.get("regime_stage", "unknown"),
        "continuation_prob": continuation, "exhaustion_risk": exhaustion,
        "chase_risk": chase, "switch_candidate": switch,
        "regime": regime.get("current_regime", "unknown"), "forward_bias": bias,
        "evidence": {"top10_freq_10d": top10_freq, "streak": streak,
                     "volume_ratio": volume, "box_position_60d": box,
                     "breadth_expansion": breadth, "mainline_fading": fading,
                     "data_insufficient": len(hist) < 10 or not hist},
        "mainline": mainline,
    }


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
    try:
        from app.datasource.akshare_source import AkshareSource
        boxes = AkshareSource().fetch_board_box_positions(names)
    except Exception as exc:  # noqa: BLE001
        logger.warning("板块前瞻箱位获取失败（标注缺失）: %s", exc)
        boxes = {}
    forecasts = []
    for row in rows:
        hist = _history(row["sector_name"], 10)
        previous = hist[-2] if len(hist) >= 2 else None
        score = _score(row, hist, previous, boxes, regime)
        for horizon in HORIZONS:
            bias = score["forward_bias"]
            if horizon == "t3":
                bias = "diverge" if score["exhaustion_risk"] >= 0.6 else bias
            elif horizon == "t5":
                bias = ("new_mainline_switch" if score["switch_candidate"] else
                        "fade" if score["exhaustion_risk"] >= 0.6 else
                        "mainline_confirm" if bias == "continue" else
                        "invalid_rotation" if regime["current_regime"] == "rotation" else "uncertain")
            forecasts.append({**score, "forward_bias": bias,
                              "forecast_horizon": horizon})
    count = repo.upsert_sector_forward_forecast(forecasts)
    return {"success": True, "trade_date": today, "count": count,
            "regime": regime.get("current_regime")}
