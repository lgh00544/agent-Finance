"""Memory Curator for auto-merged experience memories.

First version is deterministic and conservative: it expires, archives, or
proposes summaries for review. It never deletes memories and never promotes a
summary to active automatically.
"""
from __future__ import annotations

import difflib
import json
from datetime import datetime

from app.db import repo
from app.services import experience_worker


def _cfg_float(key: str) -> float:
    try:
        return float(experience_worker._cfg(key))
    except (TypeError, ValueError):
        return float(experience_worker.DEFAULTS.get(key, "0"))


def _cfg_int(key: str) -> int:
    try:
        return int(float(experience_worker._cfg(key)))
    except (TypeError, ValueError):
        return int(float(experience_worker.DEFAULTS.get(key, "0")))


def _cfg_bool(key: str) -> bool:
    return str(experience_worker._cfg(key)).lower() in ("1", "true", "yes")


def _parse_dt(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _split_tags(raw) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, (list, tuple)):
        return {str(t).strip() for t in raw if str(t).strip()}
    text = str(raw).strip()
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return {str(t).strip() for t in arr if str(t).strip()}
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return {t.strip() for t in text.replace(",", " ").split() if t.strip()}


def _similarity(a: dict, b: dict) -> float:
    left = f"{a.get('title') or ''}\n{a.get('body') or ''}"[:600]
    right = f"{b.get('title') or ''}\n{b.get('body') or ''}"[:600]
    return difflib.SequenceMatcher(None, left, right).ratio()


def _duplicate_actions(items: list[dict], threshold: float) -> list[dict]:
    actions: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for idx, left in enumerate(items):
        left_tags = _split_tags(left.get("tags"))
        if not left_tags:
            continue
        for right in items[idx + 1:]:
            pair = tuple(sorted((int(left["id"]), int(right["id"]))))
            if pair in seen or left.get("stage") != right.get("stage"):
                continue
            right_tags = _split_tags(right.get("tags"))
            if not left_tags.intersection(right_tags):
                continue
            score = _similarity(left, right)
            if score >= threshold:
                seen.add(pair)
                title = f"策展摘要候选：{left.get('stage') or ''} {','.join(sorted(left_tags & right_tags))}"
                body = (
                    f"相似经验待人工策展合并，来源 experience_id={pair[0]},{pair[1]}；"
                    f"原标题：{left.get('title') or ''} / {right.get('title') or ''}。"
                    "请人工复核后决定是否批准为 active。"
                )
                actions.append({
                    "action": "propose_summary",
                    "status": "pending_review",
                    "source_ids": list(pair),
                    "stage": left.get("stage") or "",
                    "tags": sorted(left_tags & right_tags),
                    "similarity": round(score, 4),
                    "title": title,
                    "body": body,
                })
    return actions


def run_curator(dry_run: bool = True, limit: int = 100) -> dict:
    if not _cfg_bool("memory_curator_enabled"):
        return {"dry_run": dry_run, "skipped": True, "reason": "disabled", "actions": []}

    now = datetime.now()
    limit = min(max(int(limit), 1), 500)
    retention_days = _cfg_int("memory_retention_days")
    low_confidence = _cfg_float("memory_low_confidence_threshold")
    stale_hits = _cfg_int("memory_stale_hit_threshold")
    duplicate_similarity = _cfg_float("memory_duplicate_similarity")

    active = repo.list_curator_candidates(status="active", limit=limit)
    actions: list[dict] = []
    planned_ids: set[int] = set()
    for item in active:
        expires_at = _parse_dt(item.get("expires_at"))
        if expires_at and expires_at <= now:
            planned_ids.add(int(item["id"]))
            actions.append({
                "action": "expire",
                "id": item["id"],
                "status": "expired",
                "reason": "expires_at <= now",
            })

    stale = repo.list_curator_candidates(
        status="active", older_than_days=retention_days,
        max_hit_count=stale_hits, max_confidence=low_confidence, limit=limit)
    for item in stale:
        if int(item["id"]) in planned_ids:
            continue
        planned_ids.add(int(item["id"]))
        actions.append({
            "action": "archive",
            "id": item["id"],
            "status": "archived",
            "reason": "low confidence stale memory",
        })

    duplicate_pool = [item for item in active if int(item["id"]) not in planned_ids]
    actions.extend(_duplicate_actions(duplicate_pool, duplicate_similarity))

    executed = 0
    if not dry_run:
        for action in actions:
            if action["action"] == "expire":
                if repo.mark_experience_curated(action["id"], "expired", action["reason"]):
                    executed += 1
            elif action["action"] == "archive":
                if repo.mark_experience_curated(action["id"], "archived", action["reason"]):
                    executed += 1
            elif action["action"] == "propose_summary":
                eid = repo.insert_experience(
                    action["title"], action["body"], action["stage"], action["tags"],
                    "low", 0.0, auto_merged=0, source_pending_id=None,
                    status="pending_review")
                repo.mark_experience_curated(
                    eid, "pending_review",
                    f"duplicate_summary source_ids={action['source_ids']} similarity={action['similarity']}")
                action["id"] = eid
                executed += 1

    return {"dry_run": dry_run, "skipped": False, "actions": actions,
            "action_count": len(actions), "executed": executed}
