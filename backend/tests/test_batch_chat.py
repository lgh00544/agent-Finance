"""批量对话服务测试：
1. resolve_scope 范围解析（all/tradeable/A/B/C/manual + 截断）
2. _candidate_table_text 上下文文本（含判定字段）
3. ask_batch：LLM 结构化输出 → 消息留痕 + batch 调整记录（pending），task_queue 安全标量
4. apply_batch_adjust：pending→applied 写入 candidate_adjust + 快照
5. rollback_batch_adjust：applied→rolled_back 删除覆盖 + 留原因
6. 状态机守卫：非 pending 不可 apply / 已回滚不可重复
"""
import pytest
from sqlalchemy import delete

from app.db import repo
from app.db.models import AgentChatMessage, BatchAdjust, CandidateAdjust, StockCandidate
from app.db.session import SessionLocal, init_db
from app.services.batch_chat import (apply_batch_adjust, ask_batch,
                                     resolve_scope, rollback_batch_adjust)

DATE = "2026-08-10"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(delete(AgentChatMessage))
        db.execute(delete(BatchAdjust))
        db.execute(delete(CandidateAdjust))
        db.execute(delete(StockCandidate))
        db.commit()
    repo._invalidate("candidate")
    repo._invalidate("plan")
    repo._invalidate("tradeable")
    yield


def _seed():
    """3 只候选：600001=可建仓(A)、600002=无方案(B)、600003=C 级"""
    with SessionLocal() as db:
        db.add_all([
            StockCandidate(stock_code="600001", stock_name="可建仓股", trade_date=DATE, rank=1,
                           reasons=["吸筹末期"], risk_notice=[], snapshot={"price": "23.8"},
                           detail={"confidence_tier": "强烈推荐", "risks": ["无"]}),
            StockCandidate(stock_code="600002", stock_name="无方案股", trade_date=DATE, rank=2,
                           reasons=["趋势初升"], risk_notice=[], snapshot={"price": "12.0"},
                           detail={"confidence_tier": "建议关注", "risks": ["无"]}),
            StockCandidate(stock_code="600003", stock_name="C级观察股", trade_date=DATE, rank=3,
                           reasons=["谨慎"], risk_notice=[], snapshot={"price": "5.5"},
                           detail={"confidence_tier": "谨慎观察", "risks": ["无"]}),
        ])
        db.commit()
    repo._invalidate("candidate")


def _make_answer(plan=None):
    from app.services.batch_chat import BatchAnswer
    return BatchAnswer(overall="整体结论：当前以观望为主，优先跟踪吸筹末期标的。",
                       common_points=["候选多为吸筹末期形态", "无重大利空"],
                       differences=["600001 已有建仓方案且现价在区间内，优先关注"],
                       suggestions=["建议提升吸筹末期标的关注度"],
                       adjust_plan=plan or [])


def _patch_agent_call(monkeypatch, answer):
    from app.services import batch_chat as svc
    monkeypatch.setattr(svc.common, "agent_call", lambda **kw: answer)


# ==================== 1. resolve_scope ====================

def test_resolve_scope_all_and_filters(monkeypatch):
    _seed()
    from app.services import batch_chat as svc
    # 真实判定（不调 LLM）：resolve_scope 内部只做候选读取 + 判定
    all_rows, note = resolve_scope("all", None, DATE)
    assert len(all_rows) == 3
    assert "候选" in note
    tr, _ = resolve_scope("tradeable", None, DATE)
    assert [r["stock_code"] for r in tr] == []
    a_rows, _ = resolve_scope("A", None, DATE)
    assert [r["stock_code"] for r in a_rows] == ["600001"]
    c_rows, _ = resolve_scope("C", None, DATE)
    assert [r["stock_code"] for r in c_rows] == ["600003"]
    manual, _ = resolve_scope("manual", ["600001", "600002"], DATE)
    assert {r["stock_code"] for r in manual} == {"600001", "600002"}


def test_resolve_scope_invalid():
    with pytest.raises(ValueError):
        resolve_scope("bogus", None, DATE)


def test_resolve_scope_cap_truncation():
    with SessionLocal() as db:
        for i in range(25):
            db.add(StockCandidate(stock_code=f"9{i:05d}", stock_name=f"股{i}", trade_date=DATE,
                                  rank=i + 1, reasons=[], risk_notice=[], snapshot={"price": "1"},
                                  detail={"confidence_tier": "建议关注", "risks": ["无"]}))
        db.commit()
    repo._invalidate("candidate")
    rows, note = resolve_scope("all", None, DATE)
    assert len(rows) == 20
    assert "截断" in note


# ==================== 2. 上下文文本 ====================

def test_candidate_table_text_fields():
    _seed()
    rows, _ = resolve_scope("all", None, DATE)
    from app.services.batch_chat import _candidate_table_text
    text = _candidate_table_text(rows)
    assert "600001" in text and "可建仓股" in text
    assert "评级=" in text and "判定=" in text
    assert "无重大利空" in text or "无" in text


# ==================== 3. ask_batch ====================

def test_ask_batch_records_messages_and_batch(monkeypatch):
    _seed()
    _patch_agent_call(monkeypatch, _make_answer(plan=[{
        "stock_code": "600003", "new_tier": "B", "new_label": "建议关注",
        "reason": "评级偏低，实际质量不亚于 600002", "evidence": "同为无重大利空且形态稳健"}]))

    res = ask_batch("all", None, "这批候选当前适合建仓吗？", DATE, operator="测试")
    assert res["count"] == 3
    assert res["scope"] == "all" and res["batch_id"] > 0
    assert res["answer"] == "整体结论：当前以观望为主，优先跟踪吸筹末期标的。"
    # 消息留痕（message_type=batch，user + assistant）
    msgs = repo.list_chat_messages("discover", message_type="batch")
    assert len(msgs) == 2
    user_m = [m for m in msgs if m["role"] == "user"]
    asst_m = [m for m in msgs if m["role"] == "assistant"]
    assert user_m and asst_m
    assert asst_m[0]["meta"]["adjust_plan"], "adjust_plan 应进 assistant meta"
    assert asst_m[0]["meta"]["user_msg_id"] == user_m[0]["id"]
    # batch 调整留痕（pending）
    batches = repo.list_batch_adjusts()
    assert batches and batches[0]["status"] == "pending"
    assert repo.get_batch_adjust(batches[0]["id"])["chat_user_msg_id"] == res["assistant_msg_id"]


def test_ask_batch_empty_question():
    with pytest.raises(ValueError):
        ask_batch("all", None, "   ", DATE)


# ==================== 4. apply / 5. rollback ====================

def _make_batch() -> int:
    """直接落一条 pending 调整记录（模拟 ask_batch 留痕）"""
    return repo.add_batch_adjust(
        "all", ["600003"], "测试问题", DATE,
        [{"stock_code": "600003", "new_tier": "B", "new_label": "建议关注",
          "reason": "测试", "evidence": "证据"}],
        {"items": [{"stock_code": "600003", "stock_name": "C级观察股", "tier": "C"}]},
        chat_user_msg_id=0, operator="测试")


def test_apply_then_rollback():
    _seed()
    bid = _make_batch()
    res = apply_batch_adjust(bid)
    assert res["status"] == "applied" and res["count"] == 1
    # candidate_adjust 已写入
    adjusts = repo.list_candidate_adjusts(DATE)
    assert adjusts[0]["stock_code"] == "600003"
    assert adjusts[0]["tier_override"] == "B"
    batch = repo.get_batch_adjust(bid)
    assert batch["status"] == "applied"
    assert batch["after_snapshot"]["items"][0]["tier_override"] == "B"
    # 生效后立即按 effective_tier 重判落库（前端计数/标签同步）
    tr = {r["stock_code"]: r for r in repo.list_candidate_tradeable(DATE)}
    assert tr["600003"]["tier"] == "B" and tr["600003"]["label"] == "建议关注"

    # 回滚：删除覆盖恢复原判定
    rb = rollback_batch_adjust(bid, "测试回滚")
    assert rb["status"] == "rolled_back"
    assert rb["count"] == 1
    assert repo.list_candidate_adjusts(DATE) == []
    tr = {r["stock_code"]: r for r in repo.list_candidate_tradeable(DATE)}
    assert tr["600003"]["tier"] == "C" and tr["600003"]["label"] == "观察"
    batch = repo.get_batch_adjust(bid)
    assert batch["rollback_reason"] == "测试回滚"
    assert batch["rollback_time"]
    # 重复回滚拒绝
    with pytest.raises(ValueError):
        rollback_batch_adjust(bid, "再滚一次")


def test_apply_guards_non_pending():
    _seed()
    bid = _make_batch()
    apply_batch_adjust(bid)
    with pytest.raises(ValueError) as ei:
        apply_batch_adjust(bid)                     # 已 applied
    assert "pending" in str(ei.value)
    with pytest.raises(ValueError):
        apply_batch_adjust(99999)                    # 不存在


def test_apply_skips_invalid_tier_and_unknown_code():
    _seed()
    bid = repo.add_batch_adjust(
        "manual", ["600001", "600003", "888888"], "问题", DATE,
        [{"stock_code": "600001", "new_tier": "X", "new_label": "错误档位"},   # 非法档位跳过
         {"stock_code": "600003", "new_tier": "B", "new_label": "建议关注",
          "reason": "测试", "evidence": "证据"},
         {"stock_code": "888888", "new_tier": "A", "new_label": "可建仓",
          "reason": "未知代码", "evidence": "证据"}],                            # 不在候选内跳过
        {"items": []}, chat_user_msg_id=0, operator="测试")
    res = apply_batch_adjust(bid)
    assert res["count"] == 1
    assert res["applied"][0]["stock_code"] == "600003"
