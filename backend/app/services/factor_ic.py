"""因子 IC 月度回测：只读行情，结果写入独立历史表。"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from math import isfinite

import numpy as np
import pandas as pd
import requests
from sqlalchemy import select

try:
    from scipy.stats import spearmanr
except ImportError:
    spearmanr = None

from app.core.config import settings
from app.datasource.base import DataSourceError
from app.datasource.fallback import get_datasource
from app.db.models import FactorIcHistory
from app.db.session import SessionLocal
from app.factors import factor_registry
from app.factors.data_adapter import DataAdapter, num
from app.services import kline_store

logger = logging.getLogger(__name__)

FORWARD_DAYS, ROLLING_MONTHS, MIN_SAMPLE = 20, 3, 100
# 全市场 5000+ 只 × 单只 20s+ 日K ≈ 11 小时，单次回测不可行：
# 按代码等距抽样到 UNIVERSE_LIMIT 只，并设墙钟预算，超预算即停并落库已采部分。
UNIVERSE_LIMIT = 300
# 墙钟预算由「单只耗时上限 × 目标只数」推导（与 UNIVERSE_LIMIT 解耦，不独立硬编码）：
# 采不满 MIN_SAMPLE 会让已有效的 ir 被 upsert 回 NULL，故按目标样本数反推预算。
COLLECT_TARGET_SAMPLES = settings.factor_ic_target_samples
COLLECT_BUDGET_SECONDS = int(COLLECT_TARGET_SAMPLES * settings.factor_ic_seconds_per_code)
# 采集并发：单票含 4 次串行外呼（日K+财务/资金/新闻），串行 300 票必超预算；
# 只并行「票与票之间」，票内顺序与产物不变。源站反爬与 socket 全局超时副作用见
# akshare_source._call_with_timeout 文档，故不取更高并发。
COLLECT_WORKERS = 4
# 本地日线仓库优先的覆盖容差（自然日）：首根 ≤ start+FIRST 且末根 ≥ min(end,今天)-LAST
# 才采用本地序列；新股/停牌/回补未完成一律回退远端，宁慢不错。
LOCAL_KLINE_FIRST_TOLERANCE_DAYS = 20
LOCAL_KLINE_LAST_TOLERANCE_DAYS = 10


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
                           "status": judge_status([m["ic"] for m in history
                                                   if m["sample_size"] >= MIN_SAMPLE])})
    for period in periods:
        groups = {}
        for row in (r for r in output if r["period"] == period):
            groups.setdefault(row["category"], []).append(row)
        for group in groups.values():
            # 样本不足 MIN_SAMPLE 的因子不参与排名：样本过小时 ±1.0 的伪 IC 会抢占榜首
            ranked = sorted((row for row in group if row["sample_size"] >= MIN_SAMPLE),
                            key=lambda row: (-row["abs_ic"], row["factor_id"]))
            for rank, row in enumerate(ranked, 1):
                row["rank_in_category"] = rank
    return output


def _month_ends(calendar: list[str], months: int) -> list[str]:
    # 交易日历含未来日期（如 2026-12-31），未来月份无行情可采，须先剔除再取最近 N 个月
    today = datetime.now().strftime("%Y-%m-%d")
    days = [value for value in sorted({str(item)[:10] for item in calendar}) if value <= today]
    if not days:
        return []
    latest = {}
    for value in days:
        latest[value[:7]] = value
    # 尾部钳制：月末之后不足 FORWARD_DAYS 个交易日的期次，前瞻收益尚未走完、IC 恒为 NULL
    ends = [end for end in latest.values() if sum(1 for day in days if day > end) >= FORWARD_DAYS]
    return ends[-months:]


def select_universe_codes(universe, limit: int = UNIVERSE_LIMIT) -> list[str]:
    """全市场快照 → 确定性抽样股票池：按代码排序等距取样，跨板块均匀且可复现。"""
    if universe is None or not hasattr(universe, "columns") or "code" not in universe.columns:
        return []
    codes = sorted({str(code).strip().zfill(6) for code in universe["code"].dropna()})
    if limit and len(codes) > limit:
        step = len(codes) / limit
        codes = [codes[int(index * step)] for index in range(limit)]
    return codes


def _fetch_once(source, method: str, *args):
    """取一次外挂数据；失败/空返回空表，交给 adapter 缓存，避免按 (票,月) 反复重试失败请求。"""
    try:
        value = getattr(source, method)(*args)
    except Exception as exc:  # noqa: BLE001 数据源异常类型繁多，统一降级为空表
        logger.debug("因子回测外挂数据 %s%s 失败: %s", method, args, exc)
        return pd.DataFrame()
    return value if value is not None else pd.DataFrame()


def _shift_date(date: str, days: int) -> str:
    """自然日平移（本地库覆盖判定用）"""
    return (datetime.strptime(str(date)[:10], "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def _local_kline(code: str, start: str, end: str):
    """本地日线仓库优先：仅当 [start, end] 首尾均被覆盖时采用，否则返回 None 由调用方回退远端。

    覆盖容差见 LOCAL_KLINE_*：用以区分「回补未完成」与「该票本就短历史」——新股/长期停牌会判为
    未覆盖而回退远端。宁慢不错：绝不用半段历史算 IC。
    """
    try:
        frame = kline_store.load_frame(code, start, end)
    except kline_store.MixedAdjustError:
        return None
    except Exception:  # noqa: BLE001 本地库缺表/被锁等一律回退远端
        return None
    if frame is None or frame.empty or not {"date", "close"}.issubset(frame.columns):
        return None
    dates = [str(value)[:10] for value in frame["date"].tolist()]
    if dates[0] > _shift_date(start, LOCAL_KLINE_FIRST_TOLERANCE_DAYS):
        return None
    tail = min(str(end)[:10], datetime.now().strftime("%Y-%m-%d"))
    if dates[-1] < _shift_date(tail, -LOCAL_KLINE_LAST_TOLERANCE_DAYS):
        return None
    return frame


def _warm_local(code: str, kline) -> None:
    """把远端取到的日K回写本地仓库（best-effort）：首轮付远端成本，后续轮次直接走本地。

    只写 qfq 口径（与 fetch_daily_kline 默认口径一致）；本地加速失败绝不影响回测结果。
    """
    try:
        rows = []
        for rec in kline.to_dict("records"):
            close = rec.get("close")
            if close is None or close != close:  # NaN 行跳过
                continue
            rows.append({"stock_code": code, "trade_date": str(rec.get("date"))[:10],
                         "open": rec.get("open"), "high": rec.get("high"), "low": rec.get("low"),
                         "close": close, "volume": rec.get("volume"), "amount": rec.get("amount"),
                         "source": "factor_ic", "adjust": "qfq"})
        if rows:
            kline_store.upsert_bars(rows)
    except Exception:  # noqa: BLE001 本地加速失败不得影响回测
        pass


def collect_month_records(source, month_ends: list[str], codes: list[str],
                          budget_seconds: float | None = COLLECT_BUDGET_SECONDS,
                          stats: dict | None = None) -> dict[str, list[dict]]:
    """stats 为可选出参：回填 attempted / budget_exhausted / elapsed，供调用方判断是否采满。

    采集按票并发（COLLECT_WORKERS）：只并行「票与票之间」，票内 4 次外呼顺序与产物不变；
    本地日线仓库覆盖区间时优先读本地（kline_store），否则回退远端。
    """
    records = {d[:7]: [] for d in month_ends}
    if stats is not None:
        stats["budget_exhausted"] = False
        stats["attempted"] = 0
    if not month_ends or not codes:
        return records
    started = time.monotonic()
    deadline = started + budget_seconds if budget_seconds else None
    start = (datetime.strptime(month_ends[0], "%Y-%m-%d") - timedelta(days=45)).strftime("%Y-%m-%d")
    end = (datetime.strptime(month_ends[-1], "%Y-%m-%d") + timedelta(days=45)).strftime("%Y-%m-%d")
    definitions = factor_registry.list_active()
    sectors = _fetch_once(source, "fetch_industry_spot")  # 全市场板块：整跑共用一份
    guard = threading.Lock()
    state = {"attempted": 0, "stopped": False}

    def _one(code: str) -> None:
        # 墙钟护栏：超预算即不再开新票，保证任务必定结束并落库已采数据（不出现「跑不完 → 数据空」）
        with guard:
            if deadline and time.monotonic() > deadline:
                state["stopped"] = True
                return
            state["attempted"] += 1
        try:
            kline = _local_kline(code, start, end)
            if kline is None:
                kline = source.fetch_daily_kline(code, start, end)
                if kline is not None and not kline.empty:
                    _warm_local(code, kline)  # 首轮回写本地，下一轮同票即走本地序列
            if kline is None or kline.empty or not {"date", "close"}.issubset(kline.columns):
                return
            kline = kline.sort_values("date").reset_index(drop=True)
            # 外挂数据每票只取一次（36 个月快照共用一份）；quote 置空：
            # 实时快照对历史月份属前视数据，且单次可达 88s（全市场快照兜底）。
            aux = {"quote": {}, "sectors": sectors,
                   "financial": _fetch_once(source, "fetch_financial", code),
                   "fund_flow": _fetch_once(source, "fetch_fund_flow", code),
                   "news": _fetch_once(source, "fetch_news", code)}
            rows: list[tuple] = []
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
                    "latest_close": close, "ma20": history["close"].tail(20).mean() if i >= 19 else None}, **aux)
                values = {}
                for definition in definitions:
                    try:
                        values[definition.id] = definition.func(adapter, code).value
                    except Exception:
                        values[definition.id] = None
                rows.append((snapshot[:7], {"code": code, "factor_values": values,
                                            "forward_return": future / close - 1}))
            for period, row in rows:  # list.append 原子：并发追加不同月份列表安全
                records[period].append(row)
        except Exception:
            return

    workers = max(1, min(int(COLLECT_WORKERS), len(codes)))
    if workers == 1:
        for code in codes:
            _one(code)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_one, codes))
    if state["stopped"]:
        logger.warning("因子 IC 采集超墙钟预算 %.0fs：已尝试 %d/%d 只，停止并落库已采部分",
                       budget_seconds, state["attempted"], len(codes))
    if stats is not None:
        stats["attempted"] = state["attempted"]
        stats["elapsed"] = round(time.monotonic() - started, 1)
        stats["budget_exhausted"] = bool(state["stopped"])
    return records


def persist_history(rows: list[dict]) -> int:
    if not rows:
        return 0
    # 批次级护栏：全批零样本（未采到任何样本）时不触库；只要任一行 sample_size>0，
    # 仍按原行为整批落库（保留「预算耗尽/部分采集也要留下已采数据」的既有语义）。
    if not any((row.get("sample_size") or 0) > 0 for row in rows):
        logger.warning("因子 IC 落库跳过：批次 %d 行全部 sample_size=0，未触库", len(rows))
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


# 判定顺序锁定：消息级 timeout（_TIMEOUT_KW）必须先于 connection 关键词路（_CONN_ERROR_KW）——
# 两表都含 "timeout"/"timed out"，顺序颠倒会把超时消息误判成 connection。
_CONN_ERROR_KW = ("proxy", "connection", "max retries", "getaddrinfo", "name resolution",
                  "remote end closed", "timeout", "timed out")
_TIMEOUT_KW = ("timeout", "timed out")


def _classify_error(exc: Exception) -> str:
    """取数异常分类：timeout（硬超时）/ connection（DNS·代理·连接被拒）/ unexpected（其余）。"""
    if isinstance(exc, (TimeoutError, requests.Timeout)):
        return "timeout"
    if isinstance(exc, DataSourceError) and "超时" in str(exc):
        return "timeout"
    text = ("%s %s" % (type(exc).__name__, exc)).lower()
    if any(k in text for k in _TIMEOUT_KW):
        return "timeout"
    return "connection" if any(k in text for k in _CONN_ERROR_KW) else "unexpected"


def _job_reason(codes: list[str], collected: int, max_sample: int, stats: dict, *,
                error_kind: str = "", error_msg: str = "") -> str | None:
    """给出去定位的原因（取数异常 / 预算不足 / 数据源降级）；达标返回 None。"""
    if error_kind == "timeout":
        return "取数超时：%s —— 单次调用硬超时触发，数据源无响应，可重试" % error_msg
    if error_kind == "connection":
        return "取数连接失败（DNS/代理/连接被拒）：%s —— 数据源降级，可稍后重试" % error_msg
    if error_kind:
        return "取数异常（非网络原因，疑为代码或数据格式问题，需排查）：%s" % error_msg
    if not codes:
        return "全市场快照为空（非交易日或数据源降级），股票池为 0，未采集"
    if max_sample >= MIN_SAMPLE:
        return None
    if stats.get("budget_exhausted"):
        return ("预算不足：%.0fs 内尝试 %d/%d 只、实采 %d 只，未达 MIN_SAMPLE=%d；"
                "请调高 factor_ic_target_samples 或 factor_ic_seconds_per_code"
                % (COLLECT_BUDGET_SECONDS, stats.get("attempted", 0), len(codes), collected, MIN_SAMPLE))
    return "数据源降级：股票池 %d 只、预算未耗尽但仅采到 %d 只，未达 MIN_SAMPLE=%d" % (
        len(codes), collected, MIN_SAMPLE)


def run_factor_ic_backtest_job(months: int = 36) -> dict:
    source = get_datasource()
    stats: dict = {}
    ends: list[str] = []
    codes: list[str] = []
    try:
        ends = _month_ends(source.fetch_trade_calendar(), months)
        codes = select_universe_codes(source.fetch_spot_universe())
        records = collect_month_records(source, ends, codes, COLLECT_BUDGET_SECONDS, stats=stats)
        if not any(records.values()):  # 零采集早退：零样本批次不得写入 factor_ic_history
            logger.warning("因子 IC 回测零采集：股票池 %d 只、期次 %d 个，跳过回测与落库",
                           len(codes), len(ends))
            return {"months": len(ends), "codes": len(codes), "rows": 0, "collected_codes": 0,
                    "max_sample": 0, "target_samples": COLLECT_TARGET_SAMPLES,
                    "budget_seconds": COLLECT_BUDGET_SECONDS,
                    "budget_exhausted": bool(stats.get("budget_exhausted")),
                    "sufficient": False, "error_kind": None, "skipped": True,
                    "reason": _job_reason(codes, 0, 0, stats)}
        results = run_backtest(records)
        persisted = persist_history(results)
    except Exception as exc:  # noqa: BLE001 取数异常转结构化结果，避免 cron/脚本裸崩
        error_kind = _classify_error(exc)
        logger.warning("因子 IC 回测取数失败（%s）：%s", error_kind, exc)
        return {"months": len(ends), "codes": len(codes), "rows": 0, "collected_codes": 0,
                "max_sample": 0, "target_samples": COLLECT_TARGET_SAMPLES,
                "budget_seconds": COLLECT_BUDGET_SECONDS,
                "budget_exhausted": bool(stats.get("budget_exhausted")),
                "sufficient": False, "error_kind": error_kind,
                "reason": _job_reason([], 0, 0, stats, error_kind=error_kind, error_msg=str(exc))}
    samples = [row["sample_size"] for row in results]
    collected = len({r["code"] for group in records.values() for r in group})
    max_sample = max(samples) if samples else 0
    return {"months": len(ends), "codes": len(codes), "rows": persisted,
            "collected_codes": collected, "max_sample": max_sample,
            "target_samples": COLLECT_TARGET_SAMPLES, "budget_seconds": COLLECT_BUDGET_SECONDS,
            "budget_exhausted": bool(stats.get("budget_exhausted")),
            "sufficient": max_sample >= MIN_SAMPLE, "error_kind": None,
            "reason": _job_reason(codes, collected, max_sample, stats)}


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
