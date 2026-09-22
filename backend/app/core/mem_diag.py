"""诊断用 tracemalloc 的收口开关（A3 复盘 2026-09-22）。

根因：GET /api/diagnostics/memory?trace=1 会 tracemalloc.start(15) 且从不停——
tracemalloc 为每条存活分配保留 15 帧调用栈，实测把进程 RSS 抬高约 300MB/h 且不归还
（活进程实测 traced 207MB / RSS 1414MB），是 Go/No-Go #5「内存趋势」的自伤源。

本模块统一收口，保证任何调用方都无法把 tracemalloc 永久留在开启态：
1) 默认禁止开启（MEM_DIAG_TRACE_ENABLE=false）；
2) 硬 TTL 兜底：超时后任意一次请求 / 任意一次 _reclaim_memory() 都会将其 stop。
"""
from __future__ import annotations

import time

from app.core.config import settings

FRAMES = 15                     # 记录调用栈深度（原实现固定 15）
_started_at: float | None = None


def _ttl() -> int:
    try:
        return int(settings.mem_diag_trace_ttl_s)
    except Exception:  # noqa: BLE001 配置异常不得让诊断端点 500
        return 600


def enabled() -> bool:
    """是否允许显式开启（默认 False）。"""
    return bool(getattr(settings, "mem_diag_trace_enable", False))


def state() -> dict:
    """只读状态：tracing / 已开时长 on_s / ttl_s。"""
    import tracemalloc

    on = bool(tracemalloc.is_tracing())
    return {
        "tracing": on,
        "on_s": int(time.monotonic() - _started_at) if (on and _started_at is not None) else None,
        "ttl_s": _ttl(),
    }


def stop() -> None:
    """立即关闭跟踪（幂等）。"""
    global _started_at

    import tracemalloc

    if tracemalloc.is_tracing():
        tracemalloc.stop()
    _started_at = None


def trace_guard() -> bool:
    """硬 TTL 兜底：任何来源开启的 tracemalloc 超时即 stop；返回是否仍在跟踪。"""
    global _started_at

    import tracemalloc

    if not tracemalloc.is_tracing():
        _started_at = None
        return False
    if _started_at is None:      # 外部（非本模块）开启：从此刻起算，宁早关不常开
        _started_at = time.monotonic()
    ttl = _ttl()
    if ttl >= 0 and (time.monotonic() - _started_at) > ttl:
        stop()
        return False
    return True


def start() -> bool:
    """开启跟踪；未显式启用或已超 TTL 预算时返回 False（调用方据此报 trace_disabled）。"""
    global _started_at

    import tracemalloc

    if not enabled():
        return False
    if not tracemalloc.is_tracing():
        tracemalloc.start(FRAMES)
        _started_at = time.monotonic()
    return True
