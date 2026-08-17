"""
图间流转编排：discover→score→position 主链路；monitor 独立轮询；review 独立触发
【刚性代码逻辑】只做流转调度与结果落库，不包含任何市场判断。
"""
import logging
import time

from app.datasource.akshare_source import AkshareSource
from app.graph.graphs import get_graph
from app.graph.state import StockAgentState

logger = logging.getLogger(__name__)

# 批量打分并行开关：候选 ≥ 5 只自动切换并行模式（大标的池提速），小于阈值保持串行
_PARALLEL_SCORE_MIN = 5
_PARALLEL_SCORE_MAX = 8


def _new_state(**kwargs) -> StockAgentState:
    base: StockAgentState = {
        "stage": kwargs.get("stage", ""),
        "trace": [],
    }
    base.update(kwargs)
    return base


def _exp_summary(kind: str, state: dict) -> tuple[str, str]:
    """从 run_* 结果 state 提取经验摘要与产物引用（缺失字段安全兜底，返回 ("", "") 表示无有效产出）"""
    code = state.get("stock_code") or ""
    if kind == "discover":
        cands = state.get("candidates") or []
        if not cands:
            return "", ""
        codes = ",".join(str(c.get("stock_code") or "") for c in cands[:20])
        return f"候选 {len(cands)} 只", codes
    if kind == "score":
        sr = state.get("score_result") or {}
        if not code or not sr:
            return "", ""
        return f"{code} 评分 {sr.get('score', '—')} 分 {sr.get('grade', '—')} 级", code
    if kind == "position":
        pp = state.get("position_plan") or {}
        if not code or not pp:
            return "", ""
        nb = len(pp.get("batches") or [])
        return f"{code} 建仓方案 {nb} 批", str(pp.get("plan_id") or code)
    if kind == "monitor":
        sig = state.get("holding_signal") or {}
        if not code or not sig:
            return "", ""
        return f"{code} 监控信号 {sig.get('action', '—')}", str(state.get("holding_id") or code)
    if kind == "sell":
        sd = state.get("sell_decision") or {}
        if not code or not sd:
            return "", ""
        return f"{code} 卖出决策 {sd.get('action', '—')}", str(state.get("holding_id") or code)
    if kind == "review":
        es = state.get("exit_suggest") or {}
        if not code or not es:
            return "", ""
        pnl = es.get("pnl_pct")
        pnl_txt = f"{pnl:+.2f}%" if isinstance(pnl, (int, float)) else "—"
        return f"{code} 复盘 持有 {es.get('hold_days', '—')} 天 盈亏 {pnl_txt}", \
            str(state.get("holding_id") or code)
    return "", ""


def _record_pending_experience(kind: str, state: dict) -> None:
    """热路径经验沉淀钩子：单行 INSERT，零分析，失败静默降级（不阻塞主任务）。
    复盘经验最有价值（run_review 重点）；market_intel/portfolio_sentinel 不沉淀（宁缺毋滥）。"""
    try:
        stage_map = {"discover": "选股", "score": "选股", "position": "建仓",
                     "monitor": "持仓", "sell": "持仓", "review": "持仓"}
        if kind not in stage_map:
            return
        summary, artifacts = _exp_summary(kind, state)
        if not summary:
            return
        trade_date = state.get("trade_date") or time.strftime("%Y-%m-%d")
        from app.db import repo
        repo.add_pending_experience(f"{kind}:{trade_date}", stage_map[kind], summary, artifacts)
    except Exception:  # noqa: BLE001 热路径钩子绝不抛异常影响主任务
        logger.warning("record_pending_experience 失败（降级不影响主任务）", exc_info=True)


def run_discover(trade_date: str | None = None) -> StockAgentState:
    """每日潜力股挖掘：硬过滤 → LLM 初选 → 新闻核实 → 最终候选落库"""
    date_key = trade_date or time.strftime("%Y-%m-%d")
    graph = get_graph("discover")
    state = _new_state(trade_date=date_key)
    result = graph.invoke(state)
    logger.info("discover 完成: candidates=%s", len(result.get("candidates") or []))
    _record_pending_experience("discover", result)
    return result


def run_score(code: str, stock_name: str = "", trade_date: str | None = None) -> StockAgentState:
    """单股多维打分"""
    graph = get_graph("score")
    state = _new_state(stock_code=code, stock_name=stock_name or code,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"))
    result = graph.invoke(state)
    _record_pending_experience("score", result)
    return result


# B 级建仓计划缓存时长（分级缓存：B 级 30 分钟，A 级实时计算）
_PLAN_CACHE_TTL_30M = 1800


def run_position(code: str, stock_name: str = "", trade_date: str | None = None,
                 source: str = "manual") -> StockAgentState:
    """单股建仓方案（数据同源联动 + 分级缓存 + 来源标记）：
    1) 标的来源唯一：仅最新综合评级 ≥B 的标的可生成；无评分 → 自动先跑一次
       ScoreAgent 再判级；C 级及以下（或无评级）→ 抛「评级不足」错误，禁止生成；
    2) 分级缓存：B 级 30 分钟缓存（当日已有计划且 30 分钟内直接复用，零 LLM 调用）；
       A 级实时计算，每次重新生成；
    3) 同一标的同一交易日仅保留最新一份（repo.insert_plan 去重）；
    4) source 来源标记：candidate=每日候选池联动 / manual=手动生成。"""
    from app.db import repo

    today = trade_date or time.strftime("%Y-%m-%d")
    score_row = repo.get_latest_score(code)
    if score_row is None:
        logger.info("建仓标的无评分，自动先执行评分: %s", code)
        run_score(code, stock_name, today)
        score_row = repo.get_latest_score(code)
    grade = (score_row.grade or "") if score_row else ""
    if not score_row or grade not in ("A", "B"):
        cur = grade or "无评级"
        raise ValueError(f"评级不足（当前 {cur}），暂不生成建仓计划；仅 B 级及以上评级标的可生成，"
                         f"可先在「评分报告」页完成/确认评分")
    if grade == "B":
        existing = repo.get_latest_plan(code)
        if existing is not None and existing.plan_date == today:
            age = (time.time() - existing.created_at.timestamp()) if existing.created_at else 9999.0
            if age < _PLAN_CACHE_TTL_30M:
                logger.info("建仓计划命中 B 级 30 分钟缓存: %s plan_id=%s age=%.0fs",
                            code, existing.id, age)
                return _new_state(stock_code=code, stock_name=stock_name or code,
                                  trade_date=today,
                                  position_plan={"plan_id": existing.id, "cached": True})
    graph = get_graph("position")
    state = _new_state(stock_code=code, stock_name=stock_name or code, trade_date=today,
                       plan_source=source)
    result = graph.invoke(state)
    _record_pending_experience("position", result)
    return result


def run_monitor(holding_id: int, trade_date: str | None = None,
                batch_quotes: dict[str, dict] | None = None) -> StockAgentState:
    """单持仓监控（行情 → LLM 信号 → 去重推送）"""
    from app.db import repo

    holding = repo.get_holding(holding_id)
    if holding is None:
        return _new_state(holding_id=holding_id, error=f"持仓不存在: {holding_id}")
    graph = get_graph("monitor")
    state = _new_state(holding_id=holding_id, stock_code=holding.stock_code,
                       stock_name=holding.stock_name,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"),
                       batch_quotes=batch_quotes)
    result = graph.invoke(state)
    _record_pending_experience("monitor", result)
    return result


def run_monitor_all(trade_date: str | None = None) -> list[StockAgentState]:
    """批量监控全部持仓：行情一次批量预取（全持仓统一获取后再过滤），
    避免逐只循环请求触发数据源限流；单持仓手动监控路径不受影响"""
    from app.db import repo
    from app.datasource.fallback import get_datasource

    holdings = repo.get_active_holdings()
    codes = [h.stock_code for h in holdings]
    batch: dict[str, dict] = {}
    try:
        batch = get_datasource().fetch_spot_quotes_batch(codes) if codes else {}
    except Exception as exc:  # noqa: BLE001 批量预取失败不阻塞监控（逐只路径自动兜底）
        logger.warning("批量行情预取失败，监控走逐只取数: %s", exc)
    results = []
    for h in holdings:
        try:
            results.append(run_monitor(h.id, trade_date, batch))
        except Exception as exc:  # noqa: BLE001 单持仓失败不阻塞其他
            logger.error("监控 %s 失败: %s", h.stock_code, exc)
    logger.info("批量监控完成: %s/%s（批量行情命中 %s/%s）",
                len(results), len(holdings), len(batch), len(codes))
    return results


def run_sell_decision(holding_id: int, trade_date: str | None = None) -> StockAgentState:
    """单持仓卖出决策（人工按需触发）"""
    from app.db import repo

    holding = repo.get_holding(holding_id)
    if holding is None:
        return _new_state(holding_id=holding_id, error=f"持仓不存在: {holding_id}")
    graph = get_graph("sell")
    state = _new_state(holding_id=holding_id, stock_code=holding.stock_code,
                       stock_name=holding.stock_name,
                       trade_date=trade_date or time.strftime("%Y-%m-%d"))
    result = graph.invoke(state)
    _record_pending_experience("sell", result)
    return result


def run_review(holding_id: int, trade_date: str | None = None) -> StockAgentState:
    """卖出复盘"""
    graph = get_graph("review")
    state = _new_state(holding_id=holding_id, trade_date=trade_date or time.strftime("%Y-%m-%d"))
    result = graph.invoke(state)
    _record_pending_experience("review", result)
    return result


def run_market_intel(trade_date: str | None = None) -> StockAgentState:
    """市场研判底座（独立触发：每日收盘后 1 次 + 手动入口）。
    产出 market_intel 落库，作为全部 agent 的参考维度注入，不强制改变任何判级。"""
    graph = get_graph("market_intel")
    state = _new_state(trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_portfolio_sentinel(trade_date: str | None = None) -> StockAgentState:
    """组合哨兵巡检（独立触发：交易时段每 10 分钟自动 + 手动入口）。
    与 MonitorAgent 零耦合；无持仓时正常跳过（skipped=True），不报错。"""
    graph = get_graph("portfolio_sentinel")
    state = _new_state(trade_date=trade_date or time.strftime("%Y-%m-%d"))
    return graph.invoke(state)


def run_daily_pipeline(trade_date: str | None = None) -> dict:
    """每日主链路：discover → 对全部候选打分（供面板查看评分）

    批量打分自动切换并行模式：候选 ≥5 只时以线程池并发执行（每只独立走
    run_score 图，同一 prompt/schema，结果与串行一致，提速不降质）；
    候选 <5 只保持单 Agent 串行模式。SQLite 已启用 WAL + busy_timeout，并发安全。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    date_key = trade_date or time.strftime("%Y-%m-%d")
    discover_result = run_discover(date_key)
    candidates = discover_result.get("candidates") or []

    def _score_one(cand: dict) -> dict | None:
        try:
            res = run_score(cand["stock_code"], cand["stock_name"], date_key)
            return {"code": cand["stock_code"], "name": cand.get("stock_name") or "",
                    "score": (res.get("score_result") or {}).get("score"),
                    "grade": (res.get("score_result") or {}).get("grade")}
        except Exception as exc:  # noqa: BLE001 单股失败不阻塞其他
            logger.error("打分失败 %s: %s", cand["stock_code"], exc)
            return None

    scores = []
    if len(candidates) >= _PARALLEL_SCORE_MIN:
        with ThreadPoolExecutor(max_workers=min(_PARALLEL_SCORE_MAX, len(candidates))) as pool:
            futures = [pool.submit(_score_one, cand) for cand in candidates]
            for fut in as_completed(futures):
                item = fut.result()
                if item:
                    scores.append(item)
    else:
        for cand in candidates:
            item = _score_one(cand)
            if item:
                scores.append(item)
    logger.info("批量打分完成: %s/%s（并行模式: %s）", len(scores), len(candidates),
                len(candidates) >= _PARALLEL_SCORE_MIN)

    # 三级同源联动：B 级及以上候选自动生成建仓计划（run_position 内含 B 级 30min 缓存
    # 与 C 级门槛，同一套算法无两套标准；单股失败不阻塞主链路）
    bplus = [s for s in scores if (s.get("grade") or "") in ("A", "B")]

    def _plan_one(item: dict) -> int:
        try:
            res = run_position(item["code"], item.get("name", ""), date_key, source="candidate")
            return 1 if res.get("position_plan") else 0
        except Exception as exc:  # noqa: BLE001 单股计划失败不阻塞其他
            logger.warning("建仓计划生成失败 %s: %s", item["code"], exc)
            return 0

    plans_made = 0
    if bplus:
        if len(bplus) >= _PARALLEL_SCORE_MIN:
            with ThreadPoolExecutor(max_workers=min(_PARALLEL_SCORE_MAX, len(bplus))) as pool:
                plans_made = sum(pool.map(_plan_one, bplus))
        else:
            plans_made = sum(_plan_one(i) for i in bplus)
    logger.info("建仓计划联动完成: B+ 候选 %s 只，生成 %s 份", len(bplus), plans_made)

    # 候选池「可建仓」标签联动：细筛（批量 run_score）落库后立即按本轮 stock_score.grade
    # 重算当日判定为终态（与建仓 gate 同源：评分 C/无评分 → 观察/未评级，绝不假标可建仓）；
    # 幂等覆盖（code+date 唯一），失败仅降级不阻塞主链路；页面请求不再触发口径差异的懒算。
    tradeable_n = 0
    try:
        from app.services import candidate_tradeable

        tradeable_n = candidate_tradeable.ensure_tradeable(date_key)
        logger.info("候选池可建仓标签联动完成: %s 只（%s）", tradeable_n, date_key)
    except Exception as exc:  # noqa: BLE001 标签联动失败不阻塞主链路
        logger.warning("候选池可建仓标签联动失败 %s: %s", date_key, exc)
    return {"candidates": len(candidates), "scored": len(scores), "plans": plans_made,
            "tradeable": tradeable_n}
