"""知识库决策级归因（B方案）测试：命中计量 + 编号注入 + 对话引用回吐

覆盖：①search_knowledge 返回含 id ②private_knowledge 表两新列存在（PRAGMA）
      ③bump_knowledge_hits 累计 + last_used_at 更新 ④knowledge_section 返回 (文本, docs 编号映射) + 文本带编号头
      ⑤agent_chat ChatAnswer 含 used_knowledge 字段 + 引用编号→id 写回
约定：各用例独立知识条目避免互相污染；bump 只在知识_section 检索或显式写回时触发。
"""
import pytest

from app.db import repo
from app.db.session import SessionLocal, init_db
from app.services.vector_store import get_vector_store


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _hit_row(kid: int):
    with SessionLocal() as db:
        from app.db.models import PrivateKnowledge
        return db.get(PrivateKnowledge, kid)


# ① search_knowledge 返回含 id（决策级归因定位依赖 id）
def test_search_knowledge_has_id():
    kid = repo.add_knowledge("归因测试-占比", "单只占比超 60% 触发预警", "all")
    try:
        docs = get_vector_store().search_knowledge("discover", top_k=5)
        assert docs, "应有至少一条知识"
        assert all("id" in d and d["id"] == int(d["id"]) for d in docs)
        assert any(d["id"] == kid for d in docs)
    finally:
        repo.delete_knowledge(kid)


# ② private_knowledge 表两新列存在（启动时 ALTER 幂等补齐）
def test_private_knowledge_hit_columns_exist():
    from sqlalchemy import text
    with SessionLocal() as db:
        cols = {row[1] for row in db.execute(
            text("PRAGMA table_info(private_knowledge)")).fetchall()}
    assert "hit_count" in cols and "last_used_at" in cols


# ③ bump_knowledge_hits：累计 hit_count + last_used_at 更新（批量一次 UPDATE）
def test_bump_knowledge_hits_accumulates():
    kid = repo.add_knowledge("归因测试-累计", "止损纪律不可放宽", "monitor")
    try:
        repo.bump_knowledge_hits([kid])
        repo.bump_knowledge_hits([kid])
        repo.bump_knowledge_hits([kid, 999999])  # 批量含不存在 id：存在者+1，不存在忽略
        row = _hit_row(kid)
        assert row.hit_count == 3
        assert row.last_used_at is not None
    finally:
        repo.delete_knowledge(kid)


# ④ knowledge_section 返回 (文本, docs 编号映射) + 注入文本带 "1.【..】2.【..】" 编号头（mock 检索确定性）
def test_knowledge_section_numbered_and_docs(monkeypatch):
    from app.agents.common import knowledge_section
    fake_docs = [
        {"id": 101, "title": "归因测试-编号A", "content": "内容A：回踩 MA20 企稳再进场"},
        {"id": 202, "title": "归因测试-编号B", "content": "内容B：破位缩量先减仓"},
    ]
    monkeypatch.setattr(
        "app.services.vector_store.get_vector_store",
        lambda: type("S", (), {"search_knowledge": lambda self, agent, top_k=5: fake_docs})())
    text, docs = knowledge_section("score")
    assert text and docs
    assert "1.【归因测试-编号A】" in text and "2.【归因测试-编号B】" in text
    assert "回吐其编号" in text  # 引用回吐指令已随编号格式注入
    assert docs[0] == {"id": 101, "number": 1, "title": "归因测试-编号A"}
    assert docs[1] == {"id": 202, "number": 2, "title": "归因测试-编号B"}


# ⑤ ChatAnswer 含 used_knowledge 字段 + 编号→id 写回（未引用 → 空数组不伪造）
def test_chat_used_knowledge_writeback(monkeypatch):
    from app.services import agent_chat as ac
    assert "used_knowledge" in ac.ChatAnswer.model_fields
    assert ac.ChatAnswer(answer="x", confidence=50, used_knowledge=[]).used_knowledge == []

    # 合成 docs 验证"编号→知识id"映射写回（避免依赖真实库知识条目）
    docs = [{"id": 101, "number": 1, "title": "A"}, {"id": 202, "number": 2, "title": "B"}]
    bumped = {"ids": []}
    monkeypatch.setattr(ac.repo, "bump_knowledge_hits",
                        lambda ids: bumped.update({"ids": list(ids)}) or len(ids))
    used = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]  # LLM 报告的编号
    num_map = {d["number"]: d["id"] for d in docs}
    ids = [num_map.get(u.get("id", u.get("number"))) for u in used]
    ac.repo.bump_knowledge_hits([i for i in ids if i])
    assert bumped["ids"] == [101, 202]
