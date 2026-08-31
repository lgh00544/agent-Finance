"""Batch 8: shadow knowledge observation without formal decision impact."""
from sqlalchemy import delete, inspect
from fastapi.testclient import TestClient

import pytest

from app.agents.common import knowledge_section
from app.agents.schemas import DiscoverOutput, ScoreFactor, ScoreOutput
from app.db import repo
from app.db.models import CandidateTrackVerify, KnowledgeShadowHit
from app.db.session import SessionLocal, init_db
from app.main import app
from app.services import knowledge_shadow


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    init_db()


def _cleanup(stock_code: str = "", knowledge_ids: list[int] | None = None) -> None:
    knowledge_ids = knowledge_ids or []
    with SessionLocal() as db:
        stmt = delete(KnowledgeShadowHit).where(KnowledgeShadowHit.id > 0)
        if stock_code:
            stmt = stmt.where(KnowledgeShadowHit.stock_code == stock_code)
        if knowledge_ids:
            stmt = stmt.where(KnowledgeShadowHit.knowledge_id.in_(knowledge_ids))
        if stock_code or knowledge_ids:
            db.execute(stmt)
        if stock_code:
            db.execute(delete(CandidateTrackVerify).where(
                CandidateTrackVerify.stock_code == stock_code))
        db.commit()
    for kid in knowledge_ids:
        repo.delete_knowledge(kid)


def _score_output() -> ScoreOutput:
    factors = [
        ScoreFactor(factor="动量", score=4, reason="测试动量", signal="中性"),
        ScoreFactor(factor="催化", score=8, reason="测试催化", signal="看多"),
        ScoreFactor(factor="估值", score=5, reason="测试估值", signal="中性"),
        ScoreFactor(factor="主线契合", score=6, reason="测试主线", signal="看多"),
        ScoreFactor(factor="资金面", score=5, reason="测试资金", signal="中性"),
        ScoreFactor(factor="基本面质量", score=5, reason="测试基本面", signal="中性"),
    ]
    return ScoreOutput(stock_code="800004", stock_name="影子评分", score=70,
                       grade="B", factors=factors, risk_list=["风险观察"],
                       final_advice="综合评估：测试")


def _discover_output() -> DiscoverOutput:
    return DiscoverOutput(market_summary="测试", candidates=[{
        "stock_code": "800003", "stock_name": "影子候选", "reason": "突破主线",
        "risk_notice": "风险观察", "stock_type": "拉升初期-突破型",
        "confidence_tier": "建议关注", "confidence_pct": 70.0,
        "dimensions": [
            {"dim": "基本面", "score": 70, "verdict": "支持", "advice": "测试"},
            {"dim": "技术趋势", "score": 70, "verdict": "支持", "advice": "测试"},
            {"dim": "资金/游资", "score": 60, "verdict": "中性", "advice": "测试"},
            {"dim": "舆情/风险", "score": 60, "verdict": "中性", "advice": "测试"},
            {"dim": "行业景气", "score": 70, "verdict": "支持", "advice": "测试"},
        ],
        "final_advice": "综合评估：测试", "macro_view": "宏观",
        "meso_view": "中观", "micro_view": "微观", "volume_analysis": "量能",
        "risks": ["风险A", "风险B"], "focus_type": "突破",
    }])


def test_knowledge_shadow_hit_table_is_created_idempotently():
    with SessionLocal() as db:
        columns = {column["name"] for column in inspect(db.bind).get_columns("knowledge_shadow_hit")}
    assert {
        "knowledge_id", "agent", "stock_code", "stock_name", "trade_date", "query",
        "scenario_tags", "shadow_bias", "shadow_summary", "t3_pct", "t5_pct",
        "t10_pct", "max_drawdown", "verify_status", "created_at", "updated_at",
    } <= columns


def test_shadow_status_is_never_injected_into_knowledge_section():
    text, selected = knowledge_section("score", docs=[
        {"id": 1, "title": "active", "content": "可注入", "status": "active"},
        {"id": 2, "title": "shadow", "content": "不可注入", "status": "shadow"},
    ])
    assert "可注入" in text
    assert "不可注入" not in text
    assert [item["id"] for item in selected] == [1]


def test_shadow_search_matches_current_agent_and_all_only():
    ids = [
        repo.add_knowledge("批8 shadow discover", "突破观察", "discover", status="shadow"),
        repo.add_knowledge("批8 shadow all", "通用观察", "all", status="shadow"),
        repo.add_knowledge("批8 shadow score", "评分观察", "score", status="shadow"),
        repo.add_knowledge("批8 active discover", "正式知识", "discover", status="active"),
    ]
    try:
        titles = {row["title"] for row in knowledge_shadow.search_shadow_knowledge("discover", top_k=50)}
        assert {"批8 shadow discover", "批8 shadow all"} <= titles
        assert "批8 shadow score" not in titles
        assert "批8 active discover" not in titles
    finally:
        _cleanup(knowledge_ids=ids)


def test_record_knowledge_shadow_hit_is_idempotent():
    stock_code = "800001"
    kid = repo.add_knowledge("批8 幂等", "突破主线加分", "score", status="shadow")
    try:
        first = repo.record_knowledge_shadow_hit(
            kid, "score", stock_code, "影子一号", "2026-08-31", query="突破")
        second = repo.record_knowledge_shadow_hit(
            kid, "score", stock_code, "影子一号", "2026-08-31",
            query="突破 更新", shadow_bias="boost")
        rows = repo.list_knowledge_shadow_hits(knowledge_id=kid, stock_code=stock_code)
        assert first == second
        assert len(rows) == 1
        assert rows[0]["query"] == "突破 更新"
        assert rows[0]["shadow_bias"] == "boost"
    finally:
        _cleanup(stock_code, [kid])


def test_refresh_knowledge_shadow_outcomes_backfills_track_verify():
    stock_code = "800002"
    kid = repo.add_knowledge("批8 后验", "风险观察", "discover", status="shadow")
    try:
        repo.record_knowledge_shadow_hit(
            kid, "discover", stock_code, "影子二号", "2026-08-30", shadow_bias="risk")
        row_id = repo.upsert_track_verify(
            stock_code, "影子二号", "2026-08-30", "B", 10.0)
        repo.update_track_verify(
            row_id, t3_pct=1.2, t5_pct=2.5, max_drawdown=-3.0, is_finished=1)
        result = repo.refresh_knowledge_shadow_outcomes()
        rows = repo.list_knowledge_shadow_hits(knowledge_id=kid, stock_code=stock_code)
        assert result["updated"] >= 1
        assert rows[0]["t3_pct"] == 1.2
        assert rows[0]["t5_pct"] == 2.5
        assert rows[0]["max_drawdown"] == -3.0
        assert rows[0]["verify_status"] == "finished"
        shadow_rows = [r for r in repo.list_knowledge(status="shadow") if r.id == kid]
        assert shadow_rows and shadow_rows[0].status == "shadow"
    finally:
        _cleanup(stock_code, [kid])


def test_shadow_hits_api_filters_and_status_update_keeps_reason():
    stock_code = "800005"
    kid = repo.add_knowledge("批8 API", "派发风险", "all", status="shadow")
    try:
        repo.record_knowledge_shadow_hit(
            kid, "score", stock_code, "影子五号", "2026-08-31", shadow_bias="reduce")
        client = TestClient(app)
        resp = client.get("/api/knowledge/shadow-hits",
                          params={"knowledge_id": kid, "agent": "score"})
        assert resp.status_code == 200
        assert resp.json()[0]["stock_code"] == stock_code

        resp = client.post(f"/api/knowledge/{kid}/status",
                           json={"status": "archived", "reason": "试运行未通过"})
        assert resp.status_code == 200
        rows = [r for r in repo.list_knowledge(status="archived") if r.id == kid]
        assert rows and "试运行未通过" in rows[0].risk_note
    finally:
        _cleanup(stock_code, [kid])


def test_discover_and_score_shadow_recording_does_not_change_formal_outputs(monkeypatch):
    from app.agents import discover as discover_mod
    from app.agents import score as score_mod
    from app.services import hot_money, track_verify, sector_rotation_pattern

    calls = []
    monkeypatch.setattr(knowledge_shadow, "record_shadow_hits",
                        lambda **kwargs: calls.append(kwargs) or [1])
    monkeypatch.setattr(hot_money, "aggregate_for_stock", lambda *a, **k: None)
    monkeypatch.setattr(hot_money, "build_hot_money_context", lambda *a, **k: "")
    monkeypatch.setattr(track_verify, "build_horizon_context", lambda *a, **k: "")
    monkeypatch.setattr(sector_rotation_pattern, "build_regime_context", lambda *a, **k: "")
    monkeypatch.setattr(discover_mod, "agent_call", lambda **kwargs: _discover_output())
    monkeypatch.setattr(discover_mod.repo, "hot_money_fingerprint", lambda: "fp")
    monkeypatch.setattr(discover_mod.repo, "get_candidate_detail", lambda *a: {})
    monkeypatch.setattr(discover_mod.repo, "upsert_candidate", lambda *a, **k: None)
    monkeypatch.setattr(discover_mod.repo, "replace_day_candidates", lambda *a, **k: 0)

    discover_state = discover_mod.llm_final({
        "shortlist": [{"stock_code": "800003", "stock_name": "影子候选"}],
        "trade_date": "2026-08-31", "trace": [], "universe": [],
    })
    assert discover_state["candidates"][0]["stock_code"] == "800003"
    assert "shadow" not in discover_state["candidates"][0]

    monkeypatch.setattr(score_mod, "agent_call", lambda **kwargs: _score_output())
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
    monkeypatch.setattr(score_mod.repo, "hot_money_fingerprint", lambda: "fp")
    monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)
    score_state = score_mod.llm_score({
        "stock_code": "800004", "stock_name": "影子评分", "trade_date": "2026-08-31",
        "trace": [], "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
        "news_report": [], "basic_info": {}, "hot_money": None,
    })
    assert score_state["score_result"]["stock_code"] == "800004"
    assert "shadow" not in score_state["score_result"]
    assert {call["agent"] for call in calls} == {"discover", "score"}
