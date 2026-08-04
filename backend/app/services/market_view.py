"""市场概览只读视图：三大指数实时行情 + 今日热门板块【刚性代码逻辑】。

职责边界：
- 只做数据采集与客观排序聚合（板块按涨跌幅降序取前 5、领涨龙头解析），不做任何研判；
- 领涨龙头解析：板块行情表「领涨股票」名称 → 全市场快照名称匹配代码；
  匹配失败时降级拉该板块成分股，按涨跌幅取最大者（缓存复用，不重复请求）；
- 数据源失败返回空表 + error 标注，由前端显示「数据加载中/上次缓存值」。
"""
import logging
import time

import pandas as pd

from app.datasource.akshare_source import get_datasource

logger = logging.getLogger(__name__)

# 顶部状态栏三大指数（代码 → 展示名）
INDEX_NAMES = {"sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指"}
INDEX_CODES = ["sh000001", "sz399001", "sz399006"]

HOT_SECTOR_COUNT = 5  # 首页「今日热门板块」看板数量


def index_quotes() -> dict:
    """三大指数实时行情 + 更新时间；失败返回空列表 + error 标注（前端降级展示）"""
    now_min = time.strftime("%Y-%m-%d %H:%M")
    try:
        df = get_datasource().fetch_index_spot()
    except Exception as exc:  # noqa: BLE001 行情失败不阻塞页面，返回空表由前端标注
        logger.warning("指数行情获取失败: %s", exc)
        return {"indices": [], "updated_at": now_min, "error": f"指数行情获取失败（{type(exc).__name__}）"}

    if df is None or df.empty or "code" not in df.columns:
        return {"indices": [], "updated_at": now_min, "error": None}

    indices = []
    for code in INDEX_CODES:
        row = df[df["code"].astype(str) == code]
        if row.empty:
            continue
        r = row.iloc[0]
        try:
            price = float(r.get("price"))
            change_pct = float(r.get("change_pct"))
        except (TypeError, ValueError):
            continue
        indices.append({"code": code, "name": INDEX_NAMES.get(code, r.get("name") or code),
                        "price": round(price, 2), "change_pct": round(change_pct, 2)})
    return {"indices": indices, "updated_at": now_min, "error": None}


def hot_sectors() -> dict:
    """今日涨幅前 5 行业板块（客观排序，非主观筛选）+ 领涨龙头（代码+名称）+ 更新时间"""
    now_min = time.strftime("%Y-%m-%d %H:%M")
    try:
        board_df = get_datasource().fetch_industry_spot()
    except Exception as exc:  # noqa: BLE001
        logger.warning("行业板块行情获取失败: %s", exc)
        return {"sectors": [], "updated_at": now_min, "error": f"行业板块行情获取失败（{type(exc).__name__}）"}

    if board_df is None or board_df.empty or "board_name" not in board_df.columns:
        return {"sectors": [], "updated_at": now_min, "error": None}

    boards = []
    for _, r in board_df.iterrows():
        try:
            change_pct = float(r.get("change_pct"))
        except (TypeError, ValueError):
            continue
        boards.append({"board_name": str(r["board_name"]).strip(),
                       "change_pct": round(change_pct, 2),
                       "leading_stock": str(r.get("leading_stock") or "").strip()})
    boards.sort(key=lambda b: b["change_pct"], reverse=True)

    name_to_code = _spot_name_map()
    sectors = []
    for b in boards[:HOT_SECTOR_COUNT]:
        leading_code = name_to_code.get(b["leading_stock"])
        if not leading_code and b["leading_stock"]:
            leading_code = _leading_from_cons(b["board_name"])
        sectors.append({**b, "leading_code": leading_code or ""})
    return {"sectors": sectors, "updated_at": now_min, "error": None}


def _spot_name_map() -> dict[str, str]:
    """全市场快照 名称 → 代码 映射（匹配领涨股票名称用；失败返回空表）"""
    try:
        df = get_datasource().fetch_spot_universe()
    except Exception as exc:  # noqa: BLE001
        logger.warning("全市场快照获取失败（领涨龙头代码匹配降级）: %s", exc)
        return {}
    result: dict[str, str] = {}
    for _, r in df.iterrows():
        name = str(r.get("name") or "").strip()
        code = str(r.get("code") or "").strip()
        if name and code:
            result.setdefault(name, code)
    return result


def _leading_from_cons(board_name: str) -> str:
    """降级方案：板块成分股按涨跌幅取最大者（代码）；失败返回空串"""
    try:
        df = get_datasource().fetch_industry_cons(board_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("板块成分股获取失败（%s）: %s", board_name, exc)
        return ""
    if df is None or df.empty or "code" not in df.columns:
        return ""
    best = None
    for _, r in df.iterrows():
        try:
            pct = float(r.get("change_pct"))
        except (TypeError, ValueError):
            continue
        if best is None or pct > best[1]:
            best = (str(r["code"]).strip(), pct)
    return best[0] if best else ""
