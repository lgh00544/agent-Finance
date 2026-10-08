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
    monkeypatch.setattr(sfv, "_trading_days_after", lambda target, n: [])
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


def test_verify_keeps_causal_snapshot_without_overclaiming_failure():
    regime = {
        "current_regime": "mainline", "forward_bias_t1": "continue",
        "evidence": {"leader_streak_sector": "半导体"},
    }
    forecasts = [{
        "sector_name": "半导体", "rank_no": 1, "forecast_horizon": "t1",
        "evidence": {
            "causal_confidence": 0.8,
            "causal_missing": False,
            "causal_source_trade_date": "2026-08-28",
            "causal_reason_tags": "verified_cause",
            "causal_falsification": {"t1_invalid_if": "龙头走弱"},
            "causal_has_hard_evidence": True,
            "causal_has_transmission": True,
            "causal_has_capital_behavior": True,
        },
    }]
    actual = {"2026-08-29": [_row("半导体", 8, -1.0), *_rows(["A", "B", "C", "D"])]}

    result = sfv.evaluate_forecast(regime, forecasts, actual, "t1", "2026-08-29")
    review = result["detail"]["causal_review"]

    assert result["mainline_hit"] is False
    assert review["confidence_band"] == "high"
    assert review["status"] == "market_not_validated"
    assert review["falsification"]["t1_invalid_if"] == "龙头走弱"
    assert "不自动证明" in review["note"]


def test_uncertain_prediction_marks_independent_field():
    regime = {
        "current_regime": "rotation",
        "forward_bias_t1": None,
        "forward_bias_t3": "uncertain",
        "evidence": {"leader_streak_sector": "半导体"},
    }
    forecasts = [{"sector_name": "半导体", "rank_no": 1, "forecast_horizon": "t1"}]
    actual = {"2026-08-29": [_row("半导体", 2, 2.0), *_rows(["A", "B", "C", "D"])],
              "2026-08-30": [_row("半导体", 3, 1.0), *_rows(["E", "F", "G", "H"])],
              "2026-08-31": [_row("半导体", 4, 0.5), *_rows(["I", "J", "K", "L"])]}

    result = sfv.evaluate_forecast(regime, forecasts, actual, "t3", "2026-08-30")

    assert result["mainline_hit"] is None
    assert result["miss_reason"] == "uncertain"
    assert result["uncertain"] is True
    assert result["detail"]["prediction"] == "uncertain"


def test_posterior_regime_single_day_returns_none():
    assert sfv._posterior_regime([]) == "chaos"
    assert sfv._posterior_regime([_rows(["A", "B", "C", "D", "E"])]) is None
    two_days = [_rows(["A", "B", "C", "D", "E"]),
                [_row("A", 1), _row("B", 2), _row("C", 3), _row("D", 4), _row("E", 5)]]
    assert sfv._posterior_regime(two_days) == "mainline"


def test_run_verify_backfills_all_pending_and_skips_verified(monkeypatch):
    dates = ["2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
    monkeypatch.setattr(sfv.repo, "list_sector_daily_dates",
                        lambda limit=120: list(reversed(dates)))
    monkeypatch.setattr(sfv, "_trading_days_after",
                        lambda target, n: [d for d in dates if d > target][:n])
    monkeypatch.setattr(sfv.repo, "get_sector_regime_forecast",
                        lambda d: {"current_regime": "rotation",
                                   "forward_bias_t1": "uncertain"})
    monkeypatch.setattr(sfv.repo, "list_sector_forward_forecast",
                        lambda d: [{"sector_name": "A", "rank_no": 1,
                                    "forecast_horizon": "t1"}])
    monkeypatch.setattr(sfv.repo, "list_sector_daily_by_date",
                        lambda d: _rows(["A", "B", "C", "D", "E"]))
    monkeypatch.setattr(sfv.repo, "list_sector_forecast_verify", lambda d: [])
    all_rows = []
    monkeypatch.setattr(sfv.repo, "upsert_sector_forecast_verify",
                        lambda rows: all_rows.extend(rows) or len(rows))

    result = sfv.run_sector_forecast_verify(None)

    assert result["success"] is True
    # 4 个预测日全部回填：25 无后续窗口 data_insufficient，其余 3 个正常落值
    assert len(all_rows) == 12
    assert all(r["forecast_date"] in dates for r in all_rows)
    assert len({r["forecast_date"] for r in all_rows}) == 4


def test_run_verify_skips_target_with_t5_done(monkeypatch):
    dates = ["2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
    monkeypatch.setattr(sfv.repo, "list_sector_daily_dates",
                        lambda limit=120: list(reversed(dates)))
    monkeypatch.setattr(sfv, "_trading_days_after",
                        lambda target, n: [d for d in dates if d > target][:n])
    monkeypatch.setattr(sfv.repo, "list_sector_daily_by_date",
                        lambda d: _rows(["A", "B", "C", "D", "E"]))
    monkeypatch.setattr(sfv.repo, "list_sector_forecast_verify", lambda d: [
        {"verify_horizon": "t5", "verify_date": "2026-08-30"},
    ])
    saved = {}
    monkeypatch.setattr(sfv.repo, "upsert_sector_forecast_verify",
                        lambda rows: saved.update({"rows": rows}) or len(rows))

    result = sfv.run_sector_forecast_verify(None)

    assert result["success"] is True
    assert result["skipped"] is True
    assert "rows" not in saved
