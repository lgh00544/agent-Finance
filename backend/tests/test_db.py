"""repo 数据层 CRUD 完整性测试（dev SQLite，测试库与 dev.db 隔离）"""
import pytest
from sqlalchemy import func, select

from app.db import repo
from app.db.models import (
    AgentPreference, AlertLog, Holding, NewsArticle, PositionPlan,
    ReviewResult, StockCandidate, StockScore, TradeProfile, TradeRecord,
)
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _count(model):
    with SessionLocal() as db:
        return db.execute(select(func.count()).select_from(model)).scalar_one()


def test_candidate_upsert_idempotent():
    repo.upsert_candidate("600001", "测试股A", "2026-08-03", 1,
                          ["理由一"], ["风险一"], {"price": 10.0})
    repo.upsert_candidate("600001", "测试股A", "2026-08-03", 2,
                          ["理由一", "理由二"], ["风险一", "风险二"], {"price": 11.0})
    assert _count(StockCandidate) == 1
    with SessionLocal() as db:
        row = db.execute(select(StockCandidate).where(
            StockCandidate.stock_code == "600001",
            StockCandidate.trade_date == "2026-08-03")).scalar_one()
        assert row.rank == 2
        assert row.reasons == ["理由一", "理由二"]
        assert row.snapshot == {"price": 11.0}


def test_score_upsert_and_roundtrip():
    detail = {"技术趋势": {"score": 80, "comment": "均线多头"}}
    repo.upsert_score("600002", "测试股B", "2026-08-03", 86.5, "A", detail, ["减持风险"])
    with SessionLocal() as db:
        row = db.execute(select(StockScore).where(
            StockScore.stock_code == "600002",
            StockScore.trade_date == "2026-08-03")).scalar_one()
        assert row.score == 86.5
        assert row.grade == "A"
        assert row.detail == detail
        assert row.risk_list == ["减持风险"]


def test_plan_insert_and_latest():
    batches = [{"tranche": 1, "price_zone": "10.0~10.5", "ratio_pct": 30.0},
               {"tranche": 2, "price_zone": "9.5~10.0", "ratio_pct": 30.0}]
    plan_id = repo.insert_plan("600003", "测试股C", "2026-08-03", 60.0,
                               batches, 9.0, 12.0, "分批建仓")
    assert plan_id > 0
    plan = repo.get_latest_plan("600003")
    assert plan is not None
    assert plan.total_pct == 60.0
    assert plan.batches == batches
    assert plan.stop_loss == 9.0
    assert plan.take_profit == 12.0


def test_holding_trade_lifecycle():
    hid = repo.insert_holding("600004", "测试股D", "2026-07-01", 10.0, 1000, 10000.0,
                              stop_loss=8.5, take_profit=13.0)
    repo.add_trade(hid, "600004", "buy", 10.0, 1000, "2026-07-01", "首笔")
    repo.add_trade(hid, "600004", "sell", 12.0, 500, "2026-07-20", "减半")

    holding = repo.get_holding(hid)
    assert holding.stock_code == "600004"
    assert holding.entry_price == 10.0

    trades = repo.get_trades(hid)
    # 建仓补录 buy 流水 + 手工首笔 buy + sell（insert_holding 自动补开仓）
    assert [t.side for t in trades] == ["buy", "buy", "sell"]
    assert trades[2].amount == pytest.approx(6000.0)

    assert hid in [h.id for h in repo.get_active_holdings()]
    repo.update_holding(hid, status="exited", note="清仓")
    assert hid not in [h.id for h in repo.get_active_holdings()]
    assert repo.get_holding(hid).note == "清仓"


def test_alert_insert():
    signal = {"action": "exit", "severity": "critical", "key_levels": {"止损": 8.5}}
    aid = repo.insert_alert("600005", "测试股E", "触及止损", "critical",
                            "已破止损位", "exit", signal, pushed=True)
    assert aid > 0
    with SessionLocal() as db:
        row = db.get(AlertLog, aid)
        assert row.alert_type == "触及止损"
        assert row.pushed is True
        assert row.signal == signal


def test_review_insert_and_latest_preference():
    rid = repo.insert_review("600006", "测试股F", 99, "2026-08-01", 30, -8.5,
                             {"入场逻辑": "突破", "兑现程度": "未兑现"},
                             "止损纪律执行太晚", {"偏好": "入场点", "调整方向": "更保守"})
    assert rid > 0
    with SessionLocal() as db:
        row = db.get(ReviewResult, rid)
        assert row.pnl_pct == pytest.approx(-8.5)
        assert row.plan_vs_actual["兑现程度"] == "未兑现"


def test_add_news_dedup_by_code_title():
    assert repo.add_news("600007", "测试股G", "业绩预增公告", "正文一", "东财", "url1", "2026-08-01")
    assert not repo.add_news("600007", "测试股G", "业绩预增公告", "正文二", "东财", "url1", "2026-08-01")
    assert repo.add_news("600007", "测试股G", "另一条公告", "正文三", "东财", "url2", "2026-08-02")
    with SessionLocal() as db:
        rows = db.execute(select(NewsArticle).where(
            NewsArticle.stock_code == "600007")).scalars().all()
        assert len(rows) == 2


def test_preference_version_increment():
    repo.upsert_preference({"筛选": "低吸为主"}, source_review_id=None)
    repo.upsert_preference({"筛选": "突破为主"}, source_review_id=42)
    latest = repo.get_latest_preference()
    assert latest == {"筛选": "突破为主"}
    with SessionLocal() as db:
        rows = db.execute(select(AgentPreference).order_by(
            AgentPreference.version.asc())).scalars().all()
        assert [r.version for r in rows] == [1, 2]
        assert rows[1].source_review_id == 42


def test_trade_profile_singleton_and_version():
    profile = repo.get_trade_profile()
    assert profile.id == 1
    assert profile.version == 1
    assert "持仓周期偏好" in profile.content  # 默认档案已初始化

    v2 = repo.update_trade_profile({"持仓周期偏好": "短线为主"})
    assert v2 == 2
    assert repo.get_trade_profile_content() == {"持仓周期偏好": "短线为主"}

    # 单行约束：id=1 始终只有一行
    with SessionLocal() as db:
        rows = db.execute(select(TradeProfile)).scalars().all()
        assert len(rows) == 1
        assert rows[0].version == 2
