import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.candidate_factor_proposer import CandidateItem, CandidateProposal
from app.db.models import Base, FactorCandidate
from app.services import factor_candidate


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[FactorCandidate.__table__])
    monkeypatch.setattr(factor_candidate, "SessionLocal", sessionmaker(bind=engine))


def _proposal(count=3):
    return CandidateProposal(candidates=[
        CandidateItem(name=f"候选{i}", hypothesis=f"假设{i}", candidate_id=f"fc{i:02d}")
        for i in range(1, count + 1)
    ])


def test_propose_creates_pending_rows(db, monkeypatch):
    monkeypatch.setattr(factor_candidate.proposer, "propose_candidates", lambda *_: _proposal())
    rows = factor_candidate.propose("失败案例")
    assert len(rows) == 3 and {row["status"] for row in rows} == {"pending"}


def test_validate_uses_latest_24_months(db, monkeypatch):
    monkeypatch.setattr(factor_candidate.proposer, "propose_candidates", lambda *_: _proposal(3))
    factor_candidate.propose()
    captured = {}

    def fake_backtest(records, definitions):
        captured["periods"] = list(records)
        return [{"ic": 0.1, "ir": 1.2}]

    monkeypatch.setattr(factor_candidate.factor_ic, "run_backtest", fake_backtest)
    records = {f"2024-{month:02d}": [] for month in range(1, 25)}
    records.update({f"2026-{month:02d}": [] for month in range(1, 3)})
    result = factor_candidate.validate("fc01", records)
    assert len(captured["periods"]) == 24 and result["status"] == "validated"


def test_enable_changes_pending_to_active(db, monkeypatch):
    monkeypatch.setattr(factor_candidate.proposer, "propose_candidates", lambda *_: _proposal())
    factor_candidate.propose()
    assert factor_candidate.enable("fc01")["status"] == "active"


def test_disable_preserves_row_and_marks_disabled(db, monkeypatch):
    monkeypatch.setattr(factor_candidate.proposer, "propose_candidates", lambda *_: _proposal())
    factor_candidate.propose()
    assert factor_candidate.disable("fc01")["status"] == "disabled"


def test_enable_rejects_more_than_30_active(db, monkeypatch):
    with factor_candidate.SessionLocal() as session:
        session.add_all([
            FactorCandidate(candidate_id=f"fc{i:02d}", name="已启用", status="active")
            for i in range(1, 31)
        ])
        session.add(FactorCandidate(candidate_id="fc31", name="待启用"))
        session.commit()
    with pytest.raises(ValueError, match="30"):
        factor_candidate.enable("fc31")
