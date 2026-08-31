"""通用审核 Agent 批1 测试：audit_log 落库 / 辩证 schema / pending 扫描补漏 / round2 仍 fail 不再第3轮"""
import pytest
from pydantic import ValidationError

from app.agents.audit import run_pending_audits
from app.agents.schemas import AuditOutput
from app.db import repo
from app.db.session import init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _mk_suggestion(review_id: int = 1) -> int:
    return repo.insert_agent_suggestion(
        review_id, "review", "止盈分批规则", "一次性全清", "分批止盈",
        "止盈应分批执行", "回测胜率 62%", target_kind="profile")


def _audit_out(verdict: str = "pass") -> AuditOutput:
    return AuditOutput(verdict=verdict, confidence=85,
                       support_view="有数据支持且符合资金管理原则",
                       dissent_view="弱势市况下分批可能错过反弹（亨通惨案根因1）",
                       boundary_cases="市况极差或流动性骤降时结论失效",
                       evidence_refs=["K223"], one_line_summary="建议合理")


def test_audit_log_roundtrip():
    """① audit_log 落库 + 读取 + 改 verdict"""
    lid = repo.insert_audit_log("agent_suggestion", 100, 1, "pass", 85,
                                "支持", "反对", "边界", ["K223"], "deepseek", "{}", 120)
    row = repo.get_audit_log(lid)
    assert row.verdict == "pass" and row.round == 1 and row.evidence_refs == ["K223"]
    repo.update_audit_log_verdict(lid, "fail")
    assert repo.get_audit_log(lid).verdict == "fail"


def test_audit_output_schema():
    """② 辩证 schema：必填字段校验，缺失报 ValidationError"""
    out = _audit_out()
    assert out.verdict == "pass" and out.evidence_refs == ["K223"]
    with pytest.raises(ValidationError):
        AuditOutput(verdict="pass")  # 缺其余必填字段


def test_audit_output_normalizes_common_llm_shapes():
    out = AuditOutput(verdict="pass", confidence=0.6,
                      support_view="有数据支持且符合资金管理原则",
                      dissent_view="弱势市况下分批可能错过反弹，需结合流动性场景判断",
                      one_line_summary="建议可通过")
    assert out.confidence == 60
    assert out.boundary_cases == ""
    assert out.evidence_refs == []


def test_pending_scan_respects_cutoff_and_cursor(monkeypatch):
    """③ 扫描补漏：cutoff 前存量不审、新增被审、pass 落库 + 游标推进到本轮最大"""
    old = _mk_suggestion()
    new = _mk_suggestion()
    monkeypatch.setattr("app.agents.audit.llm_audit", lambda s: _audit_out())
    monkeypatch.setattr("app.agents.audit.llm_re_audit", lambda s, d: _audit_out())
    result = run_pending_audits(cutoff_id=old)  # 启用边界 = 存量最大 id
    assert result["audited"] == 1
    old_row, new_row = repo.get_agent_suggestion(old), repo.get_agent_suggestion(new)
    assert old_row.audit_verdict == "pending" and old_row.last_audit_id is None  # 存量不被自动审核
    assert new_row.audit_verdict == "pass" and new_row.audit_round == 1 and new_row.last_audit_id
    assert repo.get_config("audit_cursor.last_id") == str(new)


def test_manual_re_audit_endpoint_submits_one_suggestion_task(monkeypatch):
    from fastapi import HTTPException
    from app.api.routes import re_audit_suggestion

    sid = _mk_suggestion()
    submitted = {}
    monkeypatch.setattr("app.api.routes._submit_task",
                        lambda kind, params: submitted.update({"kind": kind, "params": params}) or {
                            "task_id": "t-audit-one", "status": "pending"})
    res = re_audit_suggestion(sid)
    row = repo.get_agent_suggestion(sid)
    assert res == {"task_id": "t-audit-one", "status": "pending"}
    assert submitted == {"kind": "audit_one", "params": {"suggestion_id": sid}}
    assert row.audit_verdict == "pending" and row.audit_round == 0
    with pytest.raises(HTTPException) as ei:
        re_audit_suggestion(999999999)
    assert ei.value.status_code == 404


def test_round2_still_fail_no_round3(monkeypatch):
    """④ round1 fail → rethink 触发 + 游标不越过；round2 仍 fail → 定格 round2，不再第 3 轮"""
    sid = _mk_suggestion()
    rethink_calls = {"n": 0}

    def fake_rethink(review_id, reason):
        rethink_calls["n"] += 1

    monkeypatch.setattr("app.agents.audit.llm_audit", lambda s: _audit_out("fail"))
    monkeypatch.setattr("app.agents.audit.llm_re_audit", lambda s, d: _audit_out("fail"))
    monkeypatch.setattr("app.agents.audit.llm_rethink_suggestion", fake_rethink)
    repo.set_config("audit_cursor.last_id", str(sid - 1))

    r1 = run_pending_audits(cutoff_id=sid - 1)
    assert r1["rethunk"] == 1 and rethink_calls["n"] == 1
    s1 = repo.get_agent_suggestion(sid)
    assert s1.audit_verdict == "fail" and s1.audit_round == 1
    assert r1["cursor"] < sid  # 首审 fail 游标不越过未处理 id

    r2 = run_pending_audits(cutoff_id=sid - 1)
    assert r2["audited"] == 1  # round2 重审
    s2 = repo.get_agent_suggestion(sid)
    assert s2.audit_verdict == "fail" and s2.audit_round == 2
    assert rethink_calls["n"] == 1  # 不再触发 rethink

    r3 = run_pending_audits(cutoff_id=sid - 1)
    assert r3["audited"] == 0  # 无第 3 轮


def test_get_latest_audit_log_by_target():
    """① repo 层：同目标多条取最新（created_at desc），无记录返回 None"""
    from app.db import repo as _r

    _r.insert_audit_log("agent_suggestion", 900, 1, "pass", 80, "支持", "反对1", "边界",
                        ["K223"], "deepseek", "{}", 100)
    _r.insert_audit_log("agent_suggestion", 900, 2, "fail", 70, "支持", "反对2", "边界",
                        ["K223"], "deepseek", "{}", 200)
    row = _r.get_latest_audit_log_by_target("agent_suggestion", 900)
    assert row["round"] == 2 and row["dissent_view"] == "反对2"
    assert _r.get_latest_audit_log_by_target("agent_suggestion", 999999) is None


def test_audit_log_get():
    """② 端点：命中返回含 dissent_view 的行，未命中 404（detail='not found'）"""
    from fastapi import HTTPException
    from app.api.routes import get_audit_log_detail

    repo.insert_audit_log("agent_suggestion", 901, 1, "pass", 85, "支持", "反例场景", "边界",
                          ["K223"], "deepseek", "{}", 100)
    r = get_audit_log_detail("agent_suggestion", 901)
    assert r["dissent_view"] == "反例场景" and r["verdict"] == "pass"
    try:
        get_audit_log_detail("agent_suggestion", 999999)
        raise AssertionError("应 404")
    except HTTPException as e:
        assert e.status_code == 404
        assert e.detail == "not found"
