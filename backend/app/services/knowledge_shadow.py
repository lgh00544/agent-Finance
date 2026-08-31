"""Shadow knowledge observation helpers.

This module only records what shadow knowledge would have matched. It never
returns content for prompt injection and never changes agent decisions.
"""
from __future__ import annotations

import logging

from app.db import repo
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _compact_text(value: str, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def infer_shadow_bias(doc: dict) -> str:
    """First-pass deterministic label for shadow observation only."""
    methodology = str(doc.get("methodology_type") or "").strip()
    if methodology in ("risk", "sell"):
        return "risk"
    text = f"{doc.get('title') or ''} {doc.get('content') or ''}"
    if any(term in text for term in ("加分", "强化", "主线", "突破")):
        return "boost"
    if any(term in text for term in ("降权", "回避", "风险", "派发")):
        return "reduce"
    return "unknown"


def shadow_summary(doc: dict) -> str:
    title = _compact_text(doc.get("title") or "", 60)
    content = _compact_text(doc.get("content") or "", 120)
    return f"{title}: {content}" if content else title


def search_shadow_knowledge(agent: str, query: str = "",
                            scenario_tags: list[str] | None = None,
                            top_k: int = 5) -> list[dict]:
    """Search only status=shadow private knowledge for current agent plus all."""
    return get_vector_store().search_knowledge(
        agent, top_k=top_k, query=query, scenario_tags=scenario_tags, status="shadow")


def record_shadow_hits(agent: str, stock_code: str, stock_name: str, trade_date: str,
                       query: str = "", scenario_tags: list[str] | None = None,
                       top_k: int = 5) -> list[int]:
    """Record matching shadow docs as idempotent observations."""
    docs = search_shadow_knowledge(agent, query=query, scenario_tags=scenario_tags, top_k=top_k)
    hit_ids: list[int] = []
    for doc in docs:
        hit_ids.append(repo.record_knowledge_shadow_hit(
            knowledge_id=int(doc["id"]),
            agent=agent,
            stock_code=stock_code,
            stock_name=stock_name,
            trade_date=trade_date,
            query=query,
            scenario_tags=scenario_tags or doc.get("scenario_tags") or [],
            shadow_bias=infer_shadow_bias(doc),
            shadow_summary=shadow_summary(doc),
        ))
    return hit_ids
