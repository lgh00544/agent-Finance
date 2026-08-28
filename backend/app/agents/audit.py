"""通用审核 Agent（批1：只审 agent_suggestion）
collect_audit 读建议 → llm_audit 首审 / llm_re_audit 重审 → run_pending_audits 批量扫描入口"""
import json
import logging
import time

from app.agents.common import ModelLevel, agent_call
from app.agents.review import llm_rethink_suggestion
from app.agents.schemas import AuditOutput
from app.core.config import settings
from agent_prompts import audit_prompt
from app.db import repo

logger = logging.getLogger(__name__)


def collect_audit(suggestion) -> dict:
    """聚合单条待审建议 → 审核输入（只读，不改任何字段）"""
    return {"id": suggestion.id, "target_agent": suggestion.target_agent,
            "rule_name": suggestion.rule_name, "current_value": suggestion.current_value,
            "suggested_value": suggestion.suggested_value, "reason": suggestion.reason,
            "evidence": suggestion.evidence, "expected_effect": suggestion.expected_effect,
            "risk_note": suggestion.risk_note}


def llm_audit(suggestion) -> AuditOutput:
    """round1 首审：辩证裁决（缓存键含 round，不污染原缓存）"""
    return agent_call(agent="audit",
                      cache_key=f"audit:agent_suggestion:{suggestion.id}:round1",
                      system_prompt=audit_prompt.SYSTEM_PROMPT,
                      user_prompt=audit_prompt.build_user_prompt(collect_audit(suggestion)),
                      schema=AuditOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP)


def llm_re_audit(suggestion, dissent_view: str) -> AuditOutput:
    """round2 重审：追加历史 fail 原因，逐条回应反对意见"""
    return agent_call(agent="audit",
                      cache_key=f"audit:agent_suggestion:{suggestion.id}:round2",
                      system_prompt=audit_prompt.SYSTEM_PROMPT,
                      user_prompt=audit_prompt.build_re_audit_user_prompt(
                          collect_audit(suggestion), dissent_view),
                      schema=AuditOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP)


def _persist(suggestion, audit_round: int, out: AuditOutput, duration_ms: int) -> int:
    """落 audit_log + 原表 3 个 audit 字段（reasoning 存 LLM 原始 JSON 全文）"""
    log_id = repo.insert_audit_log(
        target_type="agent_suggestion", target_id=suggestion.id, audit_round=audit_round,
        verdict=out.verdict, confidence=out.confidence,
        support_view=out.support_view, dissent_view=out.dissent_view,
        boundary_cases=out.boundary_cases, evidence_refs=list(out.evidence_refs or []),
        audit_model=settings.deepseek_reasoning_model,
        reasoning=json.dumps(out.model_dump(), ensure_ascii=False, default=str),
        duration_ms=duration_ms)
    repo.update_agent_suggestion_audit(suggestion.id, audit_verdict=out.verdict,
                                       audit_round=audit_round, last_audit_id=log_id)
    return log_id


def run_pending_audits(cutoff_id: int = 0, last_scanned_id: int | None = None,
                       limit: int = 50) -> dict:
    """批量扫描待审建议辩证审核（幂等：pass/round2-fail 不再自动重审）。
    首审 fail → 调 llm_rethink_suggestion 重思考 + 游标不越过（下轮 round2 重审）；round2 仍 fail → 定格不再第 3 轮。"""
    cursor = max(cutoff_id or 0, int(repo.get_config("audit_cursor.last_id") or 0),
                 last_scanned_id or 0)
    rows = repo.list_agent_suggestions_for_audit(cursor, limit)
    audited, rethunk = 0, 0
    for s in rows:
        nxt = (s.audit_round or 0) + 1
        prev_dissent = ""
        if nxt >= 2 and s.last_audit_id:
            prev_log = repo.get_audit_log(s.last_audit_id)
            prev_dissent = prev_log.dissent_view if prev_log else ""
        t0 = time.time()
        out = llm_re_audit(s, prev_dissent) if nxt >= 2 else llm_audit(s)
        dur = int((time.time() - t0) * 1000)
        _persist(s, nxt, out, dur)
        audited += 1
        if out.verdict == "fail" and nxt == 1:
            try:
                llm_rethink_suggestion(s.review_id, out.dissent_view)  # 失败自动重思考（复用 review 链路）
                rethunk += 1
            except Exception as exc:  # noqa: BLE001 重思考失败不阻断审核状态落库
                logger.warning("audit 触发 rethink 失败 review#%s: %s", s.review_id, exc)
            break  # 游标不越过，下轮 round2 重审
        cursor = max(cursor, s.id)
    repo.set_config("audit_cursor.last_id", str(cursor))
    return {"audited": audited, "rethunk": rethunk, "cursor": cursor}
