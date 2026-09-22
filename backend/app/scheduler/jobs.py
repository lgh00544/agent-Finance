"""
APScheduler 定时任务（Asia/Shanghai）
- 工作日 16:10：每日挖掘（discover → 候选打分）
- 交易日 9:30-11:30 / 13:00-15:00 每 3 分钟：持仓批量监控（实时行情 60s 内缓存）
- 交易日 15:00-15:30：收盘数据校验（当天一次）
- 任务锁防重叠（prod=Redis / dev=内存锁）
【刚性代码逻辑】只做调度，不包含任何市场判断。
"""
import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta
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
_leader_acquired = False
_leader_owner = f"{socket.gethostname()}:{os.getpid()}"
_leader_stop = threading.Event()
_leader_thread: threading.Thread | None = None
_leader_standby_thread: threading.Thread | None = None


def _leader_ttl_seconds() -> int:
    return max(30, int(settings.scheduler_leader_ttl_seconds))


def _leader_renew_seconds() -> int:
    return max(5, min(int(settings.scheduler_leader_renew_seconds), _leader_ttl_seconds() // 2))


def _leader_renew_loop() -> None:
    global scheduler, _leader_acquired
    while not _leader_stop.wait(_leader_renew_seconds()):
        if not _leader_acquired:
            return
        try:
            ok = cache.renew_lock_owner("scheduler:leader", _leader_owner, _leader_ttl_seconds())
        except Exception as exc:  # noqa: BLE001
            ok = False
            logger.error("调度 leader 租约续期失败: %s", exc)
        if not ok:
            logger.error("调度 leader 租约丢失，停止本实例 APScheduler")
            if scheduler is not None:
                try:
                    scheduler.shutdown(wait=False)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("停止失租调度器失败: %s", exc)
                scheduler = None
            _leader_acquired = False
            _start_leader_standby()
            return


def _leader_standby_loop() -> None:
    global _leader_acquired
    while not _leader_stop.wait(max(2, _leader_renew_seconds())):
        if _leader_acquired:
            return
        try:
            if cache.acquire_lock_owner("scheduler:leader", _leader_owner, _leader_ttl_seconds()):
                _leader_acquired = True
                start_scheduler()
                _start_leader_renewal()
                logger.info("调度 leader 接管成功 owner=%s", _leader_owner)
                return
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度 leader 接管竞争失败: %s", exc)


def _start_leader_standby() -> None:
    global _leader_standby_thread
    if _leader_stop.is_set() or (_leader_standby_thread and _leader_standby_thread.is_alive()):
        return
    _leader_standby_thread = threading.Thread(
        target=_leader_standby_loop, name="scheduler-leader-standby", daemon=True)
    _leader_standby_thread.start()


def _start_leader_renewal() -> None:
    global _leader_thread
    _leader_stop.clear()
    _leader_thread = threading.Thread(
        target=_leader_renew_loop, name="scheduler-leader-renew", daemon=True)
    _leader_thread.start()

def _mark_sector_job(job_key: str, success: bool, error: str | None = None) -> None:
    cache.set(f"job:last_{job_key}", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
    cache.set(f"job:last_{job_key}_error", "" if success else (error or "unknown")[:500], 86400)


def _record_job_run(event) -> None:
    """APScheduler 执行事件 → job_run_log upsert（批A A2）；留痕失败不影响调度。"""
    try:
        from app.db.models import JobRunLog
        from app.db.session import SessionLocal

        exc = getattr(event, "exception", None)
        with SessionLocal() as db:
            row = db.get(JobRunLog, event.job_id)
            if row is None:
                row = JobRunLog(job_id=event.job_id)
                db.add(row)
            row.last_run = datetime.now()
            row.last_status = "error" if exc else "ok"
            row.last_reason = str(exc)[:500] if exc else None
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("job_run_log 写入失败: %s", exc)


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


# === DISABLED 2026-09-16: 同花顺下线（函数保留，不再被调用）===
def _in_ths_pnl_window(now: datetime) -> bool:
    """同花顺盈亏采集窗口 9:15-16:00（用户指定：盘前 15 分钟起覆盖集合竞价）"""
    hm = now.hour * 100 + now.minute
    return 915 <= hm <= 1600


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


def run_factor_ic_backtest_job() -> None:
    """每月因子 IC 回测；失败只记日志，不阻塞其他调度任务。"""
    try:
        from app.services.factor_ic import run_factor_ic_backtest_job as run_backtest
        logger.info("因子 IC 月度回测完成: %s", run_backtest())
    except Exception as exc:  # noqa: BLE001 回测失败不阻塞调度
        logger.error("因子 IC 月度回测失败: %s", exc)


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
        _reclaim_memory()


def paper_execution_job() -> None:
    """收盘后审核模拟复盘；成交仅由盘中执行器使用实时行情完成。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today) or not cache.acquire_lock("paper_execution", ttl_seconds=3600):
        return
    try:
        # 模拟复盘的 AI 闸门自动运行；失败保留 pending，页面提供重试入口。
        from app.agents.paper_review import audit_review
        for review in repo.list_paper_reviews(limit=200):
            if review.get("audit_status") == "pending":
                try:
                    from app.core.auth import reset_user_context, set_user_context
                    tokens = set_user_context(review.get("user_id") or 1, "admin")
                    try:
                        audit_review(review["id"])
                    finally:
                        reset_user_context(tokens)
                except Exception as exc:  # noqa: BLE001 审核失败不伪造通过
                    logger.warning("模拟复盘 AI 审核失败 review#%s: %s", review.get("id"), exc)
        cache.set("job:last_paper_execution", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        logger.info("模拟复盘审核轮询完成")
    finally:
        cache.release_lock("paper_execution")


def paper_monitor_job() -> None:
    """盘中模拟账户巡检；日历不可用时暂停，所有账户独立失败隔离。"""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if not _in_trading_window(now):
        return
    today = now.date().isoformat()
    try:
        if today not in (AkshareSource().fetch_trade_calendar() or []):
            return
    except Exception as exc:
        logger.warning("模拟监控暂停，交易日历不可用: %s", exc)
        return
    if not cache.acquire_lock("paper_monitor", ttl_seconds=3600):
        return
    try:
        from app.services import paper_execution, paper_monitor
        for account in repo.list_paper_accounts(status="active"):
            try:
                from app.core.auth import reset_user_context, set_user_context
                tokens = set_user_context(account.get("user_id") or 1, "admin")
                try:
                    paper_execution.run(account["id"], today)
                finally:
                    reset_user_context(tokens)
            except Exception as exc:
                logger.warning("模拟账户 %s 盘中建仓执行失败: %s", account.get("id"), exc)
            try:
                tokens = set_user_context(account.get("user_id") or 1, "admin")
                try:
                    paper_monitor.run(account["id"], today)
                finally:
                    reset_user_context(tokens)
            except Exception as exc:
                logger.warning("模拟账户 %s 盘中监控失败: %s", account.get("id"), exc)
        cache.set("job:last_paper_monitor", now.strftime("%Y-%m-%d %H:%M:%S"), 86400)
    finally:
        cache.release_lock("paper_monitor")


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
        results = []
        users = repo.list_active_users() if settings.multi_user_enabled else [
            {"id": None, "role": None}]
        from app.core.auth import reset_user_context, set_user_context
        for user in users:
            tokens = set_user_context(user["id"], user.get("role"))
            try:
                results.extend(graph_router.run_monitor_all(
                    today, user["id"], is_admin=user.get("role") == "admin"))
            finally:
                reset_user_context(tokens)
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
        users = repo.list_active_users() if settings.multi_user_enabled else [
            {"id": None, "role": None}]
        from app.core.auth import reset_user_context, set_user_context
        ps_rows = []
        for user in users:
            tokens = set_user_context(user["id"], user.get("role"))
            try:
                result = graph_router.run_portfolio_sentinel(today)
                ps_rows.append(result.get("portfolio_sentinel") or {})
            finally:
                reset_user_context(tokens)
        ps = {"sector_alerts": sum((p.get("sector_alerts") or [] for p in ps_rows), []),
              "time_stop_alerts": sum((p.get("time_stop_alerts") or [] for p in ps_rows), []),
              "skipped": bool(ps_rows) and all(p.get("skipped") for p in ps_rows)}
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
            _mark_sector_job("sector_daily", True)
            logger.info("全板块日快照完成: %s 条", result.get("rows", 0))
            # cron 闭环：快照就绪后追加触发状态机判定+归因，失败不抛
            from app.graph.router import run_sector_rotation
            run_result = run_sector_rotation()
            logger.info("板块轮动判定+归因完成: %s",
                        run_result.get("rotation_state") or run_result.get("error"))
        else:
            _mark_sector_job("sector_daily", False, str(result.get("error")))
            logger.warning("全板块日快照失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        _mark_sector_job("sector_daily", False, str(exc))
        logger.error("全板块日快照异常: %s", exc)
    finally:
        cache.release_lock("sector_daily")


def sector_regime_job() -> None:
    """行情结构识别：15:40 独立运行，不依赖 C 归因子。"""
    if not cache.acquire_lock("sector_regime", ttl_seconds=900):
        logger.info("sector_regime 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_regime import judge_regime
        result = judge_regime()
        if result.get("success"):
            _mark_sector_job("sector_regime", True)
            logger.info("行情结构识别完成: %s/%s",
                        result.get("current_regime"), result.get("regime_stage"))
        else:
            _mark_sector_job("sector_regime", False, str(result.get("error")))
            logger.warning("行情结构识别失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        _mark_sector_job("sector_regime", False, str(exc))
        logger.error("行情结构识别异常: %s", exc)
    finally:
        cache.release_lock("sector_regime")


def sector_forward_job() -> None:
    """板块前瞻：15:45 读取 C' 结构结果，独立执行 D' 纯代码计算。"""
    if not cache.acquire_lock("sector_forward", ttl_seconds=900):
        logger.info("sector_forward 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_forward_view import run_sector_forward
        result = run_sector_forward()
        if result.get("success"):
            _mark_sector_job("sector_forward", True)
            logger.info("板块前瞻完成: %s 条", result.get("count", 0))
        else:
            _mark_sector_job("sector_forward", False, str(result.get("error")))
            logger.warning("板块前瞻失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        _mark_sector_job("sector_forward", False, str(exc))
        logger.error("板块前瞻异常: %s", exc)
    finally:
        cache.release_lock("sector_forward")


def sector_forecast_verify_job() -> None:
    """前瞻验证回填：16:05 用后续真实快照验证历史 C'/D' 预测。"""
    if not cache.acquire_lock("sector_forecast_verify", ttl_seconds=900):
        logger.info("sector_forecast_verify 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_forecast_verify import run_sector_forecast_verify
        result = run_sector_forecast_verify()
        if result.get("success"):
            _mark_sector_job("sector_forecast_verify", True)
            logger.info("前瞻验证回填完成: %s 条", result.get("count", 0))
        else:
            _mark_sector_job("sector_forecast_verify", False, str(result.get("error")))
            logger.warning("前瞻验证回填失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        _mark_sector_job("sector_forecast_verify", False, str(exc))
        logger.error("前瞻验证回填异常: %s", exc)
    finally:
        cache.release_lock("sector_forecast_verify")


def sector_next_hot_job() -> None:
    """下一个风口预测：15:50 基于 D' 指标派生 top10 外候选。"""
    if not cache.acquire_lock("sector_next_hot", ttl_seconds=900):
        logger.info("sector_next_hot 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_next_hot import judge_next_hot
        result = judge_next_hot()
        if result.get("success"):
            _mark_sector_job("sector_next_hot", True)
            logger.info("下一个风口预测完成: %s 条", result.get("count", 0))
        else:
            _mark_sector_job("sector_next_hot", False, str(result.get("error")))
            logger.warning("下一个风口预测失败: %s", result.get("error"))
    except Exception as exc:  # noqa: BLE001 调度入口吞异常
        _mark_sector_job("sector_next_hot", False, str(exc))
        logger.error("下一个风口预测异常: %s", exc)
    finally:
        cache.release_lock("sector_next_hot")


def sector_radar_job() -> None:
    """行业消息雷达：观察型抓取 + K228 解读，失败不影响正式 Agent。"""
    if not cache.acquire_lock("sector_radar", ttl_seconds=1800):
        logger.info("sector_radar 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_radar import collect_sector_radar
        result = collect_sector_radar(auto_interpret=True)
        _mark_sector_job("sector_radar", not result.get("errors"),
                         "; ".join(result.get("errors", [])[:3]) or None)
        logger.info("行业消息雷达完成: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("行业消息雷达失败: %s", exc)
        _mark_sector_job("sector_radar", False, str(exc))
    finally:
        cache.release_lock("sector_radar")


def sector_radar_shadow_job() -> None:
    """行业消息雷达 shadow 回填：只做观测统计，不改变候选池。"""
    if not cache.acquire_lock("sector_radar_shadow", ttl_seconds=1800):
        logger.info("sector_radar_shadow 锁被占用，跳过本次")
        return
    try:
        from app.services.sector_radar import shadow_verify_worker
        result = shadow_verify_worker()
        _mark_sector_job("sector_radar_shadow", True)
        logger.info("行业消息雷达 shadow 回填完成: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("行业消息雷达 shadow 回填失败: %s", exc)
        _mark_sector_job("sector_radar_shadow", False, str(exc))
    finally:
        cache.release_lock("sector_radar_shadow")


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
        users = repo.list_active_users() if settings.multi_user_enabled else [
            {"id": None, "role": None}]
        from app.core.auth import reset_user_context, set_user_context
        results = []
        for user in users:
            tokens = set_user_context(user["id"], user.get("role"))
            try:
                results.append(refresh_quote_snapshot(
                    user["id"], is_admin=user.get("role") == "admin"))
            finally:
                reset_user_context(tokens)
        result = {"success": all(r.get("success") for r in results),
                  "rows": sum(int(r.get("rows") or 0) for r in results),
                  "source": ",".join(sorted({str(r.get("source") or "") for r in results}))}
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


def _reclaim_memory() -> None:
    """重 job 结束显式回收：pandas/numpy 原生缓冲不随引用释放即时归还 OS，主动 GC 压 RSS 台阶。
    并顺带按 TTL 硬关诊断端点可能开启的 tracemalloc（A3 复盘：常开会永久抬高 RSS ~300MB/h）。"""
    import gc

    from app.core import mem_diag

    mem_diag.trace_guard()
    gc.collect()


def hot_money_win_rate_job() -> None:
    """游资胜率迭代（工作日 16:30，daily_discover 16:10 + market_intel 16:20 之后）：
    归一化匹配收信号 → 统计胜率落库 + 生成降/升档建议（pending 待人工审核，不自动改档）。"""
    try:
        from app.services.hot_money_review import run_win_rate_iteration

        run_win_rate_iteration()
    except Exception as exc:  # noqa: BLE001 迭代失败不阻塞其他任务
        logger.error("游资胜率迭代失败: %s", exc)
    finally:
        _reclaim_memory()


def _next_a_share_trade_date(now_dt: datetime | None = None) -> str:
    """下一个A股交易日（简单算法：今天非周末取今天，否则顺延到周一）"""
    dt = now_dt or datetime.now()
    if dt.weekday() < 5:
        return dt.strftime("%Y-%m-%d")
    days = 2 if dt.weekday() == 5 else 1  # 周六顺延2天（到周一），周日顺延1天
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")


def collect_overnight_factor_job() -> None:
    """美股隔夜因子采集（每天 21:30 北京时间）：周六日跳过；trade_date 取下一个
    A股交易日；已有该交易日记录则跳过（幂等）；失败只记日志不阻塞其他任务。"""
    from app.services import overnight_factor

    if not settings.overnight_factor_enabled:
        logger.info("美股隔夜因子功能未开启，跳过采集")
        return
    now = datetime.now()
    if now.weekday() >= 5:
        logger.info("周末无美股隔夜参考，跳过隔夜因子采集")
        return
    trade_date = _next_a_share_trade_date(now)
    if not cache.acquire_lock("overnight_factor_collect", ttl_seconds=3600):
        logger.info("隔夜因子采集任务已在运行，跳过本次")
        return
    try:
        latest = repo.get_latest_us_overnight_factor()
        if latest and latest["trade_date"] == trade_date:
            logger.info("交易日 %s 已有隔夜因子记录，跳过采集", trade_date)
            return
        data = overnight_factor.compute_overnight_factor(trade_date)
        repo.upsert_us_overnight_factor(
            trade_date=trade_date,
            factor_value=data["factor_value"],
            band=data["band"],
            prediction=data["prediction"],
            up_count=data["up_count"],
            stocks_detail=data["stocks_detail"],
            notes=data["notes"],
        )
        logger.info("美股隔夜因子采集完成: %s band=%s prediction=%s factor=%.2f%%",
                    trade_date, data["band"], data["prediction"], data["factor_value"])
    except Exception as exc:  # noqa: BLE001 定时任务整体容错
        logger.error("美股隔夜因子采集失败: %s", exc)
    finally:
        cache.release_lock("overnight_factor_collect")


def verify_overnight_factor_job() -> None:
    """美股隔夜因子校验（工作日 9:35 开盘后）：拉上证指数今开/昨收计算开盘缺口，
    对最新一条未校验（actual_gap IS NULL）且押注方向非「不押注」的记录回填
    actual_gap 与 is_correct（缺口方向与预测一致=True）；失败只记日志不阻塞。"""
    from app.datasource import us_quote

    if not settings.overnight_factor_enabled:
        logger.info("美股隔夜因子功能未开启，跳过校验")
        return
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过隔夜因子校验", today)
        return
    if not cache.acquire_lock("overnight_factor_verify", ttl_seconds=600):
        logger.info("隔夜因子校验任务已在运行，跳过本次")
        return
    try:
        latest = repo.get_latest_us_overnight_factor()
        if not latest or latest.get("actual_gap") is not None:
            logger.info("无待校验的隔夜因子记录，跳过校验")
            return
        if latest.get("prediction") == "不押注":
            logger.info("最新记录为不押注，无需校验")
            return
        gap = us_quote.fetch_sh_index_open_gap()
        if gap is None:
            logger.warning("上证指数开盘缺口获取失败，本次跳过校验")
            return
        prediction = latest["prediction"]
        is_correct = (prediction == "高开" and gap > 0) or (prediction == "低开" and gap < 0)
        repo.upsert_us_overnight_factor(
            trade_date=latest["trade_date"],
            factor_value=latest["factor_value"],
            band=latest["band"],
            prediction=latest["prediction"],
            up_count=latest["up_count"],
            stocks_detail=latest["stocks_detail"],
            actual_gap=gap,
            is_correct=is_correct,
        )
        logger.info("美股隔夜因子校验完成: %s prediction=%s gap=%.2f%% is_correct=%s",
                    latest["trade_date"], prediction, gap, is_correct)
    except Exception as exc:  # noqa: BLE001 定时任务整体容错
        logger.error("美股隔夜因子校验失败: %s", exc)
    finally:
        cache.release_lock("overnight_factor_verify")


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
        from app.core.auth import reset_user_context, set_user_context
        users = repo.list_active_users() if settings.multi_user_enabled else [
            {"id": None, "role": None}]
        results = []
        for user in users:
            tokens = set_user_context(user["id"], user.get("role"))
            try:
                results.append(worker_run(force=force, user_id=user["id"]))
            except Exception as exc:
                logger.error("经验沉淀 Worker 用户 %s 异常: %s", user["id"], exc)
            finally:
                reset_user_context(tokens)
        result = results
        logger.info("经验沉淀 Worker: %s", result)
    except Exception as exc:  # noqa: BLE001 调度入口绝不外抛
        logger.error("经验沉淀 Worker 异常: %s", exc)
    finally:
        _reclaim_memory()


def audit_pending_job() -> None:
    """通用审核批处理：每日 03:30 低峰扫描待审建议辩证审核（audit_log 落库；首审失败触发 rethink 重审）"""
    try:
        from app.agents.audit import run_pending_audits
        from app.core.auth import reset_user_context, set_user_context
        users = repo.list_active_users() if settings.multi_user_enabled else [
            {"id": None, "role": None}]
        results = []
        for user in users:
            tokens = set_user_context(user["id"], user.get("role"))
            try:
                results.append(run_pending_audits(cutoff_id=0, user_id=user["id"]))
            except Exception as exc:
                logger.error("建议辩证审核用户 %s 异常: %s", user["id"], exc)
            finally:
                reset_user_context(tokens)
        result = {"users": results}
        errors = [e for result in results for e in result.get("errors") or []]
        error_text = "; ".join([f"#{e.get('id')}: {e.get('error')}" for e in errors])[:500]
        cache.set("job:last_audit_pending", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        cache.set("job:last_audit_pending_error", error_text, 86400)
        if error_text:
            logger.warning("建议辩证审核部分失败: %s", result)
        else:
            logger.info("建议辩证审核: %s", result)
    except Exception as exc:  # noqa: BLE001 调度入口绝不外抛
        cache.set("job:last_audit_pending", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)
        cache.set("job:last_audit_pending_error", str(exc)[:500], 86400)
        logger.error("建议辩证审核异常: %s", exc)


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
    开关 ths_pnl_enable 才跑 + 交易日 + 采集窗口 9:15-16:00；失败只落 error 不抛异常；
    Cookie 零日志（红线 R6）。"""
    return  # DISABLED 2026-09-16 同花顺下线（原逻辑保留在下方）
    if not settings.ths_pnl_enable:
        return
    now_tz = datetime.now(ZoneInfo("Asia/Shanghai"))
    today = now_tz.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        return
    if not _in_ths_pnl_window(now_tz):
        return
    from app.services import ths_pnl

    users = repo.list_active_users() if settings.multi_user_enabled else [
        {"id": None, "role": None}]
    from app.core.auth import reset_user_context, set_user_context
    for user in users:
        tokens = set_user_context(user["id"], user.get("role"))
        try:
            try:
                snapshot = ths_pnl.get_snapshot()
            except Exception as exc:  # noqa: BLE001 采集异常不崩调度，只落 error
                logger.error("同花顺盈亏采集异常: %s", exc)
                snapshot = {"error": "采集异常", "token_expired": False}
            if snapshot.get("error"):
                logger.warning("同花顺盈亏采集未成功: %s", snapshot["error"])
            repo.upsert_account_pnl_snapshot(
                trade_date=time.strftime("%Y-%m-%d"), ts=time.strftime("%H:%M:%S"),
                pnl_yk=snapshot.get("pnl_yk"), pnl_pct=snapshot.get("pnl_pct"),
                sh_pct=snapshot.get("sh_pct"), chart_data=snapshot.get("chart_data") or [],
                error=snapshot.get("error") or "",
                token_expired=snapshot.get("token_expired") or False,
                user_id=user["id"])
        except Exception as exc:  # noqa: BLE001 落库失败不阻塞调度
            logger.error("同花顺盈亏快照落库失败 user=%s: %s", user["id"], exc)
        finally:
            reset_user_context(tokens)


def feishu_daily_report_job() -> None:
    """每日收盘日报直发，按绑定用户分别生成并发送。"""
    if not settings.feishu_daily_report or not _is_trading_day(time.strftime("%Y-%m-%d")):
        return
    from app.services import holding_view  # ths_pnl DISABLED 2026-09-16
    from app.services.feishu_sender import send_text
    users = repo.list_active_users() if settings.multi_user_enabled else [
        {"id": None, "role": None, "feishu_open_id": None}]
    fallback_ids = [s.strip() for s in settings.feishu_admin_open_ids.split(",") if s.strip()]
    from app.core.auth import reset_user_context, set_user_context
    for user in users:
        tokens = set_user_context(user["id"], user.get("role"))
        try:
            lines = [f"📊 {time.strftime('%Y-%m-%d')} 收盘日报"]
            snap = {}  # DISABLED 2026-09-16：同花顺已下线，走 fallback 文案
            lines.append(f"今日盈亏: ¥{snap['pnl_yk']:,.0f}（{snap.get('pnl_pct')}%）"
                         if snap.get('pnl_yk') is not None else f"今日盈亏: {snap.get('error') or '未接入'}")
            view = holding_view.build_holding_view(
                user["id"], is_admin=user.get("role") == "admin")
            rows = view["rows"]
            mv = sum(r["market_value"] or 0 for r in rows)
            pnl = sum(r["pnl_amount"] or 0 for r in rows)
            lines.append(f"持仓 {len(rows)} 只 | 总市值 ¥{mv:,.0f} | 浮动盈亏 ¥{pnl:,.0f}")
            alerts = [a for a in repo.list_alerts(
                50, user_id=user["id"], is_admin=user.get("role") == "admin")
                if str(a.get("created_at", "")).startswith(time.strftime("%Y-%m-%d"))]
            lines.append(f"今日告警 {len(alerts)} 条")
            recipients = [user.get("feishu_open_id")] if user.get("feishu_open_id") else fallback_ids
            for oid in [x for x in recipients if x]:
                send_text(oid, "\n".join(lines))
        finally:
            reset_user_context(tokens)


def signal_scan_job() -> None:
    """买卖点信号全市场扫描（工作日 16:50 收盘后）；非交易日直接返回，不产生任何记录。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过买卖点信号扫描", today)
        return
    if not cache.acquire_lock("signal_scan", ttl_seconds=3600):
        logger.info("signal_scan 锁被占用，跳过本次")
        return
    try:
        from app.services.signal_scan import scan_signal_triggers
        logger.info("买卖点信号扫描完成: %s", scan_signal_triggers(today))
    except Exception as exc:  # noqa: BLE001 调度任务整体容错
        logger.error("买卖点信号扫描失败: %s", exc)
    finally:
        cache.release_lock("signal_scan")
        _reclaim_memory()


MIN_KLINE_BARS_FOR_BACKFILL = 250


def kline_backfill_job() -> None:
    """夜间本地日线历史回补（逐夜分批，可中断续跑）；不占 16:50 扫描窗口。

    只写本地 SQLite；每夜最多 settings.kline_backfill_batch_limit 只（断点靠本地库自身状态）。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过夜间日线回补", today)
        return
    if not cache.acquire_lock("kline_backfill", ttl_seconds=6 * 3600):
        logger.info("kline_backfill 锁被占用，跳过本次")
        return
    try:
        from app.services import kline_store
        from app.services.kline_backfill import backfill

        from app.services.kline_backfill import pending_codes

        stats = kline_store.stats()
        todo = pending_codes(min_bars=MIN_KLINE_BARS_FOR_BACKFILL)
        limit = settings.kline_backfill_batch_limit
        if limit and len(todo) > limit:
            todo = todo[:limit]
        if not todo:
            logger.info("夜间日线回补：全部已足 %d 根，无需回补（仓库 %s）",
                        MIN_KLINE_BARS_FOR_BACKFILL, stats)
            return
        names = {}
        try:
            from app.datasource.fallback import get_datasource
            spot = get_datasource().fetch_spot_universe()
            if spot is not None and not spot.empty and "name" in spot.columns:
                names = {str(r["code"]): str(r.get("name") or "") for r in spot.to_dict("records")}
        except Exception as exc:  # noqa: BLE001 名称非必需，缺失退化为空串（is_st 由本地库名兜底）
            logger.warning("夜间日线回补：股票名称获取失败，退化为空名: %s", exc)
        summary = backfill(todo, sleep_between=settings.kline_backfill_sleep, names=names,
                           workers=settings.kline_backfill_workers)
        logger.info("夜间日线回补完成: %s（仓库 %s）", summary, kline_store.stats())
    except Exception as exc:  # noqa: BLE001 调度任务整体容错
        logger.error("夜间日线回补失败: %s", exc)
    finally:
        cache.release_lock("kline_backfill")
        _reclaim_memory()


def kline_ingest_job() -> None:
    """本地日线仓库增量（工作日 16:25）；非交易日直接返回，除权票当场重建历史段。"""
    today = time.strftime("%Y-%m-%d")
    if not _is_trading_day(today):
        logger.info("今天 %s 非交易日，跳过本地日线增量", today)
        return
    if not cache.acquire_lock("kline_ingest", ttl_seconds=3600):
        logger.info("kline_ingest 锁被占用，跳过本次")
        return
    try:
        from app.services.kline_backfill import backfill
        from app.services.kline_ingest import ingest_today
        summary = ingest_today(today)
        if summary.get("ex_div_codes"):
            rebuilt = backfill(summary["ex_div_codes"], rebuild=True)
            summary["rebuilt"] = {"codes": len(summary["ex_div_codes"]), "ok": rebuilt["ok"],
                                  "failed": rebuilt["failed"]}
        logger.info("本地日线增量完成: %s", summary)
    except Exception as exc:  # noqa: BLE001 调度任务整体容错
        logger.error("本地日线增量失败: %s", exc)
    finally:
        cache.release_lock("kline_ingest")
        _reclaim_memory()


def start_scheduler() -> None:
    global scheduler, _leader_acquired
    if scheduler is not None:
        return
    if settings.multi_user_enabled:
        if settings.cache_backend != "redis":
            logger.error("多人模式拒绝启动调度：必须配置共享 Redis")
            return
        if not _leader_acquired and not cache.acquire_lock_owner(
                "scheduler:leader", _leader_owner, _leader_ttl_seconds()):
            logger.warning("多人模式当前实例不是调度 leader，跳过 APScheduler")
            _start_leader_standby()
            return
        if not _leader_acquired:
            _leader_acquired = True
            _start_leader_renewal()
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
    # 工作日 16:25 本地日线仓库增量（批量快照落当日 bar；16:50 扫描只读本地，批 1.5 容量修复）
    scheduler.add_job(kline_ingest_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=25,
                      id="kline_ingest", name="本地日线增量",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)
    # 每夜 00:40 历史回补（逐夜分批、可中断续跑）；**刻意不占 16:50 扫描窗口**
    scheduler.add_job(kline_backfill_job, "cron",
                      day_of_week="tue-sat", hour=0, minute=40,
                      id="kline_backfill", name="本地日线夜间回补",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)
    # 工作日 16:50 买卖点信号全市场扫描（批 1 只攒数据，不进任何 Agent、不触发交易动作）
    scheduler.add_job(signal_scan_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=50,
                      id="signal_scan", name="买卖点信号扫描",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)
    scheduler.add_job(run_factor_ic_backtest_job, "cron", day=1, hour=2, minute=0,
                      id="factor_ic_backtest", name="因子 IC 月度回测",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)
    # 工作日 16:30 游资胜率迭代（daily_discover/market_intel 之后；归一化匹配收信号）
    scheduler.add_job(hot_money_win_rate_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=30,
                      id="hot_money_win_rate", name="游资胜率迭代",
                      replace_existing=True, misfire_grace_time=3600)
    # 工作日 16:35 收盘后审核模拟复盘；成交只在盘中进行。
    scheduler.add_job(paper_execution_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=35,
                      id="paper_execution", name="AI模拟复盘审核",
                      replace_existing=True, misfire_grace_time=3600)
    # 交易日 9:00-16:00 每 N 分钟触发（函数内过滤：盘中高频 + 15:00-15:30 收盘校验低频）
    monitor_minutes = max(1, int(settings.monitor_interval_minutes))
    scheduler.add_job(monitor_job, "cron",
                      day_of_week="mon-fri", hour="9-16", minute=f"*/{monitor_minutes}",
                      id="monitor", name="盘中持仓监控",
                      replace_existing=True, misfire_grace_time=300)
    # 模拟研究上下文每 15 分钟复用；监控轮询至少间隔 5 分钟，控制模型调用成本。
    scheduler.add_job(paper_monitor_job, "cron",
                      day_of_week="mon-fri", hour="9-15", minute=f"*/{max(5, monitor_minutes)}",
                      id="paper_monitor", name="AI模拟盘中监控",
                      replace_existing=True, misfire_grace_time=300, max_instances=1)
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
    # 通用审核 Agent：每日 03:30 低峰批量辩证审核待审建议（游标增量，幂等）
    scheduler.add_job(audit_pending_job, "cron", hour=3, minute=30,
                      id="audit_pending", name="建议辩证审核",
                      replace_existing=True, misfire_grace_time=3600)
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
    # 飞书每日收盘日报（默认关；开启才注册，避免空转）
    if settings.feishu_daily_report:
        scheduler.add_job(feishu_daily_report_job, "cron",
                          day_of_week="mon-fri",
                          hour=settings.feishu_daily_report_hour,
                          minute=settings.feishu_daily_report_minute,
                          id="feishu_daily_report", name="飞书日报直发",
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
    # C' 行情结构识别：多窗口结构综合（收盘后 15:40，独立于 C 归因子）
    scheduler.add_job(sector_regime_job, "cron",
                      day_of_week="mon-fri", hour=15, minute=40,
                      id="sector_regime", name="行情结构识别",
                      replace_existing=True, misfire_grace_time=3600)
    # D' 板块前瞻：读取 C' 结构结果，纯代码计算（收盘后 15:45）
    scheduler.add_job(sector_forward_job, "cron",
                      day_of_week="mon-fri", hour=15, minute=45,
                      id="sector_forward", name="板块前瞻预测",
                      replace_existing=True, misfire_grace_time=3600)
    # G' 下一个风口预测：基于 D' 指标派生 top10 外候选（收盘后 15:50）
    scheduler.add_job(sector_next_hot_job, "cron",
                      day_of_week="mon-fri", hour=15, minute=50,
                      id="sector_next_hot", name="下一个风口预测",
                      replace_existing=True, misfire_grace_time=3600)
    # E'-1 前瞻验证回填：使用后续真实板块快照校验历史预测（收盘后 16:05）
    scheduler.add_job(sector_forecast_verify_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=5,
                      id="sector_forecast_verify", name="前瞻验证回填",
                      replace_existing=True, misfire_grace_time=3600)
    # 行业消息雷达：观察型 shadow，不进入正式 Agent/候选池
    scheduler.add_job(sector_radar_job, "cron",
                      day_of_week="mon-sun", hour=8, minute=0,
                      id="sector_radar", name="行业消息雷达",
                      replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(sector_radar_shadow_job, "cron",
                      day_of_week="mon-fri", hour=16, minute=25,
                      id="sector_radar_shadow", name="行业消息雷达shadow回填",
                      replace_existing=True, misfire_grace_time=3600)
    # 持仓价快照刷新：每 5 分钟 9:00-15:55（腾讯批量 → DB 兜底；独立锁）
    scheduler.add_job(quote_snapshot_refresh_job, "cron",
                      day_of_week="mon-fri", hour="9-15", minute="*/5",
                      id="quote_snapshot_refresh", name="持仓价快照刷新",
                      replace_existing=True, misfire_grace_time=300)
    # 同花顺真实账户今日盈亏采集（开关开启才注册；cron 精确 9:15-16:00 窗口、
    # 按 ths_pnl_poll_seconds 触发，仅工作日；函数内再按交易日+窗口过滤，夜间不空转）
    # === DISABLED 2026-09-16: 同花顺下线，cron 停注册 ===
    if False:
        _poll = max(10, int(settings.ths_pnl_poll_seconds))
        scheduler.add_job(ths_pnl_job, "cron", day_of_week="mon-fri",
                          hour=9, minute="15-59", second=f"*/{_poll}",
                          id="ths_pnl_915", name="同花顺今日盈亏采集",
                          replace_existing=True, misfire_grace_time=60)
        scheduler.add_job(ths_pnl_job, "cron", day_of_week="mon-fri",
                          hour="10-15", minute="*", second=f"*/{_poll}",
                          id="ths_pnl_mid", name="同花顺今日盈亏采集",
                          replace_existing=True, misfire_grace_time=60)
        scheduler.add_job(ths_pnl_job, "cron", day_of_week="mon-fri",
                          hour=16, minute=0, second=f"*/{_poll}",
                          id="ths_pnl_1600", name="同花顺今日盈亏采集",
                          replace_existing=True, misfire_grace_time=60)
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

    scheduler.add_listener(_record_job_run, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    # 美股隔夜因子：每天 21:30 采集（周末/非交易日函数内跳过，幂等）；
    # 工作日 9:35 校验开盘缺口回填台账（只读观察因子，不参与现有决策）
    scheduler.add_job(collect_overnight_factor_job, "cron",
                      hour=settings.overnight_factor_hour,
                      minute=settings.overnight_factor_minute,
                      id="overnight_factor_collect", name="美股隔夜因子采集",
                      replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(verify_overnight_factor_job, "cron", day_of_week="mon-fri",
                      hour=9, minute=35,
                      id="overnight_factor_verify", name="美股隔夜因子校验",
                      replace_existing=True, misfire_grace_time=3600)
    scheduler.start()
    logger.info("APScheduler 已启动（Asia/Shanghai）")


def stop_scheduler() -> None:
    global scheduler, _leader_acquired
    _leader_stop.set()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
    if _leader_acquired:
        cache.release_lock_owner("scheduler:leader", _leader_owner)
        _leader_acquired = False


def job_status() -> list[dict]:
    if scheduler is None:
        return []
    out = []
    for job in scheduler.get_jobs():
        out.append({"id": job.id, "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None})
    out.append({"id": "last_discover", "name": "最近挖掘", "next_run": cache.get("job:last_discover")})
    out.append({"id": "last_paper_execution", "name": "最近 AI 模拟执行",
                "next_run": cache.get("job:last_paper_execution")})
    out.append({"id": "last_paper_monitor", "name": "最近 AI 模拟盘中监控",
                "next_run": cache.get("job:last_paper_monitor")})
    out.append({"id": "last_monitor", "name": "最近监控", "next_run": cache.get("job:last_monitor")})
    out.append({"id": "last_portfolio_sentinel", "name": "最近组合哨兵", "next_run": cache.get("job:last_portfolio_sentinel")})
    out.append({"id": "last_track_verify", "name": "最近候选验证", "next_run": cache.get("job:last_track_verify")})
    out.append({"id": "last_pre_market", "name": "最近盘前快筛", "next_run": cache.get("job:last_pre_market")})
    out.append({"id": "last_market_accuracy", "name": "最近市况回填", "next_run": cache.get("job:last_market_accuracy")})
    out.append({"id": "last_sector_refresh", "name": "最近板块刷新", "next_run": cache.get("job:last_sector_refresh")})
    out.append({"id": "last_distribution_phase", "name": "最近派发期判定", "next_run": cache.get("job:last_distribution_phase")})
    out.append({"id": "last_quote_snapshot_refresh", "name": "最近持仓价刷新", "next_run": cache.get("job:last_quote_snapshot_refresh")})
    out.append({"id": "last_sector_daily", "name": "最近板块轮动日快照", "next_run": cache.get("job:last_sector_daily")})
    out.append({"id": "last_audit_pending", "name": "最近建议辩证审核", "next_run": cache.get("job:last_audit_pending"),
                "error": cache.get("job:last_audit_pending_error")})
    out.append({"id": "scheduler_leader", "name": "调度 leader",
                "next_run": cache.get_lock_owner("scheduler:leader") or ""})
    return out
