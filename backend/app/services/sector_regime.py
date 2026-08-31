"""行情结构与板块轮动前瞻·C' 多窗口纯代码识别。"""
import logging
import queue
import statistics
import threading
import time

from app.core.config import settings
from app.db import repo

logger = logging.getLogger(__name__)
TOP_N = 5


def _clamp(v):
    return max(0.0, min(1.0, float(v)))


def _top(rows):
    return [r["sector_name"] for r in rows[:TOP_N]]


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _fetch_boxes(names: list[str]) -> dict:
    """箱位是辅助证据；数据源慢/卡住时降级为空，不能阻塞 C' 结构判定。"""
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
        logger.warning("行情结构箱位获取超时，降级为空箱位")
        return {}
    if error is not None:
        logger.warning("行情结构箱位获取失败（标注缺失）: %s", error)
        return {}
    return boxes or {}


def _metrics(today, dates):
    rows = {d: repo.list_sector_daily_by_date(d) for d in dates}
    top_today = _top(rows.get(dates[0], []))
    churns = []
    for i in range(min(3, len(dates) - 1)):
        overlap = len(set(_top(rows[dates[i]])) & set(_top(rows[dates[i + 1]])))
        churns.append(1 - overlap / TOP_N)
    churn3 = _mean(churns)
    streaks = {n: repo.list_sector_daily_history(n, 10) for n in top_today}
    streak_pairs = {}
    for n, hist in streaks.items():
        count = 0
        for r in reversed(hist):
            if r["rank_no"] <= TOP_N:
                count += 1
            else:
                break
        streak_pairs[n] = count
    leader = max(streak_pairs, key=streak_pairs.get) if streak_pairs else None
    leader_streak = streak_pairs.get(leader, 0)
    top3 = top_today[:3]
    persistence = None
    if top3 and dates:
        hits = sum(1 for d in dates[:20] if any(n in _top(rows[d]) for n in top3))
        persistence = hits / min(20, len(dates))
    recent = [r for r in rows.get(dates[0], [])[:TOP_N]]
    old = [r for r in rows.get(dates[min(2, len(dates) - 1)], [])[:TOP_N]]
    recent_up = _mean([r.get("up_count") for r in recent])
    old_up = _mean([r.get("up_count") for r in old])
    breadth = _clamp((recent_up - old_up) / max(abs(old_up or 1), 1)) if recent_up is not None and old_up is not None else None
    recent_vol = _mean([r.get("volume_ratio") for r in recent])
    old_vol = _mean([r.get("volume_ratio") for r in old])
    volume_confirm = _clamp((recent_vol or 0) - (old_vol or 0)) if recent_vol is not None and old_vol is not None else None
    boxes = {}
    if top_today:
        boxes = _fetch_boxes(top_today)
    box_values = [v.get("box60_pct") for v in boxes.values() if v.get("box60_pct") is not None]
    box_median = statistics.median(box_values) / 100 if box_values else None
    return {
        "top5_churn_3d": churn3,
        "leader_streak_max_10d": leader_streak,
        "leader_streak_sector": leader,
        "top3_persistence_20d": persistence,
        "breadth_expansion_10d": breadth,
        "volume_confirm_3d": volume_confirm,
        "box_position_median_60d": box_median,
        "data_insufficient": len(dates) < 60,
    }


def judge_regime(trade_date: str | None = None) -> dict:
    """综合 3/10/20/60 日窗口，判定当前结构并落库。"""
    today = trade_date or time.strftime("%Y-%m-%d")
    dates = repo.list_sector_daily_dates(limit=60)
    if today in dates:
        dates = dates[dates.index(today):]
    if not dates or not repo.list_sector_daily_by_date(today):
        return {"success": False, "error": f"{today} 无全板块日快照"}
    e = _metrics(today, dates)
    streak = e["leader_streak_max_10d"]
    persist = e["top3_persistence_20d"] or 0
    churn = e["top5_churn_3d"] or 0
    if streak >= 3 and persist >= 0.6:
        regime = "mainline"
    elif churn >= 0.6 and streak < 3:
        regime = "rotation"
    else:
        regime = "chaos"
    box = e["box_position_median_60d"]
    vol = e["volume_confirm_3d"] or 0
    if regime != "mainline":
        stage = "unknown"
    elif streak == 2:
        stage = "start"
    elif streak >= 3 and persist >= 0.6 and churn < 0.5:
        stage = "confirm"
    elif streak >= 3 and vol > 0.2 and (box or 0) >= 0.7:
        stage = "accelerate"
    elif streak >= 3 and churn >= 0.5:
        stage = "diverge"
    elif streak < 3 and (box or 0) >= 0.7:
        stage = "fade"
    else:
        stage = "unknown"
    if regime == "mainline" and stage in ("start", "confirm"):
        t1, t3, t5 = "continue", "continue", "mainline_confirm"
    elif regime == "mainline" and stage in ("accelerate", "diverge"):
        t1, t3, t5 = "fade" if stage == "accelerate" else "switch", "diverge", "new_mainline_switch"
    elif regime == "rotation":
        t1, t3, t5 = "switch", "switch", "invalid_rotation"
    else:
        t1, t3, t5 = "uncertain", "uncertain", "uncertain"
    confidence = min(1, 0.7 + 0.1 * min(streak, 3)) if regime == "mainline" else (
        min(0.8, 0.5 + 0.1 * min(churn * 10, 3)) if regime == "rotation" else 0.4)
    if e["data_insufficient"]:
        confidence = 0.2
    result = {"success": True, "trade_date": today, "current_regime": regime,
              "regime_stage": stage, "regime_confidence": confidence,
              "forward_bias_t1": t1, "forward_bias_t3": t3, "forward_bias_t5": t5,
              "evidence": e, "notes": f"window_days={len(dates)}"}
    repo.upsert_sector_regime_forecast(result)
    return result
