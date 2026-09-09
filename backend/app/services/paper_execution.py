"""AI 模拟执行 Agent：只消费已有候选/评分/建仓事实，不重新选股、不改规则。

LLM（若上层提供）只能产生买卖意图；本模块是确定性账本适配器，负责 A 股成交约束，
并且只写 paper_* 表。真实 Holding/TradeRecord 和券商接口永远不在本模块中调用。
"""
from __future__ import annotations

import math
import copy
import hashlib
import json
from datetime import date, datetime, timedelta

from app.db import repo

LOT_SIZE = 100
COMMISSION_RATE = 0.0003
COMMISSION_MIN = 5.0
STAMP_TAX_RATE = 0.0005
TRANSFER_RATE = 0.00001
SLIPPAGE_BPS = 5.0
LIMIT_PCT_DEFAULT = 0.10
RULE_VERSION = "paper-execution-v1"


def _next_date(trade_date: str) -> str:
    try:
        return (date.fromisoformat(trade_date) + timedelta(days=1)).isoformat()
    except ValueError:
        return trade_date


def _num(value, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _fact_is_available(value: object, trade_date: str) -> bool:
    """未来数据隔离：只允许 YYYY-MM-DD/时间戳不晚于决策日。"""
    raw = str(value or "").strip()[:10]
    if not raw:
        return True
    try:
        return date.fromisoformat(raw) <= date.fromisoformat(trade_date)
    except ValueError:
        return False


_DATE_FACT_KEYS = {
    "fact_as_of", "as_of", "observed_at", "available_at", "published_at",
    "quote_date", "decision_date", "trade_date", "plan_date", "quote_time", "fetched_at",
    "created_at", "updated_at", "score_date", "date",
}


def _future_fact_paths(value: object, trade_date: str, path: str = "") -> list[str]:
    """递归找出事实包中晚于决策日的观测/来源日期。

    ``available_on`` 是模拟 T+1 的派生可卖日期，不属于行情事实，因此刻意不纳入
    日期键；其余日期只要显式出现在事实包中就必须不晚于 ``trade_date``。
    """
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            if str(key).lower() in _DATE_FACT_KEYS:
                if not _fact_is_available(item, trade_date):
                    found.append(child)
            else:
                found.extend(_future_fact_paths(item, trade_date, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_future_fact_paths(item, trade_date, f"{path}[{index}]"))
    return found


def _snapshot_price(snapshot: dict) -> float:
    return _num(snapshot.get("price") or snapshot.get("close"))


def _fees(side: str, gross: float, code: str) -> tuple[float, float, float, float]:
    commission = max(COMMISSION_MIN, gross * COMMISSION_RATE) if gross > 0 else 0.0
    stamp = gross * STAMP_TAX_RATE if side == "sell" else 0.0
    transfer = gross * TRANSFER_RATE if side in ("buy", "sell") else 0.0
    total = gross + commission + stamp + transfer if side == "buy" else gross - commission - stamp - transfer
    return round(commission, 2), round(stamp, 2), round(transfer, 2), round(total, 2)


def _limit_pct(code: str, snapshot: dict) -> float:
    explicit = _num(snapshot.get("limit_pct"), 0.0)
    if explicit > 0:
        return explicit / 100 if explicit > 1 else explicit
    if "ST" in str(snapshot.get("name") or snapshot.get("stock_name") or "").upper() and not str(code).startswith(("300", "301", "688")):
        return 0.05
    # 科创板/创业板常见 20% 涨跌幅；北交所等特殊规则必须由行情事实显式提供。
    if str(code).startswith(("300", "301", "688")):
        return 0.20
    if str(code).startswith(("4", "8", "9")):
        return 0.30
    return LIMIT_PCT_DEFAULT


def _limit_block(side: str, code: str, snapshot: dict) -> str:
    if snapshot.get("suspended") or snapshot.get("is_suspended"):
        return "suspended"
    price = _snapshot_price(snapshot)
    if price <= 0:
        return "price_missing"
    if snapshot.get("limit_up") is True and side == "buy":
        return "limit_up"
    if snapshot.get("limit_down") is True and side == "sell":
        return "limit_down"
    change = snapshot.get("change_pct")
    if change is not None:
        # 行情契约中的 change_pct 始终是百分数，0.8 表示 0.8%。
        change = _num(change) / 100
        limit = _limit_pct(code, snapshot)
        if side == "buy" and change >= limit - 1e-6:
            return "limit_up"
        if side == "sell" and change <= -limit + 1e-6:
            return "limit_down"
    return ""


def live_session_open(trade_date: str) -> bool:
    now = datetime.now()
    if trade_date != now.date().isoformat() or now.weekday() >= 5:
        return False
    from app.scheduler.jobs import _is_trading_day
    clock = now.strftime("%H:%M")
    return _is_trading_day(trade_date) and ("09:30" <= clock < "11:30" or "13:00" <= clock < "15:00")


def _live_quote_block(snapshot: dict, trade_date: str) -> str:
    from app.services.paper_valuation import quote_state
    if not live_session_open(trade_date):
        # 收盘结算窗口允许使用当日最后一笔有效行情；盘后不得用任意旧快照成交。
        raw = str(snapshot.get("quote_time") or snapshot.get("time") or "")
        try:
            observed = datetime.fromisoformat(raw)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if observed.date().isoformat() != trade_date or observed.strftime("%H:%M") < "14:50":
                return "market_closed"
        except (TypeError, ValueError):
            return "market_closed"
    if quote_state(snapshot) != "ok":
        return "quote_stale_or_time_missing"
    if _num(snapshot.get("volume")) <= 0:
        return "trading_status_missing"
    if snapshot.get("change_pct") is None and not _num(snapshot.get("prev_close")):
        return "price_limit_facts_missing"
    return ""


def _position_shares(account: dict, plan: dict, price: float, code: str = "") -> int:
    """从已有建仓计划的总仓位/首批比例计算数量，缺失时不强行交易。"""
    total_pct = _num(plan.get("total_pct"))
    batches = plan.get("batches") or []
    first = batches[0] if batches and isinstance(batches[0], dict) else {}
    ratio = _num(first.get("capital_pct") or first.get("position_pct") or first.get("weight") or first.get("ratio"), 0)
    if ratio > 1:
        ratio /= 100
    if ratio <= 0:
        ratio = 1.0
    target = _num(account.get("cash")) * (total_pct / 100.0) * ratio
    if target <= 0 or price <= 0:
        return 0
    shares = max(0, math.floor(target / price / LOT_SIZE) * LOT_SIZE)
    # 总仓位百分比是毛预算；滑点和买入费用也必须留在现金约束内，避免
    # 100% 仓位计划在落账时因几元费用抛出异常而中断整日模拟。
    executed_price = price * (1 + SLIPPAGE_BPS / 10000)
    while shares >= LOT_SIZE:
        gross = round(executed_price * shares, 2)
        if _fees("buy", gross, code)[3] <= _num(account.get("cash")) + 1e-8:
            break
        shares -= LOT_SIZE
    return shares


def _payload(account: dict, row: dict, candidate: dict, score: dict | None,
             plan: dict | None, side: str, shares: int, requested_price: float,
             trade_date: str, snapshot: dict, status: str, reason: str = "") -> dict:
    execution_key = f"paper:{account['id']}:{trade_date}:{row.get('stock_code')}:{side}"
    executed = requested_price * (1 + SLIPPAGE_BPS / 10000) if side == "buy" else requested_price * (1 - SLIPPAGE_BPS / 10000)
    executed = round(executed, 4)
    gross = round(executed * shares, 2)
    commission, stamp, transfer, total = _fees(side, gross, row.get("stock_code") or "")
    if status != "filled":
        executed = None
        gross = commission = stamp = transfer = total = 0.0
    plan_detail = plan or {}
    return {
        "execution_key": execution_key, "decision_id": f"{trade_date}:{row.get('stock_code')}",
        "candidate_id": candidate.get("id"), "score_id": (score or {}).get("id"),
        "plan_id": plan_detail.get("id"), "stock_code": row.get("stock_code") or "",
        "stock_name": row.get("stock_name") or candidate.get("stock_name") or "",
        "side": side, "requested_price": requested_price, "executed_price": executed,
        "shares": shares, "gross_amount": gross, "commission": commission,
        "stamp_tax": stamp, "transfer_fee": transfer, "total_amount": total,
        "trade_date": trade_date, "fact_as_of": str(snapshot.get("fact_as_of") or trade_date),
        "available_on": _next_date(trade_date), "status": status, "reject_reason": reason,
        "strategy_variant": account.get("strategy_variant") or "current_gate",
        "rule_version": account.get("rule_version") or RULE_VERSION,
        "model_version": account.get("model_version") or "",
        "source_label": "AI模拟",
        "metadata_json": {"prev_close": snapshot.get("prev_close"),
                           "change_pct": snapshot.get("change_pct"),
                           "stop_loss": plan_detail.get("stop_loss", 0),
                           "take_profit": plan_detail.get("take_profit", 0),
                           "cost_model": {"slippage_bps": SLIPPAGE_BPS,
                                          "commission_rate": COMMISSION_RATE,
                                          "stamp_tax_rate": STAMP_TAX_RATE,
                                          "transfer_rate": TRANSFER_RATE}},
    }


def _load_facts(trade_date: str) -> tuple[list[dict], dict, dict, dict]:
    tradeable = repo.list_candidate_tradeable(trade_date, limit=300)
    candidates = {r.get("stock_code"): r for r in repo.list_candidates(trade_date, limit=300)}
    scores = {r.get("stock_code"): r for r in repo.list_scores(date=trade_date, limit=500)}
    plans = {}
    for code in candidates:
        rows = repo.list_plans(code=code, limit=20)
        plans[code] = next((p for p in rows if p.get("status") != "expired"
                            and _fact_is_available(p.get("plan_date"), trade_date)), None)
    return tradeable, candidates, scores, plans


def run(account_id: int, trade_date: str, *, facts: dict | None = None,
        requested_sides: dict[str, str] | None = None,
        position_facts: list[dict] | None = None, quote_facts: dict | None = None,
        requested_shares: dict[str, int] | None = None) -> dict:
    """运行一个交易日；可传入 facts 进行历史重放，禁止读取未来行情。"""
    account = repo.get_paper_account(account_id)
    if account is None:
        raise ValueError("模拟账户不存在")
    if account.status != "active":
        raise ValueError("模拟账户不是 active 状态")
    date.fromisoformat(trade_date)
    mode = (facts or {}).get("mode") or ("live_paper" if facts is None else "historical_replay")
    if mode not in {"live_paper", "historical_replay"}:
        raise ValueError("未知模拟事实模式")
    if facts is None and trade_date != date.today().isoformat():
        raise ValueError("历史回放必须提供冻结事实，不能读取当前数据库补齐历史")
    requested_sides = requested_sides or {}
    if any(side not in {"buy", "sell"} for side in requested_sides.values()):
        raise ValueError("模拟方向仅支持 buy/sell")
    repo.release_paper_t1(account_id, trade_date)
    if facts is None:
        tradeable, candidates, scores, plans = _load_facts(trade_date)
    else:
        tradeable = facts.get("tradeable") or []
        candidates = facts.get("candidates") or {}
        scores = facts.get("scores") or {}
        plans = facts.get("plans") or {}
    account_dict = {"id": account.id, "cash": account.cash,
                    "strategy_variant": account.strategy_variant,
                    "rule_version": account.rule_version, "model_version": account.model_version}
    positions = {p["stock_code"]: p for p in repo.list_paper_positions(account_id, status="holding")}
    supplied_positions = {p["stock_code"]: p for p in (position_facts or [])}
    contexts = (facts or {}).get("contexts") or {}
    quote_facts = copy.deepcopy(quote_facts or {})
    tradeable = copy.deepcopy(tradeable)
    present = {r.get("stock_code") for r in tradeable}
    for code, side in requested_sides.items():
        if side == "sell" and code not in present:
            tradeable.append({"stock_code": code, "stock_name": (positions.get(code) or {}).get("stock_name", code)})
    if mode == "live_paper" and not quote_facts and tradeable:
        from app.services.paper_valuation import fetch_quotes
        try:
            quote_facts, _ = fetch_quotes([r["stock_code"] for r in tradeable])
        except Exception:
            quote_facts = {}
    results = []
    for row in tradeable:
        code = row.get("stock_code") or ""
        if not code:
            continue
        candidate = candidates.get(code) if isinstance(candidates, dict) else next((x for x in candidates if x.get("stock_code") == code), {})
        score = scores.get(code) if isinstance(scores, dict) else next((x for x in scores if x.get("stock_code") == code), None)
        plan = plans.get(code) if isinstance(plans, dict) else None
        snapshot = (candidate or {}).get("snapshot") or {}
        snapshot = {**snapshot, **((row.get("detail") or {}).get("snapshot") or {})}
        if mode == "live_paper" or code in quote_facts:
            snapshot = copy.deepcopy(quote_facts.get(code) or {})
        snapshot.setdefault("name", row.get("stock_name") or "")
        position = positions.get(code) or {}
        context = contexts.get(code) or {}
        if mode == "live_paper" and not context and row.get("is_tradeable") and code not in positions:
            from app.services import paper_context
            context = paper_context.collect(account_id, code, trade_date,
                                            base_facts={"candidate": candidate or {}, "score": score or {},
                                                        "plan": plan or {}, "tradeable": row},
                                            web_query=f"{code} {row.get('stock_name') or ''} 公告 风险")
            from app.services.paper_valuation import fetch_quotes
            # 研究发生在前，撮合报价发生在后，不能按研究前价格追溯成交。
            fresh, _ = fetch_quotes([code])
            snapshot = fresh.get(code) or {}
        price = _snapshot_price(snapshot) or _num(row.get("current_price"))
        auto_exit = bool(code in positions and plan and (
            (_num(plan.get("take_profit")) > 0 and price >= _num(plan.get("take_profit"))) or
            (_num(plan.get("stop_loss")) > 0 and price <= _num(plan.get("stop_loss")))))
        side = requested_sides.get(code, "sell" if auto_exit else "buy")
        future_fields = _future_fact_paths(
            {"tradeable": row, "candidate": candidate or {},
             "score": score or {}, "plan": plan or {}, "snapshot": snapshot,
             "context": context},
            trade_date,
        )
        if future_fields:
            payload = _payload(account_dict, row, candidate or {}, score, plan, side, 0,
                               price, trade_date, snapshot, "rejected", "future_data")
            payload["metadata_json"]["future_fields"] = future_fields[:32]
            results.append(repo.paper_apply_execution(account_id, payload))
            continue
        live_block = _live_quote_block(snapshot, trade_date) if mode == "live_paper" else ""
        if live_block:
            payload = _payload(account_dict, row, candidate or {}, score, plan, side, 0, price, trade_date, snapshot, "rejected", live_block)
        elif side == "buy":
            if not row.get("is_tradeable"):
                payload = _payload(account_dict, row, candidate or {}, score, plan, side, 0, price, trade_date, snapshot, "rejected", "not_tradeable")
            elif code in positions:
                payload = _payload(account_dict, row, candidate or {}, score, plan, side, 0, price, trade_date, snapshot, "rejected", "already_holding")
            elif not plan or not score or not candidate or price <= 0:
                payload = _payload(account_dict, row, candidate or {}, score, plan, side, 0, price, trade_date, snapshot, "rejected", "plan_or_price_missing")
            else:
                shares = _position_shares(account_dict, plan, price, code)
                reason = _limit_block(side, code, snapshot)
                if mode == "live_paper":
                    from app.services.candidate_tradeable import _zone_bounds
                    batches = plan.get("batches") or []
                    bounds = _zone_bounds((batches[0] if batches else {}).get("price_zone") or "")
                    if not bounds or not bounds[0] <= price <= bounds[1]:
                        reason = reason or "outside_entry_zone"
                if shares < LOT_SIZE:
                    reason = reason or "cash_or_plan_position_too_small"
                payload = _payload(account_dict, row, candidate or {}, score, plan, side, shares, price, trade_date, snapshot,
                                   "filled" if not reason else "rejected", reason)
        else:
            pos = positions.get(code)
            shares = pos.get("available_shares", 0) if pos else 0
            decision = ((facts or {}).get("sell_decisions") or {}).get(code) or supplied_positions.get(code, {}).get("sell_decision") or {}
            if decision.get("action") in {"partial", "reduce"}:
                ratio = _num(decision.get("reduce_ratio"))
                shares = min(shares, int((pos or {}).get("shares", 0) * ratio)) if 0 < ratio <= 1 else 0
            if requested_shares and code in requested_shares:
                shares = min(shares, max(0, int(requested_shares[code])))
            if not pos:
                reason = "no_position"
            elif shares < LOT_SIZE:
                reason = "t_plus_one_or_no_lot"
            else:
                reason = _limit_block(side, code, snapshot)
            payload = _payload(account_dict, row, candidate or {}, score, plan, side,
                               (shares // LOT_SIZE) * LOT_SIZE, price, trade_date, snapshot,
                               "filled" if not reason else "rejected", reason)
        # 每次意图冻结自己的事实，重试同一上下文幂等，新行情允许形成新意图。
        trace = {"tradeable": row, "candidate": candidate or {}, "score": score or {},
                 "plan": plan or {}, "quote": snapshot, "position": position,
                 "mode": mode, "trade_date": trade_date,
                 "sell_decision": ((facts or {}).get("sell_decisions") or {}).get(code) or {}}
        if not context:
            context_id = repo.create_paper_context(account_id, trade_date, mode, code, "execution", trace)
            context = {"id": context_id, "facts": trace}
        metadata = payload["metadata_json"]
        metadata.update({"mode": mode, "context_id": context.get("id") or supplied_positions.get(code, {}).get("context_id"),
                         "source_refs": context.get("source_refs") or [], "tool_trace": context.get("tool_trace") or [],
                         "facts": trace})
        metadata["context_hash"] = context.get("content_hash") or ""
        if mode == "live_paper":
            digest = hashlib.sha256(json.dumps({"quote": snapshot, "side": side, "context_id": metadata["context_id"]}, sort_keys=True, default=str).encode()).hexdigest()[:20]
            payload["execution_key"] += f":{digest}"
        # A rejected event is intentionally persisted to explain why no trade occurred.
        results.append(repo.paper_apply_execution(account_id, payload))
        if results[-1]["status"] == "filled":
            if side == "sell":
                # 复盘事实先落 pending；后续必须调用 review Agent 审核，再进入 paper_shadow。
                existing_reviews = repo.list_paper_reviews(account_id, limit=500)
                if not any(r.get("execution_id") == results[-1].get("id") for r in existing_reviews):
                    repo.create_paper_review(
                        account_id, code, row.get("stock_name") or code, trade_date,
                        {"execution_id": results[-1].get("id"), "execution_mode": "paper",
                         "source_type": "paper", "decision_id": payload.get("decision_id"),
                         "candidate_id": payload.get("candidate_id"),
                         "score_id": payload.get("score_id"), "plan_id": payload.get("plan_id"),
                         "trade_date": trade_date, "fact_as_of": payload.get("fact_as_of"),
                         "status": "filled", "mode": mode, "context_id": metadata["context_id"],
                         "position": position, "quote": snapshot, "context": context,
                         "exit_execution": results[-1],
                         "pnl_amount": round(results[-1]["total_amount"] - _num(position.get("avg_price")) * results[-1]["shares"], 2)},
                        execution_id=results[-1].get("id"))
            account = repo.get_paper_account(account_id)
            account_dict["cash"] = account.cash if account else account_dict["cash"]
            positions = {p["stock_code"]: p for p in repo.list_paper_positions(account_id, status="holding")}
    return {"account_id": account_id, "trade_date": trade_date, "execution_mode": "paper",
            "source_label": "AI模拟", "rule_version": RULE_VERSION,
            "filled": sum(1 for r in results if r["status"] == "filled"),
            "rejected": sum(1 for r in results if r["status"] != "filled"),
            "executions": results}
