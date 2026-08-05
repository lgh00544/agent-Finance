"""数据源断路器（连续失败 → 临时降级 → 静默探测恢复）

【刚性代码逻辑】只做状态机与日志节流，不做任何市场判断。

状态机（按 kind 独立：tick=实时行情 / snapshot=全市场快照）：
  closed        正常：每次尝试主源，失败累计连续次数；
  open          临时降级：跳过主源直接走备用，持续 cooldown 秒；
                冷却到期后下一次调用自动成为静默探测（尝试主源一次）；
                探测成功 → 切回 closed（记录恢复，INFO）；失败 → 续期 open（DEBUG）。
日志去重：只有状态切换打 WARNING/INFO，open 期间的连续失败只打 DEBUG，
避免同类型失败刷屏打满日志文件。
状态必须放模块级单例：get_datasource() 每次新建数据源实例，实例内状态无法跨调用保留。
"""
import logging
import threading
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_BREAKERS: dict[str, "CircuitBreaker"] = {}
_lock = threading.Lock()


class CircuitBreaker:
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._consecutive_failures = 0
        self._open_at: float | None = None  # 进入降级的时刻（monotonic）
        self._lock = threading.Lock()

    # ---------------- 状态查询 ----------------
    @property
    def is_degraded(self) -> bool:
        with self._lock:
            if self._open_at is None:
                return False
            # 冷却到期不算降级：下一次调用即探测主源
            return time.monotonic() - self._open_at < settings.datasource_breaker_cooldown

    def should_try(self) -> bool:
        """是否允许打主源：closed 一直允许；open 且冷却到期后允许（静默探测）"""
        return not self.is_degraded

    def state(self) -> str:
        return "degraded" if self.is_degraded else "primary"

    # ---------------- 事件记录 ----------------
    def record_success(self) -> None:
        """主源调用成功：清空连续失败；降级中成功 = 探测恢复，切回主源"""
        from app.services import datasource_stats

        with self._lock:
            was_degraded = self._open_at is not None
            self._consecutive_failures = 0
            self._open_at = None
        if was_degraded:
            datasource_stats.record_recovery(self._kind)
            logger.info("数据源 %s 主源恢复，切回正常模式", self._kind)

    def record_failure(self) -> None:
        """主源调用失败：连续计数达阈值进入降级；降级中（探测）失败则续期"""
        from app.services import datasource_stats

        with self._lock:
            self._consecutive_failures += 1
            if self._open_at is None:
                if self._consecutive_failures >= settings.datasource_breaker_threshold:
                    self._open_at = time.monotonic()
                    logger.warning(
                        "数据源 %s 连续 %d 次失败，进入临时降级 %d 秒（期间直接走备用源，"
                        "冷却到期静默探测主源自动切回）",
                        self._kind, self._consecutive_failures,
                        settings.datasource_breaker_cooldown)
                elif self._consecutive_failures == 1:
                    logger.debug("数据源 %s 主源第 1 次失败（连续 %d/%d 触发降级）",
                                 self._kind, self._consecutive_failures,
                                 settings.datasource_breaker_threshold)
                else:
                    logger.debug("数据源 %s 主源失败（连续 %d/%d 触发降级）",
                                 self._kind, self._consecutive_failures,
                                 settings.datasource_breaker_threshold)
            else:
                # 探测失败：续期降级（不打 WARNING，避免冷却期内刷屏）
                self._open_at = time.monotonic()
                logger.debug("数据源 %s 探测主源失败，续期降级 %d 秒",
                             self._kind, settings.datasource_breaker_cooldown)


def get_breaker(kind: str) -> CircuitBreaker:
    """按 kind 取断路器单例（tick/snapshot 互不影响）"""
    breaker = _BREAKERS.get(kind)
    if breaker is None:
        with _lock:
            breaker = _BREAKERS.get(kind)
            if breaker is None:
                breaker = CircuitBreaker(kind)
                _BREAKERS[kind] = breaker
    return breaker


def reset() -> None:
    """清空全部断路器状态（测试隔离用）"""
    with _lock:
        _BREAKERS.clear()
