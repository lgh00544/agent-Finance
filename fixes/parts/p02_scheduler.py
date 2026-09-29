# -*- coding: utf-8 -*-
'''scheduler/jobs.py：P0-5 / M7 / M9 / M8 / M6 / M15 / M17

嵌入的代码片段一律用三单引号包裹（原文含三双引号 docstring）。
所有 old 锚点均已在当前文件（backend/app/scheduler/jobs.py, 1352 行）逐行比对 + grep 唯一性抽样
核对为恰好出现一次；**完整锚点匹配与替换后 compile() 尚未在本会话执行过**（沙箱无可用临时目录、
子进程也看不到工作区，pytest/脚本都无法运行），由 fixes/apply_fixes.py --check 在落地前把关：
任一锚点缺失或替换后语法错误都会拒绝写入该文件，不会半应用。

P0-5 的修复范围（已按复核意见收敛）：
  a. 失租立刻降级：_leader_demote() = 先置 _leader_acquired=False（fencing 立刻拦任务）
     → 再停本实例 APScheduler → 进 standby；
  b. 每个任务执行前的 fencing 校验：_leader_owned() 回查
     cache.get_lock_owner("scheduler:leader") == _leader_owner，不是自己就跳过该次执行
     并触发 standby；经 _add_job() 统一包装到所有任务入口（漏一个就漏一个脑裂口子）。
     **只在启用 leader 锁的模式（multi_user_enabled + CACHE_BACKEND=redis）下校验**，
     单用户 + 内存锁模式直接放行，绝不打死单用户调度。
  c. 修 _leader_stop 事件复用竞态：进程级停止事件与续约线程终止事件拆成两个 Event，
     _start_leader_renewal() 不再 clear() 进程级事件。
  架构限制（如实声明，未根治）：单用户 + 内存缓存下内存锁只在进程内有效，多 uvicorn
  worker / 多容器部署仍会各自跑全套 cron 重复调度；根治必须切到 multi_user + redis。

M7 说明：所报「锁」不在 backend/app/services/kline_ingest.py 内（该文件无任何锁代码），
真实调用点在 backend/app/scheduler/jobs.py 的 kline_ingest_job（TTL=3600 的无 owner 锁），
故 M7 补丁落在 jobs.py。
'''

NAME = "scheduler"

_FILE = "backend/app/scheduler/jobs.py"

ITEMS = [
    # ==================== P0-5：leader 锁失效/脑裂 ====================
    {
        "id": "P0-5",
        "file": _FILE,
        "summary": "失租立刻降级 + 执行前 fencing 校验 + 停止事件与续约事件分离（P0-5a/b/c）",
        "edits": [
            # --- c1：新增续约终止事件与状态迁移锁 ---
            ('''_leader_acquired = False
_leader_owner = f"{socket.gethostname()}:{os.getpid()}"
_leader_stop = threading.Event()
_leader_thread: threading.Thread | None = None
_leader_standby_thread: threading.Thread | None = None''',
             '''_leader_acquired = False
_leader_owner = f"{socket.gethostname()}:{os.getpid()}"
_leader_stop = threading.Event()          # 进程级停止（stop_scheduler 置位，永不清除）
_leader_renew_stop = threading.Event()    # 续约线程终止信号（失租/降级时置位；P0-5c）
_leader_thread: threading.Thread | None = None
_leader_standby_thread: threading.Thread | None = None
_leader_state_lock = threading.Lock()     # 串行化「抢锁 / 降级 / 重建调度器」状态迁移（P0-5）'''),
            # --- b1：启用条件 + fencing 校验 helper + 降级 helper ---
            ('''def _leader_renew_seconds() -> int:
    return max(5, min(int(settings.scheduler_leader_renew_seconds), _leader_ttl_seconds() // 2))''',
             '''def _leader_renew_seconds() -> int:
    return max(5, min(int(settings.scheduler_leader_renew_seconds), _leader_ttl_seconds() // 2))


def _leader_lock_enabled() -> bool:
    """是否启用 leader 锁（P0-5）：多人模式 + 共享 Redis。

    架构限制（如实声明，勿当已根治）：单用户 + 内存缓存（默认）下锁只在进程内有效，
    多 uvicorn worker / 多容器部署仍会各自启动 APScheduler、重复执行同一批 cron；本仓库
    代码无法根治，只能靠部署约束（multi_user_enabled=True + CACHE_BACKEND=redis，
    即本函数为真）才有跨进程协调手段。
    """
    return bool(settings.multi_user_enabled and settings.cache_backend == "redis")


def _leader_owned() -> bool:
    """P0-5b：执行前 fencing 校验 —— 本实例此刻是否仍持有 leader 租约。

    * 未启用 leader 锁（单用户 + 内存锁）：无跨进程锁可校验，直接放行，绝不打死单用户调度；
    * 已启用：每次执行前回查归属，租约过期 / 被抢占 / 续约线程挂掉都能立刻发现；
    * 查询异常：宁可不执行也不双跑（按失租处理），避免脑裂。
    """
    if not _leader_lock_enabled():
        return True
    if not _leader_acquired:
        return False
    try:
        return cache.get_lock_owner("scheduler:leader") == _leader_owner
    except Exception as exc:  # noqa: BLE001 查不到归属时按失租处理，避免脑裂双跑
        logger.error("调度 leader 归属查询失败，本实例按失租处理: %s", exc)
        return False


def _ensure_leader() -> bool:
    """P0-5b：所有受 leader 保护的任务执行前的统一闸门（经 _add_job 统一包装）。

    返回 False 表示本实例已不是 leader，任务必须立刻返回（继续跑就是与新 leader 双跑）。
    未启用 leader 锁时恒为 True（单用户调度行为不变）。
    """
    if _leader_owned():
        return True
    _leader_demote("执行前 fencing 校验未通过")
    return False


def _leader_demote(reason: str) -> None:
    """P0-5a：立刻放弃 leader 身份 —— 先关闸，再停调度器，最后进 standby。

    顺序不能反：必须先把 _leader_acquired 置 False（fencing 立即拦住新任务），再
    shutdown APScheduler；否则「续约失败 → 调度器真正停止」这段窗口里本实例仍会继续
    执行任务，与新 leader 双跑（脑裂）。可从续约线程 / standby 线程 / 任务线程调用：
    shutdown(wait=False) 不等待在跑任务，不会在任务线程内自锁。
    """
    global scheduler, _leader_acquired
    with _leader_state_lock:
        was_leader = _leader_acquired
        _leader_acquired = False
        _leader_renew_stop.set()
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("停止失租调度器失败: %s", exc)
            scheduler = None
    if was_leader:
        logger.error("本实例失去调度 leader 租约（%s），已停止 APScheduler 并进入 standby", reason)
    else:
        logger.info("本实例当前不是调度 leader（%s），保持 standby", reason)
    _start_leader_standby()'''),
            # --- a1：续约循环 —— 失租走统一降级 ---
            ('''def _leader_renew_loop() -> None:
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
            return''',
             '''def _leader_renew_loop() -> None:
    # P0-5c：只监听本线程的终止信号 _leader_renew_stop，不再与进程级 _leader_stop 共用
    while not _leader_renew_stop.wait(_leader_renew_seconds()):
        if not _leader_acquired or _leader_stop.is_set():
            return
        try:
            ok = cache.renew_lock_owner("scheduler:leader", _leader_owner, _leader_ttl_seconds())
        except Exception as exc:  # noqa: BLE001 续约异常一律按失租处理
            ok = False
            logger.error("调度 leader 租约续期失败: %s", exc, exc_info=True)
        if not ok:
            # P0-5a：续约失败（返回 False 或抛异常）→ 置 _leader_acquired=False、
            # 停本实例 APScheduler、进 standby，由 _leader_demote 一次性完成。
            _leader_demote("租约续期失败或已被其他实例抢占")
            return'''),
            # --- a2：standby 循环 —— 抢锁/重建串行化 + 不让出「持锁空转」 ---
            ('''def _leader_standby_loop() -> None:
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
            logger.warning("调度 leader 接管竞争失败: %s", exc)''',
             '''def _leader_standby_loop() -> None:
    global _leader_acquired
    while not _leader_stop.wait(max(2, _leader_renew_seconds())):
        if _leader_acquired:
            return
        try:
            with _leader_state_lock:
                if not cache.acquire_lock_owner(
                        "scheduler:leader", _leader_owner, _leader_ttl_seconds()):
                    continue
                _leader_acquired = True
                start_scheduler()
                if scheduler is None:
                    # 抢到锁但调度器没建起来（如多人模式缓存后端不合法）：让出锁继续竞争，
                    # 避免「持有 leader 锁却一个任务都不跑」把整个集群的调度挡在门外。
                    _leader_acquired = False
                    cache.release_lock_owner("scheduler:leader", _leader_owner)
                    continue
                _start_leader_renewal()
            logger.info("调度 leader 接管成功 owner=%s", _leader_owner)
            return
        except Exception as exc:  # noqa: BLE001 接管异常必须让出锁复位，否则「持锁空转」
            logger.warning("调度 leader 接管竞争失败: %s", exc, exc_info=True)
            _leader_demote("standby 接管异常")'''),
            # --- c2：续约线程去重 + 不再 clear 进程级事件 ---
            ('''def _start_leader_renewal() -> None:
    global _leader_thread
    _leader_stop.clear()
    _leader_thread = threading.Thread(
        target=_leader_renew_loop, name="scheduler-leader-renew", daemon=True)
    _leader_thread.start()''',
             '''def _start_leader_renewal() -> None:
    global _leader_thread
    if _leader_thread is not None and _leader_thread.is_alive():
        return                                  # 已有续约线程在跑，避免重复续约/重复线程
    _leader_renew_stop.clear()                  # P0-5c：只清续约终止信号，绝不动进程级 _leader_stop
    _leader_thread = threading.Thread(
        target=_leader_renew_loop, name="scheduler-leader-renew", daemon=True)
    _leader_thread.start()'''),
            # --- 启用条件保持「仅多人模式 + redis」（单用户不选举） ---
            ('''def start_scheduler() -> None:
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
            _start_leader_renewal()''',
             '''def start_scheduler() -> None:
    global scheduler, _leader_acquired
    if scheduler is not None:
        return
    if settings.multi_user_enabled and settings.cache_backend != "redis":
        logger.error("多人模式拒绝启动调度：必须配置共享 Redis")
        return
    # P0-5：仅多人模式 + 共享 Redis 启用 leader 锁；单用户 + 内存锁无跨进程协调手段，
    # 保持不选举（多 worker 重复调度属架构限制，见 _leader_lock_enabled 说明）。
    if _leader_lock_enabled():
        if not _leader_acquired and not cache.acquire_lock_owner(
                "scheduler:leader", _leader_owner, _leader_ttl_seconds()):
            logger.warning("多人模式当前实例不是调度 leader，跳过 APScheduler")
            _start_leader_standby()
            return
        if not _leader_acquired:
            _leader_acquired = True
            _start_leader_renewal()'''),
            # --- 停机：两个停止事件都置位 + 释放租约容错 ---
            ('''def stop_scheduler() -> None:
    global scheduler, _leader_acquired
    _leader_stop.set()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
    if _leader_acquired:
        cache.release_lock_owner("scheduler:leader", _leader_owner)
        _leader_acquired = False''',
             '''def stop_scheduler() -> None:
    global scheduler, _leader_acquired
    _leader_stop.set()
    _leader_renew_stop.set()   # P0-5c：进程停止与续约终止是两个事件，都必须置位
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
    if _leader_acquired:
        try:
            cache.release_lock_owner("scheduler:leader", _leader_owner)
        except Exception as exc:  # noqa: BLE001 停机释放失败只告警（租约到期自动失效）
            logger.warning("释放调度 leader 租约失败: %s", exc)
        _leader_acquired = False'''),
        ],
    },
    # ==================== M7：kline_ingest 任务锁（真实调用点在 jobs.py） ====================
    {
        "id": "M7",
        "file": _FILE,
        "summary": "kline_ingest 锁 TTL 3600→1800，并改用带 owner 校验的获取/释放",
        "edits": [
            ('''def kline_ingest_job() -> None:''',
             '''def _task_lock_owner(task: str) -> str:
    """任务锁 owner 标识（M7）：host:pid:task，保证释放时只删自己持有的锁。"""
    return f"{_leader_owner}:{task}"


def kline_ingest_job() -> None:'''),
            ('''    if not cache.acquire_lock("kline_ingest", ttl_seconds=3600):
        logger.info("kline_ingest 锁被占用，跳过本次")
        return''',
             '''    # M7：TTL 由 3600 收窄到 1800 —— 原值让一次崩溃留下的死锁最长占用 1 小时，
    # 把当日 16:25 增量与后续重试全挡在门外；并改用带 owner 的锁（释放时校验归属，
    # 避免 TTL 到期后误删别的实例刚抢到的锁）。
    if not cache.acquire_lock_owner("kline_ingest", _task_lock_owner("kline_ingest"),
                                    ttl_seconds=1800):
        logger.info("kline_ingest 锁被占用（或上一实例租约未过期），跳过本次")
        return'''),
            ('''    finally:
        cache.release_lock("kline_ingest")
        _reclaim_memory()''',
             '''    finally:
        try:
            # M7：带 owner 校验释放，只释放仍属于本进程的锁
            cache.release_lock_owner("kline_ingest", _task_lock_owner("kline_ingest"))
        except Exception as exc:  # noqa: BLE001 释放失败只告警（租约到期自动失效）
            logger.warning("释放 kline_ingest 锁失败: %s", exc)
        _reclaim_memory()'''),
        ],
    },
    # ==================== M9：add_job 无异常保护 + P0-5b 统一 fencing ====================
    {
        "id": "M9",
        "file": _FILE,
        "summary": "统一 _add_job()：单任务注册失败降级 + 任务入口统一 leader fencing",
        "edits": [
            ('''import logging
import os''',
             '''import functools
import logging
import os'''),
            ('''def _mark_sector_job(job_key: str, success: bool, error: str | None = None) -> None:''',
             '''
def _guarded(func):
    """P0-5b：给任务套上执行前 leader fencing —— 本实例不是 leader 时直接跳过本次任务。

    在注册处（_add_job）统一包装，而不是逐个任务入口手写：30+ 个任务入口漏一个就漏一个
    脑裂口子。未启用 leader 锁（单用户 + 内存锁）时 _ensure_leader() 恒为 True，
    行为与改造前完全一致。functools.wraps 保留真实函数名，日志/堆栈仍指向原任务函数。
    """
    @functools.wraps(func)
    def _leader_fenced(*args, **kwargs):
        if not _ensure_leader():
            return None
        return func(*args, **kwargs)
    return _leader_fenced


def _add_job(func, *args, **kwargs) -> None:
    """统一任务注册入口（M9）+ 统一任务入口 fencing（P0-5b）。

    * M9：cron 参数非法（配置项越界/拼错）原先会让整个 start_scheduler 抛异常，
      结果是所有任务都注册不上；这里逐任务 try/except，坏的那个只丢自己，其余照常注册。
    * P0-5b：注册时统一包 _guarded（执行前校验 leader 归属）。
    * 并发语义沿用 APScheduler 默认值（已核实 BackgroundScheduler 的 _job_defaults =
      misfire_grace_time=1 / coalesce=True / max_instances=1）：错过多次只补跑一次、
      同一任务不并发；此处显式兜底声明，避免将来误删。
    """
    if scheduler is None:
        logger.error("调度器未初始化，跳过任务注册: %s", getattr(func, "__name__", func))
        return
    kwargs.setdefault("coalesce", True)
    kwargs.setdefault("max_instances", 1)
    try:
        scheduler.add_job(_guarded(func), *args, **kwargs)
    except Exception as exc:  # noqa: BLE001 单个任务注册失败不影响其他任务
        logger.error("定时任务注册失败（降级跳过，其余任务不受影响）id=%s: %s",
                     kwargs.get("id"), exc, exc_info=True)


def _mark_sector_job(job_key: str, success: bool, error: str | None = None) -> None:'''),
            # ---- 34 处 scheduler.add_job(...) → _add_job(...) ----
            ('    scheduler.add_job(track_verify_job, "cron",',
             '    _add_job(track_verify_job, "cron",'),
            ('    scheduler.add_job(fill_forward_view_job, "cron",',
             '    _add_job(fill_forward_view_job, "cron",'),
            ('    scheduler.add_job(calibrate_forward_view_job, "cron",',
             '    _add_job(calibrate_forward_view_job, "cron",'),
            ('    scheduler.add_job(daily_discover_job, "cron",',
             '    _add_job(daily_discover_job, "cron",'),
            ('    scheduler.add_job(market_intel_job, "cron",',
             '    _add_job(market_intel_job, "cron",'),
            ('    scheduler.add_job(kline_ingest_job, "cron",',
             '    _add_job(kline_ingest_job, "cron",'),
            ('    scheduler.add_job(kline_backfill_job, "cron",',
             '    _add_job(kline_backfill_job, "cron",'),
            ('    scheduler.add_job(signal_scan_job, "cron",',
             '    _add_job(signal_scan_job, "cron",'),
            ('    scheduler.add_job(run_factor_ic_backtest_job, "cron", day=1, hour=2, minute=0,',
             '    _add_job(run_factor_ic_backtest_job, "cron", day=1, hour=2, minute=0,'),
            ('    scheduler.add_job(hot_money_win_rate_job, "cron",',
             '    _add_job(hot_money_win_rate_job, "cron",'),
            ('    scheduler.add_job(paper_execution_job, "cron",',
             '    _add_job(paper_execution_job, "cron",'),
            ('    scheduler.add_job(monitor_job, "cron",',
             '    _add_job(monitor_job, "cron",'),
            ('    scheduler.add_job(paper_monitor_job, "cron",',
             '    _add_job(paper_monitor_job, "cron",'),
            ('    scheduler.add_job(portfolio_sentinel_job, "cron",',
             '    _add_job(portfolio_sentinel_job, "cron",'),
            ('    scheduler.add_job(pre_market_screen_job, "cron",',
             '    _add_job(pre_market_screen_job, "cron",'),
            ('    scheduler.add_job(market_accuracy_job, "cron",',
             '    _add_job(market_accuracy_job, "cron",'),
            ('    scheduler.add_job(experience_worker_job, "cron", hour=2, minute=0,',
             '    _add_job(experience_worker_job, "cron", hour=2, minute=0,'),
            ('    scheduler.add_job(experience_worker_job, "cron", minute="7-59/30",',
             '    _add_job(experience_worker_job, "cron", minute="7-59/30",'),
            ('    scheduler.add_job(audit_pending_job, "cron", hour=3, minute=30,',
             '    _add_job(audit_pending_job, "cron", hour=3, minute=30,'),
            ('    scheduler.add_job(maintenance_job, "cron",',
             '    _add_job(maintenance_job, "cron",'),
            ('        scheduler.add_job(dragon_tiger_job, "cron",',
             '        _add_job(dragon_tiger_job, "cron",'),
            ('        scheduler.add_job(feishu_daily_report_job, "cron",',
             '        _add_job(feishu_daily_report_job, "cron",'),
            ('    scheduler.add_job(sector_refresh_job, "cron",',
             '    _add_job(sector_refresh_job, "cron",'),
            ('    scheduler.add_job(distribution_phase_job, "cron",',
             '    _add_job(distribution_phase_job, "cron",'),
            ('    scheduler.add_job(sector_daily_job, "cron",',
             '    _add_job(sector_daily_job, "cron",'),
            ('    scheduler.add_job(sector_regime_job, "cron",',
             '    _add_job(sector_regime_job, "cron",'),
            ('    scheduler.add_job(sector_forward_job, "cron",',
             '    _add_job(sector_forward_job, "cron",'),
            ('    scheduler.add_job(sector_next_hot_job, "cron",',
             '    _add_job(sector_next_hot_job, "cron",'),
            ('    scheduler.add_job(sector_forecast_verify_job, "cron",',
             '    _add_job(sector_forecast_verify_job, "cron",'),
            ('    scheduler.add_job(sector_radar_job, "cron",',
             '    _add_job(sector_radar_job, "cron",'),
            ('    scheduler.add_job(sector_radar_shadow_job, "cron",',
             '    _add_job(sector_radar_shadow_job, "cron",'),
            ('    scheduler.add_job(quote_snapshot_refresh_job, "cron",',
             '    _add_job(quote_snapshot_refresh_job, "cron",'),
            ('    scheduler.add_job(collect_overnight_factor_job, "cron",',
             '    _add_job(collect_overnight_factor_job, "cron",'),
            ('    scheduler.add_job(verify_overnight_factor_job, "cron", day_of_week="mon-fri",',
             '    _add_job(verify_overnight_factor_job, "cron", day_of_week="mon-fri",'),
        ],
    },
    # ==================== M8：misfire_grace_time=3600 集体补跑 ====================
    {
        "id": "M8",
        "file": _FILE,
        "summary": "按任务性质收紧 misfire_grace_time（密集窗口 600s / 重任务 900s / 低峰夜间 1800s）",
        "edits": [
            ('''                      id="track_verify", name="候选池T+N验证",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="track_verify", name="候选池T+N验证",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="forward_view_fill", name="前瞻T+5回填",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="forward_view_fill", name="前瞻T+5回填",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="forward_view_calibrate", name="前瞻先验校准",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="forward_view_calibrate", name="前瞻先验校准",
                      replace_existing=True, misfire_grace_time=1800)'''),
            ('''                      id="daily_discover", name="每日潜力股挖掘",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="daily_discover", name="每日潜力股挖掘",
                      replace_existing=True, misfire_grace_time=900)'''),
            ('''                      id="market_intel", name="市场研判",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="market_intel", name="市场研判",
                      replace_existing=True, misfire_grace_time=900)'''),
            ('''                      id="kline_ingest", name="本地日线增量",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)''',
             '''                      id="kline_ingest", name="本地日线增量",
                      replace_existing=True, misfire_grace_time=900, max_instances=1)'''),
            ('''                      id="kline_backfill", name="本地日线夜间回补",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)''',
             '''                      id="kline_backfill", name="本地日线夜间回补",
                      replace_existing=True, misfire_grace_time=1800, max_instances=1)'''),
            ('''                      id="signal_scan", name="买卖点信号扫描",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)''',
             '''                      id="signal_scan", name="买卖点信号扫描",
                      replace_existing=True, misfire_grace_time=900, max_instances=1)'''),
            ('''                      id="factor_ic_backtest", name="因子 IC 月度回测",
                      replace_existing=True, misfire_grace_time=3600, max_instances=1)''',
             '''                      id="factor_ic_backtest", name="因子 IC 月度回测",
                      replace_existing=True, misfire_grace_time=1800, max_instances=1)'''),
            ('''                      id="hot_money_win_rate", name="游资胜率迭代",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="hot_money_win_rate", name="游资胜率迭代",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="paper_execution", name="AI模拟复盘审核",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="paper_execution", name="AI模拟复盘审核",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="market_accuracy", name="市况次日指数回填",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="market_accuracy", name="市况次日指数回填",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      args=[True], id="experience_worker", name="经验沉淀识别",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      args=[True], id="experience_worker", name="经验沉淀识别",
                      replace_existing=True, misfire_grace_time=1800)'''),
            ('''                      id="audit_pending", name="建议辩证审核",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="audit_pending", name="建议辩证审核",
                      replace_existing=True, misfire_grace_time=1800)'''),
            ('''                      id="db_maintenance", name="存储空间维护",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="db_maintenance", name="存储空间维护",
                      replace_existing=True, misfire_grace_time=1800)'''),
            ('''                          id="dragon_tiger", name="龙虎榜T+1拉取",
                          replace_existing=True, misfire_grace_time=3600)''',
             '''                          id="dragon_tiger", name="龙虎榜T+1拉取",
                          replace_existing=True, misfire_grace_time=600)'''),
            ('''                          id="feishu_daily_report", name="飞书日报直发",
                          replace_existing=True, misfire_grace_time=3600)''',
             '''                          id="feishu_daily_report", name="飞书日报直发",
                          replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="distribution_phase", name="派发期判定",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="distribution_phase", name="派发期判定",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="sector_daily", name="板块轮动日快照",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_daily", name="板块轮动日快照",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="sector_regime", name="行情结构识别",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_regime", name="行情结构识别",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="sector_forward", name="板块前瞻预测",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_forward", name="板块前瞻预测",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="sector_next_hot", name="下一个风口预测",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_next_hot", name="下一个风口预测",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="sector_forecast_verify", name="前瞻验证回填",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_forecast_verify", name="前瞻验证回填",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="sector_radar", name="行业消息雷达",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_radar", name="行业消息雷达",
                      replace_existing=True, misfire_grace_time=1800)'''),
            ('''                      id="sector_radar_shadow", name="行业消息雷达shadow回填",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="sector_radar_shadow", name="行业消息雷达shadow回填",
                      replace_existing=True, misfire_grace_time=600)'''),
            ('''                      id="overnight_factor_collect", name="美股隔夜因子采集",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="overnight_factor_collect", name="美股隔夜因子采集",
                      replace_existing=True, misfire_grace_time=1800)'''),
            ('''                      id="overnight_factor_verify", name="美股隔夜因子校验",
                      replace_existing=True, misfire_grace_time=3600)''',
             '''                      id="overnight_factor_verify", name="美股隔夜因子校验",
                      replace_existing=True, misfire_grace_time=600)'''),
        ],
    },
    # ==================== M6：time.strftime/datetime.now 本地时区 ====================
    {
        "id": "M6",
        "file": _FILE,
        "summary": "统一上海时间口径：新增 _cn_now()/_today_cn()，替换全部本地时间用法",
        "edits": [
            ('''logger = get_logger("scheduler")''',
             '''logger = get_logger("scheduler")

# M6：调度统一口径 Asia/Shanghai —— 本模块所有「今天 / 当前时间戳」一律走这两个 helper，
# 不再用 time.strftime() / datetime.now()（宿主机本地时区）。宿主机 TZ 非 UTC+8
# （容器未挂载 /etc/localtime）时，交易日判定与幂等键（job:last_*）会整体偏移一天/数小时。
_CN_TZ = ZoneInfo("Asia/Shanghai")


def _cn_now() -> datetime:
    """当前上海时间（M6）：本模块统一时间口径。"""
    return datetime.now(_CN_TZ)


def _today_cn() -> str:
    """上海时区的今天（M6）：交易日判定 / 幂等键统一用它。"""
    return _cn_now().strftime("%Y-%m-%d")'''),
            ('''def _mark_sector_job(job_key: str, success: bool, error: str | None = None) -> None:
    cache.set(f"job:last_{job_key}", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''def _mark_sector_job(job_key: str, success: bool, error: str | None = None) -> None:
    cache.set(f"job:last_{job_key}", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            # DB 列是 naive DateTime：aware → naive（保留上海墙上时间）后再写，契约不变
            ('''            row.last_run = datetime.now()''',
             '''            # M6：DB 列是 naive DateTime，aware 时间会破坏契约 → 取上海墙上时间后摘掉 tzinfo
            row.last_run = _cn_now().replace(tzinfo=None)'''),
            ('''    次日 16:00 自动初始化，时序自洽。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    次日 16:00 自动初始化，时序自洽。"""
    today = _today_cn()'''),
            ('''def market_intel_job() -> None:
    """每日收盘后市场研判（16:20，独立于每日挖掘；当天已生成则跳过，幂等）"""
    from app.graph.router import run_market_intel

    today = time.strftime("%Y-%m-%d")''',
             '''def market_intel_job() -> None:
    """每日收盘后市场研判（16:20，独立于每日挖掘；当天已生成则跳过，幂等）"""
    from app.graph.router import run_market_intel

    today = _today_cn()'''),
            ('''    纯代码检测，无 LLM 调用；无异常不推送不落库。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    纯代码检测，无 LLM 调用；无异常不推送不落库。"""
    today = _today_cn()'''),
            ('''        cache.set("job:last_pre_market", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        cache.set("job:last_pre_market", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''    纯数据回填，无 LLM 调用；失败不阻塞其他任务。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    纯数据回填，无 LLM 调用；失败不阻塞其他任务。"""
    today = _today_cn()'''),
            ('''        cache.set("job:last_market_accuracy", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        cache.set("job:last_market_accuracy", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''    """每日挖掘：防重锁 + 交易日校验 + 全链路"""
    today = time.strftime("%Y-%m-%d")''',
             '''    """每日挖掘：防重锁 + 交易日校验 + 全链路"""
    today = _today_cn()'''),
            ('''    """收盘后审核模拟复盘；成交仅由盘中执行器使用实时行情完成。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    """收盘后审核模拟复盘；成交仅由盘中执行器使用实时行情完成。"""
    today = _today_cn()'''),
            ('''        cache.set("job:last_paper_execution", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        cache.set("job:last_paper_execution", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''    now = datetime.now()
    if not _in_trading_window(now) and not _in_close_check_window(now):
        return
    today = time.strftime("%Y-%m-%d")''',
             '''    now = _cn_now()
    if not _in_trading_window(now) and not _in_close_check_window(now):
        return
    today = _today_cn()'''),
            ('''        cache.set("job:last_monitor", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        cache.set("job:last_monitor", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''    now = datetime.now()
    if not _in_trading_window(now):
        return
    today = time.strftime("%Y-%m-%d")''',
             '''    now = _cn_now()
    if not _in_trading_window(now):
        return
    today = _today_cn()'''),
            ('''            cache.set("job:last_portfolio_sentinel", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''            cache.set("job:last_portfolio_sentinel", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''            cache.set("job:last_sector_refresh",
                      time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''            cache.set("job:last_sector_refresh",
                      _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''        trade_date = time.strftime("%Y-%m-%d")''',
             '''        trade_date = _today_cn()'''),
            ('''        cache.set("job:last_distribution_phase",
                  time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        cache.set("job:last_distribution_phase",
                  _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''            cache.set("job:last_quote_snapshot_refresh",
                      time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''            cache.set("job:last_quote_snapshot_refresh",
                      _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''        calendar = AkshareSource().fetch_trade_calendar()
        today = time.strftime("%Y-%m-%d")''',
             '''        calendar = AkshareSource().fetch_trade_calendar()
        today = _today_cn()'''),
            ('''    today = time.strftime("%Y-%m-%d")
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))''',
             '''    today = _today_cn()
    yesterday = (_cn_now() - timedelta(days=1)).strftime("%Y-%m-%d")'''),
            ('''    dt = now_dt or datetime.now()''',
             '''    dt = now_dt or _cn_now()'''),
            ('''    now = datetime.now()
    if now.weekday() >= 5:
        logger.info("周末无美股隔夜参考，跳过隔夜因子采集")''',
             '''    now = _cn_now()
    if now.weekday() >= 5:
        logger.info("周末无美股隔夜参考，跳过隔夜因子采集")'''),
            ('''        logger.info("美股隔夜因子功能未开启，跳过校验")
        return
    today = time.strftime("%Y-%m-%d")''',
             '''        logger.info("美股隔夜因子功能未开启，跳过校验")
        return
    today = _today_cn()'''),
            ('''        cache.set("job:last_maintenance", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        cache.set("job:last_maintenance", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''        error_text = "; ".join([f"#{e.get('id')}: {e.get('error')}" for e in errors])[:500]
        cache.set("job:last_audit_pending", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''        error_text = "; ".join([f"#{e.get('id')}: {e.get('error')}" for e in errors])[:500]
        cache.set("job:last_audit_pending", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''    except Exception as exc:  # noqa: BLE001 调度入口绝不外抛
        cache.set("job:last_audit_pending", time.strftime("%Y-%m-%d %H:%M:%S"), 86400)''',
             '''    except Exception as exc:  # noqa: BLE001 调度入口绝不外抛
        cache.set("job:last_audit_pending", _cn_now().strftime("%Y-%m-%d %H:%M:%S"), 86400)'''),
            ('''                trade_date=time.strftime("%Y-%m-%d"), ts=time.strftime("%H:%M:%S"),''',
             '''                trade_date=_cn_now().strftime("%Y-%m-%d"), ts=_cn_now().strftime("%H:%M:%S"),'''),
            ('''    now_tz = datetime.now(ZoneInfo("Asia/Shanghai"))''',
             '''    now_tz = _cn_now()'''),
            ('''    """盘中模拟账户巡检；日历不可用时暂停，所有账户独立失败隔离。"""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))''',
             '''    """盘中模拟账户巡检；日历不可用时暂停，所有账户独立失败隔离。"""
    now = _cn_now()'''),
            ('''    if not settings.feishu_daily_report or not _is_trading_day(time.strftime("%Y-%m-%d")):''',
             '''    if not settings.feishu_daily_report or not _is_trading_day(_today_cn()):'''),
            ('''            lines = [f"📊 {time.strftime('%Y-%m-%d')} 收盘日报"]''',
             '''            lines = [f"📊 {_today_cn()} 收盘日报"]'''),
            ('''                if str(a.get("created_at", "")).startswith(time.strftime("%Y-%m-%d"))]''',
             '''                if str(a.get("created_at", "")).startswith(_today_cn())]'''),
            ('''    """买卖点信号全市场扫描（工作日 16:50 收盘后）；非交易日直接返回，不产生任何记录。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    """买卖点信号全市场扫描（工作日 16:50 收盘后）；非交易日直接返回，不产生任何记录。"""
    today = _today_cn()'''),
            ('''    只写本地 SQLite；每夜最多 settings.kline_backfill_batch_limit 只（断点靠本地库自身状态）。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    只写本地 SQLite；每夜最多 settings.kline_backfill_batch_limit 只（断点靠本地库自身状态）。"""
    today = _today_cn()'''),
            ('''    """本地日线仓库增量（工作日 16:25）；非交易日直接返回，除权票当场重建历史段。"""
    today = time.strftime("%Y-%m-%d")''',
             '''    """本地日线仓库增量（工作日 16:25）；非交易日直接返回，除权票当场重建历史段。"""
    today = _today_cn()'''),
        ],
    },
    # ==================== M15：user_session 只增不删 ====================
    {
        "id": "M15",
        "file": _FILE,
        "summary": "维护任务增加过期/已撤销 UserSession 清理（保留 7 天审计窗口）",
        "edits": [
            ('''def maintenance_job() -> None:
    """每周空间维护（低频）：超期新闻清理 + SQLite 真空收缩 + 向量库超期索引清理。
    仅清理非核心数据（新闻原文），候选/评分/持仓/复盘等关键分析数据不清理。"""''',
             '''def _purge_expired_sessions(grace_days: int = 7) -> int:
    """M15：清理过期 / 已撤销的 UserSession 行（该表原先只增不删，随登录次数无限膨胀）。

    保留 grace_days 天用于事后审计（expires_at 或 revoked_at 落在窗口内的先留着）；
    单项失败只告警不抛出（维护任务按项降级），返回实际清理行数。
    """
    from sqlalchemy import and_, delete, or_

    from app.db.models import UserSession
    from app.db.session import SessionLocal

    # user_session 的时间列是 naive DateTime（repo 写入同样用 naive 时间）→ 比较值也取
    # naive 上海墙上时间：既避免 aware -> MySQL DATETIME 的驱动不兼容，口径也与 M6 一致。
    cutoff = _cn_now().replace(tzinfo=None) - timedelta(days=max(0, int(grace_days)))
    try:
        with SessionLocal() as db:
            removed = db.execute(
                delete(UserSession).where(
                    or_(UserSession.expires_at < cutoff,
                        and_(UserSession.revoked_at.isnot(None),
                             UserSession.revoked_at < cutoff))
                )
            ).rowcount
            db.commit()
        return int(removed or 0)
    except Exception as exc:  # noqa: BLE001 会话清理失败不影响其他维护项
        logger.warning("过期会话清理失败（不影响其他维护项）: %s", exc)
        return 0


def maintenance_job() -> None:
    """每周空间维护（低频）：超期新闻清理 + 过期会话清理 + SQLite 真空收缩 + 向量库超期索引清理。
    仅清理非核心数据（新闻原文/过期会话），候选/评分/持仓/复盘等关键分析数据不清理。"""'''),
            ('''        stats = repo.maintenance_db()
        cutoff = time.time() - settings.news_retention_days * 86400''',
             '''        stats = repo.maintenance_db()
        # M15：user_session 表原先只增不删（每次登录/换 token 一行）→ 维护时顺手清理过期会话。
        sessions_purged = _purge_expired_sessions()
        stats["sessions_purged"] = sessions_purged
        cutoff = time.time() - settings.news_retention_days * 86400'''),
            ('''        logger.info("空间维护完成: 新闻清理 %s 条，向量索引清理 %s，库体积 %s → %s MB",
                    stats["news_deleted"], removed,
                    stats["size_before_mb"], stats["size_after_mb"])''',
             '''        logger.info("空间维护完成: 新闻清理 %s 条，过期会话清理 %s 条，向量索引清理 %s，库体积 %s → %s MB",
                    stats["news_deleted"], sessions_purged, removed,
                    stats["size_before_mb"], stats["size_after_mb"])'''),
        ],
    },
    # ==================== M17：if False 死代码（同花顺 cron 停注册） ====================
    {
        "id": "M17",
        "file": _FILE,
        "summary": "删除 if False: 死代码块，改为显式下线注释（不留裸守卫）",
        "edits": [
            ('''    # 同花顺真实账户今日盈亏采集（开关开启才注册；cron 精确 9:15-16:00 窗口、
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
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED''',
             '''    # === DISABLED 2026-09-16: 同花顺下线（M17）—— 显式下线，不注册 cron，不留死代码 ===
    # 原实现用 `if False:` 包住 3 条 ths_pnl add_job（21 行永不执行的死代码）：
    # 静态检查看不见、后人容易误判成「临时关闭」而随手打开，而 ths_pnl_job 函数体首行
    # 已 `return`（整链路下线），打开也只会白跑。恢复通道：删 ths_pnl_job 首行 return +
    # 按 settings.ths_pnl_poll_seconds 重建 cron（此处不留裸守卫）。
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED'''),
        ],
    },
]
