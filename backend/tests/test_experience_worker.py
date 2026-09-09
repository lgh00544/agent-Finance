from app.services import experience_worker
from app.services import task_queue
from app.agents.schemas import ExperienceDraft


def test_conflict_check_failure_is_fail_closed(monkeypatch):
    draft = ExperienceDraft(
        worth=True,
        title="测试经验",
        body="测试正文",
        stage="选股",
        tags=["动量"],
        impact="low",
        confidence=0.95,
    )
    monkeypatch.setattr(
        experience_worker.repo,
        "search_experience",
        lambda **kwargs: [{"id": 1, "title": "旧经验", "body": "旧正文", "tags": "动量"}],
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("冲突模型不可用")

    monkeypatch.setattr(experience_worker, "_llm_extract", _boom)
    result = experience_worker._conflict_check(draft)

    assert result["conflict"] is True
    assert result["reason"] == "冲突判定失败，转人工审核"


def test_worker_run_skips_when_locked(monkeypatch):
    monkeypatch.setattr(task_queue, "has_active", lambda kind: False)
    monkeypatch.setattr(experience_worker.cache, "acquire_lock", lambda *args, **kwargs: False)
    monkeypatch.setattr(experience_worker, "_cfg_int", lambda key: 1)
    monkeypatch.setattr(experience_worker, "_cfg_float", lambda key: 0)
    monkeypatch.setattr(experience_worker.repo, "watchdog_reset_stale_processing", lambda older_than_hours=2.0: 0)
    monkeypatch.setattr(experience_worker.repo, "pending_backlog_count", lambda: 1)
    calls = {"start": 0, "claim": 0}
    monkeypatch.setattr(
        experience_worker.repo,
        "start_worker_run",
        lambda: calls.__setitem__("start", calls["start"] + 1),
    )
    monkeypatch.setattr(
        experience_worker.repo,
        "claim_pending_batch",
        lambda batch_size=20: calls.__setitem__("claim", calls["claim"] + 1),
    )

    result = experience_worker.worker_run(force=True)

    assert result["skipped"] is True
    assert result["reason"] == "worker_locked"
    assert calls == {"start": 0, "claim": 0}


def test_worker_run_returns_soft_failure_on_retryable_db_error(monkeypatch):
    monkeypatch.setattr(task_queue, "has_active", lambda kind: False)
    monkeypatch.setattr(experience_worker.cache, "acquire_lock", lambda *args, **kwargs: True)
    released: list[str] = []
    monkeypatch.setattr(experience_worker.cache, "release_lock", lambda key: released.append(key))
    monkeypatch.setattr(experience_worker, "_cfg_int", lambda key: 1)
    monkeypatch.setattr(experience_worker, "_cfg_float", lambda key: 0)
    monkeypatch.setattr(experience_worker.repo, "watchdog_reset_stale_processing", lambda older_than_hours=2.0: 0)
    monkeypatch.setattr(experience_worker.repo, "pending_backlog_count", lambda: 1)
    monkeypatch.setattr(experience_worker, "_DB_RETRY_DELAYS", (0, 0))
    monkeypatch.setattr(
        experience_worker.repo,
        "start_worker_run",
        lambda: (_ for _ in ()).throw(RuntimeError("database is locked")),
    )
    monkeypatch.setattr(
        experience_worker.repo,
        "claim_pending_batch",
        lambda batch_size=20: (_ for _ in ()).throw(RuntimeError("database is locked")),
    )

    result = experience_worker.worker_run(force=True)

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["error"] == "database is locked"
    assert released == [experience_worker._WORKER_LOCK]
