"""统一调教接口 + 策略闭环数据层测试：
知识库 CRUD/版本感知、卖出决策记录、Agent 优化建议全流程（落库→人工审核状态机）"""
import pytest
from sqlalchemy import func, select

from app.db import repo
from app.db.models import AgentSuggestion, PrivateKnowledge, SellDecision
from app.db.session import SessionLocal, init_db
from app.services.vector_store import get_vector_store


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _count(model):
    with SessionLocal() as db:
        return db.execute(select(func.count()).select_from(model)).scalar_one()


# ================= 私有知识库 =================

def test_knowledge_crud_and_version():
    v0 = repo.knowledge_version()
    kid = repo.add_knowledge("波段战法", "回踩 MA20 企稳放量再进场", "discover")
    assert kid > 0
    v1 = repo.knowledge_version()
    assert v1 == (v0[0] + 1, max(v0[1], kid))  # 数量+1，最大ID更新

    rows = repo.list_knowledge()
    assert any(r.title == "波段战法" for r in rows)
    assert all(r.agent_tag == "discover" for r in repo.list_knowledge("discover"))
    assert repo.list_knowledge("monitor") == []  # 标签过滤

    assert repo.delete_knowledge(kid)
    assert not repo.delete_knowledge(kid)  # 已删
    assert repo.knowledge_version() == v0


def test_search_knowledge_tag_match():
    kid_all = repo.add_knowledge("通用纪律", "任何止损不可放宽", "all")
    kid_mon = repo.add_knowledge("监控要点", "放量破位优先预警", "monitor")
    try:
        docs = get_vector_store().search_knowledge("monitor", top_k=5)
        titles = [d["title"] for d in docs]
        # agent 专属 + 通用 all 标签都命中
        assert "监控要点" in titles
        assert "通用纪律" in titles
        docs_d = get_vector_store().search_knowledge("discover", top_k=5)
        assert "监控要点" not in [d["title"] for d in docs_d]
    finally:
        repo.delete_knowledge(kid_all)
        repo.delete_knowledge(kid_mon)


# ================= 卖出决策 =================

def test_sell_decision_insert_and_list():
    decision = {"stock_code": "600100", "action": "partial", "confidence": "medium",
                "reasons": ["量能背离"], "exit_price_zone": "25.0~25.6",
                "risk_warning": "继续持有风险上升", "check_list": ["核对可卖数量"]}
    hid = repo.insert_holding("600100", "测试卖出股", "2026-07-10", 24.0, 800, 19200.0)
    sid = repo.insert_sell_decision(hid, "600100", "测试卖出股", decision)
    assert sid > 0

    rows = repo.list_sell_decisions(hid)
    assert len(rows) == 1
    assert rows[0]["decision"]["action"] == "partial"
    assert rows[0]["decision"]["reasons"] == ["量能背离"]

    latest = repo.get_latest_sell_decision(hid)
    assert latest is not None
    assert latest.decision["exit_price_zone"] == "25.0~25.6"
    by_code = repo.get_sell_decisions_by_code("600100")
    assert len(by_code) == 1


# ================= 策略闭环·Agent 优化建议 =================

def test_agent_suggestion_pending_and_status_flow():
    rid = repo.insert_review("600101", "测试复盘股", 999, "2026-08-01", 20, -6.0,
                             {"入场逻辑": "低吸", "兑现程度": "部分"}, "教训", {"偏好": "风控"})
    # profile 类建议（可直接写入档案）
    s1 = repo.insert_agent_suggestion(
        rid, "monitor", "单票仓位上限", "40", "30",
        "本次仓位过重放大亏损", "止损日晚于破位 3 天", target_kind="profile")
    # prompt 类建议（需人工改文件）
    s2 = repo.insert_agent_suggestion(
        rid, "monitor", "Monitor 趋势破位判定标准", "偏重均线交叉",
        "增加量能背离双重确认", "信号滞后", "破位日 07-20 未触发预警", target_kind="prompt")
    assert s1 > 0 and s2 > 0

    pending = repo.get_agent_suggestions(status="pending")
    assert {x.id for x in pending} >= {s1, s2}
    by_review = repo.get_agent_suggestions(review_id=rid)
    assert len(by_review) == 2
    assert by_review[0].target_kind == "prompt"

    row = repo.get_agent_suggestion(s1)
    assert row.status == "pending"
    assert row.target_agent == "monitor"
    assert row.suggested_value == "30"

    # 人工审核状态机：approve → rejected 不允许再改
    repo.update_agent_suggestion_status(s1, "approved")
    assert repo.get_agent_suggestion(s1).status == "approved"
    repo.update_agent_suggestion_status(s2, "rejected")
    assert repo.get_agent_suggestion(s2).status == "rejected"
    assert repo.get_agent_suggestions(status="approved")[0].id == s1


def test_agent_suggestion_schema_validation():
    """ReviewOutput 的 agent_suggestions 结构必须通过 pydantic 校验（target_kind 限 profile/prompt）"""
    from app.agents.schemas import ReviewOutput

    out = ReviewOutput(
        plan_vs_actual={"入场逻辑": "x", "兑现程度": "y", "关键偏差": "z", "复盘结论": "w"},
        lesson="教训",
        feedback={"偏好": "f", "调整方向": "d", "理由": "r"},
        agent_suggestions=[
            {"target_agent": "score", "target_kind": "profile", "rule_name": "选股倾向",
             "current_value": "低吸", "suggested_value": "突破", "reason": "r", "evidence": "e"},
            {"target_agent": "sell", "target_kind": "prompt", "rule_name": "卖出节奏",
             "current_value": "c", "suggested_value": "s", "reason": "r", "evidence": "e"},
        ],
    )
    assert len(out.agent_suggestions) == 2
    assert out.agent_suggestions[0].target_kind == "profile"

    # 非法 target_kind 必须被拒绝
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ReviewOutput(
            plan_vs_actual={}, lesson="", feedback={},
            agent_suggestions=[{"target_agent": "score", "target_kind": "illegal",
                                "rule_name": "x", "current_value": "c",
                                "suggested_value": "s", "reason": "r", "evidence": "e"}],
        )


# ==================== 全局通用知识库基线 ====================

def test_global_base_prompt_loads():
    """全局基线 md 可加载且含关键指令（纯文件读取，无 LLM）"""
    from app.agents.common import _global_base_version, global_base_prompt

    content = global_base_prompt()
    assert "36943" in content                      # 基准本金
    assert "交叉验证" in content                    # 战法交叉验证
    assert "插槽" in content                        # 预留扩展插槽
    assert "自动下单" in content                    # 系统边界
    assert _global_base_version()                  # 内容指纹非空
    assert len(_global_base_version()) == 8        # md5 前 8 位


def test_agent_call_global_base_first(monkeypatch):
    """拼接顺序回归：全局基线必须【最先】加载，再拼接 Agent 专属 Prompt；
    缓存键携带基线指纹 g{hash}，编辑基线后 LLM 缓存自动失效"""
    import app.agents.common as common_mod
    from pydantic import BaseModel

    class _Mini(BaseModel):
        note: str = "ok"

    captured = {}

    def fake_call(agent, cache_key, system_prompt, user_prompt, schema, ttl_seconds,
                  model_level=None):
        captured["cache_key"] = cache_key
        captured["system_prompt"] = system_prompt
        captured["model_level"] = model_level
        return _Mini()

    monkeypatch.setattr(common_mod, "call_llm_cached", fake_call)

    common_mod.agent_call(agent="sell", cache_key="testkey",
                          system_prompt="【卖出专项规则】止损止盈基准",
                          user_prompt="请研判", schema=_Mini, ttl_seconds=0)

    prompt = captured["system_prompt"]
    assert prompt.index("36943") < prompt.index("【卖出专项规则】")  # 基线在前
    assert "插槽" in prompt and "交叉验证" in prompt                  # 基线内容已注入
    # 缓存键携带基线指纹 g{md5}、战法知识指纹 a{md5} 与复盘采纳规则指纹 r{...}：
    # 编辑任一侧内容（或采纳/回滚规则）后 LLM 缓存自动失效；末位为规则指纹
    assert f":g{common_mod._global_base_version()}" in captured["cache_key"]
    assert f":{common_mod._agent_knowledge_version('sell')}" in captured["cache_key"]
    assert captured["cache_key"].endswith(f":r{common_mod._rule_version()}")
    assert "派发信号" in prompt  # 战法知识库（sell.md）已注入
