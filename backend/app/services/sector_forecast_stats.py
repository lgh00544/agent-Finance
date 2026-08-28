"""E'-2 前瞻准确率统计：只读 sector_forecast_verify，不重算单条验证。"""
from datetime import datetime, timedelta

from app.db import repo

WINDOWS = (30, 60, 90)


def _rate(values: list[bool | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(1 for v in valid if v) / len(valid)


def _avg(values: list[float | None]) -> float | None:
    valid = [float(v) for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def _parse_date(value: str | None) -> datetime:
    if value:
        return datetime.strptime(value, "%Y-%m-%d")
    return datetime.now()


def summarize_forecast_accuracy(end_date: str | None = None,
                                windows: tuple[int, ...] = WINDOWS) -> dict:
    """按近 30/60/90 日与 regime 聚合命中率。"""
    end_dt = _parse_date(end_date)
    max_start = (end_dt - timedelta(days=max(windows))).strftime("%Y-%m-%d")
    end_key = end_dt.strftime("%Y-%m-%d")
    rows = repo.list_sector_forecast_verify(max_start, end_key)
    out = []
    for days in windows:
        start_key = (end_dt - timedelta(days=days)).strftime("%Y-%m-%d")
        win_rows = [r for r in rows if start_key <= r.get("forecast_date", "") <= end_key
                    and r.get("miss_reason") != "data_insufficient"]
        regimes = sorted({r.get("regime_forecast") or "unknown" for r in win_rows})
        groups = []
        for regime in regimes:
            items = [r for r in win_rows if (r.get("regime_forecast") or "unknown") == regime]
            groups.append({
                "regime": regime,
                "sample_count": len(items),
                "regime_hit_rate": _rate([r.get("regime_hit") for r in items]),
                "top5_continue_rate": _avg([r.get("top5_continue_rate") for r in items]),
                "mainline_hit_rate": _rate([r.get("mainline_hit") for r in items]),
            })
        out.append({
            "window_days": days,
            "start_date": start_key,
            "end_date": end_key,
            "sample_count": len(win_rows),
            "groups": groups,
        })
    return {"windows": out}
