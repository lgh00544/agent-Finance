"""
DeepSeek 结构化输出封装（OpenAI 兼容端点）
- 强制 json_object 模式
- pydantic 严格校验返回结构
- 最多 3 次重试，校验错误拼回 prompt 让模型修正
【刚性代码逻辑】只负责调用与结构校验，不参与任何市场研判内容。
"""
import logging
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """LLM 调用失败（重试耗尽）"""


def call_llm_cached(agent: str, cache_key: str, system_prompt: str, user_prompt: str,
                    schema: Type[T], ttl_seconds: int = 86400) -> T:
    """带缓存的结构化 LLM 调用：同一标的当日同 Agent 结果复用，节约 API 开销。
    cache_key 需包含标识参数（如 code:date）；monitor 用短 TTL 保证盘中时效。"""
    cached = cache.get_llm_json(agent, cache_key, ttl_seconds)
    if cached is not None:
        logger.info("LLM 缓存命中: %s/%s", agent, cache_key)
        return schema.model_validate(cached)
    result = llm_call_json(system_prompt, user_prompt, schema)
    cache.set_llm_json(agent, cache_key, result.model_dump(), ttl_seconds)
    return result


def get_client() -> OpenAI:
    if not settings.deepseek_api_key:
        raise LLMError("未配置 DEEPSEEK_API_KEY，请在 .env 中填写")
    return OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def llm_call_json(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    max_tokens: int | None = None,
) -> T:
    """调用 DeepSeek 并返回校验通过的结构化结果。

    重试机制：解析/校验失败时，把错误信息拼回下一轮 prompt 要求修正。
    """
    client = get_client()
    max_tokens = max_tokens or settings.llm_max_tokens
    user_content = user_prompt

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=settings.deepseek_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=0.3,  # 决策分析保持适度确定性
            )
            content = resp.choices[0].message.content or ""
            if not content.strip():
                raise ValidationError("空响应", [])  # noqa: F821 手动触发重试
            return schema.model_validate_json(content)
        except ValidationError as ve:
            logger.warning("LLM 输出校验失败（第 %d 次）: %s", attempt + 1, str(ve)[:300])
            user_content = (
                f"你上次的输出不符合要求的 JSON 结构，错误信息如下，请修正后重新输出：\n"
                f"{str(ve)[:500]}\n\n原任务：\n{user_prompt}"
            )
        except Exception as exc:  # noqa: BLE001 openai 异常类型多
            logger.warning("LLM 调用失败（第 %d 次）: %s", attempt + 1, exc)
            if attempt < 2:
                import time

                time.sleep(2 ** attempt)

    raise LLMError(f"LLM 结构化输出 3 次尝试均失败（agent={system_prompt[:30]}）")
