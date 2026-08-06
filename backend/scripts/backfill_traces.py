"""推理留痕历史数据一次性回填：从存量业务表组装 ai_reasoning_trace 记录（只增不改原表）。

用法（在 backend 目录）: python scripts/backfill_traces.py
幂等：同 code+generate_date+source_module 由 upsert 语义覆盖，可重复执行。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 项目根：agent_prompts/ 所在

from sqlalchemy import func, select  # noqa: E402

from app.db.models import (  # noqa: E402
    AiReasoningTrace, AlertLog, PositionPlan, ReviewResult, SellDecision,
    StockCandidate, StockScore,
)
from app.db.session import SessionLocal  # noqa: E402
from app.services import reasoning_trace  # noqa: E402


def _date_of(value) -> str:
    return str(value)[:10] if value else ""


def backfill() -> dict:
    counts = {"discover": 0, "score": 0, "position": 0, "alert": 0, "review": 0, "sell": 0}
    with SessionLocal() as db:
        for row in db.execute(select(StockCandidate)).scalars().all():
            reasoning_trace.trace_candidate(
                row.stock_code, row.stock_name or "", row.trade_date,
                row.reasons or [], row.risk_notice or [], row.snapshot or {},
                row.detail or {}, row.created_at)
            counts["discover"] += 1
        for row in db.execute(select(StockScore)).scalars().all():
            reasoning_trace.trace_score(
                row.stock_code, row.stock_name or "", row.trade_date,
                row.score, row.grade or "", row.detail or {}, row.risk_list or [])
            counts["score"] += 1
        for row in db.execute(select(PositionPlan)).scalars().all():
            reasoning_trace.trace_plan(
                row.stock_code, row.stock_name or "", row.plan_date, row.total_pct,
                row.batches or [], row.stop_loss, row.take_profit,
                row.rationale or "", row.id)
            counts["position"] += 1
        for row in db.execute(select(AlertLog)).scalars().all():
            reasoning_trace.trace_alert(
                row.stock_code, row.stock_name or "", _date_of(row.created_at),
                row.alert_type or "", row.severity or "", row.message or "",
                row.action or "", row.signal or {})
            counts["alert"] += 1
        for row in db.execute(select(ReviewResult)).scalars().all():
            reasoning_trace.trace_review(
                row.stock_code, row.stock_name or "", row.exit_date,
                row.plan_vs_actual or {}, row.lesson or "", row.feedback or {})
            counts["review"] += 1
        for row in db.execute(select(SellDecision)).scalars().all():
            reasoning_trace.trace_sell(
                row.stock_code, row.stock_name or "", _date_of(row.created_at),
                row.decision or {})
            counts["sell"] += 1
    reasoning_trace.flush()  # 队列内全部同步落库
    return counts


if __name__ == "__main__":
    print("开始回填推理留痕历史数据...")
    result = backfill()
    print("回填完成: %s" % result)
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(AiReasoningTrace)) or 0
    print("ai_reasoning_trace 现有总量: %d 条" % total)
