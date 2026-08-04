"""Streamlit 页面无头渲染冒烟 + 展示规范回归：
1. 全部页面可渲染且 0 异常（需后端在跑）；
2. 页面禁止直接 st.json 裸露原始 JSON（一律经 render.raw_json_expander 折叠）；
3. 原始 JSON 折叠控件默认收起（expanded=False）；
4. 股票标识统一「代码 名称」格式（600519 贵州茅台）。"""
import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 项目根（agent_prompts）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit"))  # api_client

from streamlit.testing.v1 import AppTest

PAGES_DIR = Path(__file__).resolve().parents[2] / "streamlit" / "pages"

PAGES = [
    "1_每日候选池.py",
    "2_评分报告.py",
    "3_建仓计划.py",
    "4_持仓监控.py",
    "5_交易复盘.py",
    "7_告警日志.py",
    "8_交易知识库.py",
]

_TITLES = {
    "1_每日候选池.py": "每日候选池（DiscoverAgent）",
    "2_评分报告.py": "评分报告（ScoreAgent）",
    "3_建仓计划.py": "建仓计划（PositionAgent）",
    "4_持仓监控.py": "持仓监控（MonitorAgent）",
    "5_交易复盘.py": "交易复盘（ReviewAgent）",
    "7_告警日志.py": "告警日志（MonitorAgent）",
    "8_交易知识库.py": "交易知识库（统一调教·私有战法）",
}


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(PAGES_DIR / page), default_timeout=60)
    at.run()
    assert not at.exception, f"{page} 渲染异常: {at.exception}"
    assert at.title[0].value == _TITLES[page]


def test_no_raw_st_json_in_pages():
    """页面禁止直接 st.json 裸露原始 JSON（原始 JSON 必须经 render.raw_json_expander 折叠）"""
    bad = [p for p in PAGES if "st.json(" in (PAGES_DIR / p).read_text(encoding="utf-8")]
    assert not bad, f"以下页面直接调用 st.json（应改用 render.raw_json_expander）: {bad}"


def test_raw_json_expander_default_collapsed():
    """原始 JSON 折叠控件必须默认收起"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert "expanded=False" in src
    assert "st.json(" in src  # 唯一的 st.json 入口在渲染工具内


def test_stock_label_format():
    """股票标识统一格式：代码在前、名称紧随；名称缺失/与代码相同时仅代码"""
    spec = importlib.util.spec_from_file_location("render", PAGES_DIR.parent / "render.py")
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)

    assert render.stock_label("600519", "贵州茅台") == "600519 贵州茅台"
    assert render.stock_label("600519", "600519") == "600519"
    assert render.stock_label("600519", "") == "600519"
    assert render.stock_label("601012", " 隆基绿能 ") == "601012 隆基绿能"
