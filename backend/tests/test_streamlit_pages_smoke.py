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

from streamlit.testing.v1 import AppTest

_STREAMLIT_DIR = str(Path(__file__).resolve().parents[2] / "streamlit")
PAGES_DIR = Path(__file__).resolve().parents[2] / "streamlit" / "pages"


@pytest.fixture(scope="module", autouse=True)
def _mount_streamlit_dir():
    """streamlit/ 内含 app.py，与 backend 的 app 包（namespace package）同名冲突：
    只能在 AppTest 执行时挂载，不能放模块顶层，否则收集期 `from app.db import ...`
    会被 streamlit/app.py 遮蔽（收集顺序敏感）。"""
    sys.path.append(_STREAMLIT_DIR)
    yield

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
    at = AppTest.from_file(str(PAGES_DIR / page), default_timeout=180)
    at.run()
    assert not at.exception, f"{page} 渲染异常: {at.exception}"
    assert at.title[0].value == _TITLES[page]


def test_candidate_page_interactives():
    """候选池页新交互回归：日期选择器 / 评级筛选三档 / 主表与详情折叠"""
    at = AppTest.from_file(str(PAGES_DIR / "1_每日候选池.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"候选池页渲染异常: {at.exception}"
    assert at.selectbox[0].label == "选择日期" and len(at.selectbox[0].options) >= 1
    assert [r.options for r in at.radio if r.label == "评级筛选"][0] == ["全部", "可建仓 A+B", "仅观察 C"]
    # 评级筛选切换不报错
    radio = next(r for r in at.radio if r.label == "评级筛选")
    radio.set_value("可建仓 A+B")
    at.run()
    assert not at.exception, f"评级筛选切换后异常: {at.exception}"


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


def test_home_page_renders():
    """首页看板渲染冒烟（含顶部常驻状态栏与热门板块模块）"""
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "streamlit" / "app.py"),
                           default_timeout=180)
    at.run()
    assert not at.exception, f"首页渲染异常: {at.exception}"
    assert at.title[0].value == "单人 A 股全生命周期决策 Agent 系统"


def test_top_bar_format_helpers():
    """顶部栏展示格式纯函数：金额千分位/百分比四舍五入/涨跌符号映射"""
    spec = importlib.util.spec_from_file_location("render", PAGES_DIR.parent / "render.py")
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)

    assert render._bar_money(1234567.891) == "1,234,567.89"
    assert render._bar_money(0.0) == "0.00"
    assert render._bar_money(None) == "—"
    assert render._bar_pct(40.56) == "40.6%"
    assert render._bar_pct(0.0) == "0.0%"
    assert render._bar_pct(None) == "—"
    assert render._bar_sign(0.85) == "up"
    assert render._bar_sign(-1.23) == "down"
    assert render._bar_sign(0.0) == "flat"
    assert render._bar_sign(None) == "flat"


def test_top_bar_layout_padding_css():
    """顶部固定状态栏布局规范：主内容区与侧边栏预留 4.3rem 顶距不遮挡首屏；
    状态栏本体固定悬浮（z-index 998）、width 100% 撑满视口、左右内边距对称
    （无单侧大 padding）、align-items center 统一垂直居中、line-height 1.5；
    信息按「账户资产」「大盘指数」分组展示。CSS 注入点唯一（top_status_bar）"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert '[data-testid="stMain"] { padding-top: 4.3rem; }' in src
    assert '[data-testid="stSidebarContent"] { padding-top: 4.3rem; }' in src
    assert "position: fixed" in src and "z-index: 998" in src
    assert "width: 100%" in src and "box-sizing: border-box" in src
    assert "line-height: 1.5" in src
    assert "align-items: center" in src
    assert "padding: 0.3rem 1rem" in src  # 左右对称，无单侧大 padding
    assert "29.9rem" not in src and "line-height: 2.45" not in src  # 不再出现异常参数
    assert "bar-group" in src and "bar-group-label" in src  # 分组展示 + 组标签


# ================= Agent 对话页（9_Agent对话.py） =================

def test_agent_chat_page_renders():
    """Agent 对话页渲染：标题 / 六 Agent 选择 / 三个交互标签 / 历史区"""
    at = AppTest.from_file(str(PAGES_DIR / "9_Agent对话.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"9_Agent对话.py 渲染异常: {at.exception}"
    assert at.title[0].value == "Agent 专属对话（调教 · 答疑 · 知识沉淀）"
    tabs = [t.label for t in at.tabs]
    for name in ("文字提问", "规则调教", "多模态学习", "对话历史"):
        assert name in tabs, f"缺少标签页: {name}"
    options = at.selectbox[0].options
    for agent in ("选股发现 Agent", "评分分析 Agent", "建仓方案 Agent",
                  "持仓监控 Agent", "卖出决策 Agent", "复盘迭代 Agent"):
        assert agent in options, f"缺少 Agent 选项: {agent}"
