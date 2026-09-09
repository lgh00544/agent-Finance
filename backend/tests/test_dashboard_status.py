"""首页可建仓判定的三态状态契约测试。"""

from app.services import dashboard


def test_tradeable_view_ready_and_pending(monkeypatch):
    monkeypatch.setattr(dashboard.time, "strftime", lambda fmt: "2026-09-08")
    monkeypatch.setattr(dashboard.repo, "list_candidate_tradeable", lambda date, limit: [
        {"stock_code": "600001", "is_tradeable": True},
        {"stock_code": "600002", "is_tradeable": False},
    ])
    ready = dashboard._module_tradeable_view()
    assert ready["status"] == "ready"
    assert ready["count"] == 1 and ready["total"] == 2

    monkeypatch.setattr(dashboard.repo, "list_candidate_tradeable", lambda date, limit: [])
    pending = dashboard._module_tradeable_view()
    assert pending["status"] == "pending"
    assert pending["count"] == 0 and pending["total"] == 0


def test_tradeable_view_error_is_not_zero_opportunity(monkeypatch):
    monkeypatch.setattr(dashboard.time, "strftime", lambda fmt: "2026-09-08")

    def _boom(date, limit):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(dashboard.repo, "list_candidate_tradeable", _boom)
    result = dashboard._module_tradeable_view()
    assert result["status"] == "error"
    assert result["count"] is None and result["total"] is None
    assert result["error"] == "RuntimeError"
