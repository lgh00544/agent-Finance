"""建仓计划数据同源联动测试（B+ 门槛 / 分级缓存 / 同日去重 / 流水线联动）：

1. C 级及以下（或无评级）→ 拒绝生成，抛「评级不足」错误
2. 无评分标的 → 自动先跑 ScoreAgent 再判级
3. B 级 30 分钟缓存：当日已有计划且 30 分钟内 → 直接复用，不进入图执行
4. A 级 → 实时计算（总是进入图执行）
5. insert_plan 同日去重：同一标的同一交易日仅保留最新一份
6. run_daily_pipeline：打分完成后对 B+ 候选自动生成计划（联动计数）
"""
import types
from datetime import datetime, timedelta

import pytest

from app.db import repo
from app.db.session import init_db
from app.graph import router


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


class _FakeGraph:
    def __init__(self, result):
        self._result = result

    def invoke(self, state):
        return {**state, **self._result}


def _fake_score(grade: str = "B", score: float = 75.0):
    return types.SimpleNamespace(stock_code="600001", grade=grade, score=score)


def _fake_plan(plan_date: str, age_seconds: float):
    return types.SimpleNamespace(
        id=7, plan_date=plan_date,
        created_at=datetime.now() - timedelta(seconds=age_seconds))


def test_c_grade_rejected(monkeypatch):
    """C 级及以下 → 拒绝生成，明确提示评级不足"""
    monkeypatch.setattr(repo, "get_latest_score", lambda code: _fake_score(grade="C"))
    with pytest.raises(ValueError, match="评级不足"):
        router.run_position("600001", trade_date="2026-08-09")


def test_no_grade_rejected(monkeypatch):
    """无评级记录（自动评分后仍无评级）→ 拒绝生成"""
    monkeypatch.setattr(repo, "get_latest_score", lambda code: None)
    monkeypatch.setattr(router, "run_score", lambda code, name="", date=None: None)
    with pytest.raises(ValueError, match="评级不足"):
        router.run_position("600001", trade_date="2026-08-09")


def test_auto_score_before_grade_check(monkeypatch):
    """无评分标的 → 自动先跑一次 ScoreAgent，评分后达 B 级则放行生成"""
    calls = {"n": 0}

    def _score_then_grade(code):
        if calls["n"] == 0:  # 首次查询无评分 → 触发自动评分
            return None
        return _fake_score(grade="B")

    monkeypatch.setattr(repo, "get_latest_score", _score_then_grade)

    def _fake_run_score(code, name="", date=None):
        calls["n"] += 1
        return {"score_result": {"score": 75, "grade": "B"}}

    monkeypatch.setattr(router, "run_score", _fake_run_score)
    monkeypatch.setattr(repo, "get_latest_plan", lambda code: None)  # B 级无缓存
    monkeypatch.setattr(router, "get_graph",
                        lambda name: _FakeGraph({"position_plan": {"plan_id": 1}}))
    state = router.run_position("600001", trade_date="2026-08-09")
    assert calls["n"] == 1, "应自动执行一次评分"
    assert state["position_plan"]["plan_id"] == 1


def test_b_grade_30min_cache_hit(monkeypatch):
    """B 级：当日已有计划且 30 分钟内 → 直接复用缓存，不进入图执行（零 LLM 调用）"""
    monkeypatch.setattr(repo, "get_latest_score", lambda code: _fake_score(grade="B"))
    monkeypatch.setattr(repo, "get_latest_plan",
                        lambda code: _fake_plan("2026-08-09", age_seconds=120))

    invoked = {"n": 0}
    monkeypatch.setattr(router, "get_graph",
                        lambda name: _FakeGraph({"position_plan": {"plan_id": 999}}))
    state = router.run_position("600001", trade_date="2026-08-09")
    assert state["position_plan"] == {"plan_id": 7, "cached": True}
    assert invoked["n"] == 0


def test_b_grade_cache_expired_regenerates(monkeypatch):
    """B 级：超过 30 分钟 → 缓存失效，重新进入图执行生成新计划"""
    monkeypatch.setattr(repo, "get_latest_score", lambda code: _fake_score(grade="B"))
    monkeypatch.setattr(repo, "get_latest_plan",
                        lambda code: _fake_plan("2026-08-09", age_seconds=3600))
    monkeypatch.setattr(router, "get_graph",
                        lambda name: _FakeGraph({"position_plan": {"plan_id": 88}}))
    state = router.run_position("600001", trade_date="2026-08-09")
    assert state["position_plan"]["plan_id"] == 88


def test_a_grade_always_realtime(monkeypatch):
    """A 级：即使当日已有计划也实时重新计算（不命中缓存）"""
    monkeypatch.setattr(repo, "get_latest_score", lambda code: _fake_score(grade="A", score=88))
    monkeypatch.setattr(repo, "get_latest_plan",
                        lambda code: _fake_plan("2026-08-09", age_seconds=10))
    monkeypatch.setattr(router, "get_graph",
                        lambda name: _FakeGraph({"position_plan": {"plan_id": 66}}))
    state = router.run_position("600001", trade_date="2026-08-09")
    assert state["position_plan"]["plan_id"] == 66


def test_insert_plan_same_day_dedupe():
    """同日去重：同一标的同一交易日重复生成 → 仅保留最新一份"""
    first = repo.insert_plan("600001", "测试A", "2026-08-09", 50.0,
                             [{"tranche": 1, "price_zone": "10~10.5", "ratio_pct": 30.0}],
                             9.2, 12.0, "第一版逻辑")
    second = repo.insert_plan("600001", "测试A", "2026-08-09", 40.0,
                              [{"tranche": 1, "price_zone": "9.5~10", "ratio_pct": 40.0}],
                              8.8, 11.5, "第二版逻辑")
    rows = repo.list_plans(limit=50)
    same_day = [r for r in rows if r["stock_code"] == "600001"
                and r["plan_date"] == "2026-08-09"]
    assert len(same_day) == 1, "同日同标的不应保留多份计划"
    assert same_day[0]["id"] == second and second > first
    assert same_day[0]["total_pct"] == 40.0, "应保留最新版计划"


def test_daily_pipeline_auto_plans_for_b_plus(monkeypatch):
    """每日流水线：打分完成后 B+ 候选自动生成建仓计划（同源联动）"""
    monkeypatch.setattr(router, "run_discover", lambda date: {
        "candidates": [{"stock_code": "600001", "stock_name": "测试A"},
                       {"stock_code": "600002", "stock_name": "测试B"}]})

    def _fake_run_score(code, name="", date=None):
        grade = "A" if code == "600001" else "C"  # 一 A 一 C
        return {"score_result": {"score": 80 if grade == "A" else 50, "grade": grade}}

    monkeypatch.setattr(router, "run_score", _fake_run_score)
    planned = []
    monkeypatch.setattr(router, "run_position",
                        lambda code, name="", date=None, source="manual":
                        planned.append((code, source)) or
                        {"position_plan": {"plan_id": len(planned)}})

    result = router.run_daily_pipeline("2026-08-09")
    assert result["scored"] == 2
    assert result["plans"] == 1, "仅 B+ 候选应生成计划（C 级被拒）"
    assert planned == [("600001", "candidate")], "联动生成应标记来源为每日候选池"
