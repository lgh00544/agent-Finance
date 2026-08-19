"""首页看板聚合接口（GET /api/dashboard）：一次请求返回全部模块数据

【刚性代码逻辑】只做数据组装与并行调度，不含任何研判。
各模块独立执行（ThreadPoolExecutor 并行，探活等慢操作不再串行阻塞），
单模块失败仅标注 error，不影响其余模块与整体响应。
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db import repo

logger = logging.getLogger(__name__)

_MAX_WORKERS = 8


def _system_status() -> dict:
    from app.services import status as status_service

    return status_service.system_status()


def _llm_stats() -> dict:
    from app.services import llm_stats as llm_stats_service

    return llm_stats_service.snapshot()


def _datasource_stats() -> dict:
    from app.services import datasource_stats as datasource_stats_service

    return datasource_stats_service.snapshot()


def _agent_suggestions() -> list:
    suggestions = repo.get_agent_suggestions(status="pending")
    return [{"id": s.id, "review_id": s.review_id, "target_agent": s.target_agent,
             "target_kind": s.target_kind, "rule_name": s.rule_name,
             "current_value": s.current_value, "suggested_value": s.suggested_value,
             "reason": s.reason, "evidence": s.evidence, "status": s.status,
             "created_at": str(s.created_at)} for s in suggestions]


def _module_tradeable_view() -> dict:
    """当日可建仓判定视图（只读：只取已落库判定，不触发 ensure_if_missing 懒补算；
    补算留给候选池页/每日挖掘，首页首屏零额外计算）"""
    trade_date = time.strftime("%Y-%m-%d")
    try:
        items = repo.list_candidate_tradeable(trade_date, limit=50)
        return {"date": trade_date,
                "count": sum(1 for i in items if i.get("is_tradeable")),
                "total": len(items), "items": items}
    except Exception:  # noqa: BLE001 失败返回空 items 不阻塞聚合整体
        return {"date": trade_date, "count": 0, "items": [], "total": 0}


def _module(fn):
    """模块执行器：失败仅标注 error，不中断其他模块"""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 单模块失败不影响聚合接口
        logger.warning("看板模块执行失败: %s", exc)
        return {"error": f"{type(exc).__name__}"}


def build_dashboard() -> dict:
    """并行聚合首页全部模块（系统状态/LLM统计/市况/持仓与信号/候选评分方案/复盘与建议）"""
    modules = {
        "system": _system_status,
        "llm_stats": _llm_stats,
        "datasource_stats": _datasource_stats,
        "market_condition": repo.get_latest_market_condition,
        "holdings": lambda: repo.list_holdings(status="holding"),
        "alerts": lambda: repo.list_alerts(limit=100),
        "candidates": lambda: repo.list_candidates(limit=5),
        "candidate_tradeable": _module_tradeable_view,
        "scores": lambda: repo.list_scores(limit=200),
        "plans": lambda: repo.list_plans(limit=3),
        "reviews": lambda: repo.list_reviews(limit=3),
        "pending_suggestions": _agent_suggestions,
    }
    results: dict = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_module, fn): name for name, fn in modules.items()}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "modules": results}
