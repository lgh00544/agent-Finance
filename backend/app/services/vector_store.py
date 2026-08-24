"""
文本向量检索服务（Qdrant）
- 默认：本地文件模式 Qdrant（QDRANT_MODE=local），数据存 data/qdrant_storage，
  零外部服务、迁移直接复制目录；
- QDRANT_MODE=server 时可切外部 Qdrant 服务；
- Qdrant 不可用时自动降级 SQL LIKE 关键词检索（主链路不中断）。
新闻/公告原文存于数据库 news_article 表（真源），本模块仅做索引与检索。
【刚性代码逻辑】只负责存储与检索，检索结果交由 LLM 研判。
"""
import logging
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.db.models import NewsArticle, PrivateKnowledge
from app.db.session import SessionLocal
from app.llm.embedding import embed_texts

logger = logging.getLogger(__name__)

COLLECTION = "news_docs"


def _payload_ts(published_at: str) -> int:
    """新闻发布时间 → 秒时间戳（供保留期清理过滤）；无法解析返回 0（不参与清理）"""
    import datetime

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return int(datetime.datetime.strptime(str(published_at).strip()[:19], fmt).timestamp())
        except ValueError:
            continue
    return 0


class VectorStore:
    def __init__(self) -> None:
        self._client = None
        try:
            from qdrant_client import QdrantClient

            if settings.qdrant_mode == "server":
                self._client = QdrantClient(url=settings.qdrant_url)
            else:
                # 本地文件模式：嵌入式存储，数据落在 data/qdrant_storage
                path = settings.qdrant_path
                path.mkdir(parents=True, exist_ok=True)
                self._client = QdrantClient(path=str(path))
            self._ensure_collection()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant 不可用，降级 SQL 检索: %s", exc)
            self._client = None

    def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        # 向量维度跟随 embedding 模型：siliconflow=bge-m3(1024 维)，本地=bge-small-zh(512 维)
        target_dim = 1024 if settings.embedding_provider == "siliconflow" else 512

        collections = [c.name for c in self._client.get_collections().collections]
        if COLLECTION in collections:
            try:
                existing_dim = self._client.get_collection(COLLECTION).config.params.vectors.size
                if existing_dim != target_dim:
                    logger.warning(
                        "向量集合维度 %s 与当前 embedding 模型 %s 不匹配，删除重建（需重新索引）",
                        existing_dim, target_dim)
                    self._client.delete_collection(COLLECTION)
                    collections = [c.name for c in self._client.get_collections().collections]
            except Exception as exc:  # noqa: BLE001 查询失败不阻断，走创建流程
                logger.warning("向量集合维度检查失败: %s", exc)
        if COLLECTION not in collections:
            # 本地文件模式默认启用 INT8 标量量化压缩（qdrant_compression=true），减少磁盘占用；
            # qdrant-client 1.18.0 的 QuantizationType 导出缺失（类在 http.models 中），
            # 不支持时降级为不压缩创建集合（不阻断向量检索）；低版本无 compression 参数同理
            compression = None
            if settings.qdrant_compression:
                try:
                    from qdrant_client.models import (QuantizationType, ScalarQuantization,
                                                      ScalarQuantizationConfig)
                    compression = ScalarQuantization(
                        scalar=ScalarQuantizationConfig(type=QuantizationType.INT8,
                                                        always_ram=True, quantile=0.99))
                except ImportError:
                    logger.warning("qdrant-client 无 QuantizationType，跳过 INT8 压缩")
            create_kwargs: dict = {
                "collection_name": COLLECTION,
                "vectors_config": VectorParams(size=target_dim, distance=Distance.COSINE),
            }
            if compression is not None:
                create_kwargs["compression"] = compression
            try:
                self._client.create_collection(**create_kwargs)
            except TypeError:  # 旧版本无 compression 参数
                self._client.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
                )

    # ---------------- 索引 ----------------
    def index_news(self, code: str, articles: list[dict[str, Any]]) -> None:
        """将新闻/公告写入 Qdrant（news_article 表由调用方先行落库）"""
        if not articles or self._client is None:
            return
        try:
            texts = [f"{a.get('title', '')}\n{a.get('content', '')[:500]}" for a in articles]
            vectors, emb_model = embed_texts(texts)
            if self._client is None:
                return
            from qdrant_client.models import PointStruct

            points = []
            for idx, (article, vec) in enumerate(zip(articles, vectors)):
                points.append(PointStruct(
                    id=hash(f"{code}:{article.get('title', '')}:{idx}") % (2 ** 63),
                    vector=vec,
                    payload={"code": code, "title": article.get("title", ""),
                             "published_at": article.get("published_at", ""),
                             "emb_model": emb_model,
                             "ts": _payload_ts(article.get("published_at", ""))},
                ))
            self._client.upsert(collection_name=COLLECTION, points=points)
            logger.info("已索引 %s 条新闻: %s", len(points), code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("新闻索引失败（不影响主链路）: %s", exc)

    def cleanup_old_news(self, before_ts: float) -> int:
        """删除索引时间早于 before_ts（秒时间戳）的新闻索引（与 news_article 保留期同步）；
        Qdrant 不可用或调用失败时返回 0，不阻塞主链路"""
        if self._client is None:
            return 0
        try:
            from qdrant_client.models import FieldCondition, Filter, Range

            self._client.delete(
                collection_name=COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="ts", range=Range(gt=0, lt=before_ts))]
                ),
            )
            logger.info("已清理 %s 前的新闻索引", int(before_ts))
            return 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("新闻索引清理失败（不影响主链路）: %s", exc)
            return 0

    # ---------------- 检索 ----------------
    def search_related(self, code: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """按语义相似度检索该股票的相关新闻（Qdrant 不可用时 SQL LIKE 降级）"""
        if self._client is not None:
            try:
                vectors, emb_model = embed_texts([query])
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                hits = self._client.query_points(
                    collection_name=COLLECTION,
                    query=vectors[0],
                    limit=top_k,
                    query_filter=Filter(
                        must=[
                            FieldCondition(key="code", match=MatchValue(value=code)),
                            FieldCondition(key="emb_model", match=MatchValue(value=emb_model)),
                        ]
                    ),
                ).points
                return [{"title": h.payload.get("title", ""), "published_at": h.payload.get("published_at", "")}
                        for h in hits]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Qdrant 检索失败，降级 SQL LIKE: %s", exc)
        return self._search_sql(code, query, top_k)

    def _search_sql(self, code: str, query: str, top_k: int) -> list[dict[str, Any]]:
        """降级检索：标题关键词 LIKE（单用户低频场景足够）"""
        try:
            with SessionLocal() as db:
                keywords = [k for k in query.split() if len(k) > 1][:3]
                stmt = select(NewsArticle).where(NewsArticle.stock_code == code)
                if keywords:
                    like = [NewsArticle.title.contains(k) for k in keywords]
                    from sqlalchemy import or_

                    stmt = stmt.where(or_(*like))
                stmt = stmt.order_by(NewsArticle.published_at.desc()).limit(top_k)
                rows = db.execute(stmt).scalars().all()
                return [{"title": r.title, "published_at": r.published_at} for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("SQL 检索失败: %s", exc)
            return []


    # ---------------- 私有知识库检索（统一调教接口·统一运行机制） ----------------
    def search_knowledge(self, agent: str, top_k: int = 5) -> list[dict[str, Any]]:
        """检索私有交易经验/战法资料（Agent 任务启动时自动注入）。
        知识条目为人工录入的少量高价值资料，按 agent_tag（含通用 all）精确匹配
        + 关键词 LIKE，确定性检索 dev/prod 行为一致；失败不阻塞主链路。
        """
        try:
            from sqlalchemy import or_

            with SessionLocal() as db:
                stmt = (
                    select(PrivateKnowledge)
                    .where(or_(PrivateKnowledge.agent_tag == agent,
                               PrivateKnowledge.agent_tag == "all"))
                    .order_by(PrivateKnowledge.id.desc())
                    .limit(top_k)
                )
                rows = db.execute(stmt).scalars().all()
                # 返回带 id（决策级归因：命中计量 + 对话引用编号映射依赖 id 定位）
                return [{"id": r.id, "title": r.title, "content": r.content} for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("私有知识库检索失败: %s", exc)
            return []


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """单例：本地文件模式 Qdrant 对同一存储目录加锁，必须复用同一客户端"""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
