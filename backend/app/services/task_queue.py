"""轻量后台任务队列：手动耗时任务异步化（提交即返回，不阻塞页面操作）。

- 线程池串行执行（max_workers=1，防外部接口/LLM 限流，单人使用足够）；
- 内存任务表：状态流转 pending → running → done/failed/canceled；
  字段：task_id/kind/label/params/status/attempt_id/cancel_requested/
  submitted_at/started_at/finished_at/error/result；
- 保留最近 _KEEP 条记录，超出自动裁剪；
- failed 任务支持 retry（重置状态重新入队，复用原 task_id）；
- 卡死终结：daily_pipeline / monitor_all 等长任务超时上限（_TIMEOUT_SECONDS），
  超时强制 failed(timeout) 并重建执行队列释放阻塞，新任务可立即提交；
- 手动取消：cancel(tid) 可终止 pending/running 任务并释放队列；
- 进程内运行（dev/prod 均为单进程 uvicorn），进程重启后任务表清空（本地工具可接受）。

【刚性代码逻辑】只做调度封装与状态管理，任务执行体由调用方（业务模块）提供，
本模块不包含任何市场判断。
"""
import logging
import json
import os
import socket
import threading
import time
import uuid
from contextvars import ContextVar, copy_context
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

_KEEP = 30  # 保留最近任务条数
_TIMEOUT_KINDS = {"daily_pipeline", "monitor_all"}  # 长任务：超时终结保护（防卡死占锁）
_TIMEOUT_SECONDS = 35 * 60  # 超时上限 35 分钟（方案 B：30~40 分钟区间）

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bg-task")
_lock = threading.Lock()
_publish_fence = threading.Lock()
_tasks: dict[str, dict] = {}
_seq = 0  # 提交序号（秒级时间戳相同场景下保证顺序稳定）
_instance_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
_SHARED_TASK_TTL_SECONDS = 24 * 3600
_SHARED_RECENT_LIMIT = 200
_CONTROL_TTL_SECONDS = 3600
_current_attempt: ContextVar[tuple[str, str] | None] = ContextVar(
    "task_queue_current_attempt", default=None)
_control_watchers: dict[str, threading.Event] = {}


class AttemptInvalidated(RuntimeError):
    """当前后台任务 attempt 已取消、超时或被重试，禁止继续发布业务结果。"""


def _attempt_active(attempt: tuple[str, str] | None) -> bool:
    if attempt is None:
        return True
    tid, attempt_id = attempt
    with _lock:
        task = _tasks.get(tid)
        return bool(task and task["attempt_id"] == attempt_id
                    and task["status"] == "running"
                    and not task["cancel_requested"])


def ensure_attempt_active() -> None:
    """任务上下文存在时确认本次 attempt 仍有业务发布资格。

    同步调用没有 attempt 上下文，保持原有 repo 直调行为。
    """
    if not _attempt_active(_current_attempt.get()):
        raise AttemptInvalidated("后台任务 attempt 已失效，放弃业务写入")


def submit_with_attempt_context(executor: Any, fn: Callable[..., Any],
                                *args: Any, **kwargs: Any):
    """向子线程提交工作并传播当前后台任务 attempt 上下文。

    ``ContextVar`` 默认按线程隔离，ThreadPoolExecutor 新线程不会继承
    ``_current_attempt``。每次提交都复制一个独立 Context，避免多个并发 future
    复用同一个 Context；取消、超时或重试后，子线程中的 guarded_commit 仍能
    通过 attempt_id 栅栏拒绝旧业务写入。同步调用没有 attempt 时行为不变。
    """
    ctx = copy_context()
    return executor.submit(ctx.run, fn, *args, **kwargs)


def guarded_commit(db) -> None:
    """在取消/超时栅栏内提交，确保取消返回后不再产生核心业务写入。"""
    with _publish_fence:
        try:
            ensure_attempt_active()
            db.commit()
        except AttemptInvalidated:
            db.rollback()
            raise


def _watchdog_loop() -> None:
    """守护线程：周期扫描长任务是否超时，超时强制终结并释放执行队列。
    仅标记状态+换队列；卡死线程留在旧池后台耗（Python 无法强杀线程），
    其最终跑完写库不影响（候选池落库是好事），但不再阻塞新任务。"""
    while True:
        time.sleep(30)
        with _publish_fence:
            with _lock:
                now = time.monotonic()
                for task in list(_tasks.values()):
                    started = task.get("_started_mono")
                    if (task["status"] == "running" and task["kind"] in _TIMEOUT_KINDS
                            and started and now - started > _TIMEOUT_SECONDS):
                        logger.warning("后台任务 %s(%s) 超时 %d 分钟，强制终结并释放任务队列",
                                       task["kind"], task["task_id"], _TIMEOUT_SECONDS // 60)
                        task["status"] = "failed"
                        task["cancel_requested"] = True
                        task["error"] = f"timeout after {_TIMEOUT_SECONDS // 60} minutes"
                        task["finished_at"] = _now()
                        _publish_task_locked(task)
                        _replace_executor_locked()


threading.Thread(target=_watchdog_loop, name="bg-task-watchdog", daemon=True).start()


def _replace_executor_locked() -> None:
    """丢弃旧单线程池并新建（调用方需持有 _lock）：
    卡死线程留在旧池后台耗不再占队列，排队中的 pending 任务重新入队新池。"""
    global _executor
    _executor.shutdown(wait=False)
    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bg-task")
    for tid, task in list(_tasks.items()):
        if task["status"] == "pending":
            _executor.submit(_run, tid)


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
            "attempt_id": uuid.uuid4().hex[:12], "cancel_requested": False,
            "canceled_at": None,
            "submitted_at": _now(), "started_at": None, "finished_at": None,
            "error": None, "result": None, "instance_id": _instance_id, "_fn": fn,
        }
        _tasks[tid] = task
        _trim_locked()
        _publish_task_locked(task)
        if _shared_enabled():
            stop_event = threading.Event()
            _control_watchers[tid] = stop_event
            threading.Thread(target=_remote_control_loop, args=(tid, stop_event),
                             name=f"task-control-{tid}", daemon=True).start()
    _executor.submit(_run, tid)
    return tid


def _run(tid: str) -> None:
    with _lock:
        task = _tasks.get(tid)
        if task is None or task["status"] != "pending" or task["cancel_requested"]:
            return
        task["status"] = "running"
        task["started_at"] = _now()
        task["_started_mono"] = time.monotonic()  # 超时终结基准（watchdog 用）
        _publish_task_locked(task)
        attempt_id = task["attempt_id"]
        fn = task["_fn"]
        params = task["params"]
    token = _current_attempt.set((tid, attempt_id))
    user_tokens = None
    try:
        user_id = params.get("user_id") if isinstance(params, dict) else None
        if user_id is not None:
            from app.core.auth import set_user_context
            user_tokens = set_user_context(user_id, params.get("user_role"))
        result = fn(params)  # 执行函数统一签名 fn(params: dict)
        with _lock:
            current = _tasks.get(tid)
            # 取消、超时或重试已经撤销本次 attempt 的发布资格，旧线程只能自然结束。
            if (current is not task or current["attempt_id"] != attempt_id
                    or current["status"] != "running"
                    or current["cancel_requested"]):
                return
            current["status"] = "done"
            current["result"] = _safe_result(result)
            _publish_task_locked(current)
    except AttemptInvalidated as exc:
        logger.warning("后台任务 %s(%s) attempt 已失效，放弃发布结果: %s",
                       task["kind"], tid, exc)
    except Exception as exc:  # noqa: BLE001 任务级整体容错，失败原因随任务返回供前端展示
        with _lock:
            current = _tasks.get(tid)
            if (current is task and current["attempt_id"] == attempt_id
                    and current["status"] == "running"
                    and not current["cancel_requested"]):
                current["status"] = "failed"
                current["error"] = str(exc)
                _publish_task_locked(current)
        logger.error("后台任务 %s(%s) 失败: %s", task["kind"], tid, exc)
    finally:
        with _lock:
            current_state = _tasks.get(tid, {}).get("status")
        if current_state in ("done", "canceled"):
            watcher = _control_watchers.pop(tid, None)
            if watcher is not None:
                watcher.set()
        if user_tokens is not None:
            from app.core.auth import reset_user_context
            reset_user_context(user_tokens)
        _current_attempt.reset(token)
        with _lock:
            current = _tasks.get(tid)
            if (current is task and current["attempt_id"] == attempt_id
                    and current["finished_at"] is None
                    and current["status"] in ("done", "failed", "canceled")):
                current["finished_at"] = _now()
                _publish_task_locked(current)


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


def _visible(task: dict, user_id: int | None, is_admin: bool) -> bool:
    """多人模式下只允许任务所有者或管理员访问任务记录。"""
    if not settings.multi_user_enabled:
        return True
    if is_admin:
        return True
    owner_id = (task.get("params") or {}).get("user_id")
    return user_id is not None and owner_id == user_id


def _shared_enabled() -> bool:
    return settings.multi_user_enabled and settings.cache_backend == "redis"


def _task_key(tid: str) -> str:
    return f"tasks:item:{tid}"


def _control_key(tid: str) -> str:
    return f"tasks:control:{tid}"


def _recent_key() -> str:
    return "tasks:recent"


def _publish_task_locked(task: dict) -> None:
    if not _shared_enabled():
        return
    public = _public(task)
    try:
        cache.set(_task_key(public["task_id"]),
                  json.dumps(public, ensure_ascii=False, default=str),
                  _SHARED_TASK_TTL_SECONDS)
        raw = cache.get(_recent_key())
        ids = json.loads(raw) if raw else []
        ids = [public["task_id"]] + [tid for tid in ids if tid != public["task_id"]]
        cache.set(_recent_key(), json.dumps(ids[:_SHARED_RECENT_LIMIT]),
                  _SHARED_TASK_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 状态镜像失败不影响本实例任务执行
        logger.warning("共享任务状态写入失败: %s", exc)


def _load_shared_task(tid: str) -> dict | None:
    if not _shared_enabled():
        return None
    try:
        raw = cache.get(_task_key(tid))
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("共享任务状态读取失败: %s", exc)
        return None


def _load_shared_recent() -> list[dict]:
    if not _shared_enabled():
        return []
    try:
        raw = cache.get(_recent_key())
        ids = json.loads(raw) if raw else []
        rows: list[dict] = []
        for tid in ids[:_SHARED_RECENT_LIMIT]:
            row = _load_shared_task(str(tid))
            if row:
                rows.append(row)
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("共享任务列表读取失败: %s", exc)
        return []


def _send_remote_control(tid: str, action: str, user_id: int | None,
                         is_admin: bool) -> bool:
    if not _shared_enabled():
        return False
    task = _load_shared_task(tid)
    if not task or not _visible(task, user_id, is_admin):
        return False
    try:
        cache.set(_control_key(tid), json.dumps({"action": action, "requested_by": user_id}),
                  _CONTROL_TTL_SECONDS)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("远程任务控制写入失败 tid=%s: %s", tid, exc)
        return False


def _remote_control_loop(tid: str, stop_event: threading.Event) -> None:
    while True:
        if stop_event.wait(0.5):
            return
        if not _shared_enabled():
            return
        try:
            raw = cache.get(_control_key(tid))
            if not raw:
                continue
            cache.delete(_control_key(tid))
            action = json.loads(raw).get("action")
        except Exception:
            continue
        with _publish_fence:
            with _lock:
                task = _tasks.get(tid)
                if not task:
                    return
                if task["status"] in ("done", "canceled"):
                    return
                if action == "cancel" and task["status"] in ("pending", "running"):
                    task["status"] = "canceled"
                    task["cancel_requested"] = True
                    task["error"] = "canceled by user"
                    task["canceled_at"] = _now()
                    task["finished_at"] = _now()
                    _publish_task_locked(task)
                    if task.get("_started_mono"):
                        _replace_executor_locked()
                    continue
                if action == "retry" and task["status"] == "failed":
                    task["status"] = "pending"
                    task["attempt_id"] = uuid.uuid4().hex[:12]
                    task["cancel_requested"] = False
                    task["error"] = None
                    task["result"] = None
                    task["started_at"] = None
                    task["finished_at"] = None
                    task["submitted_at"] = _now()
                    _publish_task_locked(task)
                    _executor.submit(_run, tid)
                    continue


def get(tid: str, user_id: int | None = None, *, is_admin: bool = False) -> dict | None:
    """任务详情（去掉内部 _fn 引用）"""
    with _lock:
        task = _tasks.get(tid)
        if task and _visible(task, user_id, is_admin):
            return _public(task)
    shared = _load_shared_task(tid)
    return shared if shared and _visible(shared, user_id, is_admin) else None


def recent_tasks(limit: int = 10, user_id: int | None = None,
                 *, is_admin: bool = False) -> list[dict]:
    """最近任务（提交序号倒序 = 最新在前，供页面顶部任务状态区轮询）"""
    with _lock:
        local = [_public(t) for t in _tasks.values()]
    merged: dict[str, dict] = {}
    for task in _load_shared_recent() + local:
        if _visible(task, user_id, is_admin):
            merged[task["task_id"]] = task
    rows = sorted(merged.values(),
                  key=lambda t: (str(t.get("submitted_at") or ""), int(t.get("seq") or 0)),
                  reverse=True)
    return rows[:limit]


def retry(tid: str, user_id: int | None = None, *, is_admin: bool = False) -> bool:
    """失败任务重试：重置状态重新入队（复用原 task_id 与执行函数）"""
    with _lock:
        task = _tasks.get(tid)
        if task is None:
            return _send_remote_control(tid, "retry", user_id, is_admin)
        if not _visible(task, user_id, is_admin) or task["status"] != "failed":
            return False
        task["status"] = "pending"
        task["attempt_id"] = uuid.uuid4().hex[:12]
        task["cancel_requested"] = False
        task["canceled_at"] = None
        task["error"] = None
        task["result"] = None
        task["started_at"] = None
        task["finished_at"] = None
        task["submitted_at"] = _now()
        _publish_task_locked(task)
    _executor.submit(_run, tid)
    return True


def has_active(kind: str, user_id: int | None = None, *, is_admin: bool = False) -> bool:
    """是否存在未结束（pending/running）的同类型任务：供重复触发防护"""
    with _lock:
        if any(t["kind"] == kind and t["status"] in ("pending", "running")
               and _visible(t, user_id, is_admin) for t in _tasks.values()):
            return True
    return any(t.get("kind") == kind and t.get("status") in ("pending", "running")
               and _visible(t, user_id, is_admin) for t in _load_shared_recent())


def cancel(tid: str, user_id: int | None = None, *, is_admin: bool = False) -> bool:
    """手动取消卡死任务：仅 pending/running 可取消（failed/done/canceled 不可）。
    取消后释放任务队列（正在执行的线程无法强杀，留在旧池后台耗，
    但队列立即腾出，新任务可提交；旧线程失去本次 attempt 的发布资格。"""
    with _publish_fence:
        with _lock:
            task = _tasks.get(tid)
            if task is None:
                return _send_remote_control(tid, "cancel", user_id, is_admin)
            if (not _visible(task, user_id, is_admin)
                    or task["status"] not in ("pending", "running")):
                return False
            task["status"] = "canceled"
            task["cancel_requested"] = True
            task["error"] = "canceled by user"
            task["canceled_at"] = _now()
            task["finished_at"] = _now()
            _publish_task_locked(task)
            if task.get("_started_mono"):
                _replace_executor_locked()  # 正在执行：丢弃旧池，释放被占的单线程队列
    logger.warning("后台任务 %s(%s) 已被手动取消", task["kind"], tid)
    return True


def _public(task: dict) -> dict:
    return {k: v for k, v in task.items() if k not in ("_fn", "_started_mono")}


def _trim_locked() -> None:
    """保留最近 _KEEP 条（调用方需持有 _lock）"""
    if len(_tasks) <= _KEEP:
        return
    for tid in sorted(_tasks, key=lambda t: _tasks[t]["seq"])[: len(_tasks) - _KEEP]:
        del _tasks[tid]
