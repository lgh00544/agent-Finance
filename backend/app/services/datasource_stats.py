"""行情数据源状态统计（当日累计，供首页「数据源状态」看板）

【刚性代码逻辑】只做计数聚合，不产生任何研判内容。

指标：主源调用次数 / 失败次数 / 降级次数（断路器降级期间直接走备用）/
恢复次数 / 主源成功率 / 按 kind 的当前源状态（主源正常 / 临时降级·备用源）。
埋点位置：数据源调用层（_call_with_retry / 批量行情）与断路器状态切换。
存储：缓存抽象层（dev=内存 / prod=Redis），按自然日分区，进程内锁保护，
与 llm_stats 同模式（TTL 2 天，跨午夜保留当日与昨日）。
"""
import json
import threading
import time

from app.cache import cache

_lock = threading.Lock()
_KEY_TTL = 172800  # 2 天，跨午夜保留当日与昨日

_KINDS = ("tick", "snapshot")


def _empty() -> dict:
    # 工厂函数而非模块级常量：避免浅拷贝共享 "by_kind" 子字典
    return {"requests": 0, "failures": 0, "degraded_use": 0, "recoveries": 0,
            "by_kind": {kind: {"requests": 0, "failures": 0, "degraded_use": 0,
                               "recoveries": 0} for kind in _KINDS}}


def _key() -> str:
    return f"datasource_stats:{time.strftime('%Y-%m-%d')}"


def _load() -> dict:
    raw = cache.get(_key())
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _record(kind: str, field: str) -> None:
    with _lock:
        stats = {**_empty(), **_load()}
        stats[field] += 1
        kind_stats = stats["by_kind"].setdefault(kind, {f: 0 for f in
                                                        ("requests", "failures",
                                                         "degraded_use", "recoveries")})
        kind_stats[field] += 1
        cache.set(_key(), json.dumps(stats, ensure_ascii=False), _KEY_TTL)


def record_request(kind: str) -> None:
    """主源调用一次（含重试的每次尝试）"""
    _record(kind, "requests")


def record_failure(kind: str) -> None:
    """主源调用失败一次"""
    _record(kind, "failures")


def record_degraded(kind: str) -> None:
    """断路器降级期间直接走备用（未打主源）"""
    _record(kind, "degraded_use")


def record_recovery(kind: str) -> None:
    """断路器降级 → 主源探测成功切回"""
    _record(kind, "recoveries")


def snapshot() -> dict:
    """当日快照（供前端展示）：主源调用/失败/降级/恢复次数、成功率、
    按 kind 的当前源状态与截止时间"""
    stats = {**_empty(), **_load()}
    requests = stats["requests"]
    failures = stats["failures"]
    success_rate = round((requests - failures) / requests * 100, 1) if requests else None
    kinds = []
    for kind in _KINDS:
        ks = stats["by_kind"].get(kind) or {}
        current = "degraded" if _breaker_degraded(kind) else "primary"
        kinds.append({"kind": kind, "current_source": current,
                      "requests": ks.get("requests", 0), "failures": ks.get("failures", 0),
                      "degraded_use": ks.get("degraded_use", 0),
                      "recoveries": ks.get("recoveries", 0)})
    return {
        "date": time.strftime("%Y-%m-%d"),
        "requests": requests,
        "failures": failures,
        "degraded_use": stats["degraded_use"],
        "recoveries": stats["recoveries"],
        "success_rate_pct": success_rate,
        "kinds": kinds,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _breaker_degraded(kind: str) -> bool:
    """当前断路器状态（读不到视为主源正常）"""
    try:
        from app.datasource.breaker import get_breaker

        return get_breaker(kind).is_degraded
    except Exception:  # noqa: BLE001 统计展示容错，不影响主链路
        return False
