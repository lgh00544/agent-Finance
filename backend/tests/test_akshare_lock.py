"""akshare 调用必须经全局锁串行，避免 py_mini_racer/V8 并发初始化判死进程。"""
import threading
import time

from app.datasource.akshare_lock import AKSHARE_LOCK, LockedAkshare, load_akshare


class _FakeAkshare:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.constant = "v1"

    def fetch(self, value):
        # 故意不自带锁：并发是否被串行化只能由 LockedAkshare 代理决定
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        self.active -= 1
        return f"ok:{value}"


def test_locked_akshare_serialises_concurrent_calls_and_passes_through_constants():
    module = _FakeAkshare()
    proxy = LockedAkshare(module)
    results = []
    threads = [threading.Thread(target=lambda i=i: results.append(proxy.fetch(i))) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == ["ok:0", "ok:1", "ok:2", "ok:3"]
    assert module.max_active == 1        # 并发调用被全局锁串行化
    assert proxy.constant == "v1"        # 非可调用属性原样透传


def test_load_akshare_wraps_real_module_with_lock():
    proxy = load_akshare()
    assert isinstance(proxy, LockedAkshare)
    assert callable(proxy.stock_zh_a_spot_em)
