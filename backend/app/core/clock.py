"""统一时钟（P-12 时间口径统一）。

全链"当前时间"一律走本模块，禁止裸 datetime.now()/time.strftime()/date.today()
（宿主本地时区，TZ 非 UTC+8 时落库/展示整体偏 8 小时，与调度、行情、前端对不上）。

口径约定：
- now()           -> naive datetime（UTC+8，去掉 tzinfo），与 models._now 一致，供写库/比较
- now_aware()     -> aware datetime（UTC+8），供需要 tz 的展示/计算
- today()         -> "YYYY-MM-DD"（北京时间当日）
- now_str()       -> "YYYY-MM-DD HH:MM:SS"（北京时间）
- today_date()    -> datetime.date（北京时间当日）
"""
from datetime import date, datetime, timedelta, timezone

_CN_TZ = timezone(timedelta(hours=8))


def now() -> datetime:
    """当前北京时间（naive，UTC+8）：与调度/行情/展示口径一致。"""
    return datetime.now(_CN_TZ).replace(tzinfo=None)


def now_aware() -> datetime:
    """当前北京时间（aware，UTC+8）。"""
    return datetime.now(_CN_TZ)


def today() -> str:
    """北京时间当日 YYYY-MM-DD。"""
    return now().strftime("%Y-%m-%d")


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """北京时间当前字符串，默认 YYYY-MM-DD HH:MM:SS。"""
    return now().strftime(fmt)


def today_date() -> date:
    """北京时间当日 date 对象。"""
    return now().date()
