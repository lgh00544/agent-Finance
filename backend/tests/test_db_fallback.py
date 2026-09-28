"""DB 容灾：DB_BACKEND=mysql 云端连不上时自动落本地 SQLite，且多人模式禁止降级。

设计要点（A3 复盘 2026-09-28）：云端不可用不应导致服务起不来，但降级必须显式可见；
多人模式共享主库，静默落本地会造成数据分叉，故一律 fail closed。
"""
from __future__ import annotations

from app.core.config import settings
from app.db import session


def _prep(monkeypatch, *, reachable: bool, multi: bool = False, allow: bool = True) -> None:
    monkeypatch.setattr(settings, "db_backend", "mysql")
    monkeypatch.setattr(settings, "multi_user_enabled", multi)
    monkeypatch.setattr(settings, "db_fallback_to_sqlite", allow)
    monkeypatch.setattr(session, "_mysql_reachable", lambda url: reachable)


def test_cloud_ok_keeps_mysql(monkeypatch):
    _prep(monkeypatch, reachable=True)
    url, meta = session._resolve_engine_url()
    assert url.startswith("mysql+pymysql://")
    assert meta["active"] == "mysql" and meta["fallback"] is False


def test_cloud_down_falls_back_to_sqlite(monkeypatch):
    _prep(monkeypatch, reachable=False)
    url, meta = session._resolve_engine_url()
    assert url.startswith("sqlite:///")
    assert meta["active"] == "sqlite"
    assert meta["fallback"] is True
    assert meta["requested"] == "mysql"
    assert meta["reason"]


def test_multi_user_never_degrades(monkeypatch):
    _prep(monkeypatch, reachable=False, multi=True)
    url, meta = session._resolve_engine_url()
    assert url.startswith("mysql+pymysql://")
    assert meta["fallback"] is False
    assert "多人模式" in meta["reason"]


def test_fallback_can_be_disabled(monkeypatch):
    _prep(monkeypatch, reachable=False, allow=False)
    url, meta = session._resolve_engine_url()
    assert url.startswith("mysql+pymysql://")
    assert meta["fallback"] is False
    assert "DB_FALLBACK_TO_SQLITE" in meta["reason"]


def test_sqlite_mode_never_probes(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(settings, "db_backend", "sqlite")
    monkeypatch.setattr(session, "_mysql_reachable", lambda url: calls.append(url) or True)
    url, meta = session._resolve_engine_url()
    assert url.startswith("sqlite:///")
    assert calls == []
    assert meta["fallback"] is False


def test_state_reports_active_engine(monkeypatch):
    monkeypatch.setattr(settings, "db_backend", "sqlite")
    state = session.get_db_backend_state()
    assert state["active"] == "sqlite"
    assert set(state) >= {"requested", "active", "fallback", "reason"}


def test_probe_non_raising_on_unreachable_host(monkeypatch):
    """探测契约：不可达只返回 False，绝不上抛（否则启动直接崩，容灾就失效了）。"""
    monkeypatch.setattr(settings, "db_probe_timeout_s", 1)
    monkeypatch.setattr(settings, "db_probe_attempts", 1)
    url = "mysql+pymysql://root:secret@127.0.0.1:1/nope?charset=utf8mb4"
    assert session._mysql_reachable(url) is False
