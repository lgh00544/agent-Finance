"""后台任务队列测试：提交即返回 / 状态流转 / 失败与重试 / 保留上限裁剪"""
import time

from app.services import task_queue


def _wait_status(tid: str, target: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = task_queue.get(tid)
        if task and task["status"] == target:
            return task
        time.sleep(0.02)
    raise AssertionError(f"任务 {tid} 未在 {timeout}s 内到达 {target}，当前: "
                         f"{task_queue.get(tid) and task_queue.get(tid)['status']}")


def test_submit_returns_immediately():
    tid = task_queue.submit("test_ok", "测试任务", lambda p: 42)
    assert isinstance(tid, str) and len(tid) >= 8
    task = task_queue.get(tid)
    assert task["status"] in ("pending", "running", "done")
    assert task["kind"] == "test_ok"
    assert task["label"] == "测试任务"
    assert task["submitted_at"]
    assert "_fn" not in task  # 内部函数引用不外泄


def test_success_state_transition():
    tid = task_queue.submit("test_success", "成功任务", lambda p: {"a": 1})
    task = _wait_status(tid, "done")
    assert task["status"] == "done"
    assert task["result"] == {"a": 1}
    assert task["started_at"] and task["finished_at"]
    assert task["error"] is None


def test_failed_records_error():
    def _boom(params):
        raise RuntimeError("执行失败原因")

    tid = task_queue.submit("test_fail", "失败任务", _boom)
    task = _wait_status(tid, "failed")
    assert task["status"] == "failed"
    assert "执行失败原因" in task["error"]
    assert task["result"] is None


def test_params_passed_to_fn():
    tid = task_queue.submit("test_params", "参数任务", lambda p: p["x"] + p["y"], {"x": 10, "y": 5})
    task = _wait_status(tid, "done")
    assert task["result"] == 15


def test_retry_failed_task():
    calls = {"n": 0}

    def _flaky(params):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("首次失败")
        return "ok"

    tid = task_queue.submit("test_retry", "重试任务", _flaky)
    _wait_status(tid, "failed")
    assert task_queue.retry(tid) is True
    task = _wait_status(tid, "done")
    assert task["result"] == "ok"
    assert calls["n"] == 2
    assert task["task_id"] == tid  # 复用原 task_id


def test_retry_rejects_running_or_done():
    tid = task_queue.submit("test_retry_ok", "不可重试", lambda p: 1)
    _wait_status(tid, "done")
    assert task_queue.retry(tid) is False  # done 不可重试
    assert task_queue.retry("not-exist-id") is False


def test_recent_tasks_ordered():
    ids = [task_queue.submit("test_recent", f"任务{i}", lambda p: p["i"], {"i": i})
           for i in range(5)]
    recent = task_queue.recent_tasks(limit=3)
    assert len(recent) == 3
    assert recent[0]["task_id"] == ids[-1]  # 最新在前


def test_trim_keeps_window():
    for i in range(task_queue._KEEP + 10):
        task_queue.submit("test_trim", f"裁剪{i}", lambda p: p["i"], {"i": i})
    assert len(task_queue.recent_tasks(limit=task_queue._KEEP * 2)) <= task_queue._KEEP
