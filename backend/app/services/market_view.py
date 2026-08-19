"""市场概览只读视图：三大指数实时行情 + 今日热门板块【刚性代码逻辑】。

职责边界：
- 只做数据采集与客观排序聚合（板块按涨跌幅降序取前 5、领涨龙头解析），不做任何研判；
- 领涨龙头解析：板块行情表「领涨股票」名称 → 全市场快照名称匹配代码；
  匹配失败时降级拉该板块成分股，按涨跌幅取最大者（缓存复用，不重复请求）；
- 数据源失败返回空表 + error 标注，由前端显示「数据加载中/上次缓存值」。
"""
import concurrent.futures
import logging
import time

import pandas as pd

from app.datasource.akshare_source import get_datasource
from app.datasource.base import DataSourceError

logger = logging.getLogger(__name__)

# 顶部状态栏三大指数（代码 → 展示名）
INDEX_NAMES = {"sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指"}
INDEX_CODES = ["sh000001", "sz399001", "sz399006"]

HOT_SECTOR_COUNT = 5  # 首页「今日热门板块」看板数量

# 指数行情超时控制：akshare 冷启动约 36s，10s 硬超时走降级不阻塞首屏
_INDEX_FETCH_TIMEOUT = 10.0  # 秒
# 模块级线程池单例（禁 with 块：shutdown(wait=True) 会抵消超时效果；后台线程自然结束，结果可写入 60s 缓存供下次命中）
_INDEX_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="idx-fetch")


def index_quotes() -> dict:
    """三大指数实时行情 + 更新时间；失败返回空列表 + error 标注（前端降级展示）"""
    now_min = time.strftime("%Y-%m-%d %H:%M")
    try:
        ds = get_datasource()
        fut = _INDEX_POOL.submit(ds.fetch_index_spot)
        try:
            df = fut.result(timeout=_INDEX_FETCH_TIMEOUT)
        except concurrent.futures.TimeoutError:
            # 超时：后台线程继续跑完，结果可能写入 60s 缓存供下次命中；
            # 显式抛 DataSourceError 让上层降级 + 断路器正常计数（不裸抛 TimeoutError 避免 500）
            logger.warning("指数行情获取超时（>%.0fs），走降级", _INDEX_FETCH_TIMEOUT)
            raise DataSourceError(f"指数行情获取超时（>{_INDEX_FETCH_TIMEOUT:.0f}s）")
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
    """今日涨幅前 5 行业板块 + 领涨龙头（前端只读聚合）

    v2 改造：不再每次裸打 akshare，改为读 sector_snapshot DB（由 sector_refresh_job 每 5 分钟落库）；
    DB 空 + 交易时段触发一次 refresh 兜底；DB 空 + 非交易时段返回空。
    """
    from app.services.sector_snapshot import get_hot_sectors_with_fallback
    result = get_hot_sectors_with_fallback()
    # 字段对齐：原 API 响应 {sectors, updated_at, error}；stale 为 v2 新增字段（向后兼容）
    return {
        "sectors": result.get("sectors", []),
        "updated_at": result.get("updated_at", ""),
        "stale": result.get("stale", False),
        "error": result.get("error"),
    }


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
