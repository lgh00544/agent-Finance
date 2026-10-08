"""候选因子池：提议、样本外验证与人工状态切换。"""
import ast
import math
from statistics import mean

import pandas as pd
from sqlalchemy import select

from app.agents import candidate_factor_proposer as proposer
from app.db.models import FactorCandidate
from app.db.session import SessionLocal
from app.factors.data_adapter import DataAdapter, factor
from app.services import factor_ic, factor_registry
from app.services.factor_registry import FactorDef

MAX_ACTIVE = 30

# P-11（A-14/F-6）：候选因子公式安全求值 —— 仅允许 kline 列与白名单函数/方法
_KLINE_COLUMNS = {"open", "high", "low", "close", "volume", "amount"}
_ALLOWED_METHODS = {
    "mean", "std", "shift", "pct_change", "rolling", "abs", "sum", "max", "min",
    "rank", "quantile", "clip", "diff", "ewm", "fillna", "dropna", "tail", "iloc",
}
_FORMULA_GLOBALS = {"abs": abs, "log": math.log, "sqrt": math.sqrt,
                    "exp": math.exp, "min": min, "max": max, "sum": sum}


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


def get_pending_for_sir(limit: int = 50) -> list[dict]:
    """返回待人工拍板的候选因子。"""
    limit = max(1, min(int(limit), 100))
    with SessionLocal() as db:
        rows = db.scalars(
            select(FactorCandidate).where(FactorCandidate.status == "pending")
            .order_by(FactorCandidate.created_at.desc()).limit(limit)
        ).all()
        return [_row(row) for row in rows]


def _safe_formula_func(formula: str) -> tuple[callable | None, str]:
    """把候选因子公式编译为可执行 func(data: DataAdapter, code) -> FactorResult。

    安全边界：表达式仅允许 kline 列名、数字、运算符、白名单函数与方法调用；
    禁止任意属性链（如 __class__）等复杂结构。解析失败返回 (None, 原因)。
    空白公式按占位恒 0 因子放行（既有 enable/validate 契约：无公式候选不阻塞启用流程）。
    """
    formula = (formula or "").strip()
    if not formula:
        def _zero(_adapter, _code):
            return factor(0.0, "no_formula")
        return _zero, ""
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        return None, f"公式语法错误: {exc.msg}"
    allowed = _KLINE_COLUMNS | {"ma5", "ma10", "ma20", "ma60"} | set(_FORMULA_GLOBALS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id not in allowed:
                return None, f"非法标识符: {node.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr not in _ALLOWED_METHODS:
                return None, f"非法属性访问: {node.attr}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in allowed:
                return None, f"非法函数调用: {node.func.id}"

    def make_func(data: DataAdapter, code: str):
        rows = data.kline_rows()
        df = pd.DataFrame(rows)
        if df.empty or "close" not in df.columns:
            return factor(None, "data_missing:kline")
        df = df.sort_values("date").reset_index(drop=True)
        for col in _KLINE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
        for window in (5, 10, 20, 60):
            df[f"ma{window}"] = df["close"].rolling(window).mean()
        env = {col: df[col] for col in _KLINE_COLUMNS}
        env.update({f"ma{w}": df[f"ma{w}"] for w in (5, 10, 20, 60)})
        env.update(_FORMULA_GLOBALS)
        try:
            series = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, env)
        except Exception as exc:
            return factor(None, f"formula_error:{type(exc).__name__}")
        value = series.iloc[-1] if hasattr(series, "iloc") else series
        try:
            value = float(value)
        except (TypeError, ValueError):
            return factor(None, "formula_error:non_numeric")
        if not math.isfinite(value):
            return factor(None, "formula_error:non_finite")
        return factor(max(-1.0, min(1.0, value)))

    return make_func, ""


def _collect_candidate_records(definition: FactorDef, months: int = 24,
                               budget_seconds: float = 120.0) -> dict[str, list[dict]]:
    """候选因子真实执行：复用 IC 回测采集链路，仅注入候选定义，样本外取数算 IC。"""
    from app.datasource.fallback import get_datasource
    source = get_datasource()
    ends = factor_ic._month_ends(source.fetch_trade_calendar(), months)
    if not ends:
        return {}
    universe = source.fetch_spot_universe()
    codes = factor_ic.select_universe_codes(universe, limit=60)
    stats: dict = {}
    return factor_ic.collect_month_records(
        source, ends, codes, budget_seconds=budget_seconds, stats=stats,
        exclude_codes=factor_ic.select_st_codes(universe),
        extra_definitions=[definition])


def validate(candidate_id: str | int, month_records: dict[str, list[dict]] | None = None,
             months: int = 24) -> dict:
    """取最近 N 个月样本外回测（候选因子公式真实执行），结果写验证字段。"""
    with SessionLocal() as db:
        row = _find(db, candidate_id)
        if row is None:
            raise ValueError(f"候选因子不存在: {candidate_id}")
        func, formula_error = _safe_formula_func(row.formula or "")
        if func is None:
            result = {"status": "unsupported_formula", "reason": formula_error,
                      "periods": 0, "rows": 0, "mean_ic": None, "ir": None}
        else:
            definition = FactorDef(
                id=row.candidate_id, name=row.name, category=row.category
                if row.category in {"动量", "催化", "估值", "资金", "质量", "主线"} else "主线",
                func=func, has_quantile=False, weight_hint=0.0, version="custom")
            if month_records:
                records = month_records
            else:
                records = _collect_candidate_records(definition, months=months)
            periods = sorted(records or {})[-24:]
            results = factor_ic.run_backtest({k: records[k] for k in periods}, [definition]) if periods else []
            ics = [item["ic"] for item in results if item["ic"] is not None]
            result = {
                "status": "validated" if ics else "insufficient_data",
                "periods": len(periods), "rows": sum(len(records[k]) for k in periods),
                "mean_ic": round(mean(ics), 6) if ics else None,
                "ir": results[-1].get("ir") if results else None,
            }
        row.validation_result = result
        db.commit()
        return {"candidate_id": row.candidate_id, **result}


def enable(candidate_id: str | int) -> dict:
    """人工启用候选：公式须可安全执行，启用后注册进运行期 registry（真实进入选股打分链）。"""
    with SessionLocal() as db:
        row = _find(db, candidate_id)
        if row is None:
            raise ValueError(f"候选因子不存在: {candidate_id}")
        if row.status == "active":
            return _row(row)
        func, formula_error = _safe_formula_func(row.formula or "")
        if func is None:
            raise ValueError(f"候选因子公式不可安全执行，禁止启用: {formula_error}")
        active = db.scalars(select(FactorCandidate).where(FactorCandidate.status == "active")).all()
        if len(active) >= MAX_ACTIVE:
            raise ValueError(f"候选因子启用上限为 {MAX_ACTIVE}")
        definition = FactorDef(
            id=row.candidate_id, name=row.name, category=row.category
            if row.category in {"动量", "催化", "估值", "资金", "质量", "主线"} else "主线",
            func=func, has_quantile=False, weight_hint=0.10,
            status="active", version="custom")
        factor_registry.register_custom(definition)
        row.status = "active"
        db.commit()
        return _row(row)


def disable(candidate_id: str | int) -> dict:
    """人工驳回或停用候选：同时从运行期 registry 移除（不删除历史）。"""
    with SessionLocal() as db:
        row = _find(db, candidate_id)
        if row is None:
            raise ValueError(f"候选因子不存在: {candidate_id}")
        factor_registry.unregister(row.candidate_id)
        row.status = "disabled"
        db.commit()
        return _row(row)
