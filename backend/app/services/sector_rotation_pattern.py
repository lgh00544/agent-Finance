"""板块轮动·批次D 多窗口规律分析：纯代码统计（轮动周期/生命周期/高切频次/放量延续率），零 LLM"""
import logging

from app.db import repo

logger = logging.getLogger(__name__)

TOP_N = 10
VOLUME_SIGNAL = 1.5      # 放量阈值（量比）
STREAK_MAINLINE = 5      # 主线候选：连续居 top10 天数
SWITCH_CHURN = 0.6       # 高切判定阈值


def _window_dates(days: int) -> list[str]:
    """窗口内交易日（旧→新，最多 days 个）"""
    return sorted(repo.list_sector_daily_dates(limit=days * 2))[-days:]


def _top_sets(rows_by_date: dict) -> list[set]:
    """每日 top10 板块名集合（日期升序）"""
    return [{r["sector_name"] for r in rows_by_date[d][:TOP_N]} for d in sorted(rows_by_date)]


def _churns(sets: list[set]) -> list[float]:
    """相邻两日 top10 换手率 = 1 − 重叠/TOP_N"""
    return [round(1 - len(a & b) / TOP_N, 2) for a, b in zip(sets, sets[1:])]


def _max_streaks(sets: list[set]) -> dict[str, int]:
    """各板块连续居 top10 的最长天数（启动→退潮生命周期）"""
    cur: dict[str, int] = {}
    best: dict[str, int] = {}
    for s in sets:
        for name in s:
            cur[name] = cur.get(name, 0) + 1
            best[name] = max(best.get(name, 0), cur[name])
        for name in list(cur):
            if name not in s:
                cur.pop(name, None)
    return best


def _slopes(rows_by_date: dict, dates: list[str], names: list[str]) -> list[dict]:
    """指定板块日涨跌幅最小二乘斜率（x=窗口序号，y=change_pct；样本<2 跳过）"""
    out = []
    for name in names:
        pts = [(i, r["change_pct"]) for i, d in enumerate(dates)
               for r in rows_by_date[d] if r["sector_name"] == name and r.get("change_pct") is not None]
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        n = len(pts)
        mx, my = sum(xs) / n, sum(ys) / n
        denom = sum((x - mx) ** 2 for x in xs)
        slope = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom, 3) if denom else None
        out.append({"sector_name": name, "slope": slope})
    return out


def analyze_patterns(days: int = 20) -> dict:
    """多窗口规律：①轮动周期天数 ②生命周期（平均居前天数）③高切低频次 ④放量+箱位突破次日延续率
    另附累计强度 top10 / streak≥5 主线候选 / 前 3 板块趋势斜率；数据不足返回空结构不报错"""
    dates = _window_dates(days)
    if len(dates) < 2:
        return {"success": False, "days": days, "error": "窗口内数据不足",
                "rotation_cycle_days": None, "lifecycle_avg_streak": None,
                "switch_frequency": None, "volume_breakout_continuation": None,
                "cumulative_strength_top10": [], "mainline_candidates": [], "top_slopes": []}
    rows_by_date = {d: repo.list_sector_daily_by_date(d) for d in dates}
    sets = _top_sets(rows_by_date)
    churn_list = _churns(sets)

    # ① 轮动周期天数：TOP_N / 日均换手（换手 0 → None）
    avg_churn = sum(churn_list) / len(churn_list) if churn_list else 0.0
    cycle = round(TOP_N / avg_churn) if avg_churn > 0 else None

    # ② 生命周期：板块居 top10 的平均连续天数
    streaks = _max_streaks(sets)
    lifecycle = round(sum(streaks.values()) / len(streaks), 1) if streaks else None

    # ③ 高切低频次：窗口内 churn≥0.6 的天数
    switch_count = sum(1 for c in churn_list if c >= SWITCH_CHURN)

    # ④ 放量+箱位突破次日延续率：量比≥1.5 且居前（放量≈箱位突破）→ 次日 change_pct>0 记为延续
    wins = total = 0
    for i, d in enumerate(dates[:-1]):
        signals = [r for r in rows_by_date[d]
                   if (r.get("volume_ratio") or 0) >= VOLUME_SIGNAL and r["rank_no"] <= TOP_N]
        if not signals:
            continue
        next_day = {r["sector_name"]: (r["change_pct"] or 0) for r in rows_by_date[dates[i + 1]]}
        total += len(signals)
        wins += sum(1 for s in signals if next_day.get(s["sector_name"], 0) > 0)
    continuation = round(wins / total, 2) if total else None

    # 累计强度 top10 + 主线候选 + 前 3 板块趋势斜率
    strength: dict[str, float] = {}
    for d in dates:
        for r in rows_by_date[d]:
            strength[r["sector_name"]] = strength.get(r["sector_name"], 0.0) + (r["change_pct"] or 0)
    cum_top = [{"sector_name": n, "cum_strength": round(v, 2)}
               for n, v in sorted(strength.items(), key=lambda x: -x[1])[:TOP_N]]
    mainline = [n for n, s in streaks.items() if s >= STREAK_MAINLINE]

    return {"success": True, "days": len(dates), "window_start": dates[0], "window_end": dates[-1],
            "rotation_cycle_days": cycle, "lifecycle_avg_streak": lifecycle,
            "switch_frequency": switch_count, "volume_breakout_continuation": continuation,
            "cumulative_strength_top10": cum_top,
            "mainline_candidates": mainline,
            "top_slopes": _slopes(rows_by_date, dates, [c["sector_name"] for c in cum_top[:3]])}


WINDOWS = [3, 10, 20, 60]


def get_rotation_daily(trade_date: str | None = None) -> dict:
    """当日板块轮动：状态 + top10 + 归因（默认最新一日；无数据返回空结构不报错）"""
    dates = repo.list_sector_daily_dates(limit=30)
    if not dates:
        return {"trade_date": None, "rotation_state": None, "churn_rate": None,
                "mainline_sector": None, "top10": [], "launch": []}
    d = trade_date or dates[0]
    log = repo.get_sector_rank_log(d) or {}
    top10 = [{"sector_name": r["sector_name"], "change_pct": r["change_pct"],
              "rank_no": r["rank_no"], "volume_ratio": r["volume_ratio"]}
             for r in repo.list_sector_daily_by_date(d)[:TOP_N]]
    return {"trade_date": d,
            "rotation_state": log.get("rotation_state"),
            "churn_rate": log.get("churn_rate"),
            "mainline_sector": log.get("mainline_sector"),
            "top10": top10,
            "launch": repo.list_sector_launch_by_date(d)}
