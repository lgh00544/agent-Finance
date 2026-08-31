"""
DeepSeek 结构化输出封装（OpenAI 兼容端点）
- 双模型分场景路由：ModelLevel.LIGHT（轻量默认模型，高频低成本）/ ModelLevel.DEEP（深度推理模型，复杂研判）
- 强制 json_object 模式 + 固定请求参数（温度 0.3 / max_tokens / 输出 schema 恒定，利于服务端前缀缓存）
- pydantic 严格校验返回结构，最多 3 次重试，校验错误拼回 prompt 让模型修正
- LIGHT 3 次失败自动降级为 DEEP 重试（不阻塞主流程）；重试/降级均按模型独立记录统计
【刚性代码逻辑】只负责调用与结构校验，不参与任何市场研判内容。
"""
import logging
import time
from enum import Enum
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.cache import cache
from app.core.config import settings
from app.services import llm_stats

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """LLM 调用失败（重试与降级均耗尽）"""


class ModelLevel(str, Enum):
    """场景等级 → 模型映射（调用层自动匹配，业务代码零感知）"""
    LIGHT = "light"  # 高频轻量：Discover 初筛 / Monitor 盘中巡检 / 告警生成等
    DEEP = "deep"    # 深度复杂：市况评分 / 最终候选确认 / 五维打分 / 建仓 / 卖出 / 复盘 / 重思考


def _model_for(level: ModelLevel) -> str:
    if level is ModelLevel.LIGHT:
        return settings.deepseek_default_model
    return settings.deepseek_reasoning_model


def _max_tokens_for(level: ModelLevel, max_tokens: int | None) -> int:
    """flash 自动适配小预算（无思考预留）；推理模型用 LLM_MAX_TOKENS 防大表 JSON 截断"""
    if max_tokens is not None:
        return max_tokens
    if level is ModelLevel.LIGHT:
        return settings.deepseek_flash_max_tokens
    return settings.llm_max_tokens


def get_client() -> OpenAI:
    if not settings.deepseek_api_key:
        raise LLMError("未配置 DEEPSEEK_API_KEY，请在 .env 中填写")
    return OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def _chat_once(client: OpenAI, model: str, system_prompt: str, user_content: str,
               max_tokens: int, reasoning_effort: str | None) -> str:
    """单次调用：参数恒定（json_object / 温度 0.3）；推理模型附 reasoning_effort，flash 不传推理参数"""
    kwargs = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,  # 决策分析保持适度确定性
    }
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    resp = client.chat.completions.create(**kwargs)

    usage = getattr(resp, "usage", None)
    llm_stats.record(
        model,
        getattr(usage, "prompt_cache_hit_tokens", None) if usage else None,
        getattr(usage, "prompt_cache_miss_tokens", None) if usage else None,
        getattr(usage, "completion_tokens", None) if usage else None,
    )
    return resp.choices[0].message.content or ""


def llm_call_json(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    max_tokens: int | None = None,
    model_level: ModelLevel = ModelLevel.DEEP,
) -> T:
    """调用 DeepSeek 并返回校验通过的结构化结果。

    重试机制：解析/校验失败时，把错误信息拼回下一轮 prompt 要求修正；
    LIGHT 模型连续 3 次失败自动降级为 DEEP（推理模型）重试，不阻塞主流程。
    """
    level = model_level if isinstance(model_level, ModelLevel) else ModelLevel(model_level)
    max_tokens = _max_tokens_for(level, max_tokens)
    client = get_client()
    if "json" not in f"{system_prompt}\n{user_prompt}".lower():
        system_prompt = f"{system_prompt}\n\n输出必须是合法 JSON 对象，不要输出 JSON 之外的任何文字。"

    # 尝试序列：轻量场景 = flash×3 → 降级 chat×3；深度场景 = chat×3
    attempts = [(settings.deepseek_reasoning_model, settings.reasoning_effort)] * 3
    if level is ModelLevel.LIGHT:
        attempts = [(settings.deepseek_default_model, None)] * 3 + attempts

    user_content = user_prompt
    for idx, (model, reasoning_effort) in enumerate(attempts):
        if idx == 3:
            logger.warning("轻量模型 %s 连续 3 次失败，降级为推理模型 %s 重试",
                           settings.deepseek_default_model, settings.deepseek_reasoning_model)
        try:
            content = _chat_once(client, model, system_prompt, user_content,
                                 max_tokens, reasoning_effort)
            if not content.strip():
                raise ValidationError("空响应", [])  # noqa: F821 手动触发重试
            return schema.model_validate_json(content)
        except ValidationError as ve:
            logger.warning("LLM 输出校验失败（第 %d 次）: %s", idx + 1, str(ve)[:300])
            user_content = (
                f"你上次的输出不符合要求的 JSON 结构，错误信息如下，请修正后重新输出：\n"
                f"{str(ve)[:500]}\n\n原任务：\n{user_prompt}"
            )
        except Exception as exc:  # noqa: BLE001 openai 异常类型多
            logger.warning("LLM 调用失败（第 %d 次）: %s", idx + 1, exc)
            if idx % 3 < 2:
                time.sleep(2 ** (idx % 3))

    raise LLMError(
        f"LLM 结构化输出全部尝试均失败（level={level.value}，"
        f"system_prompt={system_prompt[:30]}）")


def call_llm_cached(agent: str, cache_key: str, system_prompt: str, user_prompt: str,
                    schema: Type[T], ttl_seconds: int = 86400,
                    model_level: ModelLevel = ModelLevel.DEEP) -> T:
    """带缓存的结构化 LLM 调用：同一标的当日同 Agent 结果复用，节约 API 开销。
    cache_key 需包含标识参数（如 code:date）；monitor 用短 TTL 保证盘中时效。
    缓存键含模型名：双模型独立缓存，互不干扰。"""
    level = model_level if isinstance(model_level, ModelLevel) else ModelLevel(model_level)
    model = _model_for(level)
    cache_agent = f"{agent}:{model}"
    cached = cache.get_llm_json(cache_agent, cache_key, ttl_seconds)
    if cached is not None:
        logger.info("LLM 缓存命中: %s/%s", cache_agent, cache_key)
        return schema.model_validate(cached)
    result = llm_call_json(system_prompt, user_prompt, schema, model_level=level)
    cache.set_llm_json(cache_agent, cache_key, result.model_dump(), ttl_seconds)
    return result
