"""LLM 结构化解析层测试：pydantic 校验 + 重试机制（用假客户端验证解析层自身，不测业务结论）"""
import pytest
from pydantic import BaseModel

from app.llm import structured
from app.llm.structured import LLMError, llm_call_json


class _Out(BaseModel):
    stock_code: str
    reason: str


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self.contents.pop(0))


class _FakeChat:
    def __init__(self, contents):
        self.completions = _FakeCompletions(contents)


class _FakeClient:
    def __init__(self, contents):
        self.chat = _FakeChat(contents)


def _fake_client(contents):
    return _FakeClient(contents)


def test_valid_json_first_try(monkeypatch):
    client = _fake_client(['{"stock_code": "600001", "reason": "量能放大"}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    out = llm_call_json("sys", "user", _Out)
    assert out.stock_code == "600001"
    assert out.reason == "量能放大"
    assert len(client.chat.completions.calls) == 1


def test_invalid_then_valid_retries(monkeypatch):
    client = _fake_client([
        "这不是 JSON",
        '{"stock_code": "600002", "reason": "修复后的理由"}',
    ])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    out = llm_call_json("sys", "原始任务", _Out)
    assert out.stock_code == "600002"
    calls = client.chat.completions.calls
    assert len(calls) == 2
    # 重试时错误信息应拼回 user prompt 要求模型修正
    assert "修正" in calls[1]["messages"][-1]["content"]
    assert "原始任务" in calls[1]["messages"][-1]["content"]


def test_schema_mismatch_triggers_retry(monkeypatch):
    """结构合法但缺少必填字段 → 校验失败 → 重试"""
    client = _fake_client([
        '{"stock_code": "600003"}',
        '{"stock_code": "600003", "reason": "补充说明"}',
    ])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    out = llm_call_json("sys", "user", _Out)
    assert out.stock_code == "600003"
    assert len(client.chat.completions.calls) == 2


def test_empty_content_retries(monkeypatch):
    client = _fake_client(["", '{"stock_code": "600004", "reason": "ok"}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    out = llm_call_json("sys", "user", _Out)
    assert out.stock_code == "600004"
    assert len(client.chat.completions.calls) == 2


def test_three_failures_raise_llm_error(monkeypatch):
    client = _fake_client(["坏1", "坏2", "坏3"])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    with pytest.raises(LLMError):
        llm_call_json("sys", "user", _Out)
    assert len(client.chat.completions.calls) == 3


def test_missing_api_key_raises():
    """未配置 DEEPSEEK_API_KEY 时应给出清晰错误，而非神秘崩溃"""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(structured.settings, "deepseek_api_key", "")
    with pytest.raises(LLMError, match="DEEPSEEK_API_KEY"):
        structured.get_client()
    monkeypatch.undo()
