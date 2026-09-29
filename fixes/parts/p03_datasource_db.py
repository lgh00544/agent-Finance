# -*- coding: utf-8 -*-
'''数据源 / 连接池修复：P0-4 / M10 / M10b / M11 / M11b / M11c / M12 / M12b

涉及文件：
  - backend/app/datasource/http_client.py     P0-4 预约式限流 / M10 状态码校验 / M11 会话重试
  - backend/app/datasource/us_quote.py        M10b 显式关闭状态校验（本模块按 status_code 分支）
  - backend/app/datasource/akshare_source.py  M11b 裸 requests 调用超时拆分
  - backend/app/services/kline_ingest.py      M11c 自建会话补连接池 + 重试
  - backend/app/db/session.py                 M12 连接池扩容
  - backend/app/core/config.py                M12b 新增连接池配置字段

嵌入的代码片段一律用三单引号包裹（原文含三双引号 docstring）。
'''

NAME = "datasource_db"

_HC = "backend/app/datasource/http_client.py"
_US = "backend/app/datasource/us_quote.py"
_AK = "backend/app/datasource/akshare_source.py"
_KI = "backend/app/services/kline_ingest.py"
_DB = "backend/app/db/session.py"
_CFG = "backend/app/core/config.py"

ITEMS = [
    {
        "id": "P0-4",
        "file": _HC,
        "summary": "RateLimiter 改「锁内预约起跑时刻 + 锁外 sleep」：消除持锁串行化，平均速率/最小间隔不变",
        "edits": [
            ('''class RateLimiter:
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
            self._last = time.monotonic()''',
             '''class RateLimiter:
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
            time.sleep(delay)'''),
        ],
    },
    {
        "id": "M10",
        "file": _HC,
        "summary": "get() 默认 raise_for_status：4xx/5xx 不再静默当数据解析，保留 raise_for_status=False 逃生口",
        "edits": [
            ('''def get(url: str, *, referer: str | None = None, params: dict | None = None,
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
    return _session.get(url, params=params, headers=hdrs or None, timeout=timeout, **kwargs)''',
             '''def get(url: str, *, referer: str | None = None, params: dict | None = None,
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
    return resp'''),
        ],
    },
    {
        "id": "M11",
        "file": _HC,
        "summary": "共享 Session 挂 HTTPAdapter（连接池 20 + 仅 GET/HEAD 传输层重试）",
        "edits": [
            ('''import requests

from app.core.config import settings''',
             '''import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import settings'''),
            ('''_session = requests.Session()
_session.headers.update({
    "User-Agent": settings.datasource_user_agent,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
})''',
             '''_session = requests.Session()
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
                                       pool_connections=20, pool_maxsize=20))'''),
        ],
    },
    {
        "id": "M10b",
        "file": _US,
        "summary": "us_quote 两处 http_get 显式 raise_for_status=False，保留既有 status_code 分支",
        "edits": [
            ('''    resp = http_get(url, referer="sina")
    if resp.status_code != 200:
        raise RuntimeError(f"新浪美股行情请求失败 status={resp.status_code}")''',
             '''    # M10b：本函数按 status_code 自己分支并给出明确中文错误文案，
    # 故显式关闭共享会话的状态码校验（M10 逃生口），行为与修复前完全一致。
    resp = http_get(url, referer="sina", raise_for_status=False)
    if resp.status_code != 200:
        raise RuntimeError(f"新浪美股行情请求失败 status={resp.status_code}")'''),
            ('''        resp = http_get("http://hq.sinajs.cn/list=sh000001", referer="sina")''',
             '''        # M10b：同上，这里需要按 status_code 记 WARNING 并返回 None（不抛异常中断调度）
        resp = http_get("http://hq.sinajs.cn/list=sh000001", referer="sina",
                        raise_for_status=False)'''),
        ],
    },
    {
        "id": "M11b",
        "file": _AK,
        "summary": "个股新闻裸 requests.get 超时按连接/读取拆分（保持 requests.get，测试全量 mock 它）",
        "edits": [
            ('''    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()''',
             '''    # M11b：单值 15s 超时无法区分「连接挂起」与「响应挂起」，按数据源统一配置拆分
    # （连接超时 5s + 读取超时 min(15s, datasource_read_timeout)）。
    # 此处保留 requests.get 直连：本模块测试以 monkeypatch.setattr("requests.get", ...) 打桩，
    # 改走共享会话会绕过桩函数并触发真实网络请求。
    resp = requests.get(url, params=params, headers=headers,
                        timeout=(settings.datasource_connect_timeout,
                                min(settings.datasource_read_timeout, 15)))
    resp.raise_for_status()'''),
        ],
    },
    {
        "id": "M11c",
        "file": _KI,
        "summary": "kline 快照自建 Session 挂连接池 + 传输层重试（调用方传入的会话不动）",
        "edits": [
            ('''import requests

from app.services import kline_store as store''',
             '''import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.services import kline_store as store'''),
            ('''SNAPSHOT_URL = "https://hq.sinajs.cn/list="
HEADERS = {"Referer": "https://finance.sina.com.cn"}
DEFAULT_BATCH = 100''',
             '''SNAPSHOT_URL = "https://hq.sinajs.cn/list="
HEADERS = {"Referer": "https://finance.sina.com.cn"}
DEFAULT_BATCH = 100

# M11c：快照请求的传输层加固（夜间回补 8 并发下 Connection aborted/RemoteDisconnected 属瞬态，
# 原实现一次失败就丢整批）。只重试幂等 GET，raise_on_status=False 让状态码仍由调用方判断。
_SNAPSHOT_ADAPTER = HTTPAdapter(
    max_retries=Retry(total=2, connect=2, read=1, backoff_factor=0.5,
                      allowed_methods=frozenset({"GET", "HEAD"}), raise_on_status=False),
    pool_connections=10, pool_maxsize=20)'''),
            ('''    out: dict[str, list[str]] = {}
    errors: list = []
    sess = session or requests.Session()''',
             '''    out: dict[str, list[str]] = {}
    errors: list = []
    sess = session or requests.Session()
    if session is None:      # M11c：仅自建兜底会话挂适配器，调用方传入的会话不改其配置
        sess.mount("http://", _SNAPSHOT_ADAPTER)
        sess.mount("https://", _SNAPSHOT_ADAPTER)'''),
        ],
    },
    {
        "id": "M12",
        "file": _DB,
        "summary": "连接池按 8 线程扫描 + APScheduler 并发扩容（SQLite 分支与 PRAGMA 不变）",
        "edits": [
            ('''engine = create_engine(
    _ENGINE_URL,
    pool_pre_ping=True,
    echo=False,
)''',
             '''# M12：连接池容量与「信号扫描 8 线程 + APScheduler 多任务并发访问 DB」的并发量匹配。
# 原实现用 QueuePool 默认值（pool_size=5 / max_overflow=10 = 上限 15 条），高并发取连接时
# 溢出连接被丢弃并报 QueuePool limit reached，连接反复重建。SQLAlchemy 2.0 下文件型 SQLite
# 同样是 QueuePool，故池容量对两种后端统一放大（SQLite 的 WAL/PRAGMA 分支完全不变）；
# pool_recycle 只对 MySQL/TiDB 有意义（服务端 wait_timeout 主动断连），SQLite 本地文件不设。
_pool_kwargs: dict = {
    "pool_size": settings.db_pool_size,
    "max_overflow": settings.db_max_overflow,
    "pool_timeout": settings.db_pool_timeout,
}
if not _ENGINE_URL.startswith("sqlite"):
    _pool_kwargs["pool_recycle"] = settings.db_pool_recycle

engine = create_engine(
    _ENGINE_URL,
    pool_pre_ping=True,
    echo=False,
    **_pool_kwargs,
)'''),
        ],
    },
    {
        "id": "M12b",
        "file": _CFG,
        "summary": "新增 db_pool_size / db_max_overflow / db_pool_timeout / db_pool_recycle 配置字段",
        "edits": [
            ('''    db_fallback_to_sqlite: bool = True
    db_probe_timeout_s: int = 5           # 单次云端连接探测超时（秒）
    db_probe_attempts: int = 2            # 探测尝试次数（TiDB Serverless 冷启可能较慢）''',
             '''    db_fallback_to_sqlite: bool = True
    db_probe_timeout_s: int = 5           # 单次云端连接探测超时（秒）
    db_probe_attempts: int = 2            # 探测尝试次数（TiDB Serverless 冷启可能较慢）
    # M12：连接池容量（原用 QueuePool 默认 pool_size=5/max_overflow=10，撑不住
    # 信号扫描 8 线程 + APScheduler 多任务并发；溢出连接被丢弃 → QueuePool limit reached）
    db_pool_size: int = 20                # 常驻连接数
    db_max_overflow: int = 20             # 突发可临时超出的连接数（池上限 = 40）
    db_pool_timeout: int = 30             # 取连接最长等待秒数（等待而非立即报错）
    db_pool_recycle: int = 1800           # 连接回收秒数（仅 MySQL/TiDB，防 wait_timeout 断连）'''),
        ],
    },
]
