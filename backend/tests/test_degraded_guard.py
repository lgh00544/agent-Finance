"""A 方案（防丢）回归：降级标记读写/守卫拦截/降级自动落标记。

背景：降级期数据只写本地 SQLite，而 sync_manager backup 是「本地全表 delete + 云端覆盖」，
若不拦，云端恢复后这批数据会从活库消失（仅剩 backup/ 快照）。
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.db import degraded, session


def _marker(monkeypatch) -> Path:
    # 不用 tempfile.mkdtemp：它用 os.mkdir(0o700) 建目录，本沙箱下该目录不可写
    # （PermissionError Errno 13，即 pytest tmp_path 老问题的根因）。
    base = Path(__file__).resolve().parents[2] / ".wb_h" / "pytest_degraded"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"db_degraded_{uuid4().hex}.json"
    monkeypatch.setenv("DB_DEGRADED_MARKER", str(path))
    return path


def test_mark_read_clear_roundtrip(monkeypatch):
    path = _marker(monkeypatch)
    assert degraded.read() is None
    info = degraded.mark(reason="r1", requested="mysql", active="sqlite", db_path="/tmp/x.db")
    assert path.exists()
    got = degraded.read()
    assert got["reason"] == "r1"
    assert got["requested_backend"] == "mysql"
    assert got["degraded_since"] == info["degraded_since"]
    assert degraded.clear() is True
    assert degraded.read() is None


def test_mark_keeps_first_degraded_since(monkeypatch):
    _marker(monkeypatch)
    first = degraded.mark(reason="r1", requested="mysql", active="sqlite")["degraded_since"]
    second = degraded.mark(reason="r2", requested="mysql", active="sqlite")
    assert second["degraded_since"] == first
    assert second["reason"] == "r2"


def test_guard_blocks_only_with_marker(monkeypatch):
    _marker(monkeypatch)
    assert degraded.guard_backup()["blocked"] is False
    degraded.mark(reason="云端不可达", requested="mysql", active="sqlite")
    guard = degraded.guard_backup()
    assert guard["blocked"] is True
    assert "禁止云端→本地全表覆盖" in guard["reason"]
    degraded.clear()
    assert degraded.guard_backup()["blocked"] is False


def test_corrupt_marker_never_blocks(monkeypatch):
    path = _marker(monkeypatch)
    path.write_text("{not json", encoding="utf-8")
    assert degraded.read() is None
    assert degraded.guard_backup()["blocked"] is False


def test_fallback_writes_marker(monkeypatch):
    path = _marker(monkeypatch)
    monkeypatch.setattr(settings, "db_backend", "mysql")
    monkeypatch.setattr(settings, "multi_user_enabled", False)
    monkeypatch.setattr(settings, "db_fallback_to_sqlite", True)
    monkeypatch.setattr(session, "_mysql_reachable", lambda url: False)
    url, meta = session._resolve_engine_url()
    assert meta["fallback"] is True
    assert url.startswith("sqlite:///")
    assert path.exists()
    info = degraded.read()
    assert info["active_backend"] == "sqlite"
    assert info["requested_backend"] == "mysql"


def test_sqlite_mode_does_not_mark(monkeypatch):
    path = _marker(monkeypatch)
    monkeypatch.setattr(settings, "db_backend", "sqlite")
    session._resolve_engine_url()
    assert not path.exists()
