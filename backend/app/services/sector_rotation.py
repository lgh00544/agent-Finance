"""板块轮动·状态判定服务层：纯代码状态机（mainline/rotation/chaos）+ churn/streak 指标

【刚性代码逻辑】只做指标计算与状态判定，无 LLM；阈值代码定死（churn≥0.6 / streak≥3，
§三），调整走 review_log。数据源：sector_daily_snapshot 历史 + fetch_board_box_positions。
"""
import logging
from datetime import date

from app.db import repo

logger = logging.getLogger(__name__)

TOP_N = 5
STREAK_THRESHOLD = 3      # 连续居 top5 天数 → 主线候选
CHURN_THRESHOLD = 0.6     # 轮动市阈值


def calc_churn_rate(today_top5: list[str], yesterday_top5: list[str]) -> float:
    """榜首更替率 = 1 − (今日 top5 ∩ 昨日 top5)/5；任一侧为空 → 1.0"""
    if not today_top5 or not yesterday_top5:
        return 1.0
    overlap = len(set(today_top5) & set(yesterday_top5))
    return round(1 - overlap / TOP_N, 2)


def calc_streak(sector_name: str, days: int = 10) -> int:
    """板块连续居 top5 天数（含最新交易日；从最新往回数连续 rank_no≤5）"""
    hist = repo.list_sector_daily_history(sector_name, days)
    streak = 0
    for row in reversed(hist):  # 最新在前
        if row["rank_no"] <= TOP_N:
            streak += 1
        else:
            break
    return streak


def judge_rotation_state(trade_date: str | None = None) -> dict:
    """判定并落库当日轮动状态 + 箱位（读 sector_daily_snapshot 历史）

    规则（§三，代码定死）：
      - mainline 主线市：存在板块 streak≥3 且 top3 当日仍在
      - rotation 轮动市：churn≥0.6 且无 streak≥3 板块
      - 否则 chaos
    箱位复用 fetch_board_box_positions（top5 板块 10/60 日，失败标注缺失不阻断）。
    落 sector_daily_rank_log（同 trade_date 删后插），返回完整指标 dict。
    """
    today = trade_date or date.today().isoformat()
    today_rows = repo.list_sector_daily_by_date(today)
    today_top5 = [r["sector_name"] for r in today_rows[:TOP_N]]
    if not today_top5:
        return {"success": False, "error": f"{today} 无全板块日快照",
                "rotation_state": None, "churn_rate": None, "top5_overlap": None,
                "mainline_sector": None, "notes": "数据缺失", "box_positions": {}}

    # 昨日 top5：取 trade_date < today 的最近一日
    dates = repo.list_sector_daily_dates(limit=60)
    yesterday = None
    if today in dates:
        idx = dates.index(today)
        if idx + 1 < len(dates):
            yesterday = dates[idx + 1]
    yesterday_top5 = ([r["sector_name"] for r in repo.list_sector_daily_by_date(yesterday)[:TOP_N]]
                      if yesterday else [])

    churn = calc_churn_rate(today_top5, yesterday_top5)
    overlap = len(set(today_top5) & set(yesterday_top5))
    streaks = {name: calc_streak(name) for name in today_top5}
    top3 = today_top5[:3]
    mainline = next((n for n in today_top5
                     if streaks[n] >= STREAK_THRESHOLD and n in top3), None)

    if mainline:
        state = "mainline"
    elif churn >= CHURN_THRESHOLD and not any(s >= STREAK_THRESHOLD for s in streaks.values()):
        state = "rotation"
    else:
        state = "chaos"

    box_positions = _box_positions(today_top5)
    notes = (f"churn={churn} overlap={overlap} "
             f"streaks={sorted(streaks.items(), key=lambda x: -x[1])}")

    repo.upsert_sector_rank_log({
        "trade_date": today,
        "rotation_state": state,
        "churn_rate": churn,
        "top5_overlap": overlap,
        "mainline_sector": mainline,
        "notes": notes[:255],
    })
    return {"success": True, "trade_date": today, "rotation_state": state,
            "churn_rate": churn, "top5_overlap": overlap, "mainline_sector": mainline,
            "streaks": streaks, "notes": notes, "box_positions": box_positions}


def _box_positions(board_names: list[str]) -> dict:
    """top5 板块 10/60 日箱位（复用 fetch_board_box_positions；失败标注缺失不阻断）"""
    try:
        from app.datasource.akshare_source import AkshareSource
        return AkshareSource().fetch_board_box_positions(board_names)
    except Exception as exc:  # noqa: BLE001 单次失败不影响状态机
        logger.warning("箱位获取失败（标注缺失）: %s", exc)
        return {n: {"main_box_pct": None, "box60_pct": None, "note": "数据缺失"}
                for n in board_names}
