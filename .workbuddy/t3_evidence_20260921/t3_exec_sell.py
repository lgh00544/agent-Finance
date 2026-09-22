"""T3 8a 链路验证（执行/复盘段）：用回放事实 + requested_sides 走 Sell -> execution -> Review，
验证成交股数 100 整数倍与复盘落库；不触真实持仓/交易。"""
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, r"D:\self\backend")
os.environ.setdefault("APP_ENV", "dev")

from app.db import repo
from app.services import paper_execution

ACCOUNT = 30001
CODE = "600026"
TD = "2026-09-16"

pos = [p for p in repo.list_paper_positions(ACCOUNT, status="holding") if p["stock_code"] == CODE][0]
facts = deepcopy((pos.get("metadata") or {}).get("facts") or {})
quote = deepcopy(facts.get("quote") or {})
qt = str(quote.get("time"))
frozen = dict(facts); frozen.update({"mode": "historical_replay", "fact_as_of": qt, "trade_date": TD})
q = dict(quote); q.update({"status": "ok", "fact_as_of": qt, "quote_time": qt})
fpos = {**pos, "entry_date": pos.get("opened_trade_date"), "entry_price": pos.get("avg_price")}
fpos.pop("updated_at", None)
context = {"facts": {**frozen, "position": fpos, "quote": q}, "source_refs": [], "tool_trace": []}

before_reviews = {r.get("id") for r in repo.list_paper_reviews(ACCOUNT, limit=500)}
res = paper_execution.run(
    ACCOUNT, TD,
    facts={"mode": "historical_replay", "contexts": {CODE: context},
           "tradeable": [{"stock_code": CODE, "stock_name": pos.get("stock_name")}],
           "sell_decisions": {CODE: {"action": "sell"}}},
    requested_sides={CODE: "sell"}, requested_shares={CODE: 100},
    position_facts=[fpos], quote_facts={CODE: q})
execs = [{"id": e.get("id"), "side": e.get("side"), "shares": e.get("shares"),
          "status": e.get("status"), "reject_reason": e.get("reject_reason"),
          "price": e.get("price")} for e in res.get("executions") or []]
reviews = repo.list_paper_reviews(ACCOUNT, limit=500)
new_reviews = [{"id": r.get("id"), "stock_code": r.get("stock_code"), "execution_id": r.get("execution_id")}
               for r in reviews if r.get("id") not in before_reviews]
print(json.dumps({"filled": res.get("filled"), "rejected": res.get("rejected"),
                  "executions": execs, "new_reviews": new_reviews,
                  "all_shares_multiple_100": all((e["shares"] or 0) % 100 == 0 for e in execs if e["status"] == "filled")},
                 ensure_ascii=False, default=str))
