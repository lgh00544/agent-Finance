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
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.cache import cache
from app.core.config import settings
from app.core.logging import get_logger
from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.graph import router as graph_router

logger = get_logger("scheduler")

scheduler: BackgroundScheduler | None = None


def _is_trading_day(today: str) -> bool:
    """今天是否交易日（akshare 交易日历为全量静态历 1990~年末，成员判定即可）"""
    try:
        calendar = AkshareSource().fetch_trade_calendar()
        return bool(calendar) and today in calendar
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


def track_verify_job() -> None:
    """候选池 T+N 验证（工作日 16:00 收盘后）：初始化新候选 → 计算 T+N →
    到期收尾 → 统计 → 建议生成（锁在链路内部 run_verify_chain，幂等）。
    16:00 验证的是前一日候选（当日收盘已定格）；16:10 每日挖掘入库当日候选，
    次日 16:00 自动初始化，时序自洽。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过候选验证", today)
        return
    from app.services import track_verify

    result = track_verify.run_verify_chain(backfill=False)
    safe = {k: v for k, v in result.items() if k not in ("stats",)}
    logger.info("候选T+N验证完成: %s", safe)
    cache.set("job:last_track_verify", today, 86400)

    # 评级重做-C：因子分回填（幂等，已有则跳过；不阻塞主任务）
    try:
        backfill_result = track_verify.backfill_factor_scores()
        if backfill_result["filled"] > 0:
            logger.info("因子分回填: %s", backfill_result)
    except Exception as exc:  # noqa: BLE001 回填失败不阻塞主任务
        logger.warning("因子分回填失败: %s", exc)


def market_intel_job() -> None:
    """每日收盘后市场研判（16:20，独立于每日挖掘；当天已生成则跳过，幂等）"""
    from app.graph.router import run_market_intel

    today = time.strftime("%Y-%m-%d")
    if repo.get_market_intel(today):
        logger.info("今日市场研判已生成，跳过定时触发")
        return
    try:
        result = run_market_intel(today)
        mi = result.get("market_intel")
        if mi:
            logger.info("市场研判完成: %s（%s，风险偏好 %s）", today, mi.get("phase"),
                        mi.get("risk_appetite"))
            try:
                from app.services import pre_market_screen
                changes = pre_market_screen.market_shift_detect()
                if changes:
                    logger.info("市况切换检测: %s 项变化（%s）", len(changes),
                                "、".join(c["dim"] for c in changes))
            except Exception as exc:  # noqa: BLE001 市况切换检测失败不阻塞 market_intel 主流程
                logger.error("市况切换检测失败: %s", exc)
        elif result.get("error"):
            logger.error("市场研判失败: %s", result["error"])
    except Exception as exc:  # noqa: BLE001 定时任务整体容错
        logger.error("市场研判定时任务失败: %s", exc)


def pre_market_screen_job() -> None:
    """盘前快筛（工作日 9:25 集合竞价撮合完成后）：交易日校验 + 防重锁 300s。
    检测最近一批候选的竞价异常（大幅低开/高开/可能停牌），异常逐条落库 + 合并一条飞书；
    纯代码检测，无 LLM 调用；无异常不推送不落库。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过盘前快筛", today)
        return
    if not cache.acquire_lock("pre_market_screen", ttl_seconds=300):
        logger.info("pre_market_screen 锁被占用，跳过本次")
        return
    try:
        from app.services import pre_market_screen

        result = pre_market_screen.pre_market_screen()
        logger.info("盘前快筛完成: 检查 %s 只候选，异常 %s 只（%s）",
                    result.get("checked", 0), len(result.get("anomalies") or []),
                    result.get("skipped", "正常"))
        cache.set("job:last_pre_market", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
    except Exception as exc:  # noqa: BLE001 盘前快筛失败不阻塞其他任务
        logger.error("盘前快筛失败: %s", exc)
    finally:
        cache.release_lock("pre_market_screen")


def market_accuracy_job() -> None:
    """市况方向命中率数据沉淀（每日 15:30 收盘定稿后）：回填 market_condition 的
    '次日沪深300涨跌幅' 数据列（幂等；历史行首次运行自动全量回填）。
    纯数据回填，无 LLM 调用；失败不阻塞其他任务。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过市况次日指数回填", today)
        return
    if not cache.acquire_lock("market_accuracy", ttl_seconds=3600):
        logger.info("market_accuracy 锁被占用，跳过本次")
        return
    try:
        from app.services import market_accuracy

        result = market_accuracy.fill_market_condition_next_day()
        cache.set("job:last_market_accuracy", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        logger.info("市况次日指数回填完成: %s（今日 %s）", result.get("filled"),
                    result.get("today"))
    except Exception as exc:  # noqa: BLE001 回填失败不阻塞其他任务
        logger.error("市况次日指数回填失败: %s", exc)
    finally:
        cache.release_lock("market_accuracy")


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


def portfolio_sentinel_job() -> None:
    """组合哨兵巡检：交易时段每 10 分钟；无持仓正常跳过；异常不抛断。
    与 monitor_job 独立（各自锁/各自频率），互不影响。"""
    now = datetime.now()
    if not _in_trading_window(now):
        return
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        return
    if not cache.acquire_lock("portfolio_sentinel", ttl_seconds=600):
        logger.info("portfolio_sentinel 锁被占用，跳过本次")
        return
    try:
        result = graph_router.run_portfolio_sentinel(today)
        ps = result.get("portfolio_sentinel") or {}
        if ps.get("skipped"):
            logger.info("组合哨兵跳过（无持仓）: %s", today)
        else:
            cache.set("job:last_portfolio_sentinel", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
            logger.info("组合哨兵巡检完成: %s（板块预警 %s / 时间止损 %s）", today,
                        len(ps.get("sector_alerts") or []),
                        len(ps.get("time_stop_alerts") or []))
    except Exception as exc:  # noqa: BLE001 定时任务整体容错
        logger.error("组合哨兵巡检失败: %s", exc)
    finally:
        cache.release_lock("portfolio_sentinel")


def sector_refresh_job() -> None:
    """板块快照刷新：每 5 分钟 9:00-15:55；与 monitor_job 独立锁互不干扰

    注：jobs.py:15 已 `from app.cache import cache`，直接用 cache.xxx。
    """
    if not cache.acquire_lock("sector_refresh", ttl_seconds=240):
        logger.info("sector_refresh 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_snapshot import refresh_sector_snapshot
        result = refresh_sector_snapshot()
        if result.get("success"):
            cache.set("job:last_sector_refresh",
                      time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
            logger.info("板块快照刷新完成: %s 条", result.get("rows", 0))
        else:
            logger.warning("板块快照刷新失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        logger.error("板块快照刷新异常: %s", exc)
    finally:
        cache.release_lock("sector_refresh")


def sector_daily_job() -> None:
    """全板块日快照：工作日 15:35 收盘后刷新（删后插当日覆盖；独立锁防并发）"""
    if not cache.acquire_lock("sector_daily", ttl_seconds=600):
        logger.info("sector_daily 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_daily import refresh_sector_daily_snapshot
        result = refresh_sector_daily_snapshot()
        if result.get("success"):
            cache.set("job:last_sector_daily",
                      time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
            logger.info("全板块日快照完成: %s 条", result.get("rows", 0))
            # cron 闭环：快照就绪后追加触发状态机判定+归因，失败不抛
            from app.graph.router import run_sector_rotation
            run_result = run_sector_rotation()
            logger.info("板块轮动判定+归因完成: %s",
                        run_result.get("rotation_state") or run_result.get("error"))
        else:
            logger.warning("全板块日快照失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        logger.error("全板块日快照异常: %s", exc)
    finally:
        cache.release_lock("sector_daily")


def distribution_phase_job() -> None:
    """派发期判定：每日 15:30 收盘后，遍历「今日候选 + 当前持仓」逐只判定落库

    结果幂等落 distribution_phase_log（(trade_date, symbol) 唯一键覆盖）；
    单只失败不阻断其余；锁防并发。
    """
    if not cache.acquire_lock("distribution_phase_auto", ttl_seconds=1800):
        logger.info("distribution_phase_auto 锁被占用，跳过本次")
        return
    try:
        from app.services.distribution_phase import compute_distribution_phase
        trade_date = time.strftime("%Y-%m-%d")
        codes = {c.get("stock_code") for c in repo.list_candidates(trade_date, limit=200)
                 if c.get("stock_code")}
        codes |= {h.get("stock_code") for h in repo.list_holdings() if h.get("stock_code")}
        codes = sorted(codes)
        done, failed = 0, 0
        for code in codes:
            try:
                r = compute_distribution_phase(code, trade_date)
                repo.upsert_distribution_phase(
                    trade_date, code, r.get("phase") or 0,
                    r.get("phase_label") or "", r.get("confidence") or "",
                    r.get("six_dim") or {}, r.get("missing_data") or [])
                done += 1
            except Exception as exc:  # noqa: BLE001 单只失败不阻断其余
                logger.warning("派发期判定失败 %s: %s", code, exc)
                failed += 1
        cache.set("job:last_distribution_phase",
                  time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        logger.info("派发期判定完成: 共%d只 成功%d 失败%d", len(codes), done, failed)
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        logger.error("派发期判定异常: %s", exc)
    finally:
        cache.release_lock("distribution_phase_auto")


def quote_snapshot_refresh_job() -> None:
    """持仓价快照刷新：每 5 分钟 9:00-15:55（腾讯批量 → DB 兜底；独立锁互不干扰）"""
    if not cache.acquire_lock("quote_snapshot_refresh", ttl_seconds=240):
        logger.info("quote_snapshot_refresh 锁被占用，跳过本次")
        return
    try:
        from app.services.quote_snapshot import refresh_quote_snapshot
        result = refresh_quote_snapshot()
        if result.get("success"):
            cache.set("job:last_quote_snapshot_refresh",
                      time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
            logger.info("持仓价快照刷新完成: %s 条 (source=%s)",
                        result.get("rows", 0), result.get("source"))
        else:
            logger.warning("持仓价快照刷新失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        logger.error("持仓价快照刷新异常: %s", exc)
    finally:
        cache.release_lock("quote_snapshot_refresh")


def _is_previous_trading_day(yesterday: str) -> bool:
    """昨天是否最近交易日（龙虎榜 T+1：16:30 后拉的是昨日数据）。
    日历为全量静态历（1990~年末含未来日期）：取今天之前的最后一个交易日与昨天比对"""
    try:
        calendar = AkshareSource().fetch_trade_calendar()
        today = time.strftime("%Y-%m-%d")
        past = [d for d in (calendar or []) if d < today]
        return bool(past) and past[-1] == yesterday
    except Exception as exc:  # noqa: BLE001 日历失败时按工作日放行
        logger.warning("交易日历获取失败，按工作日放行: %s", exc)
        return True


def dragon_tiger_job() -> None:
    """龙虎榜 T+1 拉取：16:30 后抓前一日龙虎榜（游资维度数据链）。
    抓取层纯数据（东财/新浪），研判逻辑在提示词与 services/hot_money.py，此处零判断。"""
    if not settings.dragon_tiger_enable:
        return
    today = time.strftime("%Y-%m-%d")
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    if not _is_previous_trading_day(yesterday):
        logger.info("昨日 %s 非交易日，跳过龙虎榜拉取", yesterday)
        return
    if not cache.acquire_lock("dragon_tiger", ttl_seconds=7200):
        logger.info("dragon_tiger 锁被占用，跳过本次")
        return
    try:
        from app.datasource.dragon_tiger_source import (fetch_dragon_tiger,
                                                        second_source_status)

        seats = fetch_dragon_tiger(yesterday)
        logger.info("龙虎榜拉取完成 %s: 席位 %s 条", yesterday, len(seats))
        # 第二源现状如实标注（K227 诚实：无金额第二源时单源数据保持"置信度不足仅参考"）
        ss = second_source_status()
        if not ss.get("available"):
            logger.info("龙虎榜第二源现状: %s（多源采信待第二源接入）", ss.get("annotation"))
        cache.set("job:last_lhb", today, 86400)
    except Exception as exc:  # noqa: BLE001 抓取失败不阻塞其他任务
        logger.error("龙虎榜拉取失败: %s", exc)
    finally:
        cache.release_lock("dragon_tiger")


def hot_money_win_rate_job() -> None:
    """游资胜率迭代（工作日 16:30，daily_discover 16:10 + market_intel 16:20 之后）：
    归一化匹配收信号 → 统计胜率落库 + 生成降/升档建议（pending 待人工审核，不自动改档）。"""
    try:
        from app.services.hot_money_review import run_win_rate_iteration

        run_win_rate_iteration()
    except Exception as exc:  # noqa: BLE001 迭代失败不阻塞其他任务
        logger.error("游资胜率迭代失败: %s", exc)


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


def experience_worker_job(force: bool = False) -> None:
    """经验沉淀 Worker 调度入口：
    force=True（每日 02:00 主跑）直接执行；force=False（30min 探针）由 Worker 内部积压门判断，
    积压 < 阈值或 task_queue 活跃时轻量跳过。异常不外抛（调度线程吞掉告警日志）。"""
    try:
        from app.services.experience_worker import worker_run
        result = worker_run(force=force)
        logger.info("经验沉淀 Worker: %s", result)
    except Exception as exc:  # noqa: BLE001 调度入口绝不外抛
        logger.error("经验沉淀 Worker 异常: %s", exc)


def fill_forward_view_job() -> None:
    """预测性选股 2.5：每日 16:00 回填前瞻 T+5 实际涨跌（纯统计，复用 track_verify.t5_pct 不新算）"""
    try:
        from app.services.forward_view_history import fill_forward_view_actual
        result = fill_forward_view_actual()
        if result["filled"] > 0:
            logger.info("前瞻T+5回填完成: %s", result)
    except Exception as exc:  # noqa: BLE001 回填失败不阻塞调度
        logger.error("前瞻T+5回填异常: %s", exc)


def calibrate_forward_view_job() -> None:
    """预测性选股 2.5：每周日 04:00 校准前瞻先验（回算近 30 日准确率写日志，不入库）"""
    try:
        from app.services.forward_view_history import calibrate_forward_view_prior
        calibrate_forward_view_prior(lookback_days=30)
    except Exception as exc:  # noqa: BLE001 校准失败不阻塞调度
        logger.error("前瞻先验校准异常: %s", exc)


def ths_pnl_job() -> None:
    """同花顺真实账户今日盈亏采集（P0 数据通道，默认关闭）
    开关 ths_pnl_enable 才跑 + 交易日 + 交易时段；失败只落 error 不抛异常；
    Cookie 零日志（红线 R6）。"""
    if not settings.ths_pnl_enable:
        return
    now_tz = datetime.now(ZoneInfo("Asia/Shanghai"))
    today = now_tz.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        return
    if not _in_trading_window(now_tz):
        return
    from app.services import ths_pnl

    try:
        snapshot = ths_pnl.get_snapshot()
    except Exception as exc:  # noqa: BLE001 采集异常不崩调度，只落 error
        logger.error("同花顺盈亏采集异常: %s", exc)
        snapshot = {"error": "采集异常", "token_expired": False}
    if snapshot.get("error"):
        logger.warning("同花顺盈亏采集未成功: %s", snapshot["error"])
    try:
        repo.upsert_account_pnl_snapshot(
            trade_date=time.strftime("%Y-%m-%d"), ts=time.strftime("%H:%M:%S"),
            pnl_yk=snapshot.get("pnl_yk"), pnl_pct=snapshot.get("pnl_pct"),
            sh_pct=snapshot.get("sh_pct"), chart_data=snapshot.get("chart_data") or [],
            error=snapshot.get("error") or "", token_expired=snapshot.get("token_expired") or False)
    except Exception as exc:  # noqa: BLE001 落库失败不阻塞调度
        logger.error("同花顺盈亏快照落库失败: %s", exc)


def start_scheduler() -> None:
    global scheduler
    if scheduler is not None:
        return
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 工作日 16:00 候选池 T+N 验证（16:10 每日挖掘之前，验证前一日候选）
    scheduler.add_job(track_verify_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=0,
                      id="track_verify", name="候选池T+N验证",
                      replace_existing=True, misfire_grace_time=3600)
    # 预测性选股 2.5：每日 16:00 前瞻 T+5 回填（纯统计，复用 track_verify.t5_pct 不新算）
    scheduler.add_job(fill_forward_view_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=0,
                      id="forward_view_fill", name="前瞻T+5回填",
                      replace_existing=True, misfire_grace_time=3600)
    # 每周日 04:00 前瞻先验校准（回算近 30 日准确率写日志）
    scheduler.add_job(calibrate_forward_view_job, "cron",
                      day_of_week="sun", hour=4, minute=0,
                      id="forward_view_calibrate", name="前瞻先验校准",
                      replace_existing=True, misfire_grace_time=3600)
    # 工作日 16:10 每日挖掘
    scheduler.add_job(daily_discover_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=10,
                      id="daily_discover", name="每日潜力股挖掘",
                      replace_existing=True, misfire_grace_time=3600)
    # 工作日 16:20 市场研判（独立于每日挖掘；当天已生成跳过，幂等）
    scheduler.add_job(market_intel_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=20,
                      id="market_intel", name="市场研判",
                      replace_existing=True, misfire_grace_time=3600)
    # 工作日 16:30 游资胜率迭代（daily_discover/market_intel 之后；归一化匹配收信号）
    scheduler.add_job(hot_money_win_rate_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=30,
                      id="hot_money_win_rate", name="游资胜率迭代",
                      replace_existing=True, misfire_grace_time=3600)
    # 交易日 9:00-16:00 每 N 分钟触发（函数内过滤：盘中高频 + 15:00-15:30 收盘校验低频）
    monitor_minutes = max(1, int(settings.monitor_interval_minutes))
    scheduler.add_job(monitor_job, "cron",
                      day_of_week="mon-fri", hour="9-16", minute=f"*/{monitor_minutes}",
                      id="monitor", name="盘中持仓监控",
                      replace_existing=True, misfire_grace_time=300)
    # 交易日 9:00-16:00 每 10 分钟触发（函数内过滤交易时段窗口；组合级风控巡检，
    # 与 monitor 独立锁/独立频率，互不影响）
    scheduler.add_job(portfolio_sentinel_job, "cron",
                      day_of_week="mon-fri", hour="9-16", minute="*/10",
                      id="portfolio_sentinel", name="组合哨兵巡检",
                      replace_existing=True, misfire_grace_time=300)
    # 工作日 9:25 盘前快筛（集合竞价撮合完成后；候选为上一交易日 16:10 生成）
    scheduler.add_job(pre_market_screen_job, "cron",
                      day_of_week="mon-fri", hour=9, minute=25,
                      id="pre_market_screen", name="盘前快筛",
                      replace_existing=True, misfire_grace_time=300)
    # 工作日 15:30 市况次日指数回填（收盘定稿后；幂等，首次自动回填全部历史行）
    scheduler.add_job(market_accuracy_job, "cron",
                      day_of_week="mon-fri", hour=15, minute=30,
                      id="market_accuracy", name="市况次日指数回填",
                      replace_existing=True, misfire_grace_time=3600)
    # 经验沉淀：每日 02:00 主跑（与现有任务零冲突）+ 每 30 分钟积压探针（内部积压门判断，轻量）
    scheduler.add_job(experience_worker_job, "cron", hour=2, minute=0,
                      args=[True], id="experience_worker", name="经验沉淀识别",
                      replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(experience_worker_job, "cron", minute="*/30",
                      args=[False], id="experience_worker_probe", name="经验沉淀积压探针",
                      replace_existing=True, misfire_grace_time=1800)
    # 每周一次空间维护（默认周日 05:30，低频）
    scheduler.add_job(maintenance_job, "cron",
                      day_of_week=settings.db_maintenance_day_of_week,
                      hour=settings.db_maintenance_hour, minute=settings.db_maintenance_minute,
                      id="db_maintenance", name="存储空间维护",
                      replace_existing=True, misfire_grace_time=3600)
    # 龙虎榜 T+1 拉取（开关开启时生效；16:30 后抓前一日，游资维度数据链）
    if settings.dragon_tiger_enable:
        scheduler.add_job(dragon_tiger_job, "cron",
                          day_of_week="mon-fri",
                          hour=settings.dragon_tiger_hour,
                          minute=settings.dragon_tiger_minute,
                          id="dragon_tiger", name="龙虎榜T+1拉取",
                          replace_existing=True, misfire_grace_time=3600)
    # 板块快照刷新：每 5 分钟 9:00-15:55（独立锁，不与 monitor 冲突）
    scheduler.add_job(sector_refresh_job, "cron",
                      day_of_week="mon-fri", hour="9-15", minute="*/5",
                      id="sector_refresh", name="板块快照刷新",
                      replace_existing=True, misfire_grace_time=300)
    # 派发期判定：每日 15:30 收盘后逐只落库（6 维自动判定，供 Monitor/Sell/Score 参考）
    scheduler.add_job(distribution_phase_job, "cron",
                      day_of_week="mon-fri", hour=15, minute=30,
                      id="distribution_phase", name="派发期判定",
                      replace_existing=True, misfire_grace_time=3600)
    # 板块轮动数据底座：全板块日快照（收盘后 15:35，删后插当日覆盖）
    scheduler.add_job(sector_daily_job, "cron",
                      day_of_week="mon-fri", hour=15, minute=35,
                      id="sector_daily", name="板块轮动日快照",
                      replace_existing=True, misfire_grace_time=3600)
    # 持仓价快照刷新：每 5 分钟 9:00-15:55（腾讯批量 → DB 兜底；独立锁）
    scheduler.add_job(quote_snapshot_refresh_job, "cron",
                      day_of_week="mon-fri", hour="9-15", minute="*/5",
                      id="quote_snapshot_refresh", name="持仓价快照刷新",
                      replace_existing=True, misfire_grace_time=300)
    # 同花顺真实账户今日盈亏采集（开关开启才注册；函数内再按交易日+交易时段过滤）
    if settings.ths_pnl_enable:
        scheduler.add_job(ths_pnl_job, "interval",
                          seconds=max(10, int(settings.ths_pnl_poll_seconds)),
                          id="ths_pnl", name="同花顺今日盈亏采集",
                          replace_existing=True, misfire_grace_time=60)
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
    out.append({"id": "last_portfolio_sentinel", "name": "最近组合哨兵", "next_run": cache.get("job:last_portfolio_sentinel")})
    out.append({"id": "last_track_verify", "name": "最近候选验证", "next_run": cache.get("job:last_track_verify")})
    out.append({"id": "last_pre_market", "name": "最近盘前快筛", "next_run": cache.get("job:last_pre_market")})
    out.append({"id": "last_market_accuracy", "name": "最近市况回填", "next_run": cache.get("job:last_market_accuracy")})
    out.append({"id": "last_sector_refresh", "name": "最近板块刷新", "next_run": cache.get("job:last_sector_refresh")})
    out.append({"id": "last_distribution_phase", "name": "最近派发期判定", "next_run": cache.get("job:last_distribution_phase")})
    out.append({"id": "last_quote_snapshot_refresh", "name": "最近持仓价刷新", "next_run": cache.get("job:last_quote_snapshot_refresh")})
    out.append({"id": "last_sector_daily", "name": "最近板块轮动日快照", "next_run": cache.get("job:last_sector_daily")})
    return out
