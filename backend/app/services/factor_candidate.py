"""候选因子池：提议、样本外验证与人工状态切换。"""
from statistics import mean

from sqlalchemy import select

from app.agents import candidate_factor_proposer as proposer
from app.db.models import FactorCandidate
from app.db.session import SessionLocal
from app.services import factor_ic
from app.services.factor_registry import FactorDef

MAX_ACTIVE = 30


def _row(row: FactorCandidate) -> dict:
    return {column.name: getattr(row, column.name) for column in FactorCandidate.__table__.columns}


def _find(db, candidate_id: str | int) -> FactorCandidate | None:
    value = str(candidate_id)
    row = db.scalar(select(FactorCandidate).where(FactorCandidate.candidate_id == value))
    if row is None and value.isdigit():
        row = db.get(FactorCandidate, int(value))
    return row


def _next_id(used: set[str]) -> str:
    numbers = [int(item[2:]) for item in used if item.startswith("fc") and item[2:].isdigit()]
    number = max(numbers, default=0) + 1
    while f"fc{number:02d}" in used:
        number += 1
    return f"fc{number:02d}"


def propose(context: str = "", limit: int = 5) -> list[dict]:
    """调用 LLM 生成候选，全部以 pending 落库。"""
    output = proposer.propose_candidates(context, limit)
    with SessionLocal() as db:
        used = set(db.scalars(select(FactorCandidate.candidate_id)).all())
        rows = []
        for item in output.candidates[:5]:
            candidate_id = (item.candidate_id or "").strip()[:32]
            if not candidate_id or candidate_id in used:
                candidate_id = _next_id(used)
            used.add(candidate_id)
            rows.append(FactorCandidate(
                candidate_id=candidate_id, name=item.name[:64], category=item.category[:16],
                hypothesis=item.hypothesis, formula=item.formula,
                data_requirements=item.data_requirements, expected_edge=item.expected_edge,
                risk_note=item.risk_note, status="pending"))
        db.add_all(rows)
        db.commit()
        return [_row(row) for row in rows]


def validate(candidate_id: str | int, month_records: dict[str, list[dict]] | None = None) -> dict:
    """取最近 24 个月样本外回测，结果只写验证字段。"""
    with SessionLocal() as db:
        row = _find(db, candidate_id)
        if row is None:
            raise ValueError(f"候选因子不存在: {candidate_id}")
        periods = sorted(month_records or {})[-24:]
        if not periods:
            result = {"status": "insufficient_data", "periods": 0, "rows": 0}
        else:
            definition = FactorDef(
                id=row.candidate_id, name=row.name, category=row.category
                if row.category in {"动量", "催化", "估值", "资金", "质量", "主线"} else "主线",
                func=lambda *_: None, has_quantile=False, weight_hint=0.0)
            results = factor_ic.run_backtest({key: month_records[key] for key in periods}, [definition])
            ics = [item["ic"] for item in results if item["ic"] is not None]
            result = {
                "status": "validated" if results else "insufficient_data",
                "periods": len(periods), "rows": len(results),
                "mean_ic": round(mean(ics), 6) if ics else None,
                "ir": results[-1].get("ir") if results else None,
            }
        row.validation_result = result
        db.commit()
        return {"candidate_id": row.candidate_id, **result}


def enable(candidate_id: str | int) -> dict:
    """人工启用候选，硬性限制同时 active 不超过 30 个。"""
    with SessionLocal() as db:
        row = _find(db, candidate_id)
        if row is None:
            raise ValueError(f"候选因子不存在: {candidate_id}")
        if row.status == "active":
            return _row(row)
        active = db.scalars(select(FactorCandidate).where(FactorCandidate.status == "active")).all()
        if len(active) >= MAX_ACTIVE:
            raise ValueError(f"候选因子启用上限为 {MAX_ACTIVE}")
        row.status = "active"
        db.commit()
        return _row(row)


def disable(candidate_id: str | int) -> dict:
    """人工驳回或停用候选，不删除历史。"""
    with SessionLocal() as db:
        row = _find(db, candidate_id)
        if row is None:
            raise ValueError(f"候选因子不存在: {candidate_id}")
        row.status = "disabled"
        db.commit()
        return _row(row)
