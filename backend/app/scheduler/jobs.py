"""
APScheduler 定时任务（Asia/Shanghai）
- 工作日 16:10：每日挖掘（discover → 候选打分）
- 交易日 9:35-11:30 / 13:05-14:55 每 5 分钟：持仓批量监控
- 任务锁防重叠（prod=Redis / dev=内存锁）
【刚性代码逻辑】只做调度，不包含任何市场判断。
"""
import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.cache import cache
from app.core.logging import get_logger
from app.datasource.akshare_source import AkshareSource
from app.graph import router as graph_router

logger = get_logger("scheduler")

scheduler: BackgroundScheduler | None = None


def _is_trading_day(today: str) -> bool:
    """最近交易日是否就是今天（用 akshare 交易日历）"""
    try:
        calendar = AkshareSource().fetch_trade_calendar()
        return bool(calendar) and calendar[-1] == today
    except Exception as exc:  # noqa: BLE001 日历失败时按工作日放行
        logger.warning("交易日历获取失败，按工作日放行: %s", exc)
        return True


def _in_trading_window(now: datetime) -> bool:
    """盘中窗口 9:35-11:30 / 13:05-14:55（调度外层再按每5分钟触发）"""
    hm = now.hour * 100 + now.minute
    return (935 <= hm <= 1130) or (1305 <= hm <= 1455)


def daily_discover_job() -> None:
    """每日挖掘：防重锁 + 交易日校验 + 全链路"""
    today = time.strftime("%Y-%m-%d")
    if not cache.acquire_lock("daily_discover", ttl_seconds=7200):
        logger.info("daily_discover 锁被占用，跳过本次")
        return
    try:
        if not _is_trading_day(today):
            logger.info("今天 %s 非交易日，跳过挖掘", today)
            return
        result = graph_router.run_daily_pipeline(today)
        logger.info("每日挖掘完成: %s", result)
        cache.set("job:last_discover", today, 86400)
    except Exception as exc:  # noqa: BLE001 调度任务整体容错
        logger.error("每日挖掘失败: %s", exc)
    finally:
        cache.release_lock("daily_discover")


def monitor_job() -> None:
    """盘中批量监控：交易时段过滤 + 防重锁"""
    now = datetime.now()
    if not _in_trading_window(now):
        return
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        return
    if not cache.acquire_lock("monitor", ttl_seconds=300):
        logger.info("monitor 锁被占用，跳过本次")
        return
    try:
        results = graph_router.run_monitor_all(today)
        cache.set("job:last_monitor", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        logger.info("监控轮询完成: %s 持仓", len(results))
    except Exception as exc:  # noqa: BLE001
        logger.error("监控轮询失败: %s", exc)
    finally:
        cache.release_lock("monitor")


def start_scheduler() -> None:
    global scheduler
    if scheduler is not None:
        return
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 工作日 16:10 每日挖掘
    scheduler.add_job(daily_discover_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=10,
                      id="daily_discover", name="每日潜力股挖掘",
                      replace_existing=True, misfire_grace_time=3600)
    # 交易日 9:30-15:00 每 5 分钟触发，函数内过滤交易时段
    scheduler.add_job(monitor_job, "cron",
                      day_of_week="mon-fri", hour="9-15", minute="*/5",
                      id="monitor", name="盘中持仓监控",
                      replace_existing=True, misfire_grace_time=300)
    scheduler.start()
    logger.info("APScheduler 已启动（Asia/Shanghai）")


def stop_scheduler() -> None:
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None


def job_status() -> list[dict]:
    if scheduler is None:
        return []
    out = []
    for job in scheduler.get_jobs():
        out.append({"id": job.id, "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None})
    out.append({"id": "last_discover", "name": "最近挖掘", "next_run": cache.get("job:last_discover")})
    out.append({"id": "last_monitor", "name": "最近监控", "next_run": cache.get("job:last_monitor")})
    return out
