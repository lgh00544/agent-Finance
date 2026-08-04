"""
缓存抽象层：CacheBackend 协议，默认 MemoryCache（进程内，重启清空）；
CACHE_BACKEND=redis 时无缝切换 RedisCache。业务代码一律通过 cache 单例访问。
职责：
  1. 数据源结果缓存（akshare 拉取节流）
  2. LLM 分析结果缓存（同一标的当日同 Agent 结果复用，节约 API 开销）
  3. 告警去重、任务锁防重
"""
import json
import threading
import time
from abc import ABC, abstractmethod

import redis as redis_lib

from app.core.config import settings


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None:
        """删除指定前缀的全部 key（高频读结果缓存按表命名空间批量失效用）"""
    def get_llm_json(self, agent: str, key: str, ttl_seconds: int) -> dict | None:
        raw = self.get(f"llm:{agent}:{key}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_llm_json(self, agent: str, key: str, value: dict, ttl_seconds: int) -> None:
        self.set(f"llm:{agent}:{key}", json.dumps(value, ensure_ascii=False, default=str), ttl_seconds)

    # ---------- 告警去重 ----------
    def alert_deduplicated(self, dedup_key: str, ttl_seconds: int) -> bool:
        """返回 True 表示该 key 已存在（重复），调用方应跳过推送"""
        key = f"alert:{dedup_key}"
        if self.get(key) is not None:
            return True
        self.set(key, "1", ttl_seconds)
        return False

    # ---------- 分布式锁（防调度重叠）----------
    @abstractmethod
    def acquire_lock(self, lock_name: str, ttl_seconds: int = 3600) -> bool: ...

    @abstractmethod
    def release_lock(self, lock_name: str) -> None: ...


class MemoryCache(CacheBackend):
    """dev 模式：进程内缓存，线程安全"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def _expire(self, now: float) -> None:
        stale = [k for k, (_, exp) in self._store.items() if exp < now]
        for k in stale:
            self._store.pop(k, None)

    def get(self, key: str) -> str | None:
        with self._lock:
            self._expire(time.time())
            item = self._store.get(key)
            return item[0] if item else None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + ttl_seconds)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for k in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(k, None)

    def acquire_lock(self, lock_name: str, ttl_seconds: int = 3600) -> bool:
        # 内存锁：同进程内防止调度重叠
        key = f"lock:{lock_name}"
        with self._lock:
            item = self._store.get(key)
            now = time.time()
            if item and item[1] > now:
                return False
            self._store[key] = ("1", now + ttl_seconds)
            return True

    def release_lock(self, lock_name: str) -> None:
        self.delete(f"lock:{lock_name}")


class RedisCache(CacheBackend):
    """prod 模式：Redis 实现"""

    def __init__(self) -> None:
        self._client = redis_lib.from_url(settings.redis_url, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.set(key, value, ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def delete_prefix(self, prefix: str) -> None:
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=f"{prefix}*", count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def acquire_lock(self, lock_name: str, ttl_seconds: int = 3600) -> bool:
        return bool(self._client.set(f"lock:{lock_name}", "1", nx=True, ex=ttl_seconds))

    def release_lock(self, lock_name: str) -> None:
        self._client.delete(f"lock:{lock_name}")


def get_cache() -> CacheBackend:
    if settings.cache_backend == "redis":
        return RedisCache()
    return MemoryCache()


cache: CacheBackend = get_cache()
