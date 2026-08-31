"""复盘建议「一键采纳自动落地」测试（规则变更闭环）：
1. 迁移幂等：agent_suggestion v2 新列 + rule_change 表（双跑 init_db 不报错）
2. 采纳全流程：suggestion(pending) → adopt → rule_change(active) + suggestion(approved)
3. 注入段生成：硬性无条件遵守 / 软性参考权重文案（dynamic_rules_section）
4. 确定性校验拦截（双保险第二层）：完全相同去重 / 高度相似去重 / 硬规则红线冲突 /
   profile 字段命中引导 / 路由守卫（缺 confirm、缺 rule_text、已处理）
5. 回滚：status/reason/time 留痕 + get_active_rules 排除 + rule_version 变化 + 重复回滚拒绝
6. 缓存失效：采纳/回滚后直查立即反映新数据
7. profile 类建议走 approve 不受影响"""
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, inspect

from app.agents.common import HARD_RULES, dynamic_rules_section
from app.api.routes import (AdoptSuggestionBody, RollbackRuleBody, _validate_adopt,
                             adopt_agent_suggestion, approve_agent_suggestion,
                             re_review_agent_suggestion,
                             rollback_rule_change as rollback_route)
from app.db import repo
from app.db.models import AgentSuggestion, RuleChange
from app.db.session import SessionLocal, engine, init_db
from types import SimpleNamespace


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean_tables():
    """用例隔离：清空建议与规则变更表 + 失效对应读缓存（直删 SQL 不走写路径）"""
    with SessionLocal() as db:
        db.execute(delete(RuleChange))
        db.execute(delete(AgentSuggestion))
        db.commit()
    repo._invalidate("rule_change")
    yield


def _make_suggestion(rule_text: str, rule_type: str = "soft", target_kind: str = "prompt",
                     rule_name: str = "测试规则X", review_id: int | None = None,
                     priority: str = "high") -> int:
    if review_id is None:
        review_id = repo.insert_review(
            "600601", "测试股601", 1, "2026-08-01", 10, 3.2,
            {"入场逻辑": "回踩企稳", "兑现程度": "兑现"}, "止盈应分批", {"偏好": "更保守"})
    return repo.insert_agent_suggestion(
        review_id=review_id, target_agent="discover", rule_name=rule_name,
        current_value="当前值", suggested_value="建议值",
        reason="建议理由", evidence="事实依据", target_kind=target_kind,
        rule_type=rule_type, priority=priority,
        problem_desc="当前规则缺陷说明", rule_text=rule_text,
        expected_effect="预期胜率提升", risk_note="可能过滤掉部分机会",
        file_path="agent_prompts/discover.py", insert_position="第 2 段")


# ==================== 1. 迁移幂等 ====================

def test_migration_idempotent_and_new_columns():
    """双跑 init_db 幂等；agent_suggestion 含 v2 落地信息列；rule_change 表存在"""
    init_db()
    init_db()
    insp = inspect(engine)
    sug_cols = {c["name"] for c in insp.get_columns("agent_suggestion")}
    for col in ("priority", "rule_type", "problem_desc", "rule_text", "expected_effect",
                "risk_note", "file_path", "insert_position", "conflict_note", "dedup_note"):
        assert col in sug_cols, f"agent_suggestion 迁移后缺少列 {col}"
    assert "rule_change" in set(insp.get_table_names())
    rc_cols = {c["name"] for c in insp.get_columns("rule_change")}
    for col in ("source_suggestion_id", "review_id", "target_agent", "rule_type",
                "rule_name", "rule_text", "before_text", "after_text", "status",
                "rollback_reason", "rollback_time", "operator", "created_at"):
        assert col in rc_cols, f"rule_change 缺少列 {col}"
    # 状态/Agent 查询索引（_ensure_indexes 幂等补建）
    idx = {i["name"] for i in insp.get_indexes("rule_change")}
    assert "ix_rule_change_status" in idx and "ix_rule_change_agent" in idx


# ==================== 2. 采纳全流程 ====================

def test_adopt_full_flow():
    """建议 pending → adopt → rule_change(active) + suggestion(approved)，review 联动落库"""
    sid = _make_suggestion("候选池选股必须验证放量突破形态，未确认不得进入正式候选池。",
                           rule_name="形态确认")
    cid = repo.adopt_rule_suggestion(sid, operator="测试用户")
    assert cid > 0
    sug = repo.get_agent_suggestion(sid)
    assert sug.status == "approved"

    rc = repo.get_rule_change(cid)
    assert rc["status"] == "active"
    assert rc["source_suggestion_id"] == sid
    assert rc["target_agent"] == "discover"
    assert rc["rule_type"] == "soft"
    assert rc["rule_name"] == "形态确认"
    assert rc["priority"] == "high"
    assert rc["stock_code"] == "600601" and rc["stock_name"] == "测试股601"  # review 联动
    assert rc["before_text"] == "（此前无生效规则）"
    assert rc["after_text"] == sug.rule_text
    assert rc["expected_effect"] == "预期胜率提升" and rc["risk_note"] == "可能过滤掉部分机会"
    assert rc["file_path"] == "agent_prompts/discover.py" and rc["insert_position"] == "第 2 段"
    assert rc["operator"] == "测试用户"
    assert rc["rollback_time"] == "" and rc["rollback_reason"] == ""

    # 生效可见 + 列表/详情查询
    assert [r["id"] for r in repo.get_active_rules()] == [cid]
    assert repo.list_rule_changes(status="active", target_agent="discover")
    assert repo.list_rule_changes(suggestion_id=sid), "按来源建议应能查到生效记录"


def test_adopt_rejects_non_pending():
    """并发兜底：已处理建议不可再采纳"""
    sid = _make_suggestion("已处理规则文本。")
    repo.adopt_rule_suggestion(sid)
    assert repo.adopt_rule_suggestion(sid) == 0  # 已 approved → 拒绝
    repo.update_agent_suggestion_status(sid, "rejected")
    assert repo.adopt_rule_suggestion(sid) == 0  # 已驳回 → 拒绝


# ==================== 3. 注入段生成 ====================

def test_dynamic_rules_section_empty_and_hard_soft():
    """无生效规则 → 空；硬性段要求无条件遵守；软性段为参考权重（非死条件）"""
    assert dynamic_rules_section() == ""
    repo.adopt_rule_suggestion(_make_suggestion("硬性注入规则：涨停板炸板回封次数不足 3 次的标的不得追高。",
                                                rule_type="hard", rule_name="炸板硬规则"))
    repo.adopt_rule_suggestion(_make_suggestion("软性注入规则：优先选择板块龙头作为建仓对象。",
                                                rule_type="soft", rule_name="龙头软规则"))
    section = dynamic_rules_section()
    assert "复盘采纳规则·硬性" in section
    assert "无条件遵守" in section and "不得以任何理由放宽" in section
    assert "以人工硬性规则为准" in section
    assert "复盘采纳规则·参考权重" in section
    assert "非死条件" in section and "动态调整须在输出中标注理由" in section
    assert "硬性注入规则" in section and "软性注入规则" in section


# ==================== 4. 确定性校验拦截（双保险第二层） ====================

_RULE_TEXT = "候选标的必须通过放量突破形态确认，不满足时不得进入正式候选池。"


def test_validate_dedup_exact_and_similar():
    """与已生效规则完全相同/高度相似 → 去重拦截"""
    repo.adopt_rule_suggestion(_make_suggestion(_RULE_TEXT))
    ok, conflict, dedup = _validate_adopt(SimpleNamespace(rule_text=_RULE_TEXT, rule_name="重复"))
    assert not ok and not conflict and "完全相同" in dedup

    similar = _RULE_TEXT.replace("放量突破", "放量上涨")  # 高相似（>0.85）非全同
    ok, conflict, dedup = _validate_adopt(SimpleNamespace(rule_text=similar, rule_name="相似"))
    assert not ok and not conflict and "高度相似" in dedup


def test_validate_hard_rule_red_line_conflict():
    """疑似放宽/绕过硬性底线（高相似 + 放宽动词）→ 冲突拦截"""
    hard0 = HARD_RULES[0]
    weaken = hard0 + "，允许结合实际行情适当放宽执行。"
    ok, conflict, dedup = _validate_adopt(SimpleNamespace(rule_text=weaken, rule_name="放宽底线"))
    assert not ok and not dedup and "冲突" in conflict

    # 与硬性规则完全相同（无放宽动词）→ 去重拦截
    ok, conflict, dedup = _validate_adopt(SimpleNamespace(rule_text=hard0, rule_name="复述底线"))
    assert not ok and not conflict and dedup


def test_validate_profile_field_hit():
    """rule_name 命中偏好档案字段 → 引导改走 profile 通道"""
    repo.update_trade_profile({"风控容忍度": "单笔回撤容忍 6%"})
    ok, conflict, dedup = _validate_adopt(
        SimpleNamespace(rule_text="与档案无关的全新规则文本。", rule_name="风控容忍度"))
    assert not ok and "偏好档案" in conflict


def test_adopt_route_guards_and_409():
    """路由守卫：profile 走 adopt 400 / 缺 rule_text 400 / hard 缺 confirm 400 /
    校验失败 409 并回填 notes"""
    # profile 类 → 400 引导走 approve
    sid = _make_suggestion("规则文本", target_kind="profile")
    with pytest.raises(HTTPException) as ei:
        adopt_agent_suggestion(sid, AdoptSuggestionBody())
    assert ei.value.status_code == 400

    # 缺 rule_text（旧版建议）→ 400
    sid2 = _make_suggestion("", rule_name="旧版建议")
    with pytest.raises(HTTPException) as ei2:
        adopt_agent_suggestion(sid2, AdoptSuggestionBody())
    assert ei2.value.status_code == 400 and "旧版" in ei2.value.detail

    # hard 缺 confirm → 400
    sid3 = _make_suggestion("硬规则文本内容，要求无条件执行。", rule_type="hard")
    with pytest.raises(HTTPException) as ei3:
        adopt_agent_suggestion(sid3, AdoptSuggestionBody())
    assert ei3.value.status_code == 400 and "确认" in ei3.value.detail

    # hard + confirm → 采纳成功
    res = adopt_agent_suggestion(sid3, AdoptSuggestionBody(confirm=True))
    assert res["adopted"] and res["applied"] == "injected"

    # 完全相同规则（已生效）→ 409 + notes 回填
    sid4 = _make_suggestion("硬规则文本内容，要求无条件执行。", rule_type="soft")
    with pytest.raises(HTTPException) as ei4:
        adopt_agent_suggestion(sid4, AdoptSuggestionBody())
    assert ei4.value.status_code == 409
    sug4 = repo.get_agent_suggestion(sid4)
    assert "完全相同" in (sug4.dedup_note or ""), "409 应回填去重说明"


def test_profile_approve_flow_unaffected():
    """profile 类建议仍走 approve（写偏好档案 + 版本+1）；prompt 类误调 approve 400 引导"""
    sid = _make_suggestion("档案内容", target_kind="profile", rule_name="偏好字段A")
    res = approve_agent_suggestion(sid)
    assert res["applied"] == "profile" and res["profile_version"] > 0
    assert repo.get_agent_suggestion(sid).status == "approved"

    sid2 = _make_suggestion("规则文本", target_kind="prompt")
    with pytest.raises(HTTPException) as ei:
        approve_agent_suggestion(sid2)
    assert ei.value.status_code == 400 and "adopt" in ei.value.detail


def test_re_review_rejected_suggestion_resets_to_pending():
    sid = _make_suggestion("规则文本")
    repo.update_agent_suggestion_status(sid, "rejected", reason="证据不足")
    res = re_review_agent_suggestion(sid)
    row = repo.get_agent_suggestion(sid)
    assert res["status"] == "pending"
    assert row.status == "pending" and row.reject_reason == ""
    with pytest.raises(HTTPException) as ei:
        re_review_agent_suggestion(sid)
    assert ei.value.status_code == 400


# ==================== 5. 回滚 ====================

def test_rollback_flow():
    """回滚：状态/原因/时间留痕 + 生效排除 + 版本变化 + 重复回滚拒绝 + 路由 404"""
    sid = _make_suggestion("回滚测试规则：买入前必须确认当日大盘无重大利空公告。")
    cid = repo.adopt_rule_suggestion(sid)
    ver1 = repo.rule_version()
    assert repo.get_active_rules(), "回滚前应生效"

    ok = repo.rollback_rule_change(cid, "行情特征变化，撤下该规则")
    assert ok
    rc = repo.get_rule_change(cid)
    assert rc["status"] == "rolled_back"
    assert rc["rollback_reason"] == "行情特征变化，撤下该规则"
    assert rc["rollback_time"], "回滚应记录时间"
    assert repo.get_active_rules() == [], "回滚后不得再注入"
    assert repo.rule_version() != ver1, "回滚后版本指纹变化（LLM 缓存键变化）"

    # 重复回滚 → 拒绝（repo False / 路由 404）
    assert repo.rollback_rule_change(cid, "再滚一次") is False
    with pytest.raises(HTTPException) as ei:
        rollback_route(cid, RollbackRuleBody(reason="再滚一次"))
    assert ei.value.status_code == 404


def test_rollback_requires_reason():
    """路由层：回滚原因必填（至少 1 字符）"""
    sid = _make_suggestion("必填原因测试规则。")
    cid = repo.adopt_rule_suggestion(sid)
    with pytest.raises(HTTPException) as ei:
        rollback_route(cid, RollbackRuleBody(reason=" "))
    assert ei.value.status_code == 400 and "不能为空" in ei.value.detail
    rc = repo.get_rule_change(cid)
    assert rc["status"] == "active", "空白原因不得触发回滚"


# ==================== 6. 缓存失效 ====================

def test_cache_invalidation_after_adopt_and_rollback():
    """采纳/回滚走 _invalidate：直查立即反映新数据（不依赖 60s TTL）"""
    assert repo.get_active_rules() == []
    sid = _make_suggestion("缓存失效测试规则：持仓盈利回撤超过 6% 必须进入复查队列。")
    cid = repo.adopt_rule_suggestion(sid)
    assert [r["id"] for r in repo.get_active_rules()] == [cid], "采纳后直查应立即可见"
    repo.rollback_rule_change(cid, "验证缓存失效")
    assert repo.get_active_rules() == [], "回滚后直查应立即可见"
