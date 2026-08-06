"""强时效时间展示配套测试：
1. /api/system/status 探活结构（4 连接 + checked_at 北京时间格式）
2. repo 各列表接口返回 created_at 时间字段（供前端标注生成时间）
3. 首页看板 AppTest 冒烟（需后端在跑，与页面冒烟测试一致）"""
import re
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.db import repo
from app.services import status as status_service

# 注意：streamlit/ 目录里有 app.py，与 backend 的 app 包（namespace package，无 __init__.py）
# 同名冲突，只能在使用 AppTest 的测试函数内临时挂载 streamlit 路径，不能放在模块顶层。
_STREAMLIT_DIR = str(Path(__file__).resolve().parents[2] / "streamlit")

TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from app.db.session import init_db
    init_db()


@pytest.fixture
def _no_network(monkeypatch):
    """探活中的网络请求全部 mock：只验证结构，不依赖外网（仅探活单测使用，
    页面 AppTest 走真实后端，不套用本 mock）"""
    class _FakeResp:
        status_code = 200
        text = '{"data":{}}'

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResp())


def test_system_status_structure(_no_network):
    stt = status_service.system_status()
    assert TIME_RE.match(stt["checked_at"]), f"检测时间格式不符: {stt['checked_at']}"
    assert len(stt["connections"]) == 5
    names = [c["name"] for c in stt["connections"]]
    assert "后端服务" in names[0] and "数据源" in names[1]
    assert "LLM" in names[2] and "数据库" in names[3]
    for conn in stt["connections"]:
        assert TIME_RE.match(conn["checked_at"]), "每项连接必须有最后检测时间"
        assert "detail" in conn


def test_system_status_ok_flags(_no_network):
    """全部探活成功时 ok=True（DB 真实检查 + 网络 mock 为 200）"""
    stt = status_service.system_status()
    assert all(c["ok"] for c in stt["connections"])


def test_llm_missing_key_reports_failure(_no_network, monkeypatch):
    monkeypatch.setattr(status_service.settings, "deepseek_api_key", "")
    stt = status_service.system_status()
    llm = [c for c in stt["connections"] if "LLM" in c["name"]][0]
    assert llm["ok"] is False
    assert "API Key" in llm["detail"]


def test_data_source_failure_reported(_no_network, monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("网络不可达")

    monkeypatch.setattr("requests.get", _boom)
    stt = status_service.system_status()
    src = [c for c in stt["connections"] if "数据源" in c["name"]][0]
    assert src["ok"] is False


def test_list_endpoints_return_created_at():
    """候选/评分/建仓/复盘列表接口均携带 created_at（前端时间标注数据源）"""
    repo.upsert_candidate("600101", "时间测试股A", "2026-08-04", 1, ["理由"], [], {})
    repo.upsert_score("600102", "时间测试股B", "2026-08-04", 80.0, "A", {}, [])
    repo.insert_plan("600103", "时间测试股C", "2026-08-04", 50.0, [], 8.0, 12.0, "方案")
    rid = repo.insert_review("600104", "时间测试股D", 7, "2026-08-01", 10, 3.0, {}, "教训", {})

    for row in repo.list_candidates(date="2026-08-04"):
        assert row["created_at"], "候选缺少 created_at"
    for row in repo.list_scores(code="600102"):
        assert row["created_at"], "评分缺少 created_at"
    for row in repo.list_plans(code="600103"):
        assert row["created_at"], "建仓方案缺少 created_at"
    for row in repo.list_reviews(limit=50):
        assert row["created_at"], "复盘缺少 created_at"
    assert any(r["id"] == rid for r in repo.list_reviews(limit=50))


def test_home_dashboard_renders():
    """首页看板渲染冒烟：3 Tab（运行状态/今日概览/性能统计）+ 分区卡片 + 任务记录（需后端在跑）"""
    sys.path.insert(0, _STREAMLIT_DIR)  # 供首页 import api_client/render
    at = AppTest.from_file(r"D:\self\streamlit\app.py", default_timeout=180)
    at.run()
    assert not at.exception, f"首页渲染异常: {at.exception}"
    tabs = [t.label for t in at.tabs]
    for name in ("运行状态", "今日概览", "性能统计"):
        assert name in tabs, f"首页缺少 Tab: {name}"
    subs = [s.value for s in at.subheader]
    for name in ("系统服务", "定时任务调度", "任务执行记录"):
        assert name in subs, f"首页缺少模块: {name}"
    exp = [e.label for e in at.expander]
    for name in ("今日操作提示（市况五维）", "持仓与操作建议", "紧急告警日志",
                 "今日热门板块", "今日候选与建仓机会", "近期复盘动态"):
        assert name in exp, f"首页缺少分区: {name}"
    body = "\n".join(str(m.value) for m in at.markdown)
    assert "当前数据更新于" in body, "首页顶部缺少整体更新时间"
    assert not at.error, f"首页存在报错元素: {[e.value for e in at.error]}"
