from app.services import experience_worker
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
