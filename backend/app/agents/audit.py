"""通用审核 Agent（批1：只审 agent_suggestion）
collect_audit 读建议 → llm_audit 首审 / llm_re_audit 重审 → run_pending_audits 批量扫描入口"""
import json
import logging
import concurrent.futures
import time

from app.agents.common import ModelLevel, agent_call
from app.agents.review import llm_rethink_suggestion
from app.agents.schemas import AuditOutput
from app.core.config import settings
from agent_prompts import audit_prompt
from app.db import repo

logger = logging.getLogger(__name__)
AUDIT_ITEM_TIMEOUT_SECONDS = 90


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


def _call_with_timeout(fn, timeout_seconds: int, *args):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, *args)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as exc:
        raise TimeoutError(f"audit item timeout after {timeout_seconds}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def run_pending_audits(cutoff_id: int = 0, last_scanned_id: int | None = None,
                       limit: int = 50) -> dict:
    """批量扫描待审建议辩证审核（幂等：pass/round2-fail 不再自动重审）。
    单条 fail/异常/超时隔离：不中断整批；round2 仍 fail → 定格不再第 3 轮。"""
    cursor = max(cutoff_id or 0, int(repo.get_config("audit_cursor.last_id") or 0),
                 last_scanned_id or 0)
    rows = repo.list_agent_suggestions_for_audit(cursor, limit)
    audited, rethunk, failed = 0, 0, 0
    errors: list[dict] = []
    blocked_id: int | None = None
    for s in rows:
        try:
            nxt = (s.audit_round or 0) + 1
            prev_dissent = ""
            if nxt >= 2 and s.last_audit_id:
                prev_log = repo.get_audit_log(s.last_audit_id)
                prev_dissent = prev_log.dissent_view if prev_log else ""
            t0 = time.time()
            if nxt >= 2:
                out = _call_with_timeout(_call_re_audit, AUDIT_ITEM_TIMEOUT_SECONDS, s, prev_dissent)
            else:
                out = _call_with_timeout(llm_audit, AUDIT_ITEM_TIMEOUT_SECONDS, s)
            dur = int((time.time() - t0) * 1000)
            _persist(s, nxt, out, dur)
            audited += 1
            if out.verdict == "fail" and nxt == 1:
                blocked_id = s.id if blocked_id is None else min(blocked_id, s.id)
                try:
                    llm_rethink_suggestion(s.review_id, out.dissent_view)  # 失败自动重思考（复用 review 链路）
                    rethunk += 1
                except Exception as exc:  # noqa: BLE001 重思考失败不阻断审核状态落库
                    logger.warning("audit 触发 rethink 失败 review#%s: %s", s.review_id, exc)
            elif blocked_id is None:
                cursor = max(cursor, s.id)
                repo.set_config("audit_cursor.last_id", str(cursor))
        except Exception as exc:  # noqa: BLE001 单条失败隔离，后续建议继续审核
            failed += 1
            blocked_id = s.id if blocked_id is None else min(blocked_id, s.id)
            errors.append({"id": s.id, "error": str(exc)[:300]})
            logger.exception("audit 单条审核失败 suggestion#%s: %s", s.id, exc)
    repo.set_config("audit_cursor.last_id", str(cursor))
    return {"audited": audited, "rethunk": rethunk, "failed": failed,
            "errors": errors, "cursor": cursor}


def _call_re_audit(suggestion, dissent_view: str) -> AuditOutput:
    return llm_re_audit(suggestion, dissent_view)


def trigger_audit_for_suggestion(suggestion_id: int) -> dict:
    """手动触发单条建议审核：仅 pending/fail 跑一次，不推进批量游标。"""
    s = repo.get_agent_suggestion(suggestion_id)
    if s is None:
        raise LookupError("建议不存在")
    verdict = s.audit_verdict or "pending"
    if verdict not in ("pending", "fail"):
        raise ValueError(f"仅待审/驳回建议可重新审核（{verdict}）")
    if verdict == "fail":
        repo.update_agent_suggestion_audit(s.id, "pending", s.audit_round or 0, s.last_audit_id)
    nxt = (s.audit_round or 0) + 1
    prev_dissent = ""
    if nxt >= 2 and s.last_audit_id:
        prev_log = repo.get_audit_log(s.last_audit_id)
        prev_dissent = prev_log.dissent_view if prev_log else ""
    t0 = time.time()
    out = llm_re_audit(s, prev_dissent) if nxt >= 2 else llm_audit(s)
    log_id = _persist(s, nxt, out, int((time.time() - t0) * 1000))
    return {"audited": True, "suggestion_id": suggestion_id, "verdict": out.verdict,
            "round": nxt, "audit_log_id": log_id}
