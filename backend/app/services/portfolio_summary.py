"""每日组合总结（daily-summary）：从组合归因派生 + 持仓最新浮盈亏聚合。纯计算零 LLM。"""
import time

from app.services.holding_view import build_holding_view
from app.services.track_verify import build_portfolio_attribution


def build_daily_summary(days: int = 30) -> dict:
    attr = build_portfolio_attribution(days)
    rows = (build_holding_view().get("rows") or [])
    curve = attr.get("portfolio_curve") or []
    contributors = attr.get("contributors") or []
    total_cost = float(attr.get("total_cost") or 0)
    pnl_amount = sum(float(r.get("pnl_amount") or 0) for r in rows)
    market_value = round(total_cost + pnl_amount, 2)
    latest = curve[-1] if curve else None
    current = {"date": time.strftime("%Y-%m-%d"),
               "pnl_pct": latest.get("total_pnl_pct") if latest else None,
               "pnl_amount": round(pnl_amount, 2), "market_value": market_value}
    series = [{"date": p["date"], "pnl_pct": p["total_pnl_pct"]} for p in curve]
    valid = [c for c in contributors if c.get("contribution_pct") is not None]
    gainers = sorted(valid, key=lambda c: c["contribution_pct"], reverse=True)[:3]
    losers = sorted(valid, key=lambda c: c["contribution_pct"])[:3]

    def _top(items):
        return [{"code": c["stock_code"], "name": c.get("stock_name") or c["stock_code"],
                 "pnl_pct": c["contribution_pct"]} for c in items]

    if latest and total_cost:
        latest_pct = latest.get("total_pnl_pct") or 0
        head_pct = series[0]["pnl_pct"] if series else 0
        summary_text = (f"今日组合 {latest_pct:+.2f}%，近 {days} 日 {head_pct:+.2f}%，"
                        f"总市值 {market_value:,.0f} 元，当前持仓 {len(valid)} 只。")
    else:
        summary_text = "暂无持仓数据（录入建仓并刷新行情后生成组合总结）。"
    return {"days": days, "current": current, "series": series,
            "top_gainers": _top(gainers), "top_losers": _top(losers),
            "summary_text": summary_text}
