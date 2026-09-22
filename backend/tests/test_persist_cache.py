"""二级磁盘缓存（persist_cache）与 _fetch 跨进程命中的回归测试。

不用 pytest 的 tmp_path：本机 TEMP 基目录带沙箱拒绝 ACL，pytest 建 basetemp 会 PermissionError；
改用 data 目录下的临时子目录（创建/读/删已实测可用），finally 清理。
"""
import os
import shutil
import uuid
from pathlib import Path

import pandas as pd

from app.cache import cache
from app.datasource import persist_cache
from app.datasource.akshare_source import AkshareSource, _cache_key

ROOT = Path(__file__).resolve().parents[2]


def _tmp_dir() -> Path:
    """data 下的唯一临时目录。

    不用 tempfile.mkdtemp：本机（DSH 沙箱）mkdtemp 建出的目录带拒绝 ACL，写入直接 PermissionError；
    os.makedirs 建出的目录实测可读可写可删。
    """
    path = ROOT / "data" / ("ic_cache_test_%s_%s" % (os.getpid(), uuid.uuid4().hex[:8]))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _use_tmp_db(monkeypatch, tmp: Path) -> Path:
    target = tmp / "cache.db"
    monkeypatch.setattr(persist_cache, "db_path", lambda path=None: Path(target))
    return target


def test_set_get_roundtrip():
    tmp = _tmp_dir()
    try:
        path = str(tmp / "c.db")
        assert persist_cache.get("k", path) is None
        assert persist_cache.set("k", "value", 60, path) is True
        assert persist_cache.get("k", path) == "value"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_expired_entry_is_miss():
    tmp = _tmp_dir()
    try:
        path = str(tmp / "c.db")
        persist_cache.set("k", "value", -1, path)  # 已过期
        assert persist_cache.get("k", path) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_fetch_reuses_disk_cache_across_process_boundary(monkeypatch):
    """内存缓存清空（模拟新进程）后必须命中磁盘缓存，不再发起取数调用。"""
    tmp = _tmp_dir()
    try:
        _use_tmp_db(monkeypatch, tmp)
        calls: list[int] = []

        def call():
            calls.append(1)
            return pd.DataFrame({"date": ["2026-07-31"], "close": [1.0]})

        src = AkshareSource.__new__(AkshareSource)  # 跳过 __init__：_fetch 不依赖实例状态
        key = _cache_key("fin:v2:600000")
        cache.delete(key)
        first = src._fetch("fin:v2:600000", "fin", call, ttl_seconds=86400)
        assert len(calls) == 1 and len(first) == 1
        cache.delete(key)  # 模拟进程结束，内存缓存丢失
        second = src._fetch("fin:v2:600000", "fin", call, ttl_seconds=86400)
        assert len(calls) == 1, "命中磁盘缓存时不得再发起取数"
        assert len(second) == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_fetch_does_not_persist_short_lived_scope(monkeypatch):
    """非持久化范围（如行业板块快照）不得写盘。"""
    tmp = _tmp_dir()
    try:
        _use_tmp_db(monkeypatch, tmp)
        src = AkshareSource.__new__(AkshareSource)
        key = _cache_key("industry_spot")
        cache.delete(key)

        def call():
            return pd.DataFrame({"date": ["2026-07-31"], "close": [1.0]})

        src._fetch("industry_spot", "industry_spot", call, ttl_seconds=600)
        assert persist_cache.get(key) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
