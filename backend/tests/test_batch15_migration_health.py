"""Batch 15: startup migration observability and production acceptance states."""
from pathlib import Path

from app.db import session
from app.system_map import health


def test_migration_health_reports_healthy_snapshot():
    session.init_db()
    module = health.get_governance_health()["modules"]["database_migration"]

    assert module["status"] == "healthy"
    assert module["reason"] == "本进程已完成启动迁移"
    assert isinstance(module["initialized_at"], str)
    assert set(module["knowledge"]) >= {"added", "existing"}
    assert set(module["experience"]) >= {"added", "existing"}


def test_migration_health_reports_unknown_without_snapshot():
    original = health.get_init_db_result
    health.get_init_db_result = lambda: {"status": "not_run"}
    try:
        result = health.get_governance_health()
    finally:
        health.get_init_db_result = original

    module = result["modules"]["database_migration"]
    assert module["status"] == "unknown"
    assert "重启服务" in module["reason"]
    assert result["status"] in {"unknown", "error"}
    assert result["status"] != "healthy"


def test_migration_health_reports_error_without_marking_overall_healthy():
    original = health.get_init_db_result
    health.get_init_db_result = lambda: {
        "status": "failed",
        "initialized_at": "2026-09-01T10:01:00",
        "backend": "mysql",
        "database": "stock",
        "error": "permission denied while altering private_knowledge",
    }
    try:
        result = health.get_governance_health()
    finally:
        health.get_init_db_result = original

    module = result["modules"]["database_migration"]
    assert module["status"] == "error"
    assert "permission denied" in module["last_error"]
    assert result["status"] == "error"


def test_failed_init_db_persists_error_snapshot(monkeypatch):
    original_snapshot = session.get_init_db_result()
    monkeypatch.setattr(
        session.Base.metadata,
        "create_all",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("permission denied while connecting to database")
        ),
    )

    try:
        try:
            session.init_db()
        except RuntimeError:
            pass
        else:
            raise AssertionError("init_db should expose startup migration failure")

        snapshot = session.get_init_db_result()
        assert snapshot["status"] == "failed"
        assert "permission denied" in snapshot["error"]
    finally:
        session._LAST_INIT_DB_RESULT = original_snapshot


def test_health_does_not_initialize_database_or_execute_ddl(monkeypatch):
    def fail_init():
        raise AssertionError("health must not call init_db")

    monkeypatch.setattr(session, "init_db", fail_init)
    monkeypatch.setattr(
        health,
        "get_init_db_result",
        lambda: {
            "status": "ok",
            "initialized_at": "2026-09-01T10:00:00",
            "backend": "sqlite",
            "sqlite_path_digest": "0123456789ab",
            "migrations": {"knowledge": {}, "experience": {}},
        },
    )
    result = health.get_governance_health()

    assert result["modules"]["database_migration"]["status"] == "healthy"


def test_migration_snapshot_and_health_source_preserve_read_only_boundaries():
    snapshot = session.get_init_db_result()
    assert "mysql_root_password" not in repr(snapshot)
    assert "mysql+pymysql://" not in repr(snapshot)

    source = Path(health.__file__).read_text(encoding="utf-8").lower()
    assert "init_db(" not in source
    assert "db.commit" not in source
    assert "alter table" not in source
    assert "execute_trade" not in source


def test_migration_error_masks_connection_credentials():
    masked = session._safe_error(
        RuntimeError(
            "mysql+pymysql://root:secret@db.example/stock "
            "password=another-secret"
        )
    )

    assert "secret" not in masked
    assert "another-secret" not in masked
    assert "<redacted>" in masked
