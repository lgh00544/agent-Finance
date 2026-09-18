"""Coordinate existing monitor/sell adapters with an isolated paper ledger."""
from __future__ import annotations

import logging
import math
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import repo
from app.services import paper_analysis, paper_context, paper_execution, paper_valuation

logger = logging.getLogger(__name__)
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_CONTEXT_MINUTES = 15


def _quote_problem(quote: dict, trade_date: str, mode: str) -> str:
    try:
        price = float(quote.get("price") or 0)
    except (TypeError, ValueError):
        return "行情缺失或价格无效"
    if not math.isfinite(price) or price <= 0 or quote.get("status") != "ok":
        return "行情缺失或价格无效"
    if str(quote.get("fact_as_of") or "")[:10] != trade_date:
        return "行情事实日期与模拟决策日期不一致"
    if mode == "live_paper":
        raw_time = str(quote.get("quote_time") or "")
        try:
            observed = datetime.fromisoformat(raw_time)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=_SHANGHAI)
            age = (datetime.now(_SHANGHAI) - observed).total_seconds()
        except ValueError:
            return "行情时间不可核验"
        if age < -5 or age > paper_valuation.FRESH_MINUTES * 60:
            return "行情已过期或来自未来"
    return ""


def _research(account_id: int, code: str, trade_date: str, mode: str,
              recent: list[dict], historical_facts: dict | None) -> dict:
    if mode == "historical_replay":
        return paper_context.collect(account_id, code, trade_date, mode=mode,
                                     historical_facts=historical_facts or {})
    now = datetime.now(_SHANGHAI)
    for row in recent:
        if (row.get("stock_code") != code or row.get("mode") != mode or
                row.get("trade_date") != trade_date or row.get("stage") != "research"):
            continue
        try:
            created = datetime.fromisoformat(str(row.get("created_at") or ""))
            if created.tzinfo is None:
                created = created.replace(tzinfo=_SHANGHAI)
            age = (now - created).total_seconds()
            if 0 <= age <= _CONTEXT_MINUTES * 60:
                return row
        except ValueError:
            continue
    return paper_context.collect(account_id, code, trade_date, mode=mode,
                                 web_query=f"{code} 公告 风险 最新")


def run(account_id: int, trade_date: str, *, mode: str = "live_paper",
        historical_facts: dict | None = None) -> dict:
    """Refresh paper facts, analyse holdings, and delegate approved paper exits."""
    if mode not in {"live_paper", "historical_replay"}:
        raise ValueError("模拟监控模式无效")
    if mode == "live_paper" and trade_date != datetime.now(_SHANGHAI).date().isoformat():
        raise ValueError("实时模拟监控只支持当前交易日；历史日期请使用冻结事实回放")
    if mode == "historical_replay" and not isinstance(historical_facts, dict):
        raise ValueError("历史监控需要调用方提供冻结事实")
    account = repo.get_paper_account(account_id)
    if account is not None and account.status == "archived":
        raise ValueError("模拟账户已归档，禁止监控")
    if account is None or account.status != "active":
        raise ValueError("模拟账户不存在或未启用")
    if mode == "live_paper":
        valuation = paper_valuation.refresh_account(account_id)
        positions = repo.list_paper_positions(account_id, status="holding")
        quotes = {row["stock_code"]: row for row in repo.list_paper_quotes(
            account_id, paper_valuation.FRESH_MINUTES)}
        recent = repo.list_paper_contexts(account_id, limit=100)
    else:
        # Replay must not backfill from today's positions, quotes or knowledge.
        positions = historical_facts.get("positions") or []
        quotes = historical_facts.get("quotes") or {}
        recent = []
        valuation = {"source": "historical_snapshot", "errors": []}
    results = []
    for stored_position in positions:
        code = str(stored_position.get("stock_code") or "")
        if not code:
            continue
        position = {**stored_position,
                    "entry_date": stored_position.get("opened_trade_date"),
                    "entry_price": stored_position.get("avg_price")}
        quote = dict(quotes.get(code) or {})
        context_id = None
        try:
            problem = _quote_problem(quote, trade_date, mode)
            if problem:
                alert_id = repo.create_paper_alert(account_id, code, trade_date, {
                    "severity": "warning", "alert_type": "模拟行情不可用", "message": problem})
                results.append({"stock_code": code, "status": "skipped", "reason": problem,
                                "alert_id": alert_id})
                continue
            frozen_research = (historical_facts or {}).get("contexts", {}).get(code, {})
            research = _research(account_id, code, trade_date, mode, recent, frozen_research)
            context = {**(research.get("facts") or {}), "mode": mode,
                       "trade_date": trade_date, "decision_date": trade_date,
                       "fact_as_of": quote.get("fact_as_of"),
                       "context_id": research.get("id"),
                       "tool_trace": research.get("tool_trace") or [],
                       "source_refs": research.get("source_refs") or []}
            monitor = paper_analysis.monitor_position(position, quote, context)
            signal = monitor.get("signal") or {}
            sell = None
            if monitor.get("status") == "ok" and signal.get("action") in {"reduce", "exit"}:
                sell = paper_analysis.sell_position(position, quote, context, signal)
            decision = (sell or {}).get("decision") or {}
            cycle = {"position": position, "quote": quote, "research_context_id": research.get("id"),
                     "monitor": monitor, "sell": sell, "mode": mode,
                     "trade_date": trade_date, "fact_as_of": quote.get("fact_as_of")}
            context_id = repo.create_paper_context(account_id, trade_date, mode, code,
                                                   "monitor", cycle, context["tool_trace"],
                                                   context["source_refs"])
            healthy = monitor.get("status") == "ok" and (sell is None or sell.get("status") == "ok")
            alert_id = repo.create_paper_alert(account_id, code, trade_date, {
                "severity": signal.get("severity", "info") if healthy else "warning",
                "alert_type": signal.get("alert_type") if healthy else "模拟分析未完成",
                "message": signal.get("message", "模拟持仓继续观察") if healthy else
                           str((sell or monitor).get("reason") or "模型或事实不可用"),
                "context_id": context_id})
            item = {"stock_code": code, "status": "ok" if healthy else "error",
                    "context_id": context_id, "alert_id": alert_id,
                    "monitor": monitor, "sell": sell}
            if healthy and decision.get("action") in {"partial", "sell"}:
                ratio = decision.get("reduce_ratio") if decision.get("action") == "partial" else 1.0
                if ratio is None or not 0 < float(ratio) <= 1:
                    item.update(status="skipped", reason="减仓比例缺失或无效")
                else:
                    execution_quote = quote
                    if mode == "live_paper":
                        # Evidence/LLM calls may take minutes; fills need a post-decision quote.
                        paper_valuation.refresh_account(account_id)
                        execution_quote = next((row for row in repo.list_paper_quotes(
                            account_id, paper_valuation.FRESH_MINUTES) if row.get("stock_code") == code), {})
                    execution_problem = _quote_problem(execution_quote, trade_date, mode)
                    if execution_problem:
                        item.update(status="skipped", reason=execution_problem)
                        item["execution_alert_id"] = repo.create_paper_alert(account_id, code, trade_date, {
                            "severity": "warning", "alert_type": "模拟成交行情不可用",
                            "message": execution_problem, "context_id": context_id})
                        results.append(item)
                        continue
                    execution_context = {**context, "context_id": context_id,
                                         "research_context_id": research.get("id"),
                                         "sell_decision": decision, "monitor_signal": signal}
                    item["execution"] = paper_execution.run(
                        account_id, trade_date, facts={"mode": mode, "contexts": {code: execution_context},
                                                      "sell_decisions": {code: decision}},
                        requested_sides={code: "sell"}, position_facts=[position],
                        quote_facts={code: execution_quote})
            results.append(item)
        except Exception as exc:  # One paper position must not break other accounts or real monitoring.
            logger.warning("模拟持仓 %s 分析失败: %s", code, exc)
            alert_id = repo.create_paper_alert(account_id, code, trade_date, {
                "severity": "warning", "alert_type": "模拟监控异常",
                "message": str(exc)[:300], "context_id": context_id})
            results.append({"stock_code": code, "status": "error", "error": str(exc)[:300],
                            "alert_id": alert_id, "context_id": context_id})
    return {"account_id": account_id, "trade_date": trade_date, "mode": mode,
            "execution_mode": "paper", "source_label": "AI模拟", "valuation": valuation,
            "monitored": len(results), "results": results}
