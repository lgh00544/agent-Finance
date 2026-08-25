"""游资自闭环批次1：席位归一化匹配 + 胜率迭代落库。3 用例。"""
import pytest
from sqlalchemy import delete

from app.db import repo
from app.db.models import AgentSuggestion, HotMoneyProfile, LhbOriginalFlow
from app.db.session import SessionLocal, init_db
from app.services import hot_money_review


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _seed():
    with SessionLocal() as db:
        db.execute(delete(HotMoneyProfile))
        db.execute(delete(LhbOriginalFlow))
        db.execute(delete(AgentSuggestion))
        db.commit()
    repo._invalidate("hot_money_profile")
    repo._invalidate("lhb_flow")
    repo.seed_default_hot_money_profiles()
    profiles = repo.list_hot_money_profiles()
    flows = []
    for i, p in enumerate(profiles[:3]):
        flows.append({
            "trade_date": f"2026-08-{10 + i:02d}", "stock_code": f"60000{i + 1}",
            "stock_name": f"测试股{i + 1}", "lhb_type": "1d",
            "seat_name": p['seat_code'].replace("证券", "证券股份有限公司"),
            "buy_amt": 1e7, "sell_amt": 0, "net_buy": 1e7,
            "confidence": 0.9, "source": "sse"})
    repo.insert_lhb_flows(flows)
    yield


def test_normalize_seat_full_vs_short():
    from app.db.repo import normalize_seat
    assert normalize_seat("中信证券股份有限公司上海分公司") == normalize_seat("中信证券上海分公司")
    assert normalize_seat("国泰君安证券股份有限公司上海分公司") == "国泰君安上海"


def test_collect_signals_normalize_hits():
    profiles = repo.list_hot_money_profiles()
    hits = sum(1 for p in profiles if hot_money_review.collect_signals(p))
    assert len(profiles) >= 7
    assert hits >= 3


def test_win_rate_iteration_persists():
    hot_money_review.run_win_rate_iteration(
        price_lookup=lambda code, date: (0.05, 0.01))
    profiles = repo.list_hot_money_profiles()
    assert sum(1 for p in profiles if p.get("win_rate_5d") is not None) >= 1
