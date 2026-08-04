"""
APScheduler 定时任务（Asia/Shanghai）
- 工作日 16:10：每日挖掘（discover → 候选打分）
- 交易日 9:30-11:30 / 13:00-15:00 每 3 分钟：持仓批量监控（实时行情 60s 内缓存）
- 交易日 15:00-15:30：收盘数据校验（当天一次）
- 任务锁防重叠（prod=Redis / dev=内存锁）
【刚性代码逻辑】只做调度，不包含任何市场判断。
"""
import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.cache import cache
from app.core.config import settings
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
    """盘中窗口 9:30-11:30 / 13:00-15:00（调度外层按 monitor_interval_minutes 分钟触发）"""
    hm = now.hour * 100 + now.minute
    return (930 <= hm <= 1130) or (1300 <= hm <= 1500)


def _in_close_check_window(now: datetime) -> bool:
    """收盘校验窗口 15:00-15:30：非交易时段低频兜底，当天仅执行一次收盘数据校验"""
    hm = now.hour * 100 + now.minute
    return 1500 <= hm <= 1530


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
    """批量持仓监控：交易时段高频（每 N 分钟）全量监控；收盘校验窗口低频兜底"""
    now = datetime.now()
    if not _in_trading_window(now) and not _in_close_check_window(now):
        return
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        return
    if _in_close_check_window(now) and not _in_trading_window(now):
        # 收盘校验：非交易时段每 30 分钟检测一次 → 当天仅执行一次（收盘价定格后无新数据）
        if cache.get(f"job:close_checked:{today}"):
            logger.info("今日收盘校验已完成，跳过")
            return
    if not cache.acquire_lock("monitor", ttl_seconds=300):
        logger.info("monitor 锁被占用，跳过本次")
        return
    try:
        results = graph_router.run_monitor_all(today)
        cache.set("job:last_monitor", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        if _in_close_check_window(now) and not _in_trading_window(now):
            cache.set(f"job:close_checked:{today}", "1", 86400)
            logger.info("收盘校验完成: %s 持仓", len(results))
        else:
            logger.info("监控轮询完成: %s 持仓", len(results))
    except Exception as exc:  # noqa: BLE001
        logger.error("监控轮询失败: %s", exc)
    finally:
        cache.release_lock("monitor")


def maintenance_job() -> None:
    """每周空间维护（低频）：超期新闻清理 + SQLite 真空收缩 + 向量库超期索引清理。
    仅清理非核心数据（新闻原文），候选/评分/持仓/复盘等关键分析数据不清理。"""
    if not settings.db_maintenance_enabled:
        return
    if not cache.acquire_lock("db_maintenance", ttl_seconds=3600):
        logger.info("db_maintenance 锁被占用，跳过本次")
        return
    try:
        from app.db import repo
        from app.services.vector_store import get_vector_store

        stats = repo.maintenance_db()
        cutoff = time.time() - settings.news_retention_days * 86400
        removed = get_vector_store().cleanup_old_news(cutoff)
        logger.info("空间维护完成: 新闻清理 %s 条，向量索引清理 %s，库体积 %s → %s MB",
                    stats["news_deleted"], removed,
                    stats["size_before_mb"], stats["size_after_mb"])
        cache.set("job:last_maintenance", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
    except Exception as exc:  # noqa: BLE001 维护失败不阻塞其他任务
        logger.error("空间维护失败: %s", exc)
    finally:
        cache.release_lock("db_maintenance")


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
    # 交易日 9:00-16:00 每 N 分钟触发（函数内过滤：盘中高频 + 15:00-15:30 收盘校验低频）
    monitor_minutes = max(1, int(settings.monitor_interval_minutes))
    scheduler.add_job(monitor_job, "cron",
                      day_of_week="mon-fri", hour="9-16", minute=f"*/{monitor_minutes}",
                      id="monitor", name="盘中持仓监控",
                      replace_existing=True, misfire_grace_time=300)
    # 每周一次空间维护（默认周日 05:30，低频）
    scheduler.add_job(maintenance_job, "cron",
                      day_of_week=settings.db_maintenance_day_of_week,
                      hour=settings.db_maintenance_hour, minute=settings.db_maintenance_minute,
                      id="db_maintenance", name="存储空间维护",
                      replace_existing=True, misfire_grace_time=3600)
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
