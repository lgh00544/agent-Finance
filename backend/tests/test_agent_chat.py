"""Agent 专属对话服务测试：
提问答疑（知识注入+标源+信心度）/ 规则调教校验（不盲从、硬规则只读、采纳自动沉淀知识库）/
多模态学习（识别→提炼→确认落库两段式）/ 历史可回溯。
LLM 调用全部 mock：断言结构化解析与流程行为，不断言业务结论。"""
import json

import pytest

from app.agents import common
from app.db import repo
from app.services import agent_chat


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from app.db.session import init_db
    init_db()


# ================= 文字提问答疑 =================

def _fake_chat_answer(**kwargs):
    def _call(*args, **kw):
        return agent_chat.ChatAnswer(
            answer="当前持仓以波段趋势为主，宜分批管理。",
            confidence=80, sources=["分职能战法知识库", "个人偏好档案"], scope_note="")
    return _call


def test_ask_agent_payload_and_history(monkeypatch):
    """提问 → 结构化答案 + 标源 + 信心度；历史落库两行（user/assistant）"""
    monkeypatch.setattr(common, "agent_call", _fake_chat_answer())
    payload = agent_chat.ask_agent("discover", "怎么理解吸筹末期？")
    assert payload["answer"]
    assert payload["confidence"] == 80
    assert "知识库" in payload["sources"]
    history = repo.list_chat_messages("discover", limit=5)
    assert len(history) >= 2
    roles = [h["role"] for h in history[:2]]
    assert "user" in roles and "assistant" in roles
    assert history[0]["message_type"] == "qa"


def test_ask_unknown_agent_rejected():
    with pytest.raises(ValueError, match="未知 Agent"):
        agent_chat.ask_agent("nope", "问题")


def test_ask_empty_question_rejected():
    with pytest.raises(ValueError, match="不能为空"):
        agent_chat.ask_agent("score", "   ")


# ================= 规则调教校验 =================

def test_rule_adopted_auto_sinks_knowledge(monkeypatch):
    """校验通过 → 采纳结论 + 自动沉淀到该 Agent 私有知识库（agent_tag 正确）"""
    def _call(*args, **kw):
        return agent_chat.RuleFeedback(
            verdict="adopted", reason="不冲突且可执行",
            rule_title="5日涨幅上限调整", rule_content="5日涨幅≥10%时仅做观察不低吸，须回踩确认。",
            conflict_note="与现有规则无冲突，不触碰硬性规则。")
    monkeypatch.setattr(common, "agent_call", _call)
    monkeypatch.setattr(repo, "add_knowledge", lambda title, content, agent_tag: 7)
    payload = agent_chat.rule_feedback("score", "建议把超买阈值从15%降到10%")
    assert payload["verdict"] == "adopted"
    assert payload["verdict_label"] == "采纳"
    assert payload["knowledge_id"] == 7
    assert payload["rule_title"].startswith("5日涨幅")
    # 历史记录带裁决
    history = repo.list_chat_messages("score", limit=5)
    assert any(h["message_type"] == "rule" and h["verdict"] == "adopted" for h in history)


def test_rule_maintained_no_sink(monkeypatch):
    """与硬性规则冲突 → 维持原规则，且不沉淀任何知识（硬规则只读）"""
    def _call(*args, **kw):
        return agent_chat.RuleFeedback(
            verdict="maintained",
            reason="该提案试图放宽硬性规则中的止损纪律，硬性规则只能由人工修改。",
            rule_title="", rule_content="", conflict_note="与 HARD_RULES 第2条冲突。")
    monkeypatch.setattr(common, "agent_call", _call)
    added = []
    monkeypatch.setattr(repo, "add_knowledge",
                        lambda title, content, agent_tag: added.append(title) or 1)
    payload = agent_chat.rule_feedback("monitor", "建议把止损放宽到-12%")
    assert payload["verdict"] == "maintained"
    assert payload["verdict_label"] == "维持原规则"
    assert payload["knowledge_id"] is None
    assert added == []  # 未沉淀


def test_rule_partial_sinks_adjusted_content(monkeypatch):
    """部分采纳 → 沉淀调整后的规则版本"""
    def _call(*args, **kw):
        return agent_chat.RuleFeedback(
            verdict="partial", reason="方向合理，需补充边界条件",
            rule_title="资金流确认规则", rule_content="主力净流入需连续3日为正才视为有效（单日不计）。",
            conflict_note="无冲突。")
    monkeypatch.setattr(common, "agent_call", _call)
    monkeypatch.setattr(repo, "add_knowledge", lambda title, content, agent_tag: 9)
    payload = agent_chat.rule_feedback("position", "主力流入就算确认")
    assert payload["verdict"] == "partial"
    assert payload["knowledge_id"] == 9


def test_rule_invalid_verdict_falls_back_maintained(monkeypatch):
    """LLM 输出非法裁决值 → 兜底为维持原规则，安全不沉淀"""
    def _call(*args, **kw):
        return agent_chat.RuleFeedback(verdict="maybe", reason="x")
    monkeypatch.setattr(common, "agent_call", _call)
    monkeypatch.setattr(repo, "add_knowledge", lambda *a, **k: 1)
    payload = agent_chat.rule_feedback("sell", "随便改改")
    assert payload["verdict"] == "maintained"


# ================= 多模态上传学习 =================

def _fake_learn_extract(**kwargs):
    def _call(*args, **kw):
        return agent_chat.LearnExtract(
            summary="识别到 1 个知识点：放量突破形态",
            points=[agent_chat.LearnPoint(title="放量突破确认", content="收盘价站稳前高3日视为有效突破。",
                                          tags=["K线战法"], agent_tag="discover")])
    return _call


def test_learn_two_phase_flow(monkeypatch):
    """识别提炼返回确认摘要（不落库）；确认后才写入知识库"""
    added = []
    monkeypatch.setattr(agent_chat, "_extract_image_text",
                        lambda *a, **k: "放量突破：收盘站稳前高3日视为有效突破。")
    monkeypatch.setattr(common, "agent_call", _fake_learn_extract())
    monkeypatch.setattr(repo, "add_knowledge",
                        lambda title, content, agent_tag: added.append(title) or 11)
    result = agent_chat.learn_from_image("discover", b"fake-img", "kline.png")
    assert result["engine"] == "minimax"
    assert "放量突破" in result["summary"]
    points = json.loads(result["points_json"])
    assert points[0]["title"] == "放量突破确认"
    assert points[0]["tags"] == ["K线战法"]
    assert added == []  # 提炼阶段只出摘要，不落库（确认后才写入）


def test_learn_confirm_saves(monkeypatch):
    """确认（含修正标签）→ 写入对应 Agent 知识库，非法标签兜底当前 Agent"""
    saved = []
    monkeypatch.setattr(repo, "add_knowledge",
                        lambda title, content, agent_tag: saved.append(agent_tag) or 1)
    result = agent_chat.confirm_learn("score", [
        {"title": "评分细则补充", "content": "财务质量分按ROE分位计。", "agent_tag": "score"},
        {"title": "无效标签", "content": "x", "agent_tag": "hacker"},
    ])
    assert result["count"] == 2
    assert saved == ["score", "score"]  # 非法标签兜底为当前 Agent


def test_learn_empty_extract_raises(monkeypatch):
    """识别文本为空 → 明确报错提示"""
    monkeypatch.setattr(agent_chat, "_extract_image_text", lambda *a, **k: "")
    with pytest.raises(ValueError, match="识别结果为空"):
        agent_chat.learn_from_image("review", b"x", "a.png")


def test_learn_points_empty_raises(monkeypatch):
    """识别有文本但提炼无有效知识点 → 明确报错"""
    monkeypatch.setattr(agent_chat, "_extract_image_text", lambda *a, **k: "some text")
    def _call(*args, **kw):
        return agent_chat.LearnExtract(summary="s", points=[])
    monkeypatch.setattr(common, "agent_call", _call)
    with pytest.raises(ValueError, match="未能从图片中提炼"):
        agent_chat.learn_from_image("sell", b"x", "a.png")


# ================= 多模态学习·辅助文本描述 =================

def test_learn_description_section_helper():
    """补充说明节纯函数：非空返回含「图片为主、文字为辅 + 冲突以图片为准」指令；空串保持原样"""
    assert agent_chat._learn_description_section("") == ""
    assert agent_chat._learn_description_section("   ") == ""
    section = agent_chat._learn_description_section("这是周线放量突破形态")
    assert "用户补充说明" in section
    assert "图片为主、文字为辅" in section
    assert "以图片为准" in section
    assert "这是周线放量突破形态" in section


def test_learn_description_injected_into_prompts(monkeypatch):
    """描述非空：透传 _extract_image_text（MiniMax 提示增强）且结构化提炼 user_prompt 含补充说明节"""
    captured = {}

    def _spy_extract(image_bytes, filename, description=""):
        captured["desc"] = description
        return "放量突破：收盘站稳前高3日视为有效突破。"

    def _spy_agent_call(*args, **kw):
        captured["user_prompt"] = kw.get("user_prompt", "")
        return agent_chat.LearnExtract(
            summary="1 个知识点", points=[agent_chat.LearnPoint(title="放量突破确认", content="x")])

    monkeypatch.setattr(agent_chat, "_extract_image_text", _spy_extract)
    monkeypatch.setattr(common, "agent_call", _spy_agent_call)
    result = agent_chat.learn_from_image("discover", b"fake-img", "kline.png",
                                         description="重点关注突破确认信号")
    assert captured["desc"] == "重点关注突破确认信号"
    assert "用户补充说明" in captured["user_prompt"]
    assert "重点关注突破确认信号" in captured["user_prompt"]
    assert "以图片为准" in captured["user_prompt"]
    assert result["description"] == "重点关注突破确认信号"


def test_learn_description_empty_backward_compat(monkeypatch):
    """描述为空：不透传描述、提炼提示不含补充说明节，行为与旧版一致（向后兼容）"""
    captured = {}

    def _spy_extract(image_bytes, filename, description=""):
        captured["desc"] = description
        return "放量突破：收盘站稳前高3日视为有效突破。"

    def _spy_agent_call(*args, **kw):
        captured["user_prompt"] = kw.get("user_prompt", "")
        return agent_chat.LearnExtract(
            summary="1 个知识点", points=[agent_chat.LearnPoint(title="放量突破确认", content="x")])

    monkeypatch.setattr(agent_chat, "_extract_image_text", _spy_extract)
    monkeypatch.setattr(common, "agent_call", _spy_agent_call)
    agent_chat.learn_from_image("discover", b"fake-img", "kline.png")
    assert captured["desc"] == ""
    assert "用户补充说明" not in captured["user_prompt"]
    assert "图片为主、文字为辅" not in captured["user_prompt"]


def test_learn_description_in_history_meta(monkeypatch):
    """描述非空：用户历史消息 meta.description 落库；空描述不写该字段（旧数据兼容）"""
    calls = []

    def _spy_add_chat_message(agent, role, content, message_type, verdict="",
                              knowledge_id=None, meta=None):
        calls.append({"role": role, "meta": meta or {}})
        return len(calls)

    monkeypatch.setattr(agent_chat, "_extract_image_text", lambda *a, **k: "some text")
    monkeypatch.setattr(common, "agent_call", _fake_learn_extract())
    monkeypatch.setattr(repo, "add_chat_message", _spy_add_chat_message)

    agent_chat.learn_from_image("discover", b"x", "a.png", description="补充形态描述")
    user_calls = [c for c in calls if c["role"] == "user"]
    assert user_calls and user_calls[0]["meta"].get("description") == "补充形态描述"

    calls.clear()
    agent_chat.learn_from_image("discover", b"x", "a.png")
    user_calls = [c for c in calls if c["role"] == "user"]
    assert user_calls and "description" not in user_calls[0]["meta"]


def test_chat_learn_route_description(monkeypatch):
    """/agent-chat/learn：description Form 参数透传到任务参数；超 500 字返回 400"""
    import asyncio
    import os
    from io import BytesIO

    from fastapi import HTTPException, UploadFile

    from app.api.routes import chat_learn

    captured = {}

    def _fake_submit(kind, params):
        captured["kind"] = kind
        captured["params"] = params
        return {"task_id": "t", "kind": kind}

    monkeypatch.setattr("app.api.routes._submit_task", _fake_submit)

    result = asyncio.run(chat_learn(
        "discover", UploadFile(file=BytesIO(b"img"), filename="k.png"),
        description="放量突破形态"))
    assert captured["kind"] == "chat_learn"
    assert captured["params"]["description"] == "放量突破形态"
    assert result == {"task_id": "t", "kind": "chat_learn"}
    if captured["params"].get("tmp_path") and os.path.exists(captured["params"]["tmp_path"]):
        os.unlink(captured["params"]["tmp_path"])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(chat_learn(
            "discover", UploadFile(file=BytesIO(b"img"), filename="k.png"),
            description="x" * 501))
    assert exc.value.status_code == 400
    assert "上限 500" in exc.value.detail
