"""行情时段闸门（非交易时段自动降频）

【刚性代码逻辑】只做时间判断，不做任何市场判断。
  - 实时行情（tick）：仅交易时段放行（9:30-11:30 / 13:00-15:00，与 jobs.py 调度窗口一致）；
    午间休盘/盘前盘后不请求实时接口，上层直接用收盘快照兜底
  - 全市场快照（snapshot）：仅交易日放行；周末/节假日完全暂停实时请求
  - 交易日历：复用已有缓存 key "ak:trade_calendar"（akshare_source.fetch_trade_calendar
    写入，24h TTL）；日历缺失/失败时降级为工作日启发（周一至周五）
"""
from datetime import datetime, timedelta, timezone

from app.cache import cache

CN_TZ = timezone(timedelta(hours=8))


def _now() -> datetime:
    """北京时间当前时刻（模块级函数，测试 monkeypatch 目标）"""
    return datetime.now(CN_TZ)


def _load_calendar() -> set[str]:
    raw = cache.get("ak:trade_calendar")
    if not raw:
        return set()
    return {d.strip() for d in raw.split(",") if d.strip()}


def is_trading_day() -> bool:
    """是否交易日：日历缓存命中优先；缺失/失败降级为工作日启发"""
    now = _now()
    cal = _load_calendar()
    if cal:
        return now.strftime("%Y-%m-%d") in cal
    return now.weekday() < 5


def realtime_open() -> bool:
    """实时行情闸门：交易日且处于盘中窗口（9:30-11:30 / 13:00-15:00）"""
    if not is_trading_day():
        return False
    now = _now()
    minutes = now.hour * 60 + now.minute
    return (9 * 60 + 30 <= minutes < 11 * 60 + 30) or (13 * 60 <= minutes < 15 * 60)


def snapshot_allowed() -> bool:
    """全市场快照闸门：仅交易日放行（休市日返回收盘缓存/空，不请求实时接口）"""
    return is_trading_day()
