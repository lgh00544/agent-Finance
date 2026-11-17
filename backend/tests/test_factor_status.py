import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.factors  # noqa: F401 触发 25 个内置因子注册
from app.db.models import Base, FactorStatus
from app.services import factor_registry


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[FactorStatus.__table__])
    monkeypatch.setattr("app.db.session.SessionLocal", sessionmaker(bind=engine))
    yield
    for fid in ("f01", "f03"):
        factor_registry.set_factor_status(fid, "active")


def test_proposal_does_not_disable_before_decided(db):
    """回测判出的失效只落提案，未经人工确认不得下线因子。"""
    assert factor_registry.get("f01").status == "active"
    factor_registry.record_proposal("f01", "连续3月|IC|<0.02")
    assert factor_registry.get("f01").status == "active"
    assert factor_registry.list_status_rows()[0]["status"] == "proposed"

    factor_registry.decide("f01", "deprecated", "人工确认失效")
    assert factor_registry.get("f01").status == "deprecated"


def test_sync_from_db_restores_decided_and_skips_proposed(db):
    """重启后已拍板状态恢复生效；proposed 不得被误当成下线。"""
    factor_registry.decide("f01", "deprecated", "人工确认失效")
    factor_registry.record_proposal("f03", "连续3月|IC|<0.02")
    factor_registry.set_factor_status("f01", "active")

    assert factor_registry.sync_from_db() == 1
    assert factor_registry.get("f01").status == "deprecated"
    assert factor_registry.get("f03").status == "active"
