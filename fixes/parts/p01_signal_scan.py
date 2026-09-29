# -*- coding: utf-8 -*-
'''signal_scan.py：P0-1 / P0-2 / P0-3 / M1 / M2 / M3 / M4 / M5

嵌入的代码片段一律用三单引号包裹（原文含三双引号 docstring）。
'''

NAME = "signal_scan"

_FILE = "backend/app/services/signal_scan.py"

ITEMS = [
    {
        "id": "P0-1",
        "file": _FILE,
        "summary": "涨跌幅按号段定基础值再叠加 ST；900xxx 移出北交所分支",
        "edits": [
            ('''_MAIN_LIMIT = 10.0
_GEM_LIMIT = ("300", "301", "688", "689")
_BJ_LIMIT = ("4", "8", "9")


def _flags(code: str, name: str, change_pct) -> tuple[int, int]:
    """返回 (is_st, limit_up)：ST 5 / 北交所 30 / 创业板·科创板 20 / 主板 10，含 0.3% 容差。"""
    st = int("ST" in (name or "").upper())
    pct = 5.0 if st else 30.0 if code.startswith(_BJ_LIMIT) else (
        20.0 if code.startswith(_GEM_LIMIT) else _MAIN_LIMIT)
    return st, int(change_pct is not None and change_pct >= pct - 0.3)''',
             '''_MAIN_LIMIT = 10.0
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
    return st, int(change_pct is not None and change_pct >= pct - 0.3)'''),
        ],
    },
    {
        "id": "M2",
        "file": _FILE,
        "summary": "日历不足 10 交易日时显式告警 + 放宽自然日窗口，不静默缩短冷却",
        "edits": [
            ('''def _load_keys(trade_date: str) -> tuple[set, set]:
    """返回 (当日已落库键, 近 10 交易日已触发键)：前者保证重跑幂等，后者用于冷却去重。"""
    days = sorted(day for day in market_hours._load_calendar() if day < trade_date)[-_COOLDOWN_TRADING_DAYS:]
    if not days:
        day = datetime.strptime(trade_date, "%Y-%m-%d").date()
        past = ((day - timedelta(days=i)) for i in range(1, 31))
        days = [item.isoformat() for item in past if item.weekday() < 5][-_COOLDOWN_TRADING_DAYS:]''',
             '''def _load_keys(trade_date: str) -> tuple[set, set]:
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
        days = widened'''),
        ],
    },
    {
        "id": "P0-3",
        "file": _FILE,
        "summary": "批超时后不再等待残留任务（去掉 with ThreadPoolExecutor 的二次 shutdown(wait=True)）",
        "edits": [
            ('''    dropped = 0
    with ThreadPoolExecutor(max_workers=min(_PARALLEL_MAX, len(batch))) as pool:
        futures = [pool.submit(_scan_one, item, ctx) for item in batch]
        try:
            for future in as_completed(futures, timeout=timeout):
                try:
                    got, bad = future.result()
                except Exception as exc:  # noqa: BLE001 单只异常不影响该批其他票
                    errors += 1
                    logger.warning("信号扫描单只异常: %s", exc)
                    continue
                rows.extend(got)
                errors += bad
        except TimeoutError:
            dropped = sum(1 for future in futures if not future.done())
            logger.warning("信号扫描批次超时 %.0fs，保留 %d 条，丢弃 %d 只", timeout, len(rows), dropped)
            pool.shutdown(wait=False, cancel_futures=True)
    return rows, errors, dropped''',
             '''    dropped = 0
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
    return rows, errors, dropped'''),
        ],
    },
    {
        "id": "P0-2",
        "file": _FILE,
        "summary": "_persist 只捕获 IntegrityError：批量 flush 单事务 + SAVEPOINT 逐行幂等",
        "edits": [
            ('''def _persist(rows: list[dict]) -> int:
    """逐行落库：唯一约束冲突自动跳过（幂等），返回实际写入条数。"""
    done = 0
    with SessionLocal() as db:
        for row in rows:
            db.add(SignalTrigger(**row))
            try:
                db.commit()
                done += 1
            except Exception:  # noqa: BLE001 重复写入跳过
                db.rollback()
    return done''',
             '''def _persist(rows: list[dict]) -> int:
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
    return done'''),
        ],
    },
    {
        "id": "M3",
        "file": _FILE,
        "summary": "universe 代码经 _code6 归一化，剔除 float64 产生的 '600000.0'",
        "edits": [
            ('''    universe = [{"code": str(row.get("code") or ""), "name": str(row.get("name") or "")}
                for row in spot.to_dict("records") if row.get("code")]''',
             '''    # M3：spot 来自 DataFrame，code 可能是 numpy.float64 → str() 得到 '600000.0'；
    # 统一经 _code6 归一化为 6 位代码，并丢弃归一化后为空的脏行。
    universe = [{"code": _code6(row.get("code")), "name": str(row.get("name") or "")}
                for row in spot.to_dict("records") if _code6(row.get("code"))]'''),
        ],
    },
    {
        "id": "M5",
        "file": _FILE,
        "summary": "eligible 下夹紧到 0、coverage_pct 夹紧到 [0,100]",
        "edits": [
            ('''    eligible = len(universe) - incomplete - data_missing - stale - unsupported''',
             '''    # M5：各缺失桶按「命中即计数」累加，同一只票可能同时进 incomplete/stale 等多个桶，
    # 直接相减会让 eligible 为负 → coverage_pct 出现负覆盖率。下夹紧到 0。
    eligible = max(0, len(universe) - incomplete - data_missing - stale - unsupported)
    coverage_pct = min(100.0, round(eligible * 100.0 / len(universe), 1)) if universe else 0.0'''),
            ('''               "coverage_pct": round(eligible * 100.0 / len(universe), 1) if universe else 0.0,''',
             '''               "coverage_pct": coverage_pct,'''),
        ],
    },
    {
        "id": "M1",
        "file": _FILE,
        "summary": "_persist 移入 try：落库失败不再中断整个扫描",
        "edits": [
            ('''        except Exception as exc:  # noqa: BLE001 单批失败不影响其他批
            errors += 1
            dropped += len(batch)
            logger.error("信号扫描批次失败（跳过该批）: %s", exc)
            continue
        errors += bad
        dropped += lost
        records += _persist(rows)''',
             '''        except Exception as exc:  # noqa: BLE001 单批失败不影响其他批
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
                         len(rows), exc, exc_info=True)'''),
        ],
    },
    {
        "id": "M4",
        "file": _FILE,
        "summary": "except Exception 补 exc_info=True，异常不再只有一行消息",
        "edits": [
            ('''        logger.warning("本地日线读取失败 %s: %s", code, exc)''',
             '''        logger.warning("本地日线读取失败 %s: %s", code, exc, exc_info=True)'''),
            ('''            logger.warning("信号扫描日线获取失败 %s: %s", code, exc)''',
             '''            logger.warning("信号扫描日线获取失败 %s: %s", code, exc, exc_info=True)'''),
            ('''            logger.warning("信号 %s 计算异常 %s: %s", definition.id, code, exc)''',
             '''            logger.warning("信号 %s 计算异常 %s: %s", definition.id, code, exc, exc_info=True)'''),
            ('''        logger.error("信号扫描股票池获取失败: %s", exc)''',
             '''        logger.error("信号扫描股票池获取失败: %s", exc, exc_info=True)'''),
            ('''            logger.warning("本地日线名称映射读取失败: %s", exc)''',
             '''            logger.warning("本地日线名称映射读取失败: %s", exc, exc_info=True)'''),
        ],
    },
]
