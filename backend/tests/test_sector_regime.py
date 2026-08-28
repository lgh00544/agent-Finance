"""C' 行情结构识别：四个纯代码场景，不触网。"""
from app.services import sector_regime
from app.datasource.akshare_source import AkshareSource


def _fixture(monkeypatch, current, history, boxes=None, days=None):
    dates = days or ["2026-08-28", "2026-08-27", "2026-08-26", "2026-08-25"]
    rows = {d: current if i == 0 else current for i, d in enumerate(dates)}
    rows.update(history)
    monkeypatch.setattr(sector_regime.repo, "list_sector_daily_dates",
                        lambda limit=60: dates)
    monkeypatch.setattr(sector_regime.repo, "list_sector_daily_by_date",
                        lambda d: rows.get(d, []))
    monkeypatch.setattr(sector_regime.repo, "list_sector_daily_history",
                        lambda name, days=10: history.get(name, []))
    monkeypatch.setattr(sector_regime.repo, "upsert_sector_regime_forecast", lambda row: 1)
    monkeypatch.setattr(AkshareSource, "fetch_board_box_positions",
                        lambda self, names: boxes or {})


def _rows(names, rank_start=1, up=10, volume=1.2):
    return [{"sector_name": n, "rank_no": rank_start + i, "change_pct": 2.0,
             "up_count": up, "down_count": 3, "volume_ratio": volume}
            for i, n in enumerate(names)]


def _history(name, ranks):
    return [{"sector_name": name, "rank_no": rank, "change_pct": 1.0,
             "up_count": 10, "down_count": 3, "volume_ratio": 1.2}
            for rank in ranks]


def test_mainline_confirm(monkeypatch):
    names = ["A", "B", "C", "D", "E"]
    current = _rows(names)
    history = {n: _history(n, [1, 2, 3]) for n in names}
    _fixture(monkeypatch, current, history,
             boxes={n: {"box60_pct": 40} for n in names})
    result = sector_regime.judge_regime("2026-08-28")
    assert result["current_regime"] == "mainline"
    assert result["regime_stage"] == "confirm"
    assert result["forward_bias_t1"] == "continue"
    assert set(result["evidence"]) >= {
        "top5_churn_3d", "leader_streak_max_10d", "leader_streak_sector",
        "top3_persistence_20d", "breadth_expansion_10d", "volume_confirm_3d",
        "box_position_median_60d",
    }


def test_rotation_accelerate(monkeypatch):
    current = _rows(["A", "B", "C", "D", "E"])
    old = _rows(["F", "G", "H", "I", "J"])
    older = _rows(["K", "L", "M", "N", "O"])
    oldest = _rows(["P", "Q", "R", "S", "T"])
    history = {n: _history(n, [6, 7]) for n in ["A", "B", "C", "D", "E"]}
    days = ["2026-08-28", "2026-08-27", "2026-08-26", "2026-08-25"]
    _fixture(monkeypatch, current, {**history, "2026-08-27": old,
                                    "2026-08-26": older, "2026-08-25": oldest},
             boxes={}, days=days)
    result = sector_regime.judge_regime("2026-08-28")
    assert result["current_regime"] == "rotation"
    assert result["regime_stage"] == "unknown"
    assert result["forward_bias_t1"] == "switch"


def test_conflicting_evidence_is_chaos(monkeypatch):
    names = ["A", "B", "C", "D", "E"]
    current = _rows(names)
    history = {n: _history(n, [6, 7]) for n in names}
    _fixture(monkeypatch, current, history, boxes={})
    result = sector_regime.judge_regime("2026-08-28")
    assert result["current_regime"] == "chaos"
    assert result["forward_bias_t1"] == "uncertain"


def test_single_day_strength_does_not_become_mainline(monkeypatch):
    names = ["A", "B", "C", "D", "E"]
    current = _rows(names, up=20, volume=3.0)
    history = {n: _history(n, [1, 6, 7]) for n in names}
    _fixture(monkeypatch, current, history,
             boxes={n: {"box60_pct": 80} for n in names})
    result = sector_regime.judge_regime("2026-08-28")
    assert result["current_regime"] != "mainline"
    assert result["evidence"]["data_insufficient"] is True
    assert result["regime_confidence"] == 0.2
