"""D' 板块前瞻：硬公式关键分支与三窗口落库测试。"""
import time

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
    assert item["trade_date"] == "2026-08-28"
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


def test_sector_tag_written_to_forecast_payload(monkeypatch):
    row = _row(pct=8.0, volume=2.0)
    history = [_row(rank=1, pct=1.0, volume=1.0) for _ in range(10)]
    saved = _patch(monkeypatch, [row], history,
                   {"current_regime": "mainline", "regime_stage": "accelerate"},
                   {"A": {"box60_pct": 80}})
    sector_forward_view.run_sector_forward("2026-08-28")
    assert saved["items"][0]["sector_tag"] == "fade_warn"


def test_fetch_boxes_timeout_degrades_to_empty(monkeypatch):
    def slow_fetch(self, names):
        time.sleep(0.3)
        return {"A": {"box60_pct": 80}}

    monkeypatch.setattr(sector_forward_view.settings, "datasource_timeout", 0.1)
    monkeypatch.setattr(AkshareSource, "fetch_board_box_positions", slow_fetch)

    assert sector_forward_view._fetch_boxes(["A"]) == {}


def test_sector_forward_task_skips_refresh_when_target_snapshot_exists(monkeypatch):
    from app.api import routes
    from app.services import sector_daily, sector_regime

    monkeypatch.setattr(routes.repo, "list_sector_daily_by_date",
                        lambda d: [{"trade_date": d}] if d == "2026-08-28" else [])
    monkeypatch.setattr(sector_daily, "refresh_sector_daily_snapshot",
                        lambda trade_date=None: (_ for _ in ()).throw(AssertionError("unexpected refresh")))
    monkeypatch.setattr(sector_regime, "judge_regime",
                        lambda trade_date=None: {"success": True, "trade_date": trade_date})
    monkeypatch.setattr(sector_forward_view, "run_sector_forward",
                        lambda trade_date=None: {"success": True, "trade_date": trade_date})

    result = routes._task_sector_forward({"trade_date": "2026-08-28"})

    assert result["success"] is True
    assert result["trade_date"] == "2026-08-28"
    assert result["refresh"]["skipped"] is True


def test_sector_forward_task_refreshes_missing_target_date(monkeypatch):
    from app.api import routes
    from app.services import sector_daily, sector_regime

    seen = {}
    def fake_refresh(trade_date=None):
        seen["refresh_date"] = trade_date
        return {"success": True, "trade_date": trade_date, "rows": 88, "error": None}

    def fake_judge(trade_date=None):
        seen["regime_date"] = trade_date
        return {"success": True, "trade_date": trade_date}

    monkeypatch.setattr(routes.repo, "list_sector_daily_by_date", lambda d: [])
    monkeypatch.setattr(sector_daily, "refresh_sector_daily_snapshot", fake_refresh)
    monkeypatch.setattr(sector_regime, "judge_regime", fake_judge)
    monkeypatch.setattr(sector_forward_view, "run_sector_forward",
                        lambda trade_date=None: {"success": True, "trade_date": trade_date})

    result = routes._task_sector_forward({"trade_date": "2026-08-28"})

    assert result["success"] is True
    assert result["trade_date"] == "2026-08-28"
    assert seen == {"refresh_date": "2026-08-28", "regime_date": "2026-08-28"}


def test_sync_run_with_timeout_returns_partial():
    import time
    from app.api import routes

    def slow_task(params, progress):
        progress.update({"trade_date": "2026-08-28", "refresh_done": True})
        time.sleep(0.05)
        return {"success": True}

    result = routes._sync_run_with_timeout(slow_task, {}, timeout_seconds=0.001)

    assert result["status"] == "running_partial"
    assert result["trade_date"] == "2026-08-28"
    assert result["refresh_done"] is True


def test_market_diagnostics_returns_table_job_summary(monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes, "_table_latest_count",
                        lambda table, date_col="trade_date": {"latest_date": "2026-08-28", "row_count": 1})
    monkeypatch.setattr(routes, "_job_diag",
                        lambda job_key: {"last_run_at": "2026-08-28 15:45:00",
                                         "last_status": "ok", "last_error": ""})

    result = routes.get_market_diagnostics()

    assert result["status"] == "ok"
    assert result["tables"]["sector_regime_forecast"]["latest_date"] == "2026-08-28"
    assert result["jobs"]["sector_forward"]["last_status"] == "ok"


def test_sector_next_hot_route_reads_repo(monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes.repo, "list_sector_daily_dates", lambda limit=30: ["2026-08-28"])
    monkeypatch.setattr(routes.repo, "list_sector_next_hot_by_date",
                        lambda d, limit: [{"trade_date": d, "sector_name": "A", "rank_no": 11}])

    result = routes.get_sector_next_hot(limit=1)

    assert result["trade_date"] == "2026-08-28"
    assert result["items"][0]["sector_name"] == "A"
