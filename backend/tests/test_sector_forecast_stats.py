"""E'-2 前瞻准确率统计 API：只读验证结果聚合。"""
from app.services import sector_forecast_stats as stats


def test_stats_group_by_regime_and_windows(monkeypatch):
    rows = [
        {"forecast_date": "2026-08-27", "regime_forecast": "mainline",
         "regime_hit": True, "top5_continue_rate": 1.0, "mainline_hit": True,
         "miss_reason": ""},
        {"forecast_date": "2026-08-26", "regime_forecast": "mainline",
         "regime_hit": False, "top5_continue_rate": 0.5, "mainline_hit": False,
         "miss_reason": ""},
        {"forecast_date": "2026-08-25", "regime_forecast": "rotation",
         "regime_hit": True, "top5_continue_rate": None, "mainline_hit": True,
         "miss_reason": ""},
        {"forecast_date": "2026-08-24", "regime_forecast": "chaos",
         "regime_hit": None, "top5_continue_rate": None, "mainline_hit": None,
         "miss_reason": "data_insufficient"},
    ]
    monkeypatch.setattr(stats.repo, "list_sector_forecast_verify",
                        lambda start_date=None, end_date=None: rows)

    result = stats.summarize_forecast_accuracy("2026-08-28", windows=(30,))
    groups = {g["regime"]: g for g in result["windows"][0]["groups"]}

    assert result["windows"][0]["sample_count"] == 3
    assert groups["mainline"]["sample_count"] == 2
    assert groups["mainline"]["regime_hit_rate"] == 0.5
    assert groups["mainline"]["top5_continue_rate"] == 0.75
    assert groups["mainline"]["mainline_hit_rate"] == 0.5
    assert groups["rotation"]["regime_hit_rate"] == 1.0
    assert "chaos" not in groups
