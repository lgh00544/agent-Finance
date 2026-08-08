"""
LLM 链路快速验证脚本:
1. 检查 .env 中 LLM 相关配置
2. 真实调用 DeepSeek(轻量模型 + 推理模型),验证结构化输出链路
用法: .venv/Scripts/python backend/scripts/llm_check.py
"""
import sys
import time

sys.path.insert(0, ".")

# Windows 控制台 GBK 编码兜底:避免中文/emoji 打印崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.structured import get_client, llm_call_json, ModelLevel, LLMError


class PingResult(BaseModel):
    """连通性测试返回"""
    message: str = Field(description="一句话说明你收到了什么测试内容")
    ok: bool = Field(description="是否正常")
    answer: int = Field(description="7*6 的答案")


def check_config() -> bool:
    print("=" * 50)
    print("1. 配置检查 (.env)")
    print("=" * 50)
    ok = True
    for label, val in [
        ("DEEPSEEK_API_KEY", settings.deepseek_api_key),
        ("DEEPSEEK_BASE_URL", settings.deepseek_base_url),
        ("DEEPSEEK_DEFAULT_MODEL", settings.deepseek_default_model),
        ("DEEPSEEK_REASONING_MODEL", settings.deepseek_reasoning_model),
    ]:
        if not val:
            print(f"  [缺失] {label}")
            ok = False
        else:
            print(f"  [OK]   {label} = {val[:6]}...{val[-4:] if len(val) > 10 else ''}")

    # 可选配置:仅提示,不阻塞主验证
    if not settings.siliconflow_api_key:
        print("  [提示] SILICONFLOW_API_KEY 未配置(仅影响 embedding/向量检索,DeepSeek 主链路不受影响)")
    else:
        print("  [OK]   SILICONFLOW_API_KEY 已配置")
    print(f"  [OK]   EMBEDDING_PROVIDER = {settings.embedding_provider}")
    return ok


def ping(level: ModelLevel, label: str) -> bool:
    print(f"\n  -> 调用 {label} 模型 [{level.value}] ...")
    t0 = time.time()
    try:
        result = llm_call_json(
            system_prompt="你是一个连通性测试助手。请用中文一句话回复,并计算数学题,输出 JSON 格式。",
            user_prompt="测试连通性:7*6等于多少?请按 JSON 结构输出。",
            schema=PingResult,
            max_tokens=200,
            model_level=level,
        )
        cost = time.time() - t0
        print(f"  [OK] {label} 调用成功,耗时 {cost:.1f}s")
        print(f"       message: {result.message}")
        print(f"       ok: {result.ok}, answer: {result.answer}")
        return result.answer == 42
    except LLMError as e:
        print(f"  [失败] {label}: {e}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  [异常] {label}: {type(e).__name__}: {e}")
        return False


def main() -> int:
    if not check_config():
        print("\n配置缺失,请先补齐 .env 后再试")
        return 1

    print("\n" + "=" * 50)
    print("2. 真实 LLM 调用验证")
    print("=" * 50)
    r1 = ping(ModelLevel.LIGHT, "轻量(默认)模型")
    r2 = ping(ModelLevel.DEEP, "推理模型")

    print("\n" + "=" * 50)
    if r1 and r2:
        print("结论:两个模型均可正常调用,LLM 链路正常 ✅")
        return 0
    if r1 or r2:
        print("结论:至少一个模型可用(部分失败) ⚠️")
        return 2
    print("结论:LLM 调用失败 ❌")
    return 3


if __name__ == "__main__":
    sys.exit(main())
