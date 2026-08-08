"""本地 embedding 验证 + 已有新闻补索引"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from app.db.session import engine
from app.llm.embedding import embed_texts
from app.services.vector_store import get_vector_store


def main() -> None:
    print("=" * 50)
    print("1. 本地 embedding 基础验证")
    print("=" * 50)
    vecs, model = embed_texts(["测试文本", "股票新闻"])
    print(f"  [OK] model={model}, {len(vecs)} 条 x {len(vecs[0])} 维")
    assert len(vecs[0]) == 512, f"预期 512 维,实际 {len(vecs[0])}"

    print("\n" + "=" * 50)
    print("2. 为已有新闻补向量索引(Qdrant)")
    print("=" * 50)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT stock_code, title, content FROM news_article ORDER BY id")).fetchall()
    print(f"  待索引新闻 {len(rows)} 条")
    if not rows:
        return
    store = get_vector_store()
    if store is None:
        print("  [失败] Qdrant 客户端不可用")
        return
    by_code: dict[str, list[dict]] = {}
    for r in rows:
        by_code.setdefault(r.stock_code, []).append(
            {"title": r.title, "content": r.content or ""})
    total = 0
    for code, articles in by_code.items():
        store.index_news(code, articles)
        total += len(articles)
    print(f"  [OK] 已索引 {total} 条(覆盖 {len(by_code)} 只股票)")

    print("\n" + "=" * 50)
    print("3. 语义检索验证(用一条真实新闻查询)")
    print("=" * 50)
    with engine.connect() as conn:
        q = conn.execute(text(
            "SELECT stock_code, title, content FROM news_article LIMIT 1")).fetchone()
    query = f"{q.title} {q.content[:200]}"
    hits = store.search_related(q.stock_code, query, top_k=3)
    print(f"  查询: {q.title[:40]}")
    print(f"  [OK] 检索到 {len(hits)} 条相关结果")
    for h in hits:
        print(f"    - {str(h.get('title', ''))[:50]}")


if __name__ == "__main__":
    main()
