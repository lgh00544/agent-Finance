"""E'-1 行情结构前瞻后验验证：只读预测与后续快照，回填命中结果。"""
import time

from app.db import repo

HORIZON_DAYS = {"t1": 1, "t3": 3, "t5": 5}


def _top(rows: list[dict], n: int) -> list[str]:
    return [r["sector_name"] for r in rows[:n]]


def _row_by_name(rows: list[dict], name: str | None) -> dict | None:
    if not name:
        return None
    return next((r for r in rows if r.get("sector_name") == name), None)


def _sum_change(rows_by_date: dict[str, list[dict]], name: str | None) -> float | None:
    values = []
    for rows in rows_by_date.values():
        row = _row_by_name(rows, name)
        if row is None or row.get("change_pct") is None:
            return None
        values.append(float(row["change_pct"]))
    return sum(values) if values else None


def _normalize_bias(bias: str | None) -> str:
    if bias == "mainline_confirm":
        return "continue"
    if bias == "new_mainline_switch":
        return "switch"
    if bias == "invalid_rotation":
        return "diverge"
    return bias or "uncertain"


def _mainline_sector(regime: dict | None, forecasts: list[dict]) -> str | None:
    evidence = (regime or {}).get("evidence") or {}
    if evidence.get("leader_streak_sector"):
        return evidence["leader_streak_sector"]
    first = next((r for r in forecasts if r.get("rank_no") == 1), None)
    return first.get("sector_name") if first else None


def _switch_sector(forecasts: list[dict], mainline: str | None) -> str | None:
    cand = next((r for r in forecasts if r.get("switch_candidate")), None)
    if cand:
        return cand.get("sector_name")
    cand = next((r for r in forecasts
                 if r.get("sector_name") != mainline and _normalize_bias(r.get("forward_bias")) == "switch"), None)
    if cand:
        return cand.get("sector_name")
    cand = next((r for r in forecasts if r.get("sector_name") != mainline), None)
    return cand.get("sector_name") if cand else None


def _posterior_regime(days_rows: list[list[dict]]) -> str:
    if not days_rows:
        return "chaos"
    top5_sets = [set(_top(rows, 5)) for rows in days_rows]
    overlap = len(set.intersection(*top5_sets)) if len(top5_sets) > 1 else len(top5_sets[0])
    leaders = [rows[0]["sector_name"] for rows in days_rows if rows]
    if overlap >= 3:
        return "mainline"
    if len(set(leaders)) >= min(3, len(leaders)):
        return "rotation"
    return "chaos"


def evaluate_forecast(regime: dict | None, forecasts: list[dict],
                      rows_by_date: dict[str, list[dict]], horizon: str,
                      verify_date: str | None) -> dict:
    """按审核映射表计算单个 horizon 的命中结果。"""
    need_days = HORIZON_DAYS[horizon]
    if len(rows_by_date) < need_days:
        return {
            "verify_date": verify_date,
            "regime_hit": None,
            "top5_continue_rate": None,
            "mainline_hit": None,
            "regime_forecast": (regime or {}).get("current_regime"),
            "miss_reason": "data_insufficient",
            "detail": {"required_days": need_days, "actual_days": len(rows_by_date)},
        }
    horizon_bias = {
        "t1": (regime or {}).get("forward_bias_t1"),
        "t3": (regime or {}).get("forward_bias_t3"),
        "t5": (regime or {}).get("forward_bias_t5"),
    }[horizon]
    prediction = _normalize_bias(horizon_bias)
    mainline = _mainline_sector(regime, forecasts)
    switch_sector = _switch_sector(forecasts, mainline)
    dates = list(rows_by_date.keys())
    days_rows = [rows_by_date[d] for d in dates]
    top5_by_day = {d: _top(rows_by_date[d], 5) for d in dates}
    top10_by_day = {d: _top(rows_by_date[d], 10) for d in dates}
    first_rows = rows_by_date[dates[0]]
    final_rows = rows_by_date[dates[-1]]
    mainline_top5_days = sum(1 for d in dates if mainline in top5_by_day[d])
    top5_continue_rate = mainline_top5_days / need_days if mainline else None
    mainline_sum = _sum_change(rows_by_date, mainline)
    switch_sum = _sum_change(rows_by_date, switch_sector)
    first_mainline = _row_by_name(first_rows, mainline)
    final_mainline = _row_by_name(final_rows, mainline)
    final_switch = _row_by_name(final_rows, switch_sector)
    initial_top5 = {r.get("sector_name") for r in forecasts if r.get("rank_no", 99) <= 5}
    new_top5_first = bool(set(top5_by_day[dates[0]]) - initial_top5)
    posterior = _posterior_regime(days_rows)

    if prediction == "continue":
        if horizon == "t1":
            hit = bool(first_mainline and first_mainline["rank_no"] <= 5 and first_mainline["change_pct"] > 0)
        elif horizon == "t3":
            hit = mainline_top5_days == 3
        else:
            hit = mainline_sum is not None and mainline_sum > 0
    elif prediction == "switch":
        if horizon == "t1":
            hit = new_top5_first
        elif horizon == "t3":
            hit = bool(final_switch and final_switch["rank_no"] <= 5 and
                       (final_mainline is None or final_mainline["rank_no"] > 5))
        else:
            hit = switch_sum is not None and switch_sum > 0
    elif prediction == "fade":
        if horizon == "t1":
            hit = not first_mainline or first_mainline["rank_no"] > 10
        elif horizon == "t3":
            hit = any(mainline not in top10_by_day[d] for d in dates)
        else:
            hit = mainline_sum is not None and mainline_sum < 0
    elif prediction == "diverge":
        if horizon == "t1":
            hit = (regime or {}).get("regime_stage") == "diverge"
        elif horizon == "t3":
            hit = len({rows[0]["sector_name"] for rows in days_rows if rows}) >= 2
        else:
            hit = bool(final_switch and final_switch["rank_no"] <= 5)
    else:
        hit = True

    regime_hit = (regime or {}).get("current_regime") == posterior
    return {
        "verify_date": verify_date,
        "regime_hit": regime_hit,
        "top5_continue_rate": top5_continue_rate,
        "mainline_hit": hit,
        "regime_forecast": (regime or {}).get("current_regime"),
        "miss_reason": "" if hit and regime_hit else "rule_miss",
        "detail": {
            "prediction": prediction,
            "posterior_regime": posterior,
            "mainline_sector": mainline,
            "switch_sector": switch_sector,
            "mainline_change_sum": mainline_sum,
            "switch_change_sum": switch_sum,
        },
    }


def run_sector_forecast_verify(forecast_date: str | None = None) -> dict:
    """回填指定预测日；未指定时默认找已有预测日中可验证的最新一日。"""
    dates_desc = repo.list_sector_daily_dates(limit=120)
    dates = sorted(dates_desc)
    target = forecast_date
    if target is None:
        today = time.strftime("%Y-%m-%d")
        older = [d for d in dates if d < today]
        target = older[-1] if older else None
    if not target or target not in dates:
        return {"success": False, "forecast_date": target, "error": "预测日无全板块日快照"}
    start = dates.index(target) + 1
    later_dates = dates[start:start + max(HORIZON_DAYS.values())]
    regime = repo.get_sector_regime_forecast(target)
    forecasts = repo.list_sector_forward_forecast(target)
    rows = []
    for horizon, need_days in HORIZON_DAYS.items():
        window_dates = later_dates[:need_days]
        rows_by_date = {d: repo.list_sector_daily_by_date(d) for d in window_dates}
        verify_date = window_dates[-1] if len(window_dates) >= need_days else None
        item = evaluate_forecast(regime, forecasts, rows_by_date, horizon, verify_date)
        rows.append({"forecast_date": target, "verify_horizon": horizon, **item})
    count = repo.upsert_sector_forecast_verify(rows)
    return {"success": True, "forecast_date": target, "count": count, "rows": rows}
