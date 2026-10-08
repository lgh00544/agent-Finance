"""E'-2 前瞻准确率统计：只读 sector_forecast_verify，不重算单条验证。"""
from datetime import datetime, timedelta

from app.db import repo
from app.db.models import _now

WINDOWS = (30, 60, 90)


def _window_start_dates(end_key: str, days: int) -> list[str]:
    """返回 end_key 之前（含）最近 days 个交易日（B 支线：准确率窗口按交易日口径，
    避免自然日窗口混入非交易日稀释样本；交易日历不可用时退化为自然日窗口）。"""
    try:
        from app.datasource.akshare_source import AkshareSource
        calendar = sorted(AkshareSource().fetch_trade_calendar() or [])
    except Exception:  # noqa: BLE001 日历不可用退化自然日窗口
        calendar = []
    if not calendar:
        end_dt = _parse_date(end_key)
        start_key = (end_dt - timedelta(days=days)).strftime("%Y-%m-%d")
        return [start_key, end_key]
    before = [d for d in calendar if d <= end_key]
    if not before:
        return [end_key, end_key]
    picked = before[-days:]
    return [picked[0], picked[-1]]


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
    return _now()


def _group_metrics(items: list[dict], key: str, value: str) -> dict:
    rows = [row for row in items if key(row) == value]
    return {
        "band": value,
        "sample_count": len(rows),
        "regime_hit_rate": _rate([row.get("regime_hit") for row in rows]),
        "top5_continue_rate": _avg([row.get("top5_continue_rate") for row in rows]),
        "mainline_hit_rate": _rate([row.get("mainline_hit") for row in rows]),
    }


def summarize_forecast_accuracy(end_date: str | None = None,
                                windows: tuple[int, ...] = WINDOWS) -> dict:
    """按近 30/60/90 个交易日窗口（交易日历不可用时退化自然日）与 regime 聚合命中率。"""
    end_dt = _parse_date(end_date)
    max_start = (end_dt - timedelta(days=max(windows))).strftime("%Y-%m-%d")
    end_key = end_dt.strftime("%Y-%m-%d")
    rows = repo.list_sector_forecast_verify(max_start, end_key)
    out = []
    for days in windows:
        start_key, window_end = _window_start_dates(end_key, days)
        win_rows = [r for r in rows if start_key <= r.get("forecast_date", "") <= window_end
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
        def causal_band(row: dict) -> str:
            review = (row.get("detail") or {}).get("causal_review") or {}
            return review.get("confidence_band") or "missing"
        causal_groups = [_group_metrics(win_rows, causal_band, band)
                         for band in ("high", "medium", "low", "missing")
                         if any(causal_band(row) == band for row in win_rows)]
        out.append({
            "window_days": days,
            "start_date": start_key,
            "end_date": end_key,
            "sample_count": len(win_rows),
            "groups": groups,
            "causal_groups": causal_groups,
        })
    return {"windows": out}
