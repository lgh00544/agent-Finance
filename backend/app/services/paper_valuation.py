"""模拟账户行情与估值服务。

只读取 ``paper_position``，行情快照落 ``paper_quote_snapshot``，绝不复用真实持仓
行情表或修改真实资产。行情失败时保留明确状态，禁止用成本价伪造市值。
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime

from app.db import repo

logger = logging.getLogger(__name__)
FRESH_MINUTES = 10


def _safe_price(value):
    try:
        price = float(value)
        return price if math.isfinite(price) and price > 0 else None
    except (TypeError, ValueError):
        return None


def quote_state(item: dict, now: datetime | None = None) -> str:
    if _safe_price(item.get("price")) is None:
        return "unavailable"
    if item.get("quote_reference_only"):
        return "stale"
    raw = str(item.get("quote_time") or item.get("time") or "").strip()
    try:
        stamp = datetime.fromisoformat(raw)
        current = now or datetime.now(stamp.tzinfo)
        age = (current - stamp).total_seconds()
        return "ok" if 0 <= age <= FRESH_MINUTES * 60 else "stale"
    except (ValueError, TypeError):
        return "time_unknown"


def fetch_quotes(codes: list[str]) -> tuple[dict, list[str]]:
    """完整报价优先；缺少事实时间的降级结果只能作为参考。"""
    from app.datasource.fallback import get_datasource
    ds = get_datasource()
    quotes, errors = {}, []
    for method in ("fetch_tencent_quotes_batch", "fetch_spot_quotes_batch"):
        missing = [c for c in codes if quote_state(quotes.get(c, {})) != "ok"]
        if not missing:
            break
        try:
            raw = getattr(ds, method, lambda _: {})(missing)
            for code, item in (raw or {}).items():
                if code in codes and isinstance(item, dict) and _safe_price(item.get("price")) is not None:
                    if (code not in quotes or quote_state(item) == "ok" or
                            quote_state(quotes[code]) == "time_unknown" and quote_state(item) == "stale"):
                        quotes[code] = {**item, "source": item.get("source") or method}
            if not raw:
                errors.append(f"{method}: 行情源返回空数据")
        except Exception as exc:
            errors.append(f"{method}: {str(exc)[:120]}")
    for code in codes:
        if quote_state(quotes.get(code, {})) == "ok":
            continue
        try:
            item = getattr(ds, "fetch_spot_quote", lambda _code: {})(code)
            if (item and _safe_price(item.get("price")) is not None and
                    (quote_state(item) == "ok" or quote_state(quotes.get(code, {})) not in {"ok", "stale"})):
                quotes[code] = {**item, "source": item.get("source") or "spot_quote"}
        except Exception as exc:
            errors.append(f"{code}: {str(exc)[:100]}")
    return quotes, errors


def refresh_account(account_id: int) -> dict:
    """拉取模拟持仓行情并写入模拟快照；支持腾讯→东财/全市场→单股降级。"""
    positions = repo.list_paper_positions(account_id, status="holding")
    codes = [str(row.get("stock_code") or "") for row in positions if row.get("stock_code")]
    if not codes:
        return {"account_id": account_id, "source": "none", "rows": 0,
                "quote_time": time.strftime("%Y-%m-%d %H:%M:%S"), "errors": []}
    try:
        quotes, errors = fetch_quotes(codes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("模拟行情数据源初始化失败: %s", exc)
        quotes, errors = {}, [str(exc)[:200]]

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    sources = sorted({str(q.get("source") or "unknown") for q in quotes.values()})
    source = sources[0] if len(sources) == 1 else "mixed" if sources else "none"

    rows = []
    for pos in positions:
        code = pos["stock_code"]
        item = quotes.get(code)
        fact_time = str((item or {}).get("quote_time") or (item or {}).get("time") or "")
        rows.append({"stock_code": code, "stock_name": pos.get("stock_name") or code,
                     "price": _safe_price((item or {}).get("price")),
                     "change_pct": (item or {}).get("change_pct"),
                     "source": (item or {}).get("source") or source,
                     "quote_time": fact_time,
                     "fact_as_of": fact_time, "status": quote_state(item or {}), "snapshot": item or {},
                     "error": "" if quote_state(item or {}) == "ok" else "行情缺失、过期或未提供事实时间"})
    written = repo.upsert_paper_quotes(account_id, rows)
    return {"account_id": account_id, "source": source, "rows": written,
            "quote_time": now, "errors": errors}


def account_view(account_id: int, refresh: bool = True) -> dict:
    account = repo.get_paper_account(account_id)
    if account is None:
        raise ValueError("模拟账户不存在")
    refresh_result = refresh_account(account_id) if refresh and account.status != "archived" else None
    positions = repo.list_paper_positions(account_id, status="holding")
    quotes = {row["stock_code"]: row for row in repo.list_paper_quotes(account_id, None)}
    missing = [pos["stock_code"] for pos in positions if quote_state(quotes.get(pos["stock_code"], {})) != "ok"]
    references = repo.last_valid_paper_quotes(account_id, quotes, missing)
    output = []
    market_value = 0.0
    pnl_amount = 0.0
    known = True
    for pos in positions:
        quote = quotes.get(pos["stock_code"], {})
        status = quote_state(quote)
        reference_only = status != "ok" and pos["stock_code"] in references
        if reference_only:
            quote = {**quote, **references[pos["stock_code"]]}
            status = "stale"
        notice = "行情已过期，仅供参考" if reference_only else ""
        price = _safe_price(quote.get("price")) if status == "ok" or reference_only else None
        shares = int(pos.get("shares") or 0)
        avg = float(pos.get("avg_price") or 0)
        mv = pnl = pnl_pct = None
        if price is None:
            known = False
        else:
            mv = round(price * shares, 2)
            pnl = round((price - avg) * shares, 2)
            pnl_pct = round((price - avg) / avg * 100, 2) if avg > 0 else None
            market_value += mv
            pnl_amount += pnl
        output.append({**quote, **pos, "current_price": price, "market_value": mv,
                       "pnl_amount": pnl, "pnl_pct": pnl_pct,
                       "quote_source": quote.get("source"),
                       "quote_time": quote.get("quote_time"),
                       "quote_status": status, "quote_error": quote.get("error") or "",
                       "quote_reference_only": reference_only, "quote_notice": notice,
                       "fact_as_of": quote.get("quote_time")})
    market_value_out = round(market_value, 2) if known else None
    equity = round(float(account.cash) + market_value, 2) if known else None
    pnl_out = round(equity - float(account.initial_cash), 2) if equity is not None else None
    pnl_pct = round(pnl_out / float(account.initial_cash) * 100, 2) \
        if known and float(account.initial_cash) > 0 else None
    reference_only = any(row["quote_reference_only"] for row in output)
    fact_times = [row["fact_as_of"] for row in output if row["current_price"] is not None and row["fact_as_of"]]
    fact_as_of = min(fact_times, key=lambda stamp: datetime.fromisoformat(stamp).timestamp()) if fact_times else None
    sources = sorted({str(row["quote_source"] or "unknown") for row in output if row["current_price"] is not None})
    return {"account_id": account_id, "cash": account.cash,
            "initial_cash": account.initial_cash, "market_value": market_value_out,
            "equity": equity, "pnl_amount": pnl_out, "pnl_pct": pnl_pct,
            "unrealized_pnl": round(pnl_amount, 2) if known else None,
            "position_count": len(output), "positions": output,
            "valuation_as_of": fact_as_of, "fact_as_of": fact_as_of,
            "quote_source": sources[0] if len(sources) == 1 else "mixed" if sources else "none",
            "quote_status": ("stale" if reference_only else "ok") if known else "partial_or_unavailable",
            "quote_reference_only": reference_only,
            "quote_notice": "行情已过期，仅供参考" if reference_only else "",
            "quote_errors": (refresh_result or {}).get("errors") or [],
            "execution_mode": "paper", "source_label": "AI模拟",
            "real_assets_separate": True}
