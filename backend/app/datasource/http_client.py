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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import settings

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({
    "User-Agent": settings.datasource_user_agent,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

# M11：共享会话补连接池 + 传输层重试。Connection aborted / RemoteDisconnected 多为瞬态
# （正是本模块注释里「连接建立失败」的常见诱因），原实现一次失败即上抛，实时接口频繁报错
# 并被断路器误判降级。只对幂等的 GET/HEAD 重试（connect=2 / read=1 / 429·5xx=2，指数退避），
# raise_on_status=False：重试耗尽后仍返回响应，状态码校验统一交给 get() 的 raise_for_status。
_SESSION_RETRY = Retry(
    total=2,
    connect=2,
    read=1,
    status=2,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD"}),
    raise_on_status=False,
)
_session.mount("http://", HTTPAdapter(max_retries=_SESSION_RETRY,
                                      pool_connections=20, pool_maxsize=20))
_session.mount("https://", HTTPAdapter(max_retries=_SESSION_RETRY,
                                       pool_connections=20, pool_maxsize=20))

# 各主机默认 Referer（与请求目标一致，模拟正常网页访问）
_REFERERS = {
    "eastmoney": "https://finance.eastmoney.com/",
    "sina": "https://finance.sina.com.cn",
    "xueqiu": "https://xueqiu.com/",
}

_limiter_lock = threading.Lock()
_limiters: dict[str, "RateLimiter"] = {}


class RateLimiter:
    """按 kind 的最小请求间隔限流：锁内预约起跑时刻，锁外补齐间隔，线程安全。

    P0-4：原实现「持锁 time.sleep(gap)」把并发线程串行化 —— 第 k 个线程必须等前一个线程
    睡完才拿到锁，N 个并发请求被压成「每 min_interval 秒放行 1 个」且每个都要排队，
    8 线程并发时吞吐反而低于单线程（并发能力被限流锁吃光）。
    改为预约（reservation）模式：锁内只做纳秒级算术预约本次的起跑时刻，sleep 移到锁外，
    各线程并行等待、不再排队等锁。

    ⚠️ 本改动**只消除持锁串行化，不提高平均请求速率**：第 N 个调用者的起跑时刻天然为
    last + N × min_interval，平均速率仍严格等于 1/min_interval、最小间隔语义不变，
    也不会产生任何「0 间隔突发」（突发会瞬时打出多个请求，反而更容易触发源站反爬封禁）。
    """

    def __init__(self, min_interval: float) -> None:
        self._min_interval = max(float(min_interval or 0.0), 0.0)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:                      # 只做算术，不 sleep（锁占用为纳秒级）
            now = time.monotonic()
            start = max(now, self._last + self._min_interval)
            self._last = start
        delay = start - time.monotonic()      # 锁外等待：多线程各自并行等待，互不阻塞
        if delay > 0:
            time.sleep(delay)


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
        headers: dict | None = None,
        raise_for_status: bool = True, **kwargs) -> requests.Response:
    """共享会话 GET：默认浏览器请求头 + 连接/读取超时拆分；referer 填主机域名简写。

    M10：默认校验状态码 —— 原实现不调用 raise_for_status，4xx/5xx 的限流页/错误页响应体
    会被上层当成正常数据继续解析（静默脏数据，且错误被当成「数据为空」处理）。
    需要按 status_code 自行分支的调用方（如 us_quote 的中文错误文案/降级日志）显式传
    raise_for_status=False 作为逃生口。
    """
    hdrs = {}
    if referer:
        hdrs["Referer"] = _REFERERS.get(referer, referer)
    if headers:
        hdrs.update(headers)
    if timeout is None:
        timeout = (settings.datasource_connect_timeout, settings.datasource_read_timeout)
    resp = _session.get(url, params=params, headers=hdrs or None, timeout=timeout, **kwargs)
    if raise_for_status:      # M10：非 2xx 立即失败，绝不把错误页当数据往下传
        resp.raise_for_status()
    return resp


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
