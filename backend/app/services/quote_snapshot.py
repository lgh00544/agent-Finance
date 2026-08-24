"""持仓实时价快照服务层：每 5 分钟腾讯批量拉持仓价 → 落 quote_snapshot（DB 兜底）

【刚性代码逻辑】只做取数 + 落库，不做研判、不预测、不改任何交易规则。
数据源优先：腾讯 qt.gtimg.cn 批量（N 只 = 1 次 HTTP）→ 失败再试东财全市场快照过滤。
作用：持仓监控页 read 路径先读 DB（<50ms），akshare hang 不影响前端（15s 超时不再触发）。
"""
import logging
import time

from app.datasource.akshare_source import get_datasource
from app.db import repo

logger = logging.getLogger(__name__)

SNAPSHOT_FRESH_MINUTES = 10  # DB 快照新鲜窗口（与 repo.get_quote_snapshot 默认一致）


def _spot_to_prices(spot_df, codes: list[str], code_set: set[str]) -> dict[str, float]:
    """全市场快照 → {code: price}（仅持仓代码；无价/非正价不收录）"""
    out: dict[str, float] = {}
    if spot_df is None or spot_df.empty:
        return out
    for _, row in spot_df.iterrows():
        code = str(row.get("code") or "").strip()
        if code not in code_set:
            continue
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if price > 0:
            out[code] = price
    return out


def refresh_quote_snapshot() -> dict:
    """刷新持仓价快照（腾讯批量 → 失败再试全市场快照 → 落库；失败不抛）

    返回 {"success": bool, "rows": int, "error": str|None, "source": str, "updated_at": str}
    source 取值 'tencent' / 'universe' / 'none'（无持仓时不落库）。
    """
    holdings = repo.list_holdings(status="holding") or []
    if not holdings:
        return {"success": True, "rows": 0, "error": None, "source": "none",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    codes = [h["stock_code"] for h in holdings]
    code_set = set(codes)
    name_by_code = {h["stock_code"]: h.get("stock_name") or "" for h in holdings}

    ds = get_datasource()
    source = ""
    prices: dict[str, float] = {}
    change_pct_map: dict[str, float | None] = {}
    error: str | None = None

    # ① 腾讯批量（首选，N 只 = 1 次 HTTP）
    try:
        prices = ds.fetch_tencent_batch(codes)
        source = "tencent"
    except Exception as exc:  # noqa: BLE001 降级不阻塞
        error = f"腾讯批量行情失败: {exc}"
        logger.warning("持仓快照·腾讯批量失败，改走全市场快照: %s", exc)

    # ② 腾讯拿不到 → 东财全市场快照过滤（原链路；akshare 挂则返回空不阻塞）
    if not prices:
        try:
            spot = ds.fetch_spot_universe()
            prices = _spot_to_prices(spot, codes, code_set)
            source = "universe"
            if prices:
                spot_map = {str(r.get("code")).strip(): r for _, r in spot.iterrows()}
                for c, r in spot_map.items():
                    if c in code_set:
                        try:
                            change_pct_map[c] = float(r.get("change_pct")) \
                                if r.get("change_pct") not in (None, "") else None
                        except (TypeError, ValueError):
                            change_pct_map[c] = None
        except Exception as exc:  # noqa: BLE001 全市场失败也降级
            error = f"全市场快照失败: {exc}"
            logger.warning("持仓快照·东财全市场兜底失败: %s", exc)

    if not prices:
        return {"success": False, "rows": 0, "error": error or "持仓行情为空",
                "source": source, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    rows = [{
        "stock_code": c,
        "name": name_by_code.get(c, ""),
        "price": p,
        "change_pct": change_pct_map.get(c),
        "source": source,
        "updated_at": now_str,
    } for c, p in prices.items()]
    inserted = repo.upsert_quote_snapshot(rows)
    return {"success": True, "rows": inserted, "error": None,
            "source": source, "updated_at": now_str}