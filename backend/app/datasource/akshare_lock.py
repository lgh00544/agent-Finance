"""进程级串行化 akshare 调用，规避 py_mini_racer/V8 并发初始化判死进程。

akshare 部分接口内部使用 py_mini_racer；其内置 V8 在多线程并发初始化时会以
[FATAL:partition_address_space.cc(243)] Check failed: !IsConfigurablePoolInitialized()
直接判死整个 Python 进程（无 Python traceback，APScheduler 一并消失，服务静默下线）。
2026-09-28 实测：13:00 / 13:05 整点 */5 cron 簇并发触发 index_spot / industry_spot 降级路径，
进程被连续判死两次。

因此所有 akshare 调用统一经本模块代理，在全局重入锁内串行执行。
"""
from __future__ import annotations

import threading

AKSHARE_LOCK = threading.RLock()


class LockedAkshare:
    """akshare 代理：函数调用在全局锁内执行，非可调用属性原样透传。"""

    def __init__(self, module) -> None:
        self._module = module

    def __getattr__(self, name: str):
        target = getattr(self._module, name)
        if not callable(target):
            return target

        def _locked(*args, **kwargs):
            with AKSHARE_LOCK:
                return target(*args, **kwargs)

        _locked.__name__ = getattr(target, "__name__", str(name))
        _locked.__doc__ = getattr(target, "__doc__", None)
        _locked.__wrapped__ = target  # 供签名预判（_accepts_timeout）剥离包装层
        return _locked


def load_akshare():
    """返回加锁代理；akshare 缺失或导入失败时返回 None，调用方沿用原有降级逻辑。"""
    try:
        import akshare as ak
    except Exception:  # noqa: BLE001 数据源层缺失即整体降级
        return None
    return LockedAkshare(ak)
