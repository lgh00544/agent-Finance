"""模拟复盘审核入口。

This module persists only the paper review audit/shadow status.  Snapshot
analysis itself lives in :mod:`app.services.paper_analysis` and never uses the
live Holding/TradeRecord review chain.
"""

from app.db import repo
from app.services.paper_analysis import PaperAuditOutput, audit_case, review_cycle


def audit_review(review_id: int) -> dict:
    rows = repo.list_paper_reviews(limit=500)
    review = next((item for item in rows if item["id"] == review_id), None)
    if review is None:
        raise ValueError("模拟复盘不存在")
    content = dict(review.get("content") or {})
    # A stored review may already carry a generated review.  If it does not,
    # generate it from the same frozen facts before auditing; caller supplied
    # verdicts are never accepted as audit evidence.
    facts = dict(content.get("facts") or content)
    generated = content.get("review")
    if not generated:
        generated_result = review_cycle({
            **facts,
            "candidate_id": facts.get("candidate_id"),
            "score_id": facts.get("score_id"),
            "plan_id": facts.get("plan_id"),
            "trade_date": facts.get("trade_date") or review.get("review_date"),
            "review_date": review.get("review_date"),
        })
        generated = generated_result.get("review") or generated_result
    audited = audit_case(facts, generated)
    verdict = audited.get("verdict") if audited.get("status") in ("ok", "error") else "fail"
    reason = audited.get("reason") or audited.get("error") or "模拟复盘审核失败"
    result = repo.audit_paper_review(review_id, verdict, reason)
    if result and result.get("audit_status") == "passed":
        shadow = repo.mark_paper_shadow(review_id)
        if shadow:
            result.update(shadow)
    return {**(result or {}), "evidence_gaps": audited.get("evidence_gaps", []),
            "audit_agent": "paper_audit", "source_type": "paper",
            "shadow_eligible": audited.get("shadow_eligible", False),
            "formal_rule_change": False}


def review_paper_snapshot(facts: dict) -> dict:
    """Explicit Agent-facing wrapper for paper review generation."""
    return review_cycle(facts)


def audit_paper_snapshot(facts: dict, review: dict) -> dict:
    """Explicit Agent-facing wrapper for review audit; no persistence."""
    return audit_case(facts, review)
