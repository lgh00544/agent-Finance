"""
文本向量化封装
- 默认：硅基流动 SiliconCloud BAAI/bge-m3（免费 API，OpenAI 兼容端点）
- 降级：本地 sentence-transformers bge-small-zh-v1.5（离线可用，首次需下载模型）
返回 (vectors, emb_model)，调用方必须把 emb_model 写入向量库 payload，
查询时按同一模型过滤，防止维度不一致导致召回失效。
【刚性代码逻辑】仅负责向量计算。
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _embed_siliconflow(texts: list[str]) -> tuple[list[list[float]], str]:
    from openai import OpenAI

    if not settings.siliconflow_api_key:
        raise RuntimeError("未配置 SILICONFLOW_API_KEY")

    client = OpenAI(api_key=settings.siliconflow_api_key, base_url=settings.siliconflow_base_url)
    resp = client.embeddings.create(model=settings.siliconflow_embedding_model, input=texts)
    vectors = [item.embedding for item in resp.data]
    # 按输入顺序重排（API 可能乱序返回）
    vectors = [v for _, v in sorted(zip([item.index for item in resp.data], vectors))]
    return vectors, settings.siliconflow_embedding_model


_model = None


def _embed_local(texts: list[str]) -> tuple[list[list[float]], str]:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.local_embedding_model)
    return _model.encode(texts, normalize_embeddings=True).tolist(), settings.local_embedding_model


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    """返回 (向量列表, 模型标识)。siliconflow 失败自动降级本地。"""
    if not texts:
        return [], settings.siliconflow_embedding_model
    if settings.embedding_provider == "siliconflow":
        try:
            return _embed_siliconflow(texts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("硅基流动 embedding 失败，降级本地模型: %s", exc)
    try:
        return _embed_local(texts)
    except ImportError:
        raise RuntimeError(
            "本地 embedding 需要 sentence-transformers：pip install sentence-transformers")
