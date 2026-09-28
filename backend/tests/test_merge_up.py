"""B 方案（合并上云）回归：分类安全底线 + 水位解析 + 云端校验 + 缺水位拒绝执行。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sync_manager as sm  # noqa: E402


def test_classify_new_conflict_stale():
    pk = ["id"]
    local = [{"id": 1, "updated_at": "2026-09-20 10:00:00"},
             {"id": 2, "updated_at": "2026-09-20 10:00:00"},
             {"id": 3, "updated_at": "2026-09-20 10:00:00"}]
    cloud = [{"id": 2, "updated_at": "2026-09-19 10:00:00"},   # 云端旧 -> 本地更新
             {"id": 3, "updated_at": "2026-09-21 10:00:00"}]   # 云端新 -> 跳过
    cls = sm.classify_merge_rows(local, cloud, pk, "updated_at")
    assert [r["id"] for r in cls["new"]] == [1]
    assert [r["id"] for r in cls["conflict"]] == [2]
    assert [r["id"] for r in cls["stale"]] == [3]


def test_classify_never_overwrites_when_timestamp_unknown():
    """任一侧时间戳缺失、或整表无水位列，一律 stale：宁可漏合并，绝不覆盖云端。"""
    pk = ["id"]
    local = [{"id": 1, "updated_at": None}, {"id": 2, "updated_at": "2026-09-20 10:00:00"}]
    cloud = [{"id": 1, "updated_at": "2026-09-19 10:00:00"},
             {"id": 2, "updated_at": None}]
    cls = sm.classify_merge_rows(local, cloud, pk, "updated_at")
    assert cls["stale"] and not cls["conflict"] and not cls["new"]
    cls2 = sm.classify_merge_rows(local, cloud, pk, None)
    assert cls2["stale"] and not cls2["conflict"]


def test_classify_equal_timestamp_is_stale():
    pk = ["id"]
    row = {"id": 7, "updated_at": "2026-09-20 10:00:00"}
    cls = sm.classify_merge_rows([row], [dict(row)], pk, "updated_at")
    assert cls["stale"] and not cls["conflict"]


def test_merge_since_prefers_cli_then_marker():
    marker = {"degraded_since": "2026-09-28T11:24:00"}
    assert sm.merge_since(["prog", "merge-up"], marker) == "2026-09-28T11:24:00"
    assert sm.merge_since(["prog", "merge-up", "--since", "2026-09-01"], marker) == "2026-09-01"
    assert sm.merge_since(["prog", "merge-up", "--since"], marker) == "2026-09-28T11:24:00"
    assert sm.merge_since(["prog", "merge-up"], None) == ""


def test_cloud_ready_rejects_non_mysql():
    class _Dialect:
        name = "sqlite"

    class _Engine:
        dialect = _Dialect()

    assert "必须在云端可达" in sm._cloud_ready(_Engine())


def test_cloud_ready_accepts_mysql():
    class _Dialect:
        name = "mysql"

    class _Engine:
        dialect = _Dialect()

    assert sm._cloud_ready(_Engine()) == ""


def test_merge_up_without_watermark_exits_2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_manager.py", "merge-up"])
    monkeypatch.setenv("DB_DEGRADED_MARKER", str(ROOT / ".wb_h" / "merge_up_no_marker.json"))
    assert sm.cmd_merge_up() == 2
