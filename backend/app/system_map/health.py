"""Read-only governance health aggregation.

This module observes existing registry and database data only. It must not
execute Agents, submit tasks, mutate governance state, or create new records.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import select

from app.db.models import (
    AgentSuggestion,
    AuditLog,
    Experience,
    KnowledgeShadowHit,
    PendingExperience,
    PrivateKnowledge,
    RuleChange,
)
from app.db.session import SessionLocal, get_init_db_result
from app.system_map import collaboration, integrity, registry


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _module(name: str, status: str, *, counts: dict | None = None,
            updated_at: str | None = None, last_error: str | None = None,
            **extra) -> dict:
    result = {
        "module": name,
        "status": status,
        "counts": counts or {},
        "updated_at": updated_at or _now(),
        "last_error": last_error,
    }
    result.update(extra)
    return result


def _run_module(name: str, loader) -> dict:
    try:
        return loader()
    except Exception as exc:  # noqa: BLE001 each module must degrade independently
        return _module(name, "error", last_error=str(exc) or exc.__class__.__name__)


def _status_with_data(*, has_data: bool, attention: bool = False) -> str:
    if attention:
        return "attention"
    return "healthy" if has_data else "unknown"


def _system_map() -> dict:
    agents = registry.list_agents()
    workflows = registry.list_workflows()
    tools = registry.list_tools()
    return _module(
        "system_map",
        _status_with_data(has_data=bool(agents or workflows or tools)),
        counts={
            "agents": len(agents),
            "workflows": len(workflows),
            "tools": len(tools),
        },
    )


def _knowledge() -> dict:
    with SessionLocal() as db:
        rows = db.execute(select(PrivateKnowledge)).scalars().all()
        statuses = Counter((row.status or "unknown").strip() or "unknown" for row in rows)
        by_agent = Counter((row.agent_tag or "unknown").strip() or "unknown" for row in rows)
    return _module(
        "knowledge",
        _status_with_data(has_data=bool(rows)),
        counts={
            "total": len(rows),
            "active": statuses.get("active", 0),
            "shadow": statuses.get("shadow", 0),
            "archived": statuses.get("archived", 0),
            "expired": statuses.get("expired", 0),
            "unknown_status": statuses.get("unknown", 0),
        },
        by_agent=dict(sorted(by_agent.items())),
        expired_requested={"status": "unknown", "reason": "当前没有知识请求命中日志接口"},
        semantics={
            "active": "进入正式 Knowledge 注入",
            "shadow": "仅旁路观察，不进入正式 prompt",
            "archived_expired": "默认不进入正式 prompt",
        },
    )


def _shadow() -> dict:
    with SessionLocal() as db:
        rows = db.execute(
            select(KnowledgeShadowHit).order_by(
                KnowledgeShadowHit.trade_date.desc(),
                KnowledgeShadowHit.id.desc(),
            )
        ).scalars().all()
    statuses = Counter((row.verify_status or "unknown").strip() or "unknown" for row in rows)
    latest = rows[0].updated_at or rows[0].created_at if rows else None
    completed = statuses.get("finished", 0)
    unfinished = statuses.get("pending", 0) + statuses.get("partial", 0)
    failed = statuses.get("failed", 0) + statuses.get("error", 0)
    return _module(
        "shadow",
        _status_with_data(has_data=bool(rows), attention=bool(failed or unfinished)),
        counts={
            "total_hits": len(rows),
            "unfinished_t_plus_n": unfinished,
            "backfilled": completed,
            "failed_or_error": failed,
            "unknown_status": statuses.get("unknown", 0),
        },
        latest_hit_at=str(latest) if latest else None,
        semantics={
            "formal_knowledge": False,
            "formal_prompt": False,
            "formal_scoring": False,
        },
    )


def _experience() -> dict:
    with SessionLocal() as db:
        experiences = db.execute(select(Experience)).scalars().all()
        pending = db.execute(select(PendingExperience)).scalars().all()
    statuses = Counter((row.status or "unknown").strip() or "unknown" for row in experiences)
    queue_statuses = Counter((row.status or "unknown").strip() or "unknown" for row in pending)
    expired = sum(
        1 for row in experiences
        if row.expires_at is not None and row.expires_at <= datetime.now()
    )
    return _module(
        "experience_memory",
        _status_with_data(
            has_data=bool(experiences or pending),
            attention=bool(statuses.get("pending_review", 0) or queue_statuses.get("pending", 0)),
        ),
        counts={
            "total": len(experiences),
            "active": statuses.get("active", 0),
            "pending_review": statuses.get("pending_review", 0),
            "rolled_back": statuses.get("rolled_back", 0),
            "rejected": statuses.get("rejected", 0),
            "expired": statuses.get("expired", 0),
            "expired_by_time": expired,
            "pending_queue": queue_statuses.get("pending", 0),
            "processing_queue": queue_statuses.get("processing", 0),
            "failed_queue": sum(1 for row in pending if row.error),
        },
        curator_last_run={
            "status": "unknown",
            "reason": "当前没有 Memory Curator 运行记录查询接口",
        },
        semantics={
            "soft_context": True,
            "hard_rule": False,
            "curator_deletes_physical_rows": False,
            "curator_summary_auto_promotes": False,
        },
    )


def _rules_audit() -> dict:
    with SessionLocal() as db:
        suggestions = db.execute(select(AgentSuggestion)).scalars().all()
        audits = db.execute(select(AuditLog)).scalars().all()
        changes = db.execute(select(RuleChange)).scalars().all()
    pending_suggestions = [row for row in suggestions if row.status == "pending"]
    ai_pending = [
        row for row in suggestions
        if (row.audit_verdict or "pending") == "pending"
    ]
    ai_failed = [
        row for row in suggestions
        if (row.audit_verdict or "") == "fail"
    ]
    manual_pending = [
        row for row in pending_suggestions
        if (row.audit_verdict or "pending") == "pass"
    ]
    timestamps = [
        row.created_at for row in [*suggestions, *audits, *changes]
        if getattr(row, "created_at", None) is not None
    ]
    return _module(
        "rule_change_audit",
        _status_with_data(
            has_data=bool(suggestions or audits or changes),
            attention=bool(pending_suggestions or ai_failed or manual_pending),
        ),
        counts={
            "suggestions_total": len(suggestions),
            "pending": len(pending_suggestions),
            "ai_pending": len(ai_pending),
            "ai_failed": len(ai_failed),
            "manual_pending": len(manual_pending),
            "active_rules": sum(1 for row in changes if row.status == "active"),
            "rolled_back_rules": sum(1 for row in changes if row.status == "rolled_back"),
            "audit_logs": len(audits),
        },
        latest_change_at=str(max(timestamps)) if timestamps else None,
        semantics={
            "audit_gate_required": True,
            "hard_rule_human_confirm_required": True,
            "page_is_read_only": True,
        },
    )


def _collaboration() -> dict:
    rules = collaboration.list_collaboration_rules()
    allowed = sum(1 for rule in rules if rule.get("allowed"))
    nodes = {
        item["agent_id"] for item in registry.list_agents()
    }
    for rule in rules:
        nodes.add(rule["requester_agent"])
        nodes.add(rule["target_agent"])
    relation_count = len({rule["relation"] for rule in rules} | {"call", "reference", "propose_change"})
    possible = len(nodes) * max(len(nodes) - 1, 0) * relation_count
    return _module(
        "collaboration",
        _status_with_data(has_data=bool(rules)),
        counts={
            "explicit_allowed": allowed,
            "explicit_rules": len(rules),
            "default_forbidden_estimate": max(possible - len(rules), 0),
            "runtime_rejections": None,
            "unknown_callers": None,
            "unknown_targets": None,
        },
        runtime_rejection_stats={
            "status": "unknown",
            "reason": "当前没有运行时协作拒绝日志查询接口",
        },
        semantics={
            "default_policy": "deny_by_default",
            "frontend_can_modify": False,
        },
    )


def _database_migration() -> dict:
    """Expose the in-process startup migration snapshot without doing DDL."""
    snapshot = get_init_db_result()
    raw_status = snapshot.get("status")
    if raw_status == "ok":
        status = "healthy"
        reason = "本进程已完成启动迁移"
    elif raw_status == "failed":
        status = "error"
        reason = "启动迁移失败，请查看日志"
    else:
        status = "unknown"
        reason = "当前没有迁移快照，请重启服务后确认"

    result = _module(
        "database_migration",
        status,
        updated_at=snapshot.get("initialized_at"),
        last_error=snapshot.get("error") if status == "error" else None,
        reason=reason,
        migration_status=raw_status or "unknown",
        initialized_at=snapshot.get("initialized_at"),
        backend=snapshot.get("backend"),
        database=snapshot.get("database"),
        sqlite_path_digest=snapshot.get("sqlite_path_digest"),
        knowledge=snapshot.get("migrations", {}).get("knowledge", {}),
        experience=snapshot.get("migrations", {}).get("experience", {}),
        semantics={
            "startup_only": True,
            "health_endpoint_runs_ddl": False,
            "requires_restart_to_confirm": status == "unknown",
        },
    )
    if status == "unknown":
        result["last_error"] = reason
    return result


def _registration_integrity() -> dict:
    """Expose read-only System Map registration drift checks."""
    result = integrity.check_system_map_integrity()
    status = result.get("status", "unknown")
    return _module(
        "registration_integrity",
        status,
        updated_at=result.get("checked_at"),
        last_error=(
            "System Map 完整性检查发现需要处理的问题"
            if status in {"error", "attention"} and result.get("issues")
            else None
        ),
        checked_at=result.get("checked_at"),
        summary=result.get("summary", {}),
        issues=result.get("issues", []),
        sources=result.get("sources", []),
        reason=(
            "未发现登记不一致" if status == "healthy"
            else "发现需要处理的问题" if status in {"error", "attention"}
            else "当前无法确认注册完整性"
        ),
    )


def get_governance_health() -> dict:
    """Return module-level read-only governance health and observable gaps."""
    module_loaders = [
        ("system_map", _system_map),
        ("knowledge", _knowledge),
        ("shadow", _shadow),
        ("experience_memory", _experience),
        ("rule_change_audit", _rules_audit),
        ("collaboration", _collaboration),
        ("database_migration", _database_migration),
        ("registration_integrity", _registration_integrity),
    ]
    modules = {
        name: _run_module(name, loader)
        for name, loader in module_loaders
    }
    statuses = [item["status"] for item in modules.values()]
    errors = [item for item in modules.values() if item["status"] == "error"]
    attention = [item for item in modules.values() if item["status"] == "attention"]
    unknown = [item for item in modules.values() if item["status"] == "unknown"]
    if errors:
        overall = "error"
    elif attention:
        overall = "attention"
    elif unknown:
        overall = "unknown"
    else:
        overall = "healthy"
    return {
        "status": overall,
        "complete": not errors and not unknown,
        "module_count": len(modules),
        "healthy_modules": statuses.count("healthy"),
        "attention_modules": statuses.count("attention"),
        "error_modules": statuses.count("error"),
        "unknown_modules": statuses.count("unknown"),
        "updated_at": _now(),
        "last_errors": [
            {"module": item["module"], "error": item["last_error"]}
            for item in [*errors, *attention]
            if item.get("last_error")
        ],
        "modules": modules,
    }
