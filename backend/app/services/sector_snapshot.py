"""板块快照服务层：每 5 分钟从 akshare 抓板块行情 → 解析领涨龙头 → 落 sector_snapshot 表

【刚性代码逻辑】只做数据采集 + 排序 + 落库，不做研判，不做推送。
数据源：akshare.fetch_industry_spot + fetch_industry_cons（kind=snapshot 走断路器）
"""
import logging
import time
from datetime import datetime

from app.db import repo

logger = logging.getLogger(__name__)

STALE_THRESHOLD_SECONDS = 30 * 60  # 30 分钟判为 stale


def refresh_sector_snapshot() -> dict:
    """刷新板块快照（每 5 分钟，由 scheduler 触发；失败不抛）

    返回 {"success": bool, "rows": int, "error": str|None, "updated_at": str}

    注：`_spot_name_map/_leading_from_cons` 通过函数内 lazy import 从 market_view 取，
    规避 sector_snapshot ↔ market_view 互 import 循环（模块顶不互 import）。
    """
    from app.datasource.akshare_source import AkshareSource
    # lazy import 规避循环：market_view.hot_sectors() → sector_snapshot.get_hot_sectors_with_fallback()
    #                          ← sector_snapshot.refresh_sector_snapshot() → market_view._spot_name_map
    from app.services.market_view import _spot_name_map, _leading_from_cons
    today = time.strftime("%Y-%m-%d")
    try:
        ds = AkshareSource()
        board_df = ds.fetch_industry_spot()
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "rows": 0, "error": f"板块行情获取失败: {exc}",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    if board_df is None or board_df.empty or "board_name" not in board_df.columns:
        return {"success": False, "rows": 0, "error": "板块行情返回空表",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # 复用 market_view 既有逻辑（已有完整排序 + 领涨龙头解析降级链）
    boards = []
    for _, r in board_df.iterrows():
        try:
            pct = float(r.get("change_pct"))
        except (TypeError, ValueError):
            continue
        boards.append({"board_name": str(r["board_name"]).strip(),
                       "change_pct": round(pct, 2),
                       "leading_stock": str(r.get("leading_stock") or "").strip()})
    boards.sort(key=lambda b: b["change_pct"], reverse=True)

    name_to_code = _spot_name_map()
    rows = []
    for idx, b in enumerate(boards[:5]):
        leading_code = name_to_code.get(b["leading_stock"])
        if not leading_code and b["leading_stock"]:
            leading_code = _leading_from_cons(b["board_name"])
        rows.append({
            "trade_date": today,
            "sector_name": b["board_name"],
            "change_pct": b["change_pct"],
            "leading_stock_name": b["leading_stock"],
            "leading_stock_code": leading_code or "",
            "source": "em",  # 主源标识；akshare 降级到新浪后 _BOARD_COLS 标准化统一
            "rank_no": idx + 1,
        })

    if not rows:
        return {"success": False, "rows": 0, "error": "无有效板块数据",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    inserted = repo.upsert_sector_snapshot(rows)
    return {"success": True, "rows": inserted, "error": None,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def get_hot_sectors_with_fallback() -> dict:
    """首页热路径：读 DB；带 staleness 标注

    返回 {"sectors": list, "updated_at": str, "stale": bool, "error": str|None}
    分支：
      1. DB 有数据 + 新鲜 < 30min → 直接返回
      2. DB 有数据 + stale ≥ 30min → 返回旧值 + stale=true
      3. DB 无数据 + 交易时段 → 同步触发一次 refresh 兜底后返回
      4. DB 无数据 + 非交易时段 → 返回空 + error
    """
    from app.datasource.market_hours import snapshot_allowed
    today = time.strftime("%Y-%m-%d")
    sectors = repo.list_sector_snapshot_by_date(today, limit=5)
    updated_at = repo.get_sector_snapshot_updated_at(today) or ""

    if sectors:
        # 计算新鲜度
        stale = False
        if updated_at:
            try:
                last_ts = datetime.strptime(updated_at[:19], "%Y-%m-%d %H:%M:%S")
                stale = (datetime.now() - last_ts).total_seconds() > STALE_THRESHOLD_SECONDS
            except (ValueError, TypeError):
                stale = True  # 解析失败也判 stale，让前端标注
        return {"sectors": sectors, "updated_at": updated_at,
                "stale": stale, "error": None}

    # DB 无数据：交易时段触发一次 refresh 兜底；非交易时段直接返回空
    if snapshot_allowed():
        refresh_result = refresh_sector_snapshot()
        if refresh_result.get("success"):
            sectors = repo.list_sector_snapshot_by_date(today, limit=5)
            return {"sectors": sectors,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "stale": False, "error": None}
        return {"sectors": [], "updated_at": "", "stale": False,
                "error": refresh_result.get("error", "板块行情暂不可用")}
    return {"sectors": [], "updated_at": "", "stale": False,
            "error": "非交易时段，板块行情暂不可用"}
