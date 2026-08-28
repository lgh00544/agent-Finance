"""D' 板块前瞻：硬公式关键分支与三窗口落库测试。"""
from app.datasource.akshare_source import AkshareSource
from app.services import sector_forward_view


def _row(name="A", rank=1, pct=3.0, volume=2.0, up=20):
    return {"sector_name": name, "rank_no": rank, "change_pct": pct,
            "volume_ratio": volume, "up_count": up, "down_count": 3}


def _patch(monkeypatch, rows, history, regime, boxes):
    monkeypatch.setattr(sector_forward_view.repo, "list_sector_daily_by_date",
                        lambda d: rows)
    monkeypatch.setattr(sector_forward_view.repo, "list_sector_daily_history",
                        lambda name, days=10: history)
    monkeypatch.setattr(sector_forward_view.repo, "get_sector_regime_forecast",
                        lambda d: regime)
    saved = {}
    monkeypatch.setattr(sector_forward_view.repo, "upsert_sector_forward_forecast",
                        lambda items: saved.update({"items": items}) or len(items))
    monkeypatch.setattr(AkshareSource, "fetch_board_box_positions",
                        lambda self, names: boxes)
    return saved


def test_high_box_and_surge_raise_risk(monkeypatch):
    row = _row(pct=8.0, volume=2.0)
    history = [_row(rank=1, pct=1.0, volume=1.0) for _ in range(10)]
    saved = _patch(monkeypatch, [row], history,
                   {"current_regime": "mainline", "regime_stage": "accelerate"},
                   {"A": {"box60_pct": 80}})
    result = sector_forward_view.run_sector_forward("2026-08-28")
    item = saved["items"][0]
    assert result["success"] is True
    assert item["exhaustion_risk"] >= 0.6
    assert item["chase_risk"] >= 0.6
    assert item["forward_bias"] == "fade"
    assert len(saved["items"]) == 3


def test_low_box_consecutive_expanding_can_switch(monkeypatch):
    row = _row(pct=2.0, volume=2.0)
    history = [_row(rank=8, pct=1.0, volume=1.0),
               _row(rank=8, pct=1.0, volume=1.0)]
    regime = {
        "current_regime": "mainline", "regime_stage": "diverge",
        "evidence": {"leader_streak_sector": "OLD"},
    }
    saved = _patch(monkeypatch, [row], history, regime,
                   {"A": {"box60_pct": 50}})
    sector_forward_view.run_sector_forward("2026-08-28")
    item = next(r for r in saved["items"] if r["forecast_horizon"] == "t5")
    assert item["switch_candidate"] is True
    assert item["forward_bias"] == "new_mainline_switch"


def test_missing_box_keeps_risk_and_null_continuation(monkeypatch):
    row = _row(volume=None)
    history = [_row(rank=1) for _ in range(10)]
    saved = _patch(monkeypatch, [row], history,
                   {"current_regime": "rotation", "regime_stage": "unknown"},
                   {})
    result = sector_forward_view.run_sector_forward("2026-08-28")
    assert result["success"] is True
    assert saved["items"][0]["continuation_prob"] is None
    assert saved["items"][0]["switch_candidate"] is False
