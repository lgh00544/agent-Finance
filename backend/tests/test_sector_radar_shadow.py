"""行业消息雷达 shadow 回填：只统计，不影响正式候选池。"""
import pandas as pd

from app.services import sector_radar


def test_shadow_worker_fills_returns_and_direction(monkeypatch):
    captured = {}

    class DS:
        def fetch_industry_hist(self, sector_name, start_date, end_date):
            return pd.DataFrame([
                {"date": "2026-09-07", "close": 100.0},
                {"date": "2026-09-08", "close": 102.0},
                {"date": "2026-09-10", "close": 105.0},
                {"date": "2026-09-14", "close": 108.0},
                {"date": "2026-09-15", "close": 109.0},
                {"date": "2026-09-16", "close": 111.0},
            ])

    monkeypatch.setattr(sector_radar, "get_datasource", lambda: DS())
    monkeypatch.setattr(sector_radar.repo, "list_sector_shadow_pending", lambda limit: [{
        "id": 1, "interpret_id": 9, "sector_code": "new_energy",
        "sector_name": "新能源", "signal_date": "2026-09-07",
        "base_index_value": 100.0, "t1_return": None, "t3_return": None,
        "t5_return": None,
    }])
    monkeypatch.setattr(sector_radar.repo, "get_sector_news_interpret",
                        lambda iid: {"polarity": "positive"})
    monkeypatch.setattr(sector_radar.repo, "update_sector_shadow",
                        lambda vid, values: captured.update(values) or True)

    assert sector_radar.shadow_verify_worker()["updated"] == 1
    assert captured["t1_return"] == 2.0
    assert captured["t5_return"] == 11.0
    assert captured["direction_correct"] is True
