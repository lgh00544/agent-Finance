"""经验沉淀闭环 · 定时 Worker（离线识别、限流、分层分流）

worker_run() 主流程：
1. watchdog 前置：processing 超 2h 复位 pending（防 Worker 崩溃卡死队列）；
2. 积压门：非 force（30min 探针）且积压 < 阈值 → 跳过；force（02:00 主跑）直接执行；
3. task_queue 防并发：experience 任务活跃则推迟；
4. 批次原子认领 → 逐条 LLM 抽取（llm_call_json 内置重试）→ 分层分流 → release_pending；
5. 批间 sleep 限流（配置 worker_sleep_sec）。

热路径零分析（pending 单行写入），识别全部离线在此 Worker 完成。
"""
import json
import logging
import time

from pydantic import BaseModel

from app.agents.schemas import ExperienceDraft, RouteConflict
from app.core.config import settings
from app.db import repo
from app.llm.structured import ModelLevel, llm_call_json
from app.services import llm_stats
from agent_prompts import experience_prompt

logger = logging.getLogger(__name__)

# 设置默认值（M5 前端可改 experience_config 表热加载覆盖，无需重启）
DEFAULTS = {
    "worker_cron": "0 2 * * *",       # 调度 cron（默认每日 02:00）
    "worker_model": "flash",           # LIGHT=flash 轻量模型
    "confidence_threshold": "0.85",    # 自动合并置信阈值
    "auto_merge_enabled": "1",         # 自动合并总开关（0 时全走 Digest/M3）
    "worker_sleep_sec": "3",           # 批间限流
    "digest_backlog_threshold": "50",  # 积压触发阈值
    "memory_curator_enabled": "1",     # Memory Curator 总开关
    "memory_retention_days": "90",     # 低置信旧记忆保留天数
    "memory_low_confidence_threshold": "0.55",
    "memory_stale_hit_threshold": "0",
    "memory_duplicate_similarity": "0.86",
}


def _cfg(key: str) -> str:
    """读配置（DB experience_config 覆盖优先，无则默认）"""
    val = repo.get_config(key)
    if val is None or str(val).strip() == "":
        val = DEFAULTS.get(key, "")
    return str(val)


def _cfg_float(key: str) -> float:
    try:
        return float(_cfg(key))
    except (TypeError, ValueError):
        return float(DEFAULTS.get(key, "0"))


def _cfg_int(key: str) -> int:
    try:
        return int(float(_cfg(key)))
    except (TypeError, ValueError):
        return int(float(DEFAULTS.get(key, "0")))


def _cfg_bool(key: str) -> bool:
    return str(_cfg(key)).lower() in ("1", "true", "yes")


def _split_tags(raw) -> set:
    """解析经验 tags 字符串（逗号/空格分隔 JSON 数组）为集合"""
    if not raw:
        return set()
    if isinstance(raw, (list, tuple)):
        return {str(t).strip() for t in raw if str(t).strip()}
    txt = str(raw).replace('"', "").strip()
    if txt.startswith("[") and txt.endswith("]"):
        try:
            arr = json.loads(txt)
            return {str(t).strip() for t in arr if str(t).strip()}
        except (json.JSONDecodeError, TypeError):
            pass
    return {t.strip() for t in txt.replace(",", " ").split() if t.strip()}


def _llm_extract(system: str, user: str, schema) -> BaseModel:
    """LLM 结构化抽取统一入口（提供方可配置，默认 minimax 失败自动降级 deepseek flash）。

    - provider=minimax：调 MiniMaxClient().chat_text() → schema.model_validate_json(content)；
      任何异常/校验失败/空响应 → 降级 llm_call_json(LIGHT) 重试一次；
    - provider=deepseek：保持原 llm_call_json(LIGHT) 行为（回归零差异）。
    - MiniMax 成功路径记录 MiniMax-M3 的 usage 成本（缺 usage 记 0）。
    """
    if settings.experience_worker_provider == "minimax":
        try:
            from app.services.multimodal import MiniMaxClient
            content, usage = MiniMaxClient().chat_text(system, user)
            if content and content.strip():
                parsed = schema.model_validate_json(content)
                llm_stats.record(
                    "MiniMax-M3",
                    int(usage.get("prompt_cache_hit_tokens") or 0),
                    int(usage.get("prompt_tokens") or 0),
                    int(usage.get("completion_tokens") or 0),
                )
                return parsed
            logger.warning("MiniMax 抽取空响应，降级 deepseek flash")
        except Exception as exc:  # noqa: BLE001 MiniMax 无密钥/失败/校验失败 → 降级
            logger.warning("MiniMax 抽取失败（降级 deepseek flash）: %s", exc)
    return llm_call_json(system, user, schema, model_level=ModelLevel.LIGHT)


def route_draft(draft: ExperienceDraft, pending_id: int) -> dict:
    """分层分流（四态落库）：
    - impact=high → pending_review（高影响硬闸门，M3 两步确认，无自动绕过）；
    - impact=low 且 confidence≥阈值 且无冲突 且自动合并开关开 → active + auto_merged=1 + review_log(auto)；
    - 其余（低置信/冲突/开关关）→ pending_review（Digest 批量过目）。
    返回分流结果 dict（供日志/测试断言）。"""
    if not draft.worth or not draft.title.strip():
        return {"status": "skip", "reason": "worth=false 或标题为空，不沉淀"}

    threshold = _cfg_float("confidence_threshold")
    auto_merge_on = _cfg_bool("auto_merge_enabled")

    if draft.impact == "high":
        eid = repo.insert_experience(draft.title, draft.body, draft.stage, draft.tags,
                                     "high", draft.confidence, auto_merged=0,
                                     source_pending_id=pending_id, status="pending_review")
        return {"status": "pending_review", "eid": eid, "reason": "impact=high 硬闸门（M3）"}

    if auto_merge_on and draft.confidence >= threshold:
        conflict = _conflict_check(draft)
        if not conflict["conflict"]:
            eid = repo.insert_experience(draft.title, draft.body, draft.stage, draft.tags,
                                         "low", draft.confidence, auto_merged=1,
                                         source_pending_id=pending_id, status="active")
            repo.write_review_log(eid, "auto_merge", "auto",
                                  note=f"conf={draft.confidence:.2f}")
            return {"status": "active", "eid": eid, "auto_merged": 1,
                    "reason": "低影响自动合并（conf≥阈值且无冲突）"}
        # 冲突 → Digest（落 pending_review 行，M2 可人工过目/驳回）
        eid = repo.insert_experience(draft.title, draft.body, draft.stage, draft.tags,
                                     draft.impact, draft.confidence, auto_merged=0,
                                     source_pending_id=pending_id, status="pending_review")
        return {"status": "pending_review", "eid": eid,
                "reason": f"冲突（{conflict['reason']}），转 Digest 人工过目"}

    eid = repo.insert_experience(draft.title, draft.body, draft.stage, draft.tags,
                                 draft.impact, draft.confidence, auto_merged=0,
                                 source_pending_id=pending_id, status="pending_review")
    return {"status": "pending_review", "eid": eid, "reason": "Digest 待审核（低置信/开关关）"}


def _conflict_check(draft: ExperienceDraft) -> dict:
    """两段式冲突判定：
    ① 代码层：同 stage 的 active 经验，tags 有交集的优先（候选过滤）；
    ② LLM 层：ROUTE_PROMPT 附候选列表，判定结论是否相反（代码不做语义判断）。
    LLM 判定失败视为无冲突（auto_merged 项可回滚兜底），记录告警。"""
    cands = repo.search_experience(stage=draft.stage, k=5)
    if not cands:
        return {"conflict": False, "reason": "无同阶段候选经验"}
    draft_tags = _split_tags(draft.tags)
    if draft_tags:
        overlap = [c for c in cands if draft_tags & _split_tags(c.get("tags"))]
        if overlap:
            cands = overlap[:5]
    user = json.dumps({
        "new_draft": {"title": draft.title, "body": (draft.body or "")[:300],
                      "stage": draft.stage},
        "candidates": [{"id": c["id"], "title": c["title"],
                        "body": (c["body"] or "")[:200]} for c in cands[:5]],
    }, ensure_ascii=False)
    try:
        res = _llm_extract(experience_prompt.ROUTE_PROMPT, user, RouteConflict)
        return {"conflict": res.conflict, "conflicting_ids": res.conflicting_ids,
                "reason": res.reason}
    except Exception as exc:  # noqa: BLE001 冲突判定失败不阻断自动合并（可回滚兜底）
        logger.warning("冲突判定 LLM 失败（视为无冲突）: %s", exc)
        return {"conflict": False, "reason": "冲突判定失败，视为无冲突"}


def _process_item(item: dict) -> None:
    """逐条：LLM 抽取（llm_call_json 内置重试/降级）→ worth 判断 → 分层分流 → release_pending"""
    pending_id = item["id"]
    user = json.dumps({"task_id": item["task_id"], "stage": item["stage"],
                       "summary": item["summary"], "artifacts_ref": item["artifacts_ref"]},
                      ensure_ascii=False)
    try:
        draft = _llm_extract(experience_prompt.EXTRACT_SYSTEM, user, ExperienceDraft)
    except Exception as exc:  # noqa: BLE001 抽取失败标 done+error，不残留 processing
        logger.warning("经验抽取失败 pending=%s: %s", pending_id, exc)
        repo.release_pending(pending_id, error=f"extract_failed: {exc}")
        return
    if not draft.worth:
        repo.release_pending(pending_id, error=None)  # 无经验，正常完成
        return
    result = route_draft(draft, pending_id)
    logger.info("经验分流 pending=%s → %s（%s）", pending_id, result["status"],
                result.get("reason", ""))
    repo.release_pending(pending_id, error=None)


def worker_run(force: bool = False) -> dict:
    """Worker 主流程（供调度/手动触发；force=True 时忽略积压门直接执行）"""
    from app.services import task_queue

    watchdog_reset = repo.watchdog_reset_stale_processing(older_than_hours=2.0)
    backlog = repo.pending_backlog_count()
    threshold = _cfg_int("digest_backlog_threshold")
    if not force and backlog < threshold:
        logger.info("经验 Worker 跳过：积压 %s < 阈值 %s", backlog, threshold)
        return {"skipped": True, "reason": "backlog_low", "backlog": backlog,
                "watchdog_reset": watchdog_reset}
    if task_queue.has_active("experience"):
        logger.info("经验 Worker 推迟：experience 任务活跃")
        return {"skipped": True, "reason": "task_busy", "backlog": backlog,
                "watchdog_reset": watchdog_reset}

    run_id = repo.start_worker_run()
    claimed = repo.claim_pending_batch(batch_size=20)
    processed = 0
    err_count = 0
    sleep_sec = _cfg_float("worker_sleep_sec")
    try:
        for item in claimed:
            try:
                _process_item(item)
                processed += 1
            except Exception as exc:  # noqa: BLE001 单条异常不中断批次
                err_count += 1
                logger.error("经验处理异常 pending=%s: %s", item.get("id"), exc)
                repo.release_pending(item["id"], error=f"process_error: {exc}")
            if sleep_sec > 0:
                time.sleep(sleep_sec)
        repo.finish_worker_run(run_id, processed, "success")
        return {"run_id": run_id, "processed": processed, "errors": err_count,
                "claimed": len(claimed), "watchdog_reset": watchdog_reset, "skipped": False}
    except Exception as exc:  # noqa: BLE001
        repo.finish_worker_run(run_id, processed, "failed", error=str(exc))
        raise
