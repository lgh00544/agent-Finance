"""Batch 14: schema drift migrations and startup migration diagnostics."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from app.db.session import (
    SessionLocal,
    _add_columns,
    _ensure_experience_curator_columns,
    _ensure_knowledge_hit_columns,
    _is_duplicate_column_error,
    init_db,
)


def _columns(engine, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


def test_init_db_reports_migrations_and_creates_governance_columns():
    result = init_db()
    second_result = init_db()

    assert result["status"] == "ok"
    assert second_result["status"] == "ok"
    assert second_result["migrations"]["knowledge"]["added"] == []
    assert second_result["migrations"]["experience"]["added"] == []
    assert result["migrations"]["knowledge"]["table"] == "private_knowledge"
    assert result["migrations"]["experience"]["table"] == "experience"
    with SessionLocal() as db:
        assert "risk_note" in _columns(db.bind, "private_knowledge")
        assert "curator_note" in _columns(db.bind, "experience")


def test_old_sqlite_tables_receive_missing_columns_and_keep_data():
    old_engine = create_engine("sqlite://")
    with old_engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE private_knowledge ("
            "id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, content TEXT NOT NULL, "
            "agent VARCHAR(32) NOT NULL, created_at DATETIME)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE experience ("
            "id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, body TEXT NOT NULL, "
            "stage VARCHAR(32) NOT NULL, tags JSON, confidence FLOAT, status VARCHAR(16))"
        )
        conn.execute(
            text(
                "INSERT INTO private_knowledge "
                "(id, title, content, agent) VALUES (1, '旧知识', '旧内容', 'score')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO experience "
                "(id, title, body, stage, tags, confidence, status) "
                "VALUES (1, '旧经验', '旧正文', '选股', '[]', 0.8, 'active')"
            )
        )

    knowledge_result = _ensure_knowledge_hit_columns(old_engine)
    experience_result = _ensure_experience_curator_columns(old_engine)

    assert "risk_note" in knowledge_result["added"]
    assert "curator_note" in experience_result["added"]
    assert {
        "hit_count", "last_used_at", "source_type", "methodology_type",
        "market_scope", "scenario_tags", "evidence_level", "valid_from",
        "valid_to", "status", "risk_note",
    } <= _columns(old_engine, "private_knowledge")
    assert {"hit_count", "last_used_at", "expires_at", "curator_note"} <= (
        _columns(old_engine, "experience")
    )

    with old_engine.connect() as conn:
        knowledge = conn.execute(
            text(
                "SELECT title, content, hit_count, source_type, methodology_type, "
                "market_scope, evidence_level, status, risk_note "
                "FROM private_knowledge WHERE id = 1"
            )
        ).mappings().one()
        experience = conn.execute(
            text(
                "SELECT title, body, hit_count, curator_note "
                "FROM experience WHERE id = 1"
            )
        ).mappings().one()

    assert knowledge["title"] == "旧知识"
    assert knowledge["content"] == "旧内容"
    assert knowledge["hit_count"] == 0
    assert knowledge["source_type"] == "manual"
    assert knowledge["methodology_type"] == "general"
    assert knowledge["market_scope"] == "all"
    assert knowledge["evidence_level"] == "unverified"
    assert knowledge["status"] == "active"
    assert knowledge["risk_note"] == ""
    assert experience["title"] == "旧经验"
    assert experience["body"] == "旧正文"
    assert experience["hit_count"] == 0
    assert experience["curator_note"] == ""

    second_knowledge = _ensure_knowledge_hit_columns(old_engine)
    second_experience = _ensure_experience_curator_columns(old_engine)
    assert second_knowledge["added"] == []
    assert second_experience["added"] == []
    assert "risk_note" in second_knowledge["existing"]
    assert "curator_note" in second_experience["existing"]


def test_sqlite_missing_table_failure_is_not_silenced():
    old_engine = create_engine("sqlite://")

    with pytest.raises(OperationalError):
        _ensure_knowledge_hit_columns(old_engine)


def test_duplicate_column_classification_does_not_match_other_failures():
    assert _is_duplicate_column_error(RuntimeError("1060 Duplicate column name 'risk_note'"))
    assert _is_duplicate_column_error(RuntimeError("Duplicate column"))
    assert not _is_duplicate_column_error(ConnectionError("connection refused"))
    assert not _is_duplicate_column_error(PermissionError("permission denied"))
    assert not _is_duplicate_column_error(RuntimeError("table doesn't exist"))


class _FakeConnection:
    def __init__(self, error):
        self.engine = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
        self.error = error

    def exec_driver_sql(self, statement):
        raise self.error


class _FakeBegin:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FakeEngine:
    def __init__(self, error):
        self.dialect = SimpleNamespace(name="mysql")
        self.error = error

    def begin(self):
        return _FakeBegin(_FakeConnection(self.error))


def test_mysql_duplicate_is_idempotent_but_connection_failure_raises():
    duplicate = _add_columns(
        _FakeEngine(RuntimeError("1060 Duplicate column name 'risk_note'")),
        "private_knowledge",
        {"risk_note": "TEXT NOT NULL DEFAULT ''"},
    )
    assert duplicate["added"] == []
    assert duplicate["existing"] == ["risk_note"]

    with pytest.raises(ConnectionError):
        _add_columns(
            _FakeEngine(ConnectionError("database connection refused")),
            "private_knowledge",
            {"risk_note": "TEXT NOT NULL DEFAULT ''"},
        )
