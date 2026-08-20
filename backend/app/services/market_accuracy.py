"""市况方向命中率数据沉淀（批次5·#4）：market_condition 回填"次日沪深300涨跌幅"

职责边界：【刚性代码逻辑】只做数据回填，不做任何命中率计算/市场判断。
- fill_market_condition_next_day(): 对 next_day_index_pct IS NULL 且 trade_date < 今日 的历史市况行，
  拉沪深300日线，计算"选中日后下一交易日收盘涨跌幅"回填，形成"研判评分 → 次日实际"闭环。

基准固定沪深300（东财 stock_zh_index_daily_em 接口，secid 需带交易所前缀 sh000300）。
失败/缺数据逐行跳过，不报错不阻塞；幂等由 next_day_index_pct IS NULL 查询条件保证。
"""
import logging
import time
from datetime import datetime, timedelta

from app.datasource.fallback import get_datasource
from app.db import repo
from app.db.models import MarketCondition
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_INDEX_SYMBOL = "sh000300"   # 沪深300（东财指数接口需带交易所前缀；纯数字000300仅适用于个股日K接口）
_BENCH_NAME = "沪深300"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def collect_unfilled_market_conditions() -> list[dict]:
    """查待回填的市况行：next_day_index_pct IS NULL 且 trade_date < 今日（升序）。"""
    today = _today()
    with SessionLocal() as db:
        rows = db.execute(
            MarketCondition.__table__.select().where(
                MarketCondition.next_day_index_pct.is_(None),
                MarketCondition.trade_date < today
            ).order_by(MarketCondition.trade_date.asc())
        ).mappings().all()
        return [{"trade_date": r["trade_date"], "total_score": r["total_score"],
                 "cap": r["cap"], "summary": r["summary"]} for r in rows]


def fill_market_condition_next_day() -> dict:
    """回填市况次日指数涨跌（幂等；逐行 try/跳过，不报错不阻塞）。
    返回 {"filled": [trade_date], "skipped": [trade_date], "today": today}。"""
    today = _today()
    rows = collect_unfilled_market_conditions()
    source = get_datasource()
    filled: list[str] = []
    skipped: list[str] = []
    for r in rows:
        trade_date = r["trade_date"]
        try:
            df = source.fetch_index_daily(_INDEX_SYMBOL, trade_date, today)
            pct = _next_day_pct(df, trade_date)
            if pct is None:
                skipped.append(trade_date)   # 缺数据/找不到下一交易日，无法回填
                continue
            repo.update_market_condition_next_day(trade_date, pct)
            filled.append(trade_date)
        except Exception as exc:  # noqa: BLE001 单行失败跳过，不阻塞整体
            logger.warning("市况回填 %s 失败（跳过）: %s", trade_date, exc)
            skipped.append(trade_date)
    logger.info("市况次日指数回填完成: 填 %s 条（%s）跳过 %s 条（%s）",
                len(filled), filled, len(skipped), skipped)
    return {"filled": filled, "skipped": skipped, "today": today}


def _next_day_pct(df, trade_date: str) -> float | None:
    """从指数日线（按日期升序）取 trade_date 当日收盘为 base、其后第一条为 next，
    返回 pct=(next/base-1)*100（round 2）；找不到下一交易日或数据缺失返回 None。"""
    if df is None or df.empty or "close" not in df.columns or "date" not in df.columns:
        return None
    dates = df["date"].astype(str).tolist()
    closes = [_float(x) for x in df["close"].tolist()]
    if trade_date not in dates:
        return None
    idx = dates.index(trade_date)
    if idx + 1 >= len(dates):
        return None
    base, nxt = closes[idx], closes[idx + 1]
    if base is None or nxt is None or base <= 0:
        return None
    return round((nxt / base - 1) * 100, 2)


def _float(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else f  # NaN → None
    except (TypeError, ValueError):
        return None
