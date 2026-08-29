# -*- coding: utf-8 -*-
"""飞书 teach 补丁：remember/forget/teach 三意图 + 硬规则门 + 降级 + 同步/异步。
只测 chat_handlers 分发逻辑，LLM 与偏好存储均 mock（不触真实 DB / 不调网络）。"""
from types import SimpleNamespace

import pytest

from app.services import agent_chat, chat_handlers as ch
from app.services import feishu_bridge as fb


@pytest.fixture(autouse=True)
def _clear_drafts():
    fb._drafts.clear()
    yield
    fb._drafts.clear()


def _mock_teach(monkeypatch, profile=None, pending=None, verdict="adopted"):
    store = profile if profile is not None else {}
    pend = pending if pending is not None else []
    monkeypatch.setattr(ch.repo, "get_trade_profile_content", lambda: store)
    monkeypatch.setattr(ch.repo, "update_trade_profile", lambda c: store.update(c) or 2)
    monkeypatch.setattr(ch.repo, "add_pending_experience",
                        lambda tid, stage, summary, ref: pend.append((stage, summary, ref)) or 1)
    monkeypatch.setattr(agent_chat, "_require_agent", lambda a: {"name": "评分分析 Agent"})
    monkeypatch.setattr(ch.common, "agent_call",
                        lambda **k: SimpleNamespace(verdict=verdict, reason="理由", rule_title="规则",
                                                    rule_content="正文", conflict_note=""))
    return store, pend


def test_remember_direct_write(monkeypatch):
    store, _ = _mock_teach(monkeypatch)
    r = ch.dispatch("记住 我持有 600519", "remember", {}, "", "ou_1")
    assert "已记住" in r and store.get("我持有 600519") == "我持有 600519"


def test_remember_threshold_degrades_to_teach(monkeypatch):
    """P1 修复：仓位类个人规则降级 teach 待审，不硬拒"""
    _, pend = _mock_teach(monkeypatch)
    r = ch.dispatch("记住 仓位不超过 5 成", "remember", {}, "", "ou_1")
    assert "待审核" in r and "硬规则" not in r and pend[0][0] == "feishu_tutoring"


def test_teach_submits_pending(monkeypatch):
    _, pend = _mock_teach(monkeypatch)
    r = ch.dispatch("教 以后都追涨停", "teach", {"agent": "score"}, "", "ou_1")
    assert "待审核" in r and pend and pend[0][2]["source"] == "feishu"


def test_teach_hard_threshold_rejected(monkeypatch):
    _, pend = _mock_teach(monkeypatch)
    r = ch.dispatch("止损改成 3%", "teach", {"agent": "sell"}, "", "ou_1")
    assert "硬规则" in r and "只读" in r and not pend  # 不进 LLM 不落库


def test_threshold_word_alone_goes_to_llm(monkeypatch):
    """黑名单词单现（止损是 5%）→ 不硬拒，进 LLM 校验"""
    calls = []
    monkeypatch.setattr(ch.repo, "add_pending_experience", lambda *a, **k: 1)
    monkeypatch.setattr(agent_chat, "_require_agent", lambda a: {"name": "卖出 Agent"})
    monkeypatch.setattr(ch.common, "agent_call",
                        lambda **k: calls.append(k["agent"]) or SimpleNamespace(
                            verdict="maintained", reason="不构成规则变更", rule_title="", rule_content=""))
    r = ch.dispatch("止损是 5%", "teach", {"agent": "sell"}, "", "ou_1")
    assert "硬规则" not in r and calls == ["sell"] and "维持原规则" in r


def test_forget_deletes_key(monkeypatch):
    store, _ = _mock_teach(monkeypatch, profile={"我持有 600519": "我持有 600519"})
    r = ch.dispatch("忘掉 我持有 600519", "forget", {}, "", "ou_1")
    assert "已删除" in r and "我持有 600519" not in store


def test_forget_no_match(monkeypatch):
    _, _ = _mock_teach(monkeypatch, profile={"其他": "其他"})
    r = ch.dispatch("忘掉 不存在的事", "forget", {}, "", "ou_1")
    assert "无匹配" in r


def test_teach_long_proposal_async(monkeypatch):
    submitted = {}
    monkeypatch.setattr(ch.task_queue, "submit",
                        lambda kind, label, fn, params: submitted.update(kind=kind) or "tid")
    r = ch.dispatch("教 " + "x" * 60, "teach", {"agent": "score"}, "", "ou_1")
    assert "处理中" in r and submitted.get("kind") == "feishu_teach"


def test_draft_collects_mixed_pieces_and_finishes(monkeypatch):
    store, pend = _mock_teach(monkeypatch)
    assert "开启草稿" in ch.dispatch("教·存草稿", "draft", {}, "", "ou_1")
    assert "已存第 1 条" in ch.dispatch("补一条 我持有 600519", "draft", {}, "", "ou_1")
    assert "已存第 2 条" in ch.dispatch("教 以后都止损先看量能", "teach", {"agent": "sell"}, "", "ou_1")
    r = ch.dispatch("完成", "draft", {}, "", "ou_1")
    assert "草稿已提交" in r and store.get("我持有 600519") == "我持有 600519"
    assert pend and pend[0][0] == "feishu_tutoring" and "ou_1" not in fb._drafts


def test_draft_cancel_and_empty_finish():
    assert "开启草稿" in ch.dispatch("先存着", "draft", {}, "", "ou_1")
    assert ch.dispatch("放弃", "draft", {}, "", "ou_1") == "已丢弃 0 条"
    assert ch.dispatch("完成", "draft", {}, "", "ou_1") == "草稿为空，无可提交"


def test_teach_reject_guides_to_draft(monkeypatch):
    _, pend = _mock_teach(monkeypatch, verdict="maintained")
    r = ch.dispatch("教 以后都追涨停", "teach", {"agent": "score"}, "", "ou_1")
    assert "维持原规则" in r and "如需多轮教，先发「教·存草稿」开草稿" in r and not pend


def test_draft_cleanup_expires_old_state():
    fb._drafts["ou_1"] = fb.DraftState(created_at=1)
    assert fb._cleanup_drafts(now=1 + fb._DRAFT_TTL + 1) == 1
    assert fb._drafts == {}


def test_router_keywords():
    from app.services.chat_router import _route_regex

    assert _route_regex("教·存草稿")[0] == "draft"
    assert _route_regex("补一条 我持有 600519")[0] == "draft"
    assert _route_regex("完成")[0] == "draft"
    assert _route_regex("放弃")[0] == "draft"
    assert _route_regex("记住 我持有 600519")[0] == "remember"
    assert _route_regex("忘掉 我持有 600519")[0] == "forget"  # forget 优先于 remember
    assert _route_regex("教 以后都止损")[0] == "teach"
    assert _route_regex("止损改成 3%")[0] == "teach"
    assert _route_regex("止损是 5%")[0] == "teach"  # 阈值词单现
    assert _route_regex("教 以后都止损")[1]["agent"] == "sell"  # 领域识别
