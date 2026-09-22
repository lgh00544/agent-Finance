"""A3 复盘守卫（2026-09-22）：诊断端点不得把 tracemalloc 永久留在开启态。

背景：trace=1 原实现 tracemalloc.start(15) 后从不停，实测把活进程 RSS 抬到 1.4GB（traced 207MB）。
"""
from __future__ import annotations

import tracemalloc

from app.api import routes
from app.core import mem_diag
from app.core.config import settings


def _reset() -> None:
    mem_diag.stop()
    assert not tracemalloc.is_tracing()


def test_trace_disabled_by_default(monkeypatch):
    """默认 False：trace=1 不得开启 tracemalloc，且明确回报已禁用。"""
    monkeypatch.setattr(settings, "mem_diag_trace_enable", False)
    _reset()
    info = routes.diagnostics_memory(trace=1)
    assert "trace_disabled" in info
    assert info["tracing"] is False
    assert not tracemalloc.is_tracing()
    assert "traced_current_kb" not in info


def test_trace_enabled_reports_sites_then_ttl_reaps(monkeypatch):
    """启用后可采样；TTL 到期后即使不带 trace 参数的请求也会自动 stop。"""
    monkeypatch.setattr(settings, "mem_diag_trace_enable", True)
    monkeypatch.setattr(settings, "mem_diag_trace_ttl_s", 600)
    _reset()
    info = routes.diagnostics_memory(trace=1)
    assert info["tracing"] is True
    assert isinstance(info["trace_top"], list)
    assert "traced_current_kb" in info

    monkeypatch.setattr(settings, "mem_diag_trace_ttl_s", 0)
    info2 = routes.diagnostics_memory()
    assert info2["tracing"] is False
    assert not tracemalloc.is_tracing()


def test_explicit_stop(monkeypatch):
    """trace=-1 立即关闭，不留常开态。"""
    monkeypatch.setattr(settings, "mem_diag_trace_enable", True)
    monkeypatch.setattr(settings, "mem_diag_trace_ttl_s", 600)
    _reset()
    routes.diagnostics_memory(trace=1)
    assert tracemalloc.is_tracing()
    info = routes.diagnostics_memory(trace=-1)
    assert info["trace_stopped"] is True
    assert info["tracing"] is False
    assert not tracemalloc.is_tracing()


def test_guard_reaps_externally_started_tracing(monkeypatch):
    """外部（非本模块）开启的 tracemalloc 同样被 TTL 兜住，防止绕过收口。"""
    monkeypatch.setattr(settings, "mem_diag_trace_ttl_s", 0)
    _reset()
    tracemalloc.start(5)
    assert tracemalloc.is_tracing()
    mem_diag.trace_guard()
    assert not tracemalloc.is_tracing()
