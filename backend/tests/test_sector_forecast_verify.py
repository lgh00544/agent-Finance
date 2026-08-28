"""E'-1 前瞻验证回填：审核映射表关键分支测试。"""
from app.services import sector_forecast_verify as sfv


def _row(name, rank, pct=1.0):
    return {"sector_name": name, "rank_no": rank, "change_pct": pct}


def _rows(names):
    return [_row(n, i + 1, 1.0) for i, n in enumerate(names)]


def test_t1_continue_hit():
    regime = {
        "current_regime": "mainline",
        "forward_bias_t1": "continue",
        "evidence": {"leader_streak_sector": "半导体"},
    }
    forecasts = [{"sector_name": "半导体", "rank_no": 1, "forecast_horizon": "t1"}]
    actual = {"2026-08-29": [_row("半导体", 2, 2.0), *_rows(["A", "B", "C", "D"])]}

    result = sfv.evaluate_forecast(regime, forecasts, actual, "t1", "2026-08-29")

    assert result["mainline_hit"] is True
    assert result["top5_continue_rate"] == 1.0
    assert result["regime_forecast"] == "mainline"
    assert result["miss_reason"] == ""


def test_t3_switch_hit_when_new_sector_stays_top5_and_mainline_weakens():
    regime = {
        "current_regime": "mainline",
        "forward_bias_t3": "switch",
        "evidence": {"leader_streak_sector": "旧主线"},
    }
    forecasts = [
        {"sector_name": "旧主线", "rank_no": 1, "forecast_horizon": "t3"},
        {"sector_name": "新方向", "rank_no": 6, "forecast_horizon": "t3",
         "switch_candidate": True},
    ]
    actual = {
        "2026-08-29": [_row("新方向", 4), _row("旧主线", 6), *_rows(["A", "B", "C"])],
        "2026-08-30": [_row("新方向", 3), _row("旧主线", 8), *_rows(["D", "E", "F"])],
        "2026-08-31": [_row("新方向", 2), _row("旧主线", 9), *_rows(["G", "H", "I"])],
    }

    result = sfv.evaluate_forecast(regime, forecasts, actual, "t3", "2026-08-31")

    assert result["mainline_hit"] is True
    assert result["detail"]["switch_sector"] == "新方向"


def test_data_insufficient_marks_nulls(monkeypatch):
    monkeypatch.setattr(sfv.repo, "list_sector_daily_dates",
                        lambda limit=120: ["2026-08-29", "2026-08-28"])
    monkeypatch.setattr(sfv.repo, "get_sector_regime_forecast",
                        lambda d: {"current_regime": "rotation", "forward_bias_t5": "uncertain"})
    monkeypatch.setattr(sfv.repo, "list_sector_forward_forecast",
                        lambda d: [{"sector_name": "A", "rank_no": 1}])
    monkeypatch.setattr(sfv.repo, "list_sector_daily_by_date",
                        lambda d: _rows(["A", "B", "C", "D", "E"]))
    saved = {}
    monkeypatch.setattr(sfv.repo, "upsert_sector_forecast_verify",
                        lambda rows: saved.update({"rows": rows}) or len(rows))

    result = sfv.run_sector_forecast_verify("2026-08-28")
    t5 = next(r for r in saved["rows"] if r["verify_horizon"] == "t5")

    assert result["success"] is True
    assert t5["regime_hit"] is None
    assert t5["top5_continue_rate"] is None
    assert t5["mainline_hit"] is None
    assert t5["miss_reason"] == "data_insufficient"
