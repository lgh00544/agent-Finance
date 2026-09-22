"""T3 8a 链路验证驱动：用 30001 持仓自带的冻结事实做 historical_replay，
走 holdings -> Monitor -> Sell -> execution -> Review（不触真实交易/持仓）。"""
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, r"D:\self\backend")
os.environ.setdefault("APP_ENV", "dev")

from app.db import repo
from app.services import paper_monitor

ACCOUNT = 30001


def replay_one(pos: dict) -> dict:
    code = str(pos.get("stock_code") or "")
    facts = deepcopy((pos.get("metadata") or {}).get("facts") or {})
    quote = deepcopy(facts.get("quote") or {})
    trade_date = str(facts.get("trade_date") or "")[:10]
    quote_time = str(quote.get("time") or quote.get("quote_time") or "")
    if not (code and trade_date and quote_time):
        return {"stock_code": code, "error": "缺少冻结事实/报价时间"}
    frozen = dict(facts)
    frozen["mode"] = "historical_replay"
    frozen["fact_as_of"] = quote_time
    frozen["trade_date"] = trade_date
    q = dict(quote)
    q.update({"status": "ok", "fact_as_of": quote_time, "quote_time": quote_time})
    frozen_pos = {**pos, "entry_date": pos.get("opened_trade_date"),
                  "entry_price": pos.get("avg_price")}
    frozen_pos.pop("updated_at", None)  # 回放不得带入晚于冻结日的观测时间
    hf = {"positions": [frozen_pos], "quotes": {code: q},
          "contexts": {code: {"facts": frozen, "source_refs": [], "tool_trace": []}}}
    try:
        res = paper_monitor.run(ACCOUNT, trade_date, mode="historical_replay",
                                historical_facts=hf)
    except Exception as exc:  # noqa: BLE001 单只失败不影响其余
        return {"stock_code": code, "trade_date": trade_date,
                "error": f"{type(exc).__name__}: {exc}"}
    items = []
    for item in res.get("results") or []:
        monitor = item.get("monitor") or {}
        signal = monitor.get("signal") or {}
        sell = item.get("sell") or {}
        decision = sell.get("decision") or {}
        execution = item.get("execution") or {}
        items.append({
            "stock_code": item.get("stock_code"), "status": item.get("status"),
            "reason": item.get("reason"),
            "monitor_status": monitor.get("status"),
            "action": signal.get("action"), "severity": signal.get("severity"),
            "alert_type": signal.get("alert_type"),
            "sell_status": sell.get("status"), "sell_action": decision.get("action"),
            "reduce_ratio": decision.get("reduce_ratio"),
            "execution_ids": [e.get("id") for e in (execution.get("executions") or [])],
            "execution_shares": [e.get("shares") for e in (execution.get("executions") or [])],
            "alert_id": item.get("alert_id"), "context_id": item.get("context_id"),
        })
    return {"stock_code": code, "trade_date": trade_date, "results": items}


def main() -> None:
    positions = repo.list_paper_positions(ACCOUNT, status="holding")
    out = [replay_one(p) for p in positions]
    alerts = repo.list_paper_alerts(ACCOUNT, limit=500)
    executions = repo.list_paper_executions(ACCOUNT, limit=500)
    reviews = repo.list_paper_reviews(ACCOUNT, limit=500)
    summary = {
        "replay": out,
        "after": {
            "alerts": len(alerts),
            "executions": len(executions),
            "reviews": len(reviews),
            "review_codes": sorted({r.get("stock_code") for r in reviews}),
            "sold_shares": [e.get("shares") for e in executions
                            if str(e.get("side") or "") == "sell"][-6:],
        },
    }
    print(json.dumps(summary, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
