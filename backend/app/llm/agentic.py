"""ReAct 智能体研判环(只读工具版 PoC)。

把「代码一次打包数据 → 单发 LLM」换成「模型反复 观察→调工具→推理, 证据充分后输出 pydantic schema」。
不修改既有 structured.py 单发链路, 作为可选项接入; 工具由调用方传入(只读), 环本身不做任何对外写操作。

用法参考 scripts/agentic_poc.py。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.llm.structured import ModelLevel, _max_tokens_for, get_client

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def _truncate(text: str, limit: int = 2000) -> str:
    if text is None:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[:limit] + f"...(截断, 共{len(text)}字符)"


def run_agentic_judge(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    tools: list[dict],
    tool_funcs: dict[str, Callable],
    max_rounds: int = 8,
    max_tokens: int | None = None,
    model_level: ModelLevel = ModelLevel.DEEP,
) -> tuple[T | None, dict]:
    """执行 ReAct 循环。

    - tools: OpenAI function 定义列表(只读工具的 JSON schema)
    - tool_funcs: name -> 可调用只读函数(异常由调用方包装, 环不做写操作)
    - 无工具调用的一轮 => 视为最终输出, 按 schema 校验; 失败把错误拼回并继续

    返回 (校验通过的结果 | None, 过程日志)。过程日志含 thinking/tool/final 步骤, 可直接展示。
    """
    client = get_client()
    model = (settings.deepseek_reasoning_model if model_level is ModelLevel.DEEP
             else settings.deepseek_default_model)
    reasoning_effort = settings.reasoning_effort if model_level is ModelLevel.DEEP else None
    budget = _max_tokens_for(model_level, max_tokens)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    trace: list[dict] = []
    last_error: str | None = None

    for round_no in range(1, max_rounds + 1):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": budget,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 openai 异常类型多
            logger.warning("agentic 第 %d 轮调用失败: %s", round_no, exc)
            return None, {"rounds": round_no, "ok": False,
                          "error": f"LLM 调用失败: {exc}", "trace": trace}

        msg = resp.choices[0].message
        thinking = getattr(msg, "reasoning_content", None) or ""
        if thinking:
            trace.append({"round": round_no, "kind": "thinking", "text": _truncate(thinking, 800)})

        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ]})
            for tc in tool_calls:
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                fn = tool_funcs.get(fn_name)
                if fn is None:
                    result: Any = {"error": f"未知工具: {fn_name}"}
                else:
                    try:
                        result = fn(**args)
                    except Exception as exc:  # noqa: BLE001 工具异常不中断
                        result = {"error": f"工具执行失败: {exc}"}
                result_text = _truncate(json.dumps(result, ensure_ascii=False, default=str), 3000)
                trace.append({"round": round_no, "kind": "tool", "tool": fn_name, "args": args,
                              "result": _truncate(result_text, 1200)})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})
            continue

        # 无工具调用 => 最终 JSON
        content = (msg.content or "").strip()
        if not content:
            last_error = "空响应"
            messages.append({"role": "user", "content": "你的输出为空, 请重新输出最终 JSON。"})
            continue
        try:
            obj = schema.model_validate_json(content)
            trace.append({"round": round_no, "kind": "final", "content": _truncate(content, 300)})
            return obj, {"rounds": round_no, "ok": True, "trace": trace}
        except ValidationError as ve:
            last_error = str(ve)[:500]
            messages.append({"role": "user", "content":
                             f"你的输出不符合要求的 JSON 结构, 错误信息: {last_error}\n"
                             f"请直接输出符合 schema 的最终 JSON(不要再调用工具)。"})
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:300]
            messages.append({"role": "user", "content": f"输出解析失败: {last_error}\n请直接输出最终 JSON。"})

    return None, {"rounds": max_rounds, "ok": False,
                  "error": f"达到最大轮数, 未产出合法结果; 最后错误: {last_error}", "trace": trace}