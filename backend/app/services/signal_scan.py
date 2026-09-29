"""买卖点信号全市场扫描：只攒数据，不发通知、不进 Agent、不触发任何交易动作。"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timedelta

import numpy as np

from app.core.config import settings
from app.datasource import market_hours
from app.datasource.fallback import get_datasource
from app.db.models import SignalTrigger
from app.db.session import SessionLocal
from app.indicators import compute_signal_snapshot
from app.services.signal_registry import list_all

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
MIN_BARS = 250
_LOOKBACK_DAYS = 420
_COOLDOWN_TRADING_DAYS = 10
_TOTAL_BUDGET_SECONDS = 540
_BATCH_BUDGET_SECONDS = 120
_PARALLEL_MIN = 3
_PARALLEL_MAX = 8
_NULL_FIELDS = ("exec_price", "ret_5", "ret_10", "ret_20", "excess_10", "excess_20",
                "max_profit_20", "max_drawdown_20", "filled_at")
_MAIN_LIMIT = 10.0
_GEM_LIMIT = ("300", "301", "688", "689")   # 创业板/科创板：20%
_BJ_LIMIT = ("4", "8", "92")                # 北交所（含 920 新号段）：30%
_B_SHARE_LIMIT = ("900", "200")             # 沪/深 B 股：10%，不得并入北交所分支
_ST_MAIN_LIMIT = 5.0                        # 仅主板 ST 压缩到 5%


def _code6(code) -> str:
    """归一化 6 位股票代码：容忍 float64 残留（'600000.0'）与市场后缀（'600000.SH'）。

    M3：全市场快照来自 DataFrame，code 可能是 numpy.float64，str() 得到 '600000.0'：
    既会落库脏代码，也让下面所有 startswith 前缀判定失效。
    """
    text = str(code or "").strip().split(".")[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:6].zfill(6) if digits else ""


def _limit_pct(code: str, st: bool) -> float:
    """按代码前缀定基础涨跌幅，再叠加 ST 规则（P0-1）。

    原实现「ST 一律 5%」把创业板/科创板 ST（300/301/688/689，实为 20%）误判为 5%；
    startswith(("4","8","9")) 又把沪市 B 股 900xxx 当成北交所 30%（实为 10%）。
    正确顺序：先按号段定基础涨跌幅，再只对主板 ST 叠加 5% 规则（北交所/双创 ST 不变）。
    """
    prefix = _code6(code)
    if prefix.startswith(_BJ_LIMIT):
        return 30.0
    if prefix.startswith(_GEM_LIMIT):
        return 20.0
    if prefix.startswith(_B_SHARE_LIMIT):
        return _MAIN_LIMIT
    return _ST_MAIN_LIMIT if st else _MAIN_LIMIT


def _flags(code: str, name: str, change_pct) -> tuple[int, int]:
    """返回 (is_st, limit_up)：主板 ST 5 / 北交所 30 / 创业板·科创板 20 / 主板 10，含 0.3% 容差。"""
    st = int("ST" in (name or "").upper())
    pct = _limit_pct(code, st)
    return st, int(change_pct is not None and change_pct >= pct - 0.3)


def _load_keys(trade_date: str) -> tuple[set, set]:
    """返回 (当日已落库键, 近 10 交易日已触发键)：前者保证重跑幂等，后者用于冷却去重。

    M2：日历缓存缺失/可用交易日不足 10 天时，原实现静默按「自然日→工作日」回退再切 10 天，
    长假前后实际覆盖不足 10 个交易日，冷却窗口被悄悄压缩（等于放宽冷却、重复触发）。
    改为显式告警 + 放宽到 30 个自然日：只放宽不回缩，宁可多抑制也不漏抑制。
    """
    days = sorted(day for day in market_hours._load_calendar() if day < trade_date)[-_COOLDOWN_TRADING_DAYS:]
    if len(days) < _COOLDOWN_TRADING_DAYS:
        day = datetime.strptime(trade_date, "%Y-%m-%d").date()
        span = max(_COOLDOWN_TRADING_DAYS * 3, 30)
        widened = sorted({(day - timedelta(days=i)).isoformat() for i in range(1, span + 1)})
        logger.warning("交易日历可用日不足 %d 天（实际 %d 天），%s 的冷却窗口显式放宽到 %s 起",
                       _COOLDOWN_TRADING_DAYS, len(days), trade_date, widened[0])
        days = widened
    with SessionLocal() as db:
        rows = db.query(SignalTrigger.trade_date, SignalTrigger.stock_code, SignalTrigger.signal_id).filter(
            SignalTrigger.trade_date >= (days[0] if days else trade_date),
            SignalTrigger.trade_date <= trade_date).all()
    return ({(code, sig) for day, code, sig in rows if day == trade_date},
            {(code, sig) for day, code, sig in rows if day != trade_date})


def _local_kline(code: str, ctx: dict):
    """本地日线仓库优先（批1.5）：不足 MIN_BARS / 复权口径混用 → 记审计计数并返回 None。"""
    try:
        from app.services import kline_store
        if not kline_store.has_enough(code, MIN_BARS):
            kind = "unsupported" if code in (ctx.get("unsupported_codes") or ()) else "incomplete"
            _mark_missing(ctx, code, kind)
            return None
        return kline_store.load_frame(code, ctx["start"], ctx["end"])
    except kline_store.MixedAdjustError as exc:  # noqa: BLE001 复权漂移：宁可缺数据不算指标
        logger.warning("本地日线复权口径混用（拒绝计算）%s: %s", code, exc)
        _mark_missing(ctx, code, "incomplete")
        return None
    except Exception as exc:  # noqa: BLE001 本地库异常不阻断扫描
        logger.warning("本地日线读取失败 %s: %s", code, exc, exc_info=True)
        _mark_missing(ctx, code, "incomplete")
        return None


def _mark_missing(ctx: dict, code: str, kind: str) -> None:
    """审计计数 + 缺失清单（有上限，避免 summary 爆炸）；stale=本地有但末根不是当日

    计数独立于 counters（local/remote 保持原契约，不破坏既有调用方与测试）。
    """
    missing, lock = ctx.get("missing"), ctx.get("lock")
    if missing is None or lock is None:
        return
    with lock:
        missing[kind] = missing.get(kind, 0) + 1
        bucket = ctx.setdefault(kind, [])
        if len(bucket) < 100:
            bucket.append(code)


def _bump(ctx: dict, key: str) -> None:
    """本地/远端取材计数（ctx 未带计数器时静默跳过，保持外部干跑工具可用）"""
    counters, lock = ctx.get("counters"), ctx.get("lock")
    if counters is None or lock is None:
        return
    with lock:
        counters[key] += 1


def _scan_one(item: dict, ctx: dict) -> tuple[list[dict], int]:
    """单只票：本地仓库优先 → 缺则远端 → 算一次快照 → 跑全部信号；异常只计数、不阻断。"""
    code, rows = item["code"], []
    kline = _local_kline(code, ctx)
    if kline is not None:
        _bump(ctx, "local")
    else:
        if ctx.get("local_only"):
            if code not in (ctx.get("unsupported_codes") or ()):
                _mark_missing(ctx, code, "data_missing")  # 短史票已由 _local_kline 记 unsupported，不重复计
            return rows, 0
        _bump(ctx, "remote")  # 计入「仍需远端」的尝试（成败都算，用于核实本地覆盖率）
        try:
            kline = ctx["source"].fetch_daily_kline(code, ctx["start"], ctx["end"])
        except Exception as exc:  # noqa: BLE001 单只失败留空，不阻断批
            logger.warning("信号扫描日线获取失败 %s: %s", code, exc, exc_info=True)
            return rows, 1
    if kline is None or len(kline) < MIN_BARS or "close" not in getattr(kline, "columns", []):
        _mark_missing(ctx, code, "incomplete")
        return rows, 0
    if "date" in kline.columns:
        kline = kline.sort_values("date")
        if str(kline["date"].iloc[-1])[:10] != ctx["trade_date"]:
            _mark_missing(ctx, code, "stale")  # 停牌/本地缺当日 bar：不记录但入清单
            return rows, 0
    try:
        close = float(kline["close"].iloc[-1])
    except (TypeError, ValueError):
        _mark_missing(ctx, code, "incomplete")
        return rows, 0
    if not np.isfinite(close):
        return rows, 0
    snap = compute_signal_snapshot(kline)
    if not snap:
        return rows, 0
    name = item.get("name") or ctx.get("names", {}).get(code, "")
    st, limit_up = _flags(code, name, snap.get("change_pct"))
    errors = 0
    for definition in ctx["defs"]:
        if (code, definition.id) in ctx["today"]:
            continue
        try:
            hit = definition.func(snap, kline, code).hit
        except Exception as exc:  # noqa: BLE001 计算异常记 error，不阻断扫描
            errors += 1
            logger.warning("信号 %s 计算异常 %s: %s", definition.id, code, exc, exc_info=True)
            continue
        if not hit:
            continue
        row = dict.fromkeys(_NULL_FIELDS)
        row.update(trade_date=ctx["trade_date"], stock_code=code, signal_id=definition.id, is_st=st,
                   direction=definition.direction, trigger_close=close, limit_up=limit_up,
                   dedup=int((code, definition.id) in ctx["cooldown"]))
        rows.append(row)
    return rows, errors


def _scan_batch(batch: list[dict], ctx: dict, timeout: float) -> tuple[list[dict], int, int]:
    """批内并发；单只失败不影响批内其他票；批超时保留已完成结果并丢弃未完成。"""
    rows: list[dict] = []
    errors = 0
    if len(batch) < _PARALLEL_MIN:
        for item in batch:
            got, bad = _scan_one(item, ctx)
            rows.extend(got)
            errors += bad
        return rows, errors, 0
    dropped = 0
    # P0-3：不能用 with ThreadPoolExecutor —— __exit__ 会再执行一次 shutdown(wait=True)，
    # 把超时分支刚做的 shutdown(wait=False) 覆盖掉，540s 总预算被架空（批次仍阻塞到跑完）。
    # 改为显式 shutdown(wait=False, cancel_futures=True)，扫描主流程不再等待残留任务。
    pool = ThreadPoolExecutor(max_workers=min(_PARALLEL_MAX, len(batch)),
                              thread_name_prefix="signal-scan")
    futures = [pool.submit(_scan_one, item, ctx) for item in batch]
    try:
        try:
            for future in as_completed(futures, timeout=timeout):
                try:
                    got, bad = future.result()
                except Exception as exc:  # noqa: BLE001 单只异常不影响该批其他票
                    errors += 1
                    logger.warning("信号扫描单只异常: %s", exc, exc_info=True)
                    continue
                rows.extend(got)
                errors += bad
        except TimeoutError:
            dropped = sum(1 for future in futures if not future.done())
            logger.warning("信号扫描批次超时 %.0fs，保留 %d 条，丢弃 %d 只", timeout, len(rows), dropped)
    finally:
        # cancel_futures 只取消未开始的任务；已在跑的任务（requests 阻塞中）无法中断，
        # 但本函数立即返回，不再阻塞后续批次与总预算；残留线程由解释器退出时兜底回收。
        pool.shutdown(wait=False, cancel_futures=True)
    return rows, errors, dropped


def _persist(rows: list[dict]) -> int:
    """整批单事务落库：唯一约束冲突（重复写入）跳过该行，其余异常带堆栈上抛。

    P0-2：原实现逐行 commit + except Exception 无差别吞异常 —— 连接断开、字段约束错误、
    列超长等都被当成「重复写入」静默跳过（落库静默丢失且无法察觉），同时每行一次事务
    使落库吞吐极低。改为：批量 flush 单事务 + 只捕获 IntegrityError（幂等去重语义），
    以 SAVEPOINT（begin_nested）保证单行冲突只回滚该行，其它异常原样抛出交给调用方。
    """
    if not rows:
        return 0
    from sqlalchemy.exc import IntegrityError  # 局部导入：不新增模块级依赖

    done = 0
    with SessionLocal() as db:
        for row in rows:
            try:
                with db.begin_nested():   # SAVEPOINT：冲突只回滚这一行
                    db.add(SignalTrigger(**row))
                    db.flush()            # 冲突在此暴露，而不是拖到最后一次 commit
                done += 1
            except IntegrityError:        # 唯一约束冲突 = 该信号已存在，幂等跳过
                continue
        db.commit()
    return done


def scan_signal_triggers(trade_date: str | None = None, local_only: bool | None = None) -> dict:
    """全市场信号扫描并落表 signal_trigger；非交易日直接返回，不产生任何记录。

    分批 ≤500 只、批内并发、单批失败跳过不影响其他批；总预算 540s，超时保留已完成批次。
    local_only=True（批1.5）时只读本地日线仓库：缺数据的票记 incomplete/data_missing 并进
    补数队列，**禁止静默回退逐票远端**，使扫描时长稳定、结果可审计。"""
    if local_only is None:
        local_only = settings.kline_scan_local_only
    if not market_hours.is_trading_day():
        return {"trade_date": "", "universe": 0, "records": 0, "errors": 0, "dropped": 0,
                "reason": "not_trading_day"}
    day = trade_date or datetime.now().strftime("%Y-%m-%d")
    source = get_datasource()
    try:
        spot = source.fetch_spot_universe()
    except Exception as exc:  # noqa: BLE001 股票池失败：不产生记录
        logger.error("信号扫描股票池获取失败: %s", exc, exc_info=True)
        return {"trade_date": day, "universe": 0, "records": 0, "errors": 0, "dropped": 0,
                "reason": "error:universe"}
    if spot is None or spot.empty:
        return {"trade_date": day, "universe": 0, "records": 0, "errors": 0, "dropped": 0,
                "reason": "empty_universe"}
    # M3：spot 来自 DataFrame，code 可能是 numpy.float64 → str() 得到 '600000.0'；
    # 统一经 _code6 归一化为 6 位代码，并丢弃归一化后为空的脏行。
    universe = [{"code": _code6(row.get("code")), "name": str(row.get("name") or "")}
                for row in spot.to_dict("records") if _code6(row.get("code"))]
    short_set: set[str] = set()
    if local_only:
        try:
            from app.services import kline_store
            local_names = kline_store.name_map()
            for item in universe:
                if not item["name"]:
                    item["name"] = local_names.get(item["code"], "")
            short_set = kline_store.short_codes()
            if short_set:
                logger.info("本地仓库短史票 %d 只，标记 unsupported（源可取但 <MIN_BARS，不再重试）", len(short_set))
        except Exception as exc:  # noqa: BLE001 本地名称缺失不阻断（退化为股票池名称）
            logger.warning("本地日线名称映射读取失败: %s", exc, exc_info=True)
    today_keys, cooldown_keys = _load_keys(day)
    ctx = {
        "trade_date": day, "defs": list_all(), "source": source, "today": today_keys,
        "start": (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d"),
        "end": day, "cooldown": cooldown_keys, "local_only": bool(local_only),
        "lock": threading.Lock(), "counters": {"local": 0, "remote": 0},
        "missing": {"incomplete": 0, "data_missing": 0, "stale": 0, "unsupported": 0},
        "unsupported_codes": short_set,
    }
    records = errors = dropped = 0
    reason = "ok"
    started = time.monotonic()
    for offset in range(0, len(universe), BATCH_SIZE):
        remaining = _TOTAL_BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            reason = "total_budget_exceeded"
            logger.warning("信号扫描超出总预算 %ss，已落 %d 条记录", _TOTAL_BUDGET_SECONDS, records)
            break
        batch = universe[offset:offset + BATCH_SIZE]
        try:
            rows, bad, lost = _scan_batch(batch, ctx, min(remaining, _BATCH_BUDGET_SECONDS))
        except Exception as exc:  # noqa: BLE001 单批失败不影响其他批
            errors += 1
            dropped += len(batch)
            logger.error("信号扫描批次失败（跳过该批）: %s", exc, exc_info=True)
            continue
        errors += bad
        dropped += lost
        try:
            # M1：_persist 原来在 try 之外 —— DB 会话创建失败/连接断开会直接中断整个
            # 全市场扫描（前面已落库的批次白跑、后续批次全丢）。移入 try，单批落库失败只丢该批。
            records += _persist(rows)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.error("信号扫描落库失败（本批 %d 条未写入，下次扫描重跑补齐）: %s",
                         len(rows), exc, exc_info=True)
        logger.info("信号扫描批次 %d~%d 命中 %d 条，累计落库 %d 条",
                    offset, offset + len(batch), len(rows), records)
    counters = ctx["counters"]
    incomplete, data_missing = ctx["missing"]["incomplete"], ctx["missing"]["data_missing"]
    stale = ctx["missing"]["stale"]
    unsupported = ctx["missing"].get("unsupported", 0)
    # M5：各缺失桶按「命中即计数」累加，同一只票可能同时进 incomplete/stale 等多个桶，
    # 直接相减会让 eligible 为负 → coverage_pct 出现负覆盖率。下夹紧到 0。
    eligible = max(0, len(universe) - incomplete - data_missing - stale - unsupported)
    coverage_pct = min(100.0, round(eligible * 100.0 / len(universe), 1)) if universe else 0.0
    summary = {"trade_date": day, "universe": len(universe), "records": records, "errors": errors,
               "dropped": dropped, "reason": reason, "local_only": bool(local_only),
               "eligible": eligible, "incomplete": incomplete, "data_missing": data_missing,
               "stale": stale, "unsupported": unsupported,
               "coverage_pct": coverage_pct,
               "local_bars": counters["local"], "remote_bars": counters["remote"],
               "incomplete_codes": ctx.get("incomplete", [])[:20],
               "data_missing_codes": ctx.get("data_missing", [])[:20],
               "unsupported_codes": ctx.get("unsupported", [])[:20]}
    logger.info("信号扫描结束 %s: %s", day, summary)
    return summary
