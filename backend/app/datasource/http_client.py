"""数据源 HTTP 请求层（连接池/浏览器请求头/超时/限流）

【刚性代码逻辑】只做请求加固，不做任何市场判断。
  - 共享 requests.Session：TCP 连接池 + keep-alive，避免每次请求新建连接（
    连接建立失败正是实时接口频繁报 Connection aborted 的常见诱因之一）
  - 浏览器 User-Agent + 按主机 Referer，降低被反爬拦截概率
  - 连接/读取超时拆分：连接慢与响应慢分别处置，避免单侧长时间挂起
  - RateLimiter：同类实时请求最小间隔，防高频请求触发对方限流
"""
import logging
import threading
import time

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({
    "User-Agent": settings.datasource_user_agent,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

# 各主机默认 Referer（与请求目标一致，模拟正常网页访问）
_REFERERS = {
    "eastmoney": "https://finance.eastmoney.com/",
    "sina": "https://finance.sina.com.cn",
    "xueqiu": "https://xueqiu.com/",
}

_limiter_lock = threading.Lock()
_limiters: dict[str, "RateLimiter"] = {}


class RateLimiter:
    """按 kind 的最小请求间隔限流：间隔不足时 sleep 补齐，线程安全"""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            gap = self._last + self._min_interval - now
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()


def get_limiter(kind: str) -> RateLimiter:
    """按 kind 取限流器单例（tick/snapshot/kline 等互不影响）"""
    limiter = _limiters.get(kind)
    if limiter is None:
        with _limiter_lock:
            limiter = _limiters.get(kind)
            if limiter is None:
                limiter = RateLimiter(settings.datasource_min_request_interval)
                _limiters[kind] = limiter
    return limiter


def get(url: str, *, referer: str | None = None, params: dict | None = None,
        timeout: tuple[float, float] | float | None = None,
        headers: dict | None = None, **kwargs) -> requests.Response:
    """共享会话 GET：默认浏览器请求头 + 连接/读取超时拆分；referer 填主机域名简写"""
    hdrs = {}
    if referer:
        hdrs["Referer"] = _REFERERS.get(referer, referer)
    if headers:
        hdrs.update(headers)
    if timeout is None:
        timeout = (settings.datasource_connect_timeout, settings.datasource_read_timeout)
    return _session.get(url, params=params, headers=hdrs or None, timeout=timeout, **kwargs)


# ---------------- akshare 内部 requests 请求头加固 ----------------

_patched = False


def patch_requests_headers() -> None:
    """一次性 patch requests.utils.default_headers 补浏览器 UA（仅 UA，不设全局 Referer，
    避免各主机 Referer 语义冲突）。akshare 内部函数直接用 requests.get 发请求且不传
    headers，无法逐接口注入，只能从 requests 层全局兜底。守卫防重复 patch。"""
    global _patched
    if _patched:
        return
    import requests.utils

    _orig = requests.utils.default_headers

    def _headers() -> dict:
        h = _orig()
        h["User-Agent"] = settings.datasource_user_agent
        return h

    requests.utils.default_headers = _headers
    _patched = True
