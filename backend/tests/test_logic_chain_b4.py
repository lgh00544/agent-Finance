"""第4批逻辑链修复 · 批次18 归属判定回归（单用户 legacy 放行 / 多人 fail-closed / 写入默认归属）"""
from datetime import datetime

import pytest

from app.api.routes import adopt_review_suggestion
from app.core.config import settings
from app.db import repo
from app.db.models import ReviewResult
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def test_legacy_null_owner_review_is_adoptable_in_single_user_mode(monkeypatch):
    """单用户模式：历史 user_id=NULL 的复盘仍可被归属分支放行（修复前 404）。"""
    monkeypatch.setattr(settings, "multi_user_enabled", False)
    rid = repo.insert_review(
        "600704", "批4 legacy 无归属", 1, "2026-08-01", 5, 1.5,
        {"入场逻辑": "回测"}, "测试教训",
        {"profile_suggestion": {"field": "批4归属测试", "value": "旧入口值"}},
    )
    with SessionLocal() as db:  # 模拟历史 legacy 行：归属回写为 NULL
        db.query(ReviewResult).filter(ReviewResult.id == rid).update(
            {"user_id": None}, synchronize_session=False)
        db.commit()
    row = repo.get_review_for_user(rid, repo.ensure_default_user())
    assert row is not None and row.user_id is None
    result = adopt_review_suggestion(rid)
    assert result["adopted"] is True and result["legacy_adopt"] is True


def test_review_ownership_fails_closed_in_multi_user_mode(monkeypatch):
    """多人模式：他人复盘不可读（本人/管理员可读），归属分支不回退。"""
    monkeypatch.setattr(settings, "multi_user_enabled", True)
    stamp = str(int(datetime.now().timestamp() * 1_000_000))
    owner = repo.create_user("b4-owner-" + stamp, "secret", "researcher")
    other = repo.create_user("b4-other-" + stamp, "secret", "researcher")
    rid = repo.insert_review("600705", "批4归属股", 1, "2026-08-01", 5, 1.5, {}, "", {},
                             user_id=owner["id"])
    assert repo.get_review_for_user(rid, owner["id"]) is not None
    assert repo.get_review_for_user(rid, other["id"]) is None
    assert repo.get_review_for_user(rid, other["id"], is_admin=True) is not None


def test_insert_review_records_owner_by_default(monkeypatch):
    """写入侧默认归属与 insert_agent_suggestion 同口径：不再落 NULL。"""
    monkeypatch.setattr(settings, "multi_user_enabled", False)
    rid = repo.insert_review("600706", "批4默认归属", 1, "2026-08-01", 5, 1.5, {}, "", {})
    assert repo.get_review(rid).user_id is not None
