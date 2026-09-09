"""手动挖掘链路修复配套测试：重复触发防护 / 强制刷新缓存 / 候选日期按需查询 / 缓存防穿透"""
import threading
import time

import pytest
from fastapi import HTTPException


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from app.db.session import init_db
    init_db()


# ================= 重复触发防护 =================

def test_has_active_true_while_running():
    """任务执行期间 has_active(kind)=True，提交同类型任务应被拒绝"""
    from app.services import task_queue

    tid = task_queue.submit("guard_probe", "防重探测",
                            lambda p: time.sleep(0.4), {"v": 1})
    try:
        assert task_queue.has_active("guard_probe") is True
        assert task_queue.has_active("other_kind") is False
    finally:
        # 等待执行完毕，避免残留占用队列
        for _ in range(50):
            if task_queue.get(tid)["status"] not in ("pending", "running"):
                break
            time.sleep(0.05)


def test_submit_rejects_active_kind(monkeypatch):
    """_submit_task 对正在执行的任务类型抛 409（重复触发防护）"""
    from app.api.routes import _submit_task

    monkeypatch.setattr("app.api.routes.task_queue.has_active", lambda kind: True)
    with pytest.raises(HTTPException) as exc:
        _submit_task("daily_pipeline", {})
    assert exc.value.status_code == 409
    assert "正在执行" in exc.value.detail


# ================= 手动触发强制刷新当日 LLM 缓存 =================

def test_manual_pipeline_invalidates_daily_cache(monkeypatch):
    """手动触发每日挖掘：先失效当日初选/终选/市况缓存，再真实执行全链路"""
    import time as _t

    from app.cache import cache
    from app.api.routes import _task_daily_pipeline
    from app.graph import router as graph_router

    date_key = _t.strftime("%Y-%m-%d")
    cache.set(f"shortlist:v2:{date_key}", "x", 86400)
    cache.set(f"final:v2:{date_key}", "x", 86400)
    cache.set(f"market:v2:{date_key}", "x", 86400)
    cache.set(f"shortlist:v2:2099-01-01", "keep", 86400)  # 非当日缓存不受影响

    calls: list[str] = []

    def _fake_pipeline():
        calls.append("run")
        return {"candidates": 3, "scored": 2}

    monkeypatch.setattr(graph_router, "run_daily_pipeline", _fake_pipeline)
    result = _task_daily_pipeline({})

    assert calls == ["run"], "必须真实执行全链路（不得命中缓存）"
    assert result == {"candidates": 3, "scored": 2, "date": date_key}
    assert cache.get(f"shortlist:v2:{date_key}") is None
    assert cache.get(f"final:v2:{date_key}") is None
    assert cache.get(f"market:v2:{date_key}") is None
    assert cache.get(f"shortlist:v2:2099-01-01") == "keep"  # 其他日期缓存保留
    for key in (f"shortlist:v2:{date_key}", f"final:v2:{date_key}",
                f"market:v2:{date_key}", "shortlist:v2:2099-01-01"):
        cache.delete_prefix(key.split(":")[0] + ":" + key.split(":")[1] + ":")


# ================= 候选池按日期按需查询 =================

def test_candidate_dates_desc(monkeypatch):
    """list_candidate_dates 返回去重降序日期；页面据此默认只加载最新一天"""
    from sqlalchemy import text

    from app.cache import cache
    from app.db import repo
    from app.db.session import SessionLocal

    # 清空候选表（per-PID 隔离测试库）：避免其他测试的候选日期干扰断言
    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate"))
        db.commit()
    cache.delete_prefix("dbq:candidate:")
    repo.upsert_candidate("600001", "日期测试A", "2026-08-01", 1, ["r"], [], {}, {})
    repo.upsert_candidate("600002", "日期测试B", "2026-08-03", 1, ["r"], [], {}, {})
    repo.upsert_candidate("600003", "日期测试C", "2026-08-02", 1, ["r"], [], {}, {})
    repo.upsert_candidate("600001", "日期测试A", "2026-08-03", 2, ["r"], [], {}, {})

    dates = repo.list_candidate_dates()
    assert dates[:3] == ["2026-08-03", "2026-08-02", "2026-08-01"]

    # 按日期查询仅返回当日候选（按需加载的基础）
    day_rows = repo.list_candidates(date="2026-08-02")
    assert [r["stock_code"] for r in day_rows] == ["600003"]

    for code in ("600001", "600002", "600003"):
        with repo.SessionLocal() as db:
            from sqlalchemy import text
            db.execute(text(f"DELETE FROM stock_candidate WHERE stock_code='{code}'"))
            db.commit()
    cache.delete_prefix("dbq:candidate:")


# ================= 当日候选快照替换（不残留历史版本） =================

def test_upsert_candidate_refreshes_created_at():
    """同日同股覆盖更新：created_at 刷新为新执行时间（前端去重取最大即最新版本）"""
    from sqlalchemy import text

    from app.cache import cache
    from app.db import repo
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate"))
        db.commit()
    cache.delete_prefix("dbq:candidate:")

    repo.upsert_candidate("600001", "覆盖测试", "2026-08-05", 1, ["r1"], [], {}, {})
    first = repo.list_candidates(date="2026-08-05")[0]["created_at"]
    repo.upsert_candidate("600001", "覆盖测试", "2026-08-05", 3, ["r2"], [], {}, {})
    second = repo.list_candidates(date="2026-08-05")[0]
    assert second["rank"] == 3 and second["reasons"] == ["r2"]
    assert second["created_at"] >= first, "覆盖更新后 created_at 必须刷新为新时间"

    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate"))
        db.commit()
    cache.delete_prefix("dbq:candidate:")


def test_replace_day_candidates_removes_stale():
    """当日快照替换：新执行未选中的当日旧股被删除，不残留历史版本"""
    from sqlalchemy import text

    from app.cache import cache
    from app.db import repo
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate"))
        db.commit()
    cache.delete_prefix("dbq:candidate:")
    repo.upsert_candidate("600001", "旧股A", "2026-08-05", 1, ["r"], [], {}, {})
    repo.upsert_candidate("600002", "旧股B", "2026-08-05", 2, ["r"], [], {}, {})
    repo.upsert_candidate("600003", "留用股", "2026-08-05", 3, ["r"], [], {}, {})
    repo.upsert_candidate("600004", "其他日期", "2026-08-04", 1, ["r"], [], {}, {})

    removed = repo.replace_day_candidates({"600003"}, "2026-08-05")
    assert removed == 2, "当日非本次结果的旧股应被删除"
    codes = {r["stock_code"] for r in repo.list_candidates(date="2026-08-05")}
    assert codes == {"600003"}
    # 其他日期不受影响
    assert any(r["stock_code"] == "600004" for r in repo.list_candidates(date="2026-08-04"))

    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate"))
        db.commit()
    cache.delete_prefix("dbq:candidate:")


# ================= 缓存防穿透 =================

def test_dbq_none_not_cached():
    """loader 返回 None（异常值）时不写入缓存，避免缓存穿透"""
    from app.cache import cache
    from app.db import repo

    cache.delete_prefix("dbq:")
    calls = []

    def _load_none() -> None:
        calls.append(1)
        return None

    out = repo._dbq("probe", {"k": 1}, _load_none)
    assert out is None
    assert len(calls) == 1
    # 命中缓存应返回缓存值；None 未缓存 → 每次重新执行 loader
    out = repo._dbq("probe", {"k": 1}, _load_none)
    assert out is None and len(calls) == 2
    cache.delete_prefix("dbq:")


def test_cancel_running_task_cannot_write_business_row():
    """取消在业务函数提交前发生时，核心业务表不得留下旧 attempt 的写入。"""
    from sqlalchemy import select

    from app.db import repo
    from app.db.models import AlertLog
    from app.db.session import SessionLocal
    from app.services import task_queue

    code = "ZZCANCEL"
    started = threading.Event()
    release = threading.Event()

    def _write_after_release(_params):
        started.set()
        release.wait(5)
        repo.insert_alert(code, "取消测试", "cancel_probe", "info",
                          "不应落库", "review", {}, False)
        return "unexpected"

    tid = task_queue.submit("test_cancel_business_write", "取消业务写入",
                            _write_after_release)
    assert started.wait(2)
    assert task_queue.cancel(tid) is True
    release.set()
    deadline = time.time() + 2
    while time.time() < deadline:
        task = task_queue.get(tid)
        if task and task["status"] == "canceled":
            break
        time.sleep(0.02)
    task = task_queue.get(tid)
    assert task["status"] == "canceled"
    assert task["result"] is None

    with SessionLocal() as db:
        rows = db.execute(
            select(AlertLog).where(AlertLog.stock_code == code)
        ).scalars().all()
    assert rows == []


def _wait_task_terminal(tid: str, timeout: float = 5.0) -> dict:
    from app.services import task_queue

    deadline = time.time() + timeout
    while time.time() < deadline:
        task = task_queue.get(tid)
        if task and task["status"] in ("done", "failed", "canceled"):
            return task
        time.sleep(0.02)
    raise AssertionError(f"任务 {tid} 未在 {timeout}s 内结束: {task_queue.get(tid)}")


def test_cancel_daily_pipeline_parallel_score_cannot_write_business_row(monkeypatch):
    """每日链路评分线程必须继承 attempt；取消后子线程的旧写入被栅栏拒绝。"""
    from sqlalchemy import delete, select

    from app.db import repo
    from app.db.models import AlertLog
    from app.db.session import SessionLocal
    from app.graph import router
    from app.services import task_queue

    code_prefix = "ZZPAR_SCORE_"
    candidates = [{"stock_code": f"{code_prefix}{i}", "stock_name": f"评分取消{i}"}
                  for i in range(1, 6)]
    started = threading.Event()
    release = threading.Event()

    def _fake_discover(_trade_date=None):
        return {"candidates": candidates}

    def _fake_run_score(code, stock_name="", trade_date=None):
        started.set()
        release.wait(5)
        repo.insert_alert(code, stock_name, "cancel_probe", "info",
                          "并行评分旧 attempt 不应落库", "review", {}, False)
        return {"score_result": {"score": 80, "grade": "C"}}

    monkeypatch.setattr(router, "run_discover", _fake_discover)
    monkeypatch.setattr(router, "run_score", _fake_run_score)
    monkeypatch.setattr("app.services.candidate_tradeable.ensure_tradeable", lambda _date: 0)

    tid = task_queue.submit("test_cancel_parallel_score", "并行评分取消栅栏",
                            lambda p: router.run_daily_pipeline("2026-08-05"))
    assert started.wait(2)
    assert task_queue.cancel(tid) is True
    release.set()
    task = _wait_task_terminal(tid)
    assert task["status"] == "canceled"
    assert task["result"] is None

    try:
        with SessionLocal() as db:
            rows = db.execute(select(AlertLog).where(
                AlertLog.stock_code.like(f"{code_prefix}%"),
                AlertLog.alert_type == "cancel_probe")).scalars().all()
        assert rows == []
    finally:
        with SessionLocal() as db:
            db.execute(delete(AlertLog).where(AlertLog.stock_code.like(f"{code_prefix}%")))
            db.commit()


def test_cancel_daily_pipeline_parallel_plan_cannot_write_business_row(monkeypatch):
    """每日链路建仓线程同样继承 attempt；取消后旧计划线程不得写业务表。"""
    from sqlalchemy import delete, select

    from app.db import repo
    from app.db.models import AlertLog
    from app.db.session import SessionLocal
    from app.graph import router
    from app.services import task_queue

    code_prefix = "ZZPAR_PLAN_"
    candidates = [{"stock_code": f"{code_prefix}{i}", "stock_name": f"建仓取消{i}"}
                  for i in range(1, 6)]
    plan_started = threading.Event()
    release = threading.Event()

    def _fake_discover(_trade_date=None):
        return {"candidates": candidates}

    def _fake_run_score(code, stock_name="", trade_date=None):
        return {"score_result": {"score": 90, "grade": "A"}}

    def _fake_run_position(code, stock_name="", trade_date=None, source="manual"):
        plan_started.set()
        release.wait(5)
        repo.insert_alert(code, stock_name, "cancel_probe", "info",
                          "并行建仓旧 attempt 不应落库", "review", {}, False)
        return {"position_plan": {"plan_id": code}}

    monkeypatch.setattr(router, "run_discover", _fake_discover)
    monkeypatch.setattr(router, "run_score", _fake_run_score)
    monkeypatch.setattr(router, "run_position", _fake_run_position)
    monkeypatch.setattr("app.services.candidate_tradeable.ensure_tradeable", lambda _date: 0)

    tid = task_queue.submit("test_cancel_parallel_plan", "并行建仓取消栅栏",
                            lambda p: router.run_daily_pipeline("2026-08-05"))
    assert plan_started.wait(2)
    assert task_queue.cancel(tid) is True
    release.set()
    task = _wait_task_terminal(tid)
    assert task["status"] == "canceled"
    assert task["result"] is None

    try:
        with SessionLocal() as db:
            rows = db.execute(select(AlertLog).where(
                AlertLog.stock_code.like(f"{code_prefix}%"),
                AlertLog.alert_type == "cancel_probe")).scalars().all()
        assert rows == []
    finally:
        with SessionLocal() as db:
            db.execute(delete(AlertLog).where(AlertLog.stock_code.like(f"{code_prefix}%")))
            db.commit()


def test_retry_invalidates_old_parallel_context_before_delayed_write():
    """重试替换 attempt_id 后，旧 attempt 的延迟子线程不能发布业务结果。"""
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import delete, select

    from app.db import repo
    from app.db.models import AlertLog
    from app.db.session import SessionLocal
    from app.services import task_queue

    code = "ZZRETRY_CTX"
    child_started = threading.Event()
    release = threading.Event()
    executors: list[ThreadPoolExecutor] = []
    calls = {"n": 0}

    def _delayed_write(_params):
        child_started.set()
        release.wait(5)
        try:
            repo.insert_alert(code, "重试上下文", "retry_probe", "info",
                              "旧 attempt 不应落库", "review", {}, False)
        except task_queue.AttemptInvalidated:
            return "blocked"
        return "unexpected"

    def _retryable(_params):
        calls["n"] += 1
        if calls["n"] == 1:
            executor = ThreadPoolExecutor(max_workers=1)
            executors.append(executor)
            task_queue.submit_with_attempt_context(executor, _delayed_write, {})
            assert child_started.wait(2)
            executor.shutdown(wait=False)
            raise RuntimeError("首次 attempt 失败")
        return "retry-ok"

    tid = task_queue.submit("test_retry_context", "重试上下文栅栏", _retryable)
    _wait_task_terminal(tid)
    assert task_queue.retry(tid) is True
    task = _wait_task_terminal(tid)
    assert task["status"] == "done"
    assert task["result"] == "retry-ok"

    release.set()
    try:
        for executor in executors:
            executor.shutdown(wait=True)
        with SessionLocal() as db:
            rows = db.execute(select(AlertLog).where(
                AlertLog.stock_code == code,
                AlertLog.alert_type == "retry_probe")).scalars().all()
        assert rows == []
    finally:
        release.set()
        for executor in executors:
            executor.shutdown(wait=True)
        with SessionLocal() as db:
            db.execute(delete(AlertLog).where(AlertLog.stock_code == code))
            db.commit()
