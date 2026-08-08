"""查看最近候选池与评分明细,验证挖掘结果质量"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from app.db.session import engine


def main() -> None:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT stock_code, stock_name, rank, reasons, risk_notice FROM stock_candidate "
            "ORDER BY rank LIMIT 20")).fetchall()
        print(f"== 候选池 {len(rows)} 只 ==")
        for r in rows:
            print(f"  #{r.rank} {r.stock_code} {r.stock_name}")
            print(f"      理由: {str(r.reasons)[:80]}")
            print(f"      风险: {str(r.risk_notice)[:60]}")

        scores = conn.execute(text(
            "SELECT stock_code, stock_name, score, grade, detail, risk_list "
            "FROM stock_score ORDER BY score DESC LIMIT 20")).fetchall()
        print(f"\n== 评分 {len(scores)} 只 ==")
        for s in scores:
            print(f"  {s.stock_code} {s.stock_name}: 总分{s.score} 等级{s.grade} "
                  f"风险: {str(s.risk_list)[:60]}")
            print(f"      detail: {str(s.detail)[:100]}")

        cond = conn.execute(text(
            "SELECT trade_date, total_score, summary FROM market_condition ORDER BY id DESC LIMIT 1")).fetchone()
        if cond:
            print(f"\n== 市况 ==\n  {cond.trade_date} 评分{cond.total_score}: {str(cond.summary)[:100]}")

        news = conn.execute(text(
            "SELECT COUNT(DISTINCT stock_code) FROM news_article")).scalar()
        print(f"\n== 新闻 ==\n  共覆盖 {news} 只股票(总数 {conn.execute(text('SELECT COUNT(*) FROM news_article')).scalar()} 条)")


if __name__ == "__main__":
    main()
