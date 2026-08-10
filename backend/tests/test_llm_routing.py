"""LLM 调用层优化测试：双模型分场景路由 + 降级重试 + 参数恒定 + Prompt 段序固定 + 调用统计
（用假客户端验证调用层自身，不测业务结论；不触网）"""
import time

from pydantic import BaseModel

from app.agents import common as common_mod
from app.llm import structured
from app.llm.structured import LLMError, ModelLevel, call_llm_cached, llm_call_json
from app.services import llm_stats as llm_stats_mod
from app.core.config import settings


class _Out(BaseModel):
    ok: bool = True


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, hit=0, miss=0, completion=0):
        self.prompt_cache_hit_tokens = hit
        self.prompt_cache_miss_tokens = miss
        self.completion_tokens = completion


class _FakeResponse:
    def __init__(self, content, usage=None):
        self.choices = [_FakeChoice(content)]
        self.usage = usage


class _FakeCompletions:
    def __init__(self, contents, usage=None):
        self.contents = list(contents)
        self.calls = []
        self.usage = usage

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self.contents.pop(0), usage=self.usage)


class _FakeChat:
    """模拟 openai 客户端 client.chat.completions.create 路径"""

    def __init__(self, contents, usage=None):
        self.completions = _FakeCompletions(contents, usage=usage)


class _FakeClient:
    def __init__(self, contents, usage=None):
        self.chat = _FakeChat(contents, usage=usage)


class _BoomChat:
    def __init__(self):
        self.completions = _BoomCompletions()


class _BoomClient:
    """所有调用抛错（模拟接口不可达/限流）"""

    def __init__(self):
        self.chat = _BoomChat()


class _BoomCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("接口不可达")


class _FlashFailThenOkChat:
    def __init__(self):
        self.completions = _FlashFailThenOk()


class _FlashFailThenOkClient:
    """flash 全部失败、chat 成功（验证降级路径）"""

    def __init__(self):
        self.chat = _FlashFailThenOkChat()

    @property
    def calls(self):
        return self.chat.completions.calls


class _FlashFailThenOk:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["model"] == settings.deepseek_default_model:
            raise RuntimeError("flash 限流")
        return _FakeResponse('{"ok": true}')


def _no_sleep(monkeypatch):
    monkeypatch.setattr(structured.time, "sleep", lambda s: None)


# ================= 模型路由与参数 =================

def test_light_routes_to_default_model(monkeypatch):
    client = _FakeClient(['{"ok": true}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    out = llm_call_json("sys", "user", _Out, model_level=ModelLevel.LIGHT)
    assert out.ok is True
    kw = client.chat.completions.calls[0]
    assert kw["model"] == settings.deepseek_default_model
    assert "reasoning_effort" not in kw  # flash 关闭推理相关参数
    assert kw["max_tokens"] == settings.deepseek_flash_max_tokens


def test_deep_routes_to_reasoning_model(monkeypatch):
    client = _FakeClient(['{"ok": true}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    llm_call_json("sys", "user", _Out, model_level=ModelLevel.DEEP)
    kw = client.chat.completions.calls[0]
    assert kw["model"] == settings.deepseek_reasoning_model
    assert kw["reasoning_effort"] == settings.reasoning_effort
    assert kw["max_tokens"] == settings.llm_max_tokens


def test_deep_is_default_level(monkeypatch):
    """默认场景等级 = 深度推理模型（保持既有调用语义不变）"""
    client = _FakeClient(['{"ok": true}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    llm_call_json("sys", "user", _Out)
    assert client.chat.completions.calls[0]["model"] == settings.deepseek_reasoning_model


def test_explicit_max_tokens_override(monkeypatch):
    client = _FakeClient(['{"ok": true}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    llm_call_json("sys", "user", _Out, max_tokens=1234, model_level=ModelLevel.LIGHT)
    assert client.chat.completions.calls[0]["max_tokens"] == 1234


# ================= 降级重试 =================

def test_light_falls_back_to_reasoning_model(monkeypatch):
    """flash 连续 3 次失败 → 自动降级 chat 重试成功，不阻塞主流程"""
    _no_sleep(monkeypatch)
    client = _FlashFailThenOkClient()
    monkeypatch.setattr(structured, "get_client", lambda: client)
    out = llm_call_json("sys", "user", _Out, model_level=ModelLevel.LIGHT)
    assert out.ok is True
    assert len(client.calls) == 4
    assert client.calls[3]["model"] == settings.deepseek_reasoning_model
    assert client.calls[3]["reasoning_effort"] == settings.reasoning_effort


def test_light_fallback_exhausted_raises(monkeypatch):
    """flash 与 chat 全部失败 → LLMError（flash 3 次 + chat 3 次）"""
    _no_sleep(monkeypatch)
    client = _BoomClient()
    monkeypatch.setattr(structured, "get_client", lambda: client)
    try:
        llm_call_json("sys", "user", _Out, model_level=ModelLevel.LIGHT)
        raise AssertionError("应抛 LLMError")
    except LLMError:
        assert len(client.chat.completions.calls) == 6


def test_deep_has_no_fallback(monkeypatch):
    """深度场景失败只重试本模型 3 次（与既有行为一致，不引入额外降级）"""
    _no_sleep(monkeypatch)
    client = _BoomClient()
    monkeypatch.setattr(structured, "get_client", lambda: client)
    try:
        llm_call_json("sys", "user", _Out)
        raise AssertionError("应抛 LLMError")
    except LLMError:
        assert len(client.chat.completions.calls) == 3


# ================= 结果缓存：双模型独立 =================

class _DictCache:
    def __init__(self):
        self.store = {}

    def get_llm_json(self, agent, key, ttl):
        return self.store.get(f"llm:{agent}:{key}")

    def set_llm_json(self, agent, key, value, ttl):
        self.store[f"llm:{agent}:{key}"] = value


def test_cached_results_isolated_by_model(monkeypatch):
    """同一 agent/key 不同模型各走各的缓存，互不干扰"""
    _no_sleep(monkeypatch)
    client = _FakeClient(['{"ok": true}', '{"ok": true}'])
    monkeypatch.setattr(structured, "get_client", lambda: client)
    monkeypatch.setattr(structured, "cache", _DictCache())

    call_llm_cached("agent_x", "k1", "sys", "user", _Out, model_level=ModelLevel.LIGHT)
    call_llm_cached("agent_x", "k1", "sys", "user", _Out, model_level=ModelLevel.LIGHT)  # 命中
    call_llm_cached("agent_x", "k1", "sys", "user", _Out, model_level=ModelLevel.DEEP)   # 另一模型
    assert len(client.chat.completions.calls) == 2  # 两次真实调用，第三次命中 light 缓存


# ================= Prompt 段序固定化 =================

class _Version:
    version = 7


def _patch_sections(monkeypatch, base="【基线】", rules="【规则】", profile="【偏好】",
                    knowledge="【知识】", tactic="【战法知识】", tactic_ver="aA1",
                    rule_ver="0:0"):
    monkeypatch.setattr(common_mod.repo, "get_trade_profile", lambda: _Version())
    monkeypatch.setattr(common_mod, "_knowledge_version", lambda: "k2:5")
    monkeypatch.setattr(common_mod, "_global_base_version", lambda: "gabc")
    monkeypatch.setattr(common_mod, "_rule_version", lambda: rule_ver)
    monkeypatch.setattr(common_mod, "global_base_prompt", lambda: base)
    monkeypatch.setattr(common_mod, "hard_rules_section", lambda: rules)
    monkeypatch.setattr(common_mod, "profile_section", lambda: profile)
    monkeypatch.setattr(common_mod, "knowledge_section", lambda agent: knowledge)
    monkeypatch.setattr(common_mod, "_agent_knowledge_text", lambda agent: tactic)
    monkeypatch.setattr(common_mod, "_agent_knowledge_version", lambda agent: tactic_ver)
    captured = {}

    def fake_call(agent, cache_key, system_prompt, user_prompt, schema,
                  ttl_seconds=86400, model_level=None):
        captured["sys"] = system_prompt
        captured["key"] = cache_key
        captured["level"] = model_level
        return _Out()

    monkeypatch.setattr(common_mod, "call_llm_cached", fake_call)
    return captured


def test_agent_call_section_order_fixed(monkeypatch):
    """段序永久固定：基线 → 硬性规则 → 偏好 → 私有知识库 → 战法知识库 → Agent 专属 Prompt"""
    captured = _patch_sections(monkeypatch)
    common_mod.agent_call("discover", "shortlist:v2:2026-08-04",
                          "【专属 Prompt】", "【动态数据】", _Out,
                          model_level=ModelLevel.LIGHT)
    assert captured["sys"] == ("【基线】\n\n【规则】\n\n"
                               "【用户个人交易偏好档案】（你的研判必须尊重用户这些偏好，"
                               "如有冲突需在输出中说明）\n【偏好】\n\n"
                               "【知识】\n\n"
                               "【分职能战法知识库】（沉淀自《潜力股发掘方法论》，全部条目为参考权重，"
                               "不是死条件；与硬性规则冲突时以硬性规则为准，动态调整须在输出中标注理由）\n"
                               "【战法知识】\n\n【专属 Prompt】")
    assert captured["key"] == "shortlist:v2:2026-08-04:v7:k2:5:ggabc:aA1:r0:0"
    assert captured["level"] is ModelLevel.LIGHT


def test_agent_call_optional_sections(monkeypatch):
    """关闭偏好/私有知识注入时对应段跳过（战法知识库为独立常驻段）；空基线不产生空段"""
    captured = _patch_sections(monkeypatch, base="")
    common_mod.agent_call("score", "k", "【专属 Prompt】", "u", _Out,
                          with_profile=False, with_knowledge=False)
    assert captured["sys"] == ("【规则】\n\n"
                               "【分职能战法知识库】（沉淀自《潜力股发掘方法论》，全部条目为参考权重，"
                               "不是死条件；与硬性规则冲突时以硬性规则为准，动态调整须在输出中标注理由）\n"
                               "【战法知识】\n\n【专属 Prompt】")
    captured = _patch_sections(monkeypatch)
    common_mod.agent_call("score", "k", "【专属 Prompt】", "u", _Out,
                          with_profile=False, with_knowledge=False)
    assert captured["sys"] == ("【基线】\n\n【规则】\n\n"
                               "【分职能战法知识库】（沉淀自《潜力股发掘方法论》，全部条目为参考权重，"
                               "不是死条件；与硬性规则冲突时以硬性规则为准，动态调整须在输出中标注理由）\n"
                               "【战法知识】\n\n【专属 Prompt】")


# ================= 调用统计 =================

class _DictStatsCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl_seconds):
        self.store[key] = value


def test_llm_stats_record_and_snapshot(monkeypatch):
    """当日累计：请求数/命中·未命中 token/命中率/模型分布/截止时间"""
    fake_cache = _DictStatsCache()
    monkeypatch.setattr(llm_stats_mod, "cache", fake_cache)
    monkeypatch.setattr(llm_stats_mod, "_key", lambda: "llm_stats:test")

    llm_stats_mod.record("deepseek-v4-flash", 100, 50, 10)
    llm_stats_mod.record("deepseek-chat", 0, 30, 20)
    llm_stats_mod.record("deepseek-v4-flash", 60, 20, 5)

    snap = llm_stats_mod.snapshot()
    assert snap["requests"] == 3
    assert snap["hit_tokens"] == 160 and snap["miss_tokens"] == 100
    assert snap["completion_tokens"] == 35
    assert snap["hit_rate_pct"] == 61.5  # 160/260
    assert snap["models"][0]["model"] == "deepseek-v4-flash"
    assert snap["models"][0]["calls"] == 2 and snap["models"][0]["pct"] == 66.7
    assert snap["models"][1]["calls"] == 1 and snap["models"][1]["pct"] == 33.3
    assert snap["date"] == time.strftime("%Y-%m-%d") and snap["checked_at"]


def test_llm_stats_empty_day(monkeypatch):
    fake_cache = _DictStatsCache()
    monkeypatch.setattr(llm_stats_mod, "cache", fake_cache)
    monkeypatch.setattr(llm_stats_mod, "_key", lambda: "llm_stats:none")
    snap = llm_stats_mod.snapshot()
    assert snap["requests"] == 0
    assert snap["hit_tokens"] == 0 and snap["hit_rate_pct"] is None
    assert snap["models"] == []


def test_llm_stats_records_from_response_usage(monkeypatch):
    """调用层每次成功响应自动记录服务端 usage；无 usage 字段不抛错"""
    _no_sleep(monkeypatch)
    usage = _FakeUsage(hit=200, miss=50, completion=30)
    client = _FakeClient(['{"ok": true}'], usage=usage)
    monkeypatch.setattr(structured, "get_client", lambda: client)
    monkeypatch.setattr(structured, "cache", _DictCache())
    fake_stats = _DictStatsCache()
    monkeypatch.setattr(llm_stats_mod, "cache", fake_stats)
    monkeypatch.setattr(llm_stats_mod, "_key", lambda: "llm_stats:usage")

    llm_call_json("sys", "user", _Out, model_level=ModelLevel.LIGHT)
    snap = llm_stats_mod.snapshot()
    assert snap["requests"] == 1
    assert snap["hit_tokens"] == 200 and snap["miss_tokens"] == 50
    assert snap["models"][0]["model"] == settings.deepseek_default_model
