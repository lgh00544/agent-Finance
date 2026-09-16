import importlib.util

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, FactorCandidate
from app.services import factor_candidate


def _load(name):
    path = f"backend/scripts/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[FactorCandidate.__table__])
    monkeypatch.setattr(factor_candidate, "SessionLocal", sessionmaker(bind=engine))


def test_check_market_condition_reports_missing_reason(monkeypatch):
    script = _load("check_market_condition")
    monkeypatch.setattr(script.repo, "get_latest_market_condition", lambda: None)
    result = script.main()
    assert result["weights"] is None and result["reason"]


def test_get_pending_for_sir_returns_only_pending(db):
    with factor_candidate.SessionLocal() as session:
        session.add_all([
            FactorCandidate(candidate_id="fc01", name="待审", status="pending"),
            FactorCandidate(candidate_id="fc02", name="已启用", status="active"),
        ])
        session.commit()
    rows = factor_candidate.get_pending_for_sir()
    assert [row["candidate_id"] for row in rows] == ["fc01"]


def test_validate_script_marks_uncomputable_candidate(db, monkeypatch):
    script = _load("validate_candidates")
    with factor_candidate.SessionLocal() as session:
        session.add(FactorCandidate(candidate_id="fc01", name="候选", status="pending"))
        session.commit()
    monkeypatch.setattr(script, "init_db", lambda: None)
    source = type("Source", (), {"fetch_spot_universe": lambda self: {"code": []}})()
    monkeypatch.setattr(script, "get_datasource", lambda: source)
    monkeypatch.setattr(script, "_month_ends", lambda source: [])
    monkeypatch.setattr(script.factor_ic, "collect_month_records", lambda *args: {})
    result = script.main(["fc01"])
    assert result[0]["status"] == "insufficient_data"
    assert "reason" in result[0]
