"""因子 IC 月度回测：只读行情，结果写入独立历史表。"""
from datetime import datetime, timedelta
from math import isfinite

import numpy as np
from sqlalchemy import select

try:
    from scipy.stats import spearmanr
except ImportError:
    spearmanr = None

from app.datasource.fallback import get_datasource
from app.db.models import FactorIcHistory
from app.db.session import SessionLocal
from app.factors import factor_registry
from app.factors.data_adapter import DataAdapter, num

FORWARD_DAYS, ROLLING_MONTHS, MIN_SAMPLE = 20, 3, 100


def _rank(values):
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), float)
    for start in range(len(values)):
        if start and values[order[start]] == values[order[start - 1]]:
            continue
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2 + 1
    return ranks


def calc_ic(values: list, returns: list) -> float | None:
    pairs = [(num(v), num(r)) for v, r in zip(values, returns)]
    pairs = [(v, r) for v, r in pairs if v is not None and r is not None]
    if len(pairs) < 2:
        return None
    xs, ys = zip(*pairs)
    ic = spearmanr(xs, ys).statistic if spearmanr else np.corrcoef(_rank(xs), _rank(ys))[0, 1]
    return round(float(ic), 6) if isfinite(float(ic)) else None


def calc_ir(months: list[dict]) -> float | None:
    values = [m["ic"] for m in months[-ROLLING_MONTHS:]
              if m.get("sample_size", 0) >= MIN_SAMPLE and m.get("ic") is not None]
    if len(values) < ROLLING_MONTHS:
        return None
    std = float(np.std(values, ddof=1))
    return round(float(np.mean(values) / std), 6) if std else None


def judge_status(ics: list[float | None]) -> str:
    recent = ics[-ROLLING_MONTHS:]
    return ("deprecated_candidate" if len(recent) == ROLLING_MONTHS
            and all(v is not None and v < 0.02 for v in recent) else "active")


def run_backtest(month_records: dict[str, list[dict]], definitions=None) -> list[dict]:
    definitions = sorted(definitions or factor_registry.list_active(), key=lambda d: d.id)
    periods, output = sorted(month_records), []
    for definition in definitions:
        monthly = []
        for period in periods:
            rows = month_records[period]
            values = [r.get("factor_values", {}).get(definition.id) for r in rows]
            returns = [r.get("forward_return") for r in rows]
            monthly.append({"period": period, "ic": calc_ic(values, returns),
                            "sample_size": sum(num(v) is not None and num(r) is not None
                                               for v, r in zip(values, returns))})
        for index, current in enumerate(monthly):
            history = monthly[:index + 1]
            valid = [m["ic"] for m in history if m["ic"] is not None]
            output.append({"factor_id": definition.id, "factor_name": definition.name,
                           "category": definition.category, "period": current["period"],
                           "ic": current["ic"], "ir": calc_ir(history),
                           "hit_rate": sum(v > 0 for v in valid) / len(valid) if valid else 0.0,
                           "sample_size": current["sample_size"], "abs_ic": abs(current["ic"] or 0),
                           "rank_in_category": 0,
                           "status": judge_status([m["ic"] for m in history])})
    for period in periods:
        groups = {}
        for row in (r for r in output if r["period"] == period):
            groups.setdefault(row["category"], []).append(row)
        for group in groups.values():
            for rank, row in enumerate(sorted(group, key=lambda r: (-r["abs_ic"], r["factor_id"])), 1):
                row["rank_in_category"] = rank
    return output


def _month_ends(calendar: list[str], months: int) -> list[str]:
    latest = {}
    for value in sorted(str(item)[:10] for item in calendar):
        latest[value[:7]] = value
    return list(latest.values())[-months:]


def collect_month_records(source, month_ends: list[str], codes: list[str]) -> dict[str, list[dict]]:
    records = {d[:7]: [] for d in month_ends}
    if not month_ends:
        return records
    start = (datetime.strptime(month_ends[0], "%Y-%m-%d") - timedelta(days=45)).strftime("%Y-%m-%d")
    end = (datetime.strptime(month_ends[-1], "%Y-%m-%d") + timedelta(days=45)).strftime("%Y-%m-%d")
    definitions = factor_registry.list_active()
    for code in codes:
        try:
            kline = source.fetch_daily_kline(code, start, end)
            if kline is None or kline.empty or not {"date", "close"}.issubset(kline.columns):
                continue
            kline = kline.sort_values("date").reset_index(drop=True)
            for snapshot in month_ends:
                hits = kline.index[kline["date"].astype(str).str[:10] == snapshot].tolist()
                if not hits or hits[0] + FORWARD_DAYS >= len(kline):
                    continue
                i = hits[0]
                close, future = num(kline.iloc[i]["close"]), num(kline.iloc[i + FORWARD_DAYS]["close"])
                if close in (None, 0) or future is None:
                    continue
                history = kline.iloc[:i + 1]
                adapter = DataAdapter(source=source, code=code, kline=history, indicators={
                    "latest_close": close, "ma20": history["close"].tail(20).mean() if i >= 19 else None})
                values = {}
                for definition in definitions:
                    try:
                        values[definition.id] = definition.func(adapter, code).value
                    except Exception:
                        values[definition.id] = None
                records[snapshot[:7]].append({"code": code, "factor_values": values,
                                               "forward_return": future / close - 1})
        except Exception:
            continue
    return records


def persist_history(rows: list[dict]) -> int:
    if not rows:
        return 0
    with SessionLocal() as db:
        keys = {(r["factor_id"], r["period"]) for r in rows}
        existing = {(r.factor_id, r.period): r for r in db.execute(select(FactorIcHistory)).scalars()
                    if (r.factor_id, r.period) in keys}
        for payload in rows:
            current = existing.get((payload["factor_id"], payload["period"]))
            if current is None:
                db.add(FactorIcHistory(**payload))
            else:
                for key, value in payload.items():
                    setattr(current, key, value)
        db.commit()
    return len(rows)


def run_factor_ic_backtest_job(months: int = 36) -> dict:
    source = get_datasource()
    ends = _month_ends(source.fetch_trade_calendar(), months)
    universe = source.fetch_spot_universe()
    codes = universe["code"].astype(str).str.zfill(6).tolist() if universe is not None and "code" in universe else []
    return {"months": len(ends), "codes": len(codes),
            "rows": persist_history(run_backtest(collect_month_records(source, ends, codes)))}


def list_history(factor_id_filter: str = "", period: str = "", limit: int = 50) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(FactorIcHistory)
        if factor_id_filter:
            stmt = stmt.where(FactorIcHistory.factor_id == factor_id_filter)
        if period:
            stmt = stmt.where(FactorIcHistory.period == period)
        stmt = stmt.order_by(FactorIcHistory.period.desc(), FactorIcHistory.abs_ic.desc()).limit(max(1, min(limit, 500)))
        return [{c.name: getattr(row, c.name) for c in FactorIcHistory.__table__.columns}
                for row in db.execute(stmt).scalars()]
