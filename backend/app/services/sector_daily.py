"""板块轮动·全板块日快照服务层：收盘后 15:35 抓全板块 → 涨幅排序 → 删后插落库

【刚性代码逻辑】只做数据采集 + 全板块排序 + 落库，不做研判，不做推送。
数据源：akshare.fetch_industry_spot（kind=snapshot 走断路器 + 600s 缓存）
字段口径：_BOARD_COLS 标准化后的 df 直接映射；东财缺失字段如实 NULL（K227 不编造）。
"""
import logging
import time

from app.db import repo

logger = logging.getLogger(__name__)


def refresh_sector_daily_snapshot(trade_date: str | None = None) -> dict:
    """全板块日快照刷新（工作日 15:35，由 scheduler 触发；失败不抛）

    返回 {"success": bool, "rows": int, "error": str|None}
    全板块落库（不截取 top5），rank_no 按当日涨幅 1~N 排序。
    """
    from app.datasource.akshare_source import AkshareSource
    # 领涨股代码解析链（复用 sector_snapshot 既有逻辑，供批C 连板/资金/新闻证据取数）
    from app.services.market_view import _leading_from_cons, _spot_name_map
    today = trade_date or time.strftime("%Y-%m-%d")
    try:
        board_df = AkshareSource().fetch_industry_spot()
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "trade_date": today, "rows": 0, "error": f"板块行情获取失败: {exc}"}

    if board_df is None or board_df.empty or "board_name" not in board_df.columns:
        return {"success": False, "trade_date": today, "rows": 0, "error": "板块行情返回空表"}

    name_to_code = _spot_name_map()
    rows = []
    for _, r in board_df.iterrows():
        try:
            pct = float(r.get("change_pct"))
        except (TypeError, ValueError):
            continue
        name = str(r.get("board_name") or "").strip()
        if not name:
            continue
        leading_name = str(r.get("leading_stock") or "").strip()
        leading_code = name_to_code.get(leading_name) if leading_name else ""
        if not leading_code and leading_name:
            try:
                leading_code = _leading_from_cons(name)
            except Exception:  # noqa: BLE001 代码解析失败降级空串
                leading_code = ""
        rows.append({
            "trade_date": today,
            "sector_name": name,
            "change_pct": round(pct, 2),
            "rank_no": 0,  # 下方全板块排序后填充
            "up_count": _num(r, "up_count"),
            "down_count": _num(r, "down_count"),
            "volume_ratio": _num(r, "volume_ratio"),
            "turnover_rate": _num(r, "turnover_rate"),
            "leading_stock_name": leading_name,
            "leading_stock_code": leading_code,
            "leading_chg": _num(r, "leading_chg"),
            "source": "em",
        })

    if not rows:
        return {"success": False, "trade_date": today, "rows": 0, "error": "无有效板块数据"}

    rows.sort(key=lambda x: x["change_pct"], reverse=True)
    for i, row in enumerate(rows):
        row["rank_no"] = i + 1

    inserted = repo.upsert_sector_daily_snapshot(rows)
    return {"success": True, "trade_date": today, "rows": inserted, "error": None}


def _num(row, key):
    """安全转 float：None/NaN/非法 → None（缺数据如实 NULL，不编造）"""
    v = row.get(key)
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None
