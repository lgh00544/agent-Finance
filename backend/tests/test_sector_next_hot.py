"""G' 板块标签与下一个风口预测测试。"""
from app.datasource.akshare_source import AkshareSource
from app.services import sector_forward_view
from app.services import sector_next_hot


def _row(name="A", rank=11, pct=3.0, volume=2.0, up=20):
    return {"sector_name": name, "rank_no": rank, "change_pct": pct,
            "volume_ratio": volume, "up_count": up, "down_count": 3}


def test_one_day_fly_tag():
    row = _row(pct=10.0)
    hist = [_row(rank=20, pct=0.1, volume=1.0) for _ in range(10)]
    score = sector_forward_view._score(row, hist, hist[-1], {"A": {"box60_pct": 80}},
                                       {"current_regime": "chaos", "regime_stage": "unknown"})
    assert score["sector_tag"] == "one_day_fly"


def test_mainline_seed_tag_priority():
    row = _row(volume=1.5, up=30)
    hist = [_row(rank=3, volume=1.0, up=10) for _ in range(10)]
    regime = {"current_regime": "mainline", "regime_stage": "diverge",
              "evidence": {"leader_streak_sector": "OLD"}}
    score = sector_forward_view._score(row, hist, hist[-2], {"A": {"box60_pct": 50}}, regime)
    assert score["sector_tag"] == "mainline_seed"


def test_next_hot_candidates_sorted(monkeypatch):
    rows = [_row(f"S{i}", rank=10 + i, volume=2.0) for i in range(1, 7)]
    regime = {"current_regime": "mainline", "regime_stage": "diverge",
              "evidence": {"leader_streak_sector": "OLD"}}
    histories = {r["sector_name"]: [_row(r["sector_name"], rank=8, volume=1.0),
                                    _row(r["sector_name"], rank=8, volume=1.0)]
                 for r in rows}
    monkeypatch.setattr(sector_next_hot.repo, "get_sector_regime_forecast", lambda d: regime)
    monkeypatch.setattr(sector_next_hot.repo, "list_sector_daily_by_date", lambda d: rows)
    monkeypatch.setattr(sector_next_hot.repo, "list_sector_daily_history",
                        lambda name, days=10: histories[name])
    monkeypatch.setattr(AkshareSource, "fetch_board_box_positions",
                        lambda self, names: {n: {"box60_pct": 50} for n in names})
    saved = {}
    monkeypatch.setattr(sector_next_hot.repo, "upsert_sector_next_hot",
                        lambda items, trade_date=None: saved.update({"items": items}) or len(items))
    result = sector_next_hot.judge_next_hot("2026-08-28")
    assert result["count"] == 5
    assert [r["sector_name"] for r in saved["items"]][:2] == ["S1", "S2"]


def test_expected_horizon_days_switch_and_high_freq():
    score = {"switch_candidate": True, "evidence": {"top10_freq_10d": 0.8}}
    days = sector_next_hot._expected_days(score, _row(rank=12), {"current_regime": "mainline"})
    assert days >= 3
