"""轻量后台任务队列：手动耗时任务异步化（提交即返回，不阻塞页面操作）。

- 线程池串行执行（max_workers=1，防外部接口/LLM 限流，单人使用足够）；
- 内存任务表：状态流转 pending → running → done/failed；
  字段：task_id/kind/label/params/status/submitted_at/started_at/finished_at/error/result；
- 保留最近 _KEEP 条记录，超出自动裁剪；
- failed 任务支持 retry（重置状态重新入队，复用原 task_id）；
- 进程内运行（dev/prod 均为单进程 uvicorn），进程重启后任务表清空（本地工具可接受）。

【刚性代码逻辑】只做调度封装与状态管理，任务执行体由调用方（业务模块）提供，
本模块不包含任何市场判断。
"""
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

_KEEP = 30  # 保留最近任务条数

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bg-task")
_lock = threading.Lock()
_tasks: dict[str, dict] = {}
_seq = 0  # 提交序号（秒级时间戳相同场景下保证顺序稳定）


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def submit(kind: str, label: str, fn: Callable, params: dict | None = None) -> str:
    """提交任务立即返回 task_id；fn 为实际执行函数，统一签名 fn(params: dict)"""
    global _seq
    tid = uuid.uuid4().hex[:12]
    with _lock:
        _seq += 1
        task: dict[str, Any] = {
            "task_id": tid, "kind": kind, "label": label, "seq": _seq,
            "params": dict(params or {}), "status": "pending",
            "submitted_at": _now(), "started_at": None, "finished_at": None,
            "error": None, "result": None, "_fn": fn,
        }
        _tasks[tid] = task
        _trim_locked()
    _executor.submit(_run, tid)
    return tid


def _run(tid: str) -> None:
    task = _tasks.get(tid)
    if task is None:
        return
    task["status"] = "running"
    task["started_at"] = _now()
    try:
        result = task["_fn"](task["params"])  # 执行函数统一签名 fn(params: dict)
        task["status"] = "done"
        task["result"] = _safe_result(result)
    except Exception as exc:  # noqa: BLE001 任务级整体容错，失败原因随任务返回供前端展示
        task["status"] = "failed"
        task["error"] = str(exc)
        logger.error("后台任务 %s(%s) 失败: %s", task["kind"], tid, exc)
    finally:
        task["finished_at"] = _now()


def _safe_result(result: Any) -> Any:
    """结果只保留 JSON 安全的摘要（失败/异常时为空），不放大内存占用。
    dict/list 递归保留嵌套结构（如对话回答中的 announcement 结构化数据）；
    非 JSON 类型收窄为字符串摘要。"""
    if isinstance(result, dict):
        return {k: _safe_result(v) for k, v in result.items()}
    if isinstance(result, list):
        return [_safe_result(v) for v in result[:100]]
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    return str(result)[:200]


def get(tid: str) -> dict | None:
    """任务详情（去掉内部 _fn 引用）"""
    with _lock:
        task = _tasks.get(tid)
        return _public(task) if task else None


def recent_tasks(limit: int = 10) -> list[dict]:
    """最近任务（提交序号倒序 = 最新在前，供页面顶部任务状态区轮询）"""
    with _lock:
        items = [t for t in sorted(_tasks.values(), key=lambda t: t["seq"], reverse=True)[:limit]]
        return [_public(t) for t in items]


def retry(tid: str) -> bool:
    """失败任务重试：重置状态重新入队（复用原 task_id 与执行函数）"""
    with _lock:
        task = _tasks.get(tid)
        if task is None or task["status"] != "failed":
            return False
        task["status"] = "pending"
        task["error"] = None
        task["result"] = None
        task["started_at"] = None
        task["finished_at"] = None
        task["submitted_at"] = _now()
    _executor.submit(_run, tid)
    return True


def has_active(kind: str) -> bool:
    """是否存在未结束（pending/running）的同类型任务：供重复触发防护"""
    with _lock:
        return any(t["kind"] == kind and t["status"] in ("pending", "running")
                   for t in _tasks.values())


def _public(task: dict) -> dict:
    return {k: v for k, v in task.items() if k != "_fn"}


def _trim_locked() -> None:
    """保留最近 _KEEP 条（调用方需持有 _lock）"""
    if len(_tasks) <= _KEEP:
        return
    for tid in sorted(_tasks, key=lambda t: _tasks[t]["seq"])[: len(_tasks) - _KEEP]:
        del _tasks[tid]
