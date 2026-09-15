from fastapi.testclient import TestClient

from app.main import app
from app.services import factor_ic


def _row(**overrides):
    row = {
        "id": 1, "factor_id": "f01", "factor_name": "20日动量",
        "category": "动量", "period": "2026-08", "ic": 0.031,
        "ir": 1.2, "hit_rate": 0.67, "sample_size": 120,
        "abs_ic": 0.031, "rank_in_category": 1, "status": "active",
    }
    return {**row, **overrides}


def test_factor_ic_api_returns_history(monkeypatch):
    monkeypatch.setattr(factor_ic, "list_history", lambda *args: [_row()])
    response = TestClient(app).get("/api/factor-ic-history")
    assert response.status_code == 200
    assert response.json()[0]["factor_id"] == "f01"


def test_factor_ic_api_passes_filters_and_limit(monkeypatch):
    captured = {}

    def fake_list(factor_id, period, limit):
        captured.update(factor_id=factor_id, period=period, limit=limit)
        return []

    monkeypatch.setattr(factor_ic, "list_history", fake_list)
    response = TestClient(app).get(
        "/api/factor-ic-history?factor_id=f07&period=2026-07&limit=25")
    assert response.status_code == 200 and response.json() == []
    assert captured == {"factor_id": "f07", "period": "2026-07", "limit": 25}


def test_factor_ic_api_preserves_rank_and_deprecated_status(monkeypatch):
    rows = [_row(), _row(id=2, factor_id="f02", rank_in_category=2,
                         status="deprecated_candidate", ic=0.005)]
    monkeypatch.setattr(factor_ic, "list_history", lambda *args: rows)
    payload = TestClient(app).get("/api/factor-ic-history").json()
    assert [item["rank_in_category"] for item in payload] == [1, 2]
    assert payload[1]["status"] == "deprecated_candidate"
