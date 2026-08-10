"""可建仓判定 service 测试：
1. _zone_bounds 区间解析（正常/单点/失败）
2. judge_tradeable 三条件命中/未命中矩阵（无方案/买点偏离/C 级/重大利空/现价兜底/区间无法解析）
3. _effective_tier 人工覆盖优先 + 置信档位映射兜底
4. ensure_tradeable 幂等落库 + ensure_if_missing 懒补算
5. plan_candidate_count 联动指标
6. tradeable_view 视图形状（count=0 也明确返回）
"""
import pytest
from sqlalchemy import delete

from app.db import repo
from app.db.models import CandidateAdjust, CandidateTradeable, PositionPlan, StockCandidate
from app.db.session import SessionLocal, init_db
from app.services.candidate_tradeable import (_effective_tier, _zone_bounds,
                                              ensure_if_missing, ensure_tradeable,
                                              judge_tradeable, plan_candidate_count,
                                              tier_of, tradeable_view)

DATE = "2026-08-10"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(delete(CandidateAdjust))
        db.execute(delete(CandidateTradeable))
        db.execute(delete(PositionPlan))
        db.execute(delete(StockCandidate))
        db.commit()
    repo._invalidate("tradeable")
    repo._invalidate("candidate")
    repo._invalidate("plan")
    yield


# ==================== 1. _zone_bounds ====================

def test_zone_bounds_parse():
    assert _zone_bounds("现价 23.5~24.0") == (23.5, 24.0)
    assert _zone_bounds("23.5~24.0") == (23.5, 24.0)
    assert _zone_bounds("现价 23.5") == (23.5, 23.5)       # 单点兜底
    assert _zone_bounds("区间待定") is None                # 无法解析
    assert _zone_bounds("") is None
    assert _zone_bounds(None) is None


# ==================== 2. judge_tradeable 矩阵 ====================

def _cand(tier="强烈推荐", risks=None):
    return {"stock_code": "600000", "stock_name": "测试股",
            "detail": {"confidence_tier": tier, "risks": risks or ["无重大风险"]}}


def _plan(zone="现价 23.5~24.0", price=23.8):
    return {"plan_date": DATE, "status": "active", "batches": [{"price_zone": zone}],
            "detail": {"quant": {"current_price": price}}}


def test_judge_tradeable_all_ok():
    res = judge_tradeable(_cand(), "A", _plan(), {"price": "23.8"})
    assert res["is_tradeable"] == 1
    assert res["label"] == "可建仓"
    assert res["cond_grade"] == 1 and res["cond_price"] == 1 and res["cond_risk"] == 1
    assert res["plan_exists"] == 1


def test_judge_tradeable_no_plan():
    res = judge_tradeable(_cand(), "A", None, {"price": "23.8"})
    assert res["is_tradeable"] == 0
    assert res["label"] == "建议关注"
    assert res["plan_exists"] == 0
    assert "暂无建仓方案" in res["block_reason"]


def test_judge_tradeable_price_drift():
    res = judge_tradeable(_cand(), "A", _plan(price=26.0), None)
    assert res["is_tradeable"] == 0
    assert "偏离首仓区间" in res["block_reason"]


def test_judge_tradeable_c_tier():
    res = judge_tradeable(_cand(tier="谨慎观察"), "C", _plan(), {"price": "23.8"})
    assert res["is_tradeable"] == 0
    assert res["label"] == "观察"      # C 级仅观察


def test_judge_tradeable_major_negative():
    cand = _cand(risks=["收到立案通知书"])
    res = judge_tradeable(cand, "A", _plan(), {"price": "23.8"})
    assert res["is_tradeable"] == 0
    assert "重大利空" in res["block_reason"]


def test_judge_tradeable_price_fallback_to_plan():
    res = judge_tradeable(_cand(), "A", _plan(price=23.7), None)   # 无快照，取 plan.quant
    assert res["current_price"] == 23.7
    assert res["is_tradeable"] == 1


def test_judge_tradeable_unparseable_zone():
    res = judge_tradeable(_cand(), "A", _plan(zone="区间待定"), {"price": "23.8"})
    assert res["is_tradeable"] == 0
    assert "无法解析" in res["block_reason"]


def test_tier_of_mapping():
    assert tier_of("强烈推荐") == "A"
    assert tier_of("建议关注") == "B"
    assert tier_of("谨慎观察") == "C"
    assert tier_of("") == ""


# ==================== 3. _effective_tier ====================

def test_effective_tier_override_first():
    cand = _cand(tier="谨慎观察")
    assert _effective_tier(cand, {"600000": {"tier_override": "A"}}) == "A"
    assert _effective_tier(cand, {}) == "C"


# ==================== 4. ensure_tradeable 幂等 ====================

def _seed_candidates():
    with SessionLocal() as db:
        db.add_all([
            StockCandidate(stock_code="600001", stock_name="可建仓股", trade_date=DATE, rank=1,
                           reasons=["吸筹末期"], risk_notice=[], snapshot={"price": "23.8"},
                           detail={"confidence_tier": "强烈推荐", "risks": ["无"]}),
            StockCandidate(stock_code="600002", stock_name="无方案股", trade_date=DATE, rank=2,
                           reasons=["趋势初升"], risk_notice=[], snapshot={"price": "12.0"},
                           detail={"confidence_tier": "建议关注", "risks": ["无"]}),
            StockCandidate(stock_code="600003", stock_name="C级观察股", trade_date=DATE, rank=3,
                           reasons=["谨慎"], risk_notice=[], snapshot={"price": "5.5"},
                           detail={"confidence_tier": "谨慎观察", "risks": ["无"]}),
        ])
        db.commit()
    repo._invalidate("candidate")


def _seed_plan():
    with SessionLocal() as db:
        db.add(PositionPlan(stock_code="600001", stock_name="可建仓股", plan_date=DATE,
                            status="active", total_pct=20, batches=[{"price_zone": "现价 23.5~24.0"}],
                            detail={"quant": {"current_price": 23.8}}, source="candidate"))
        db.commit()
    repo._invalidate("plan")


def test_ensure_tradeable_and_lazy():
    _seed_candidates()
    _seed_plan()                              # 600001 有建仓方案 → 可建仓
    assert ensure_tradeable(DATE) == 3
    rows = repo.list_candidate_tradeable(DATE)
    by_code = {r["stock_code"]: r for r in rows}
    assert by_code["600001"]["is_tradeable"] == 1
    assert by_code["600001"]["label"] == "可建仓"
    assert by_code["600002"]["is_tradeable"] == 0        # 无方案 → 建议关注
    assert "暂无建仓方案" in by_code["600002"]["block_reason"]
    assert by_code["600003"]["label"] == "观察"           # C 级仅观察
    # 幂等：再次执行条数不变，行数不变
    assert ensure_tradeable(DATE) == 3
    assert len(repo.list_candidate_tradeable(DATE)) == 3
    # ensure_if_missing：已有记录 → 0
    assert ensure_if_missing(DATE) == 0


def test_ensure_tradeable_plan_applied():
    _seed_candidates()
    _seed_plan()
    assert ensure_tradeable(DATE) == 3
    by_code = {r["stock_code"]: r for r in repo.list_candidate_tradeable(DATE)}
    assert by_code["600001"]["plan_exists"] == 1
    assert plan_candidate_count(DATE) == 1                # 600002 A 级且无方案


def test_plan_candidate_count_after_override():
    _seed_candidates()
    _seed_plan()
    repo.upsert_candidate_adjust("600003", "C级观察股", DATE, "B", "建议关注",
                                 "测试覆盖 C→B", operator="test")
    assert ensure_tradeable(DATE) == 3
    assert plan_candidate_count(DATE) == 2                # 600002 + 600003(覆盖后 A/B 且无方案)


# ==================== 6. tradeable_view 形状 ====================

def test_tradeable_view_shape_zero_ok():
    assert tradeable_view(DATE)["count"] == 0             # 无候选 → 0 明确返回
    view = tradeable_view(DATE)
    assert view["date"] == DATE
    assert set(view) == {"date", "count", "plan_candidate_count", "total", "items"}
