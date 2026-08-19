"""
MiniMax M3 可选多模态能力调用层（默认关闭，零开销）

【职责边界】只做两件事：
1. 通用图片理解接口 analyze_image(图片字节, 文本指令) → 模型文本输出，
   当前供持仓截图 OCR 识别（MINIMAX_OCR_ENABLE=true 时启用），
   后续 K 线图形态研判 / 技术形态识别 / 财报截图解析等场景直接复用，无需重构调用框架；
2. 引擎装配：默认关闭返回 None（不加载任何依赖、不发起任何请求），
   开启后惰性装配 MiniMax M3（官方 OpenAI 兼容 /v1/chat/completions 端点）。

业务代码不直接依赖 MiniMax 原生 SDK：更换多模态模型只需新增实现类并修改工厂装配，
上层只感知 MultimodalClient 协议。识别结果一律由上层转为结构化字段，可落库参与后续
Agent 研判；本层不做任何市场判断。
"""
import base64
import logging
import threading
import time
from typing import Protocol, runtime_checkable

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI 兼容 Chat Completions 路径（MINIMAX_BASE_URL 已含 /v1）
_CHAT_PATH = "/chat/completions"
# 官方单张图片上限 10MB（与 OCR 服务上限一致）
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_TIMEOUT = 15                      # 请求超时（与数据源层一致）
_RETRY_DELAYS = (1.5, 3.0)         # 指数退避重试（网络/服务端瞬时故障自愈）
_MAX_TOKENS_DEFAULT = 2048         # 默认最大输出 token


def _guess_mime(image_bytes: bytes) -> str:
    """按文件头猜测图片 MIME（MiniMax 官方支持 JPEG/PNG/GIF/WEBP）"""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"  # 兜底：未支持格式（如 BMP）由上层回退本地 PaddleOCR


@runtime_checkable
class MultimodalClient(Protocol):
    """多模态引擎统一接口：图片 + 文本指令 → 文本输出（K线/财报等新场景直接复用）"""

    def analyze_image(self, image_bytes: bytes, prompt: str,
                      max_tokens: int = _MAX_TOKENS_DEFAULT) -> str: ...


class MiniMaxClient:
    """MiniMax M3 实现：官方 OpenAI 兼容端点，base64 内联图片输入

    失败抛 RuntimeError（中文信息），由上层回退下一引擎，不阻塞业务流程。
    """

    def __init__(self) -> None:
        if not settings.minimax_api_key:
            raise RuntimeError("MiniMax 密钥未配置：请在 .env 设置 MINIMAX_API_KEY 后重启后端")

    def analyze_image(self, image_bytes: bytes, prompt: str,
                      max_tokens: int = _MAX_TOKENS_DEFAULT) -> str:
        """发送图片 + 指令 → 返回模型文本输出"""
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise RuntimeError(
                f"图片过大（{len(image_bytes) / 1024 / 1024:.1f}MB），"
                f"多模态识别上限 {MAX_IMAGE_BYTES // 1024 // 1024}MB")
        url = f"{settings.minimax_base_url.rstrip('/')}{_CHAT_PATH}"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": settings.minimax_model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{_guess_mime(image_bytes)};base64,{b64}"}},
            ]}],
            "max_tokens": max_tokens,
            # 结构化提取直接作答，关闭思考以缩短响应时间
            "thinking": {"type": "disabled"},
        }
        headers = {"Authorization": f"Bearer {settings.minimax_api_key}"}
        last_err: Exception | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS, 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                return str(data["choices"][0]["message"]["content"])
            except Exception as exc:  # noqa: BLE001 网络/服务端/格式异常统一重试
                last_err = exc
                logger.warning("MiniMax 多模态请求第 %d 次失败: %s", attempt, exc)
                if attempt < len(_RETRY_DELAYS):
                    time.sleep(delay)
        raise RuntimeError(f"MiniMax 多模态请求失败: {last_err}")

    def chat_text(self, system: str, user: str, max_tokens: int = 2048) -> tuple[str, dict]:
        """纯文本 chat（无 image 字段）：供经验沉淀 Worker 等文本抽取场景复用 MiniMax-M3。

        复用 _CHAT_PATH/_TIMEOUT/_RETRY_DELAYS（1.5s/3.0s 指数退避）；
        先带 response_format=json_object 请求，若 API 返回 400 说明不支持该参数，
        捕获后去掉 response_format 重试一次（普通文本）；返回 (content, usage_dict) 供成本统计。
        失败抛 RuntimeError（中文信息），由上层降级。"""
        url = f"{settings.minimax_base_url.rstrip('/')}{_CHAT_PATH}"
        headers = {"Authorization": f"Bearer {settings.minimax_api_key}"}
        base_payload = {
            "model": settings.minimax_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "thinking": {"type": "disabled"},
        }
        last_err: Exception | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS, 1):
            try:
                payload = {**base_payload, "response_format": {"type": "json_object"}}
                resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
                if resp.status_code == 400:
                    # 不支持 response_format：去参重试一次（普通文本）
                    logger.warning("MiniMax 文本请求 response_format 400，去掉重试（第 %d 次）", attempt)
                    resp = requests.post(url, json=base_payload, headers=headers, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                content = str(data["choices"][0]["message"]["content"])
                usage = data.get("usage") or {}
                usage_dict = {
                    "prompt_tokens": usage.get("prompt_tokens") or 0,
                    "completion_tokens": usage.get("completion_tokens") or 0,
                    "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
                }
                return content, usage_dict
            except Exception as exc:  # noqa: BLE001 网络/服务端/格式异常统一重试
                last_err = exc
                logger.warning("MiniMax 文本请求第 %d 次失败: %s", attempt, exc)
                if attempt < len(_RETRY_DELAYS):
                    time.sleep(delay)
        raise RuntimeError(f"MiniMax 文本请求失败: {last_err}")


_client: MiniMaxClient | None = None
_client_lock = threading.Lock()


def get_multimodal_client() -> MultimodalClient | None:
    """多模态引擎工厂：默认关闭返回 None（零开销）；启用后惰性装配 MiniMax"""
    global _client
    if not settings.minimax_enable:
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                if not settings.minimax_api_key:
                    logger.warning("MINIMAX_ENABLE=true 但未配置 MINIMAX_API_KEY，多模态能力不可用")
                    return None
                _client = MiniMaxClient()
    return _client
