"""Freeze read-only paper research facts before analysis or historical replay."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time as day_time, timezone, timedelta
import hashlib
import json
from typing import Any

from app.agents import agentic_tools
from app.db import repo
from app.services import paper_web

TOOL_ARGS = {
    "get_quote": lambda c, d: {"code": c},
    "get_daily_kline": lambda c, d: {"code": c, "days": 30},
    "get_news": lambda c, d: {"code": c, "limit": 8},
    "get_financial": lambda c, d: {"code": c},
    "get_fund_flow": lambda c, d: {"code": c},
    "search_knowledge": lambda c, d: {"code": c, "query": "趋势 资金 风险", "top_k": 5},
    "get_sector_regime": lambda c, d: {"trade_date": d},
    "get_factor_calibration": lambda c, d: {"period": "t5"},
    "get_distribution_phase": lambda c, d: {"code": c, "trade_date": d},
    "get_capital_view": lambda c, d: {"code": c, "trade_date": d},
    "get_hot_money_context": lambda c, d: {"code": c, "trade_date": d},
}
PAPER_READONLY_TOOLS = tuple(TOOL_ARGS)
_ZONE = timezone(timedelta(hours=8))
_TIME_KEYS = frozenset({
    "date", "trade_date", "decision_date", "decision_at", "fact_as_of", "as_of",
    "observed_at", "available_at", "published_at", "fetched_at", "created_at",
    "updated_at", "quote_time", "timestamp", "plan_date", "entry_date", "exit_date",
    "review_date", "opened_trade_date", "latest_date", "generate_date", "report_date",
})


def _now() -> datetime:
    return datetime.now(_ZONE)


def require_mode_date(mode: str, trade_date: str) -> date:
    if mode not in {"live_paper", "historical_replay"}:
        raise ValueError("paper context mode 仅支持 live_paper/historical_replay")
    if not isinstance(trade_date, str) or len(trade_date) != 10:
        raise ValueError("trade_date 必须为 YYYY-MM-DD")
    parsed = date.fromisoformat(trade_date)
    today = _now().date()
    if mode == "live_paper" and parsed != today:
        raise ValueError("live_paper 仅可用于今天；历史日期必须使用冻结事实重放")
    if parsed > today:
        raise ValueError("不得使用未来交易日期")
    return parsed


def _timestamp(value: Any, *, end_of_day: bool = False) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, day_time.max if end_of_day else day_time.min)
    elif isinstance(value, str):
        raw = value.strip()
        if len(raw) == 10:
            parsed = datetime.combine(date.fromisoformat(raw), day_time.max if end_of_day else day_time.min)
        else:
            if len(raw) < 19 or raw[10] not in {"T", " "}:
                raise ValueError("invalid timestamp")
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        raise ValueError("invalid timestamp")
    return parsed.replace(tzinfo=_ZONE) if parsed.tzinfo is None else parsed.astimezone(_ZONE)


def snapshot_time_errors(value: Any, cutoff: Any, path: str = "") -> list[str]:
    """Check observation timestamps recursively, preserving intraday precision.

    Settlement/expiry dates such as available_on are schedules, not observations.
    Empty optional dates express missing data; malformed nonempty dates are rejected.
    """
    try:
        boundary = _timestamp(cutoff, end_of_day=True)
    except (ValueError, TypeError):
        return ["invalid:decision_cutoff"]
    errors = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            if str(key).lower() in _TIME_KEYS and item not in (None, ""):
                try:
                    observed = _timestamp(item)
                except (ValueError, TypeError):
                    errors.append(f"invalid:{child}")
                else:
                    if observed > boundary:
                        errors.append(f"future:{child}")
            elif isinstance(item, (dict, list, tuple)):
                errors.extend(snapshot_time_errors(item, boundary, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            errors.extend(snapshot_time_errors(item, boundary, f"{path}[{index}]"))
    return errors


def content_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def collect(account_id: int, stock_code: str, trade_date: str, *, mode: str = "live_paper",
            web_query: str = "", web_urls: list[str] | None = None,
            historical_facts: dict | None = None, base_facts: dict | None = None) -> dict:
    require_mode_date(mode, trade_date)
    if not stock_code:
        raise ValueError("缺少 stock_code")
    if base_facts is not None and not isinstance(base_facts, dict):
        raise ValueError("base_facts 必须为事实对象")
    facts = deepcopy(base_facts or {})
    trace, source_refs = [], []
    if mode == "historical_replay":
        if not isinstance(historical_facts, dict) or not historical_facts:
            raise ValueError("historical_replay 必须提供非空 historical_facts 冻结事实")
        if web_query or web_urls:
            raise ValueError("历史重放禁止联网补充证据")
        frozen = historical_facts.get("facts", historical_facts)
        if not isinstance(frozen, dict) or not frozen.get("fact_as_of"):
            raise ValueError("历史冻结事实必须包含 fact_as_of")
        for key, value in deepcopy(frozen).items():
            if key in facts and facts[key] != value:
                raise ValueError(f"历史冻结事实冲突: {key}")
            facts[key] = value
        source_refs = deepcopy(historical_facts.get("source_refs") or [])
        source_trace = deepcopy(historical_facts.get("tool_trace") or [])
        trace.append({"tool": "historical_snapshot", "status": "ok",
                      "content_hash": content_hash(frozen), "source_trace": source_trace})
    elif historical_facts is not None:
        raise ValueError("historical_facts 仅供 historical_replay 使用")
    for key, expected in (("stock_code", stock_code), ("trade_date", trade_date)):
        if facts.get(key) not in (None, "", expected):
            raise ValueError(f"冻结事实标识冲突: {key}")
        facts[key] = expected
    facts["mode"] = mode
    cutoff = facts.get("decision_at") or trade_date
    errors = snapshot_time_errors(facts, cutoff)
    if errors:
        raise ValueError("历史事实时间校验失败: " + "; ".join(errors[:10]))
    if mode == "live_paper":
        for name, arg_builder in TOOL_ARGS.items():
            args = arg_builder(stock_code, trade_date)
            observed_at = _now().isoformat()
            try:
                fn = agentic_tools.TOOL_FUNCS.get(name)
                if fn is None:
                    raise LookupError(f"只读工具未注册: {name}")
                result = deepcopy(fn(**args))
                tool_errors = snapshot_time_errors(result, _now())
                if tool_errors:
                    raise ValueError("工具事实时间越界: " + "; ".join(tool_errors[:5]))
            except Exception as exc:
                result = {"error": str(exc)[:256]}
            digest = content_hash(result)
            status = "error" if isinstance(result, dict) and result.get("error") else "ok"
            facts[name] = result
            trace.append({"tool": name, "status": status, "args": args,
                          "result": deepcopy(result), "observed_at": observed_at,
                          "content_hash": digest})
            source_refs.append({"type": "system_tool", "tool": name, "status": status,
                                "content_hash": digest, "fact_as_of": observed_at})
        web_rows = [paper_web.fetch(account_id, trade_date, url, stock_code)
                    for url in (web_urls or [])[:5]]
        if web_query:
            search = paper_web.search(account_id, trade_date, web_query, stock_code)
            web_rows.extend(search.get("results") or [])
            trace.append({"tool": "paper_web.search", "status": search.get("status"),
                          "args": {"query": web_query}, "result": search,
                          "content_hash": content_hash(search)})
        facts["web_evidence"] = web_rows
        for row in web_rows:
            source_refs.append({"type": "web", "url": row.get("url"),
                                "content_hash": row.get("content_hash"),
                                "fact_as_of": row.get("fact_as_of"),
                                "status": row.get("status"), "trust": "external_evidence_only"})
        facts["fact_as_of"] = _now().isoformat()
    else:
        errors = snapshot_time_errors({"facts": facts, "source_refs": source_refs}, cutoff)
        if errors:
            raise ValueError("历史事实时间校验失败: " + "; ".join(errors[:10]))
    digest = content_hash(facts)
    context_id = repo.create_paper_context(account_id, trade_date, mode, stock_code,
                                           "research", facts, trace, source_refs)
    return {"id": context_id, "account_id": account_id, "trade_date": trade_date,
            "stock_code": stock_code, "mode": mode, "facts": deepcopy(facts),
            "tool_trace": deepcopy(trace), "source_refs": deepcopy(source_refs),
            "context_hash": digest, "created_at": _now().isoformat()}
