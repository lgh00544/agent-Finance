"""Streamlit 页面无头渲染冒烟 + 展示规范回归：
1. 全部页面可渲染且 0 异常（需后端在跑）；
2. 页面禁止直接 st.json 裸露原始 JSON（一律经 render.raw_json_expander 折叠）；
3. 原始 JSON 折叠控件默认收起（expanded=False）；
4. 股票标识统一「代码 名称」格式（600519 贵州茅台）。"""
import importlib.util
import re
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
    "5_游资追踪.py",
    "6_交易复盘.py",
    "8_告警日志.py",
    "9_交易知识库.py",
]

_TITLES = {
    "1_每日候选池.py": "每日候选池（DiscoverAgent）",
    "2_评分报告.py": "评分报告（ScoreAgent）",
    "3_建仓计划.py": "建仓计划（PositionAgent）",
    "4_持仓监控.py": "持仓监控（MonitorAgent）",
    "5_游资追踪.py": "游资追踪（Hot Money）",
    "6_交易复盘.py": "交易复盘（ReviewAgent）",
    "8_告警日志.py": "告警日志（MonitorAgent）",
    "9_交易知识库.py": "交易知识库（统一调教·私有战法）",
}


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(PAGES_DIR / page), default_timeout=180)
    at.run()
    assert not at.exception, f"{page} 渲染异常: {at.exception}"
    assert at.title[0].value == _TITLES[page]


def test_candidate_page_interactives():
    """候选池页新交互回归：日期选择器 / 评级筛选三档（segmented_control）/ 列表行与详情折叠"""
    at = AppTest.from_file(str(PAGES_DIR / "1_每日候选池.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"候选池页渲染异常: {at.exception}"
    assert at.selectbox[0].label == "选择日期" and len(at.selectbox[0].options) >= 1
    assert at.segmented_control[0].label == "评级筛选"
    assert at.segmented_control[0].options == ["全部候选", "可建仓 A+B", "观察 C"]

    # ===== 数据真实渲染断言（2026-08-06 假绿修复：仅断言无异常会漏检列表崩溃被吞） =====
    def _assert_list_state():
        md_text = "\n".join(m.value for m in at.markdown if m.value)
        for err in ("后端服务连接失败", "数据库查询失败", "请求超时", "数据解析失败", "加载失败"):
            assert err not in md_text, f"API 正常时页面不应显示错误卡片: {md_text[:200]}"
        # 列表行（#N 代码 名称）或空状态说明必须出现其一；两者皆无 = 列表被异常吞掉
        row_or_empty = re.search(r"#\d+\s+\d{6}\s+\S+", md_text) or "当日无候选" in md_text
        assert row_or_empty, "候选列表既无渲染行也无空状态说明（可能被异常吞掉转错误卡片）"

    _assert_list_state()
    # 评级筛选切换不报错，且筛选后列表状态仍合法
    at.segmented_control[0].set_value("可建仓 A+B")
    at.run()
    assert not at.exception, f"评级筛选切换后异常: {at.exception}"
    _assert_list_state()


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
    """股票标识统一格式：代码在前、名称紧随；名称缺失/等于代码显示「名称待补」，
    禁止只展示纯代码（2026-08-05 名称修复硬性规则）"""
    spec = importlib.util.spec_from_file_location("render", PAGES_DIR.parent / "render.py")
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)

    assert render.stock_label("600519", "贵州茅台") == "600519 贵州茅台"
    assert render.stock_label("600519", "600519") == "600519 名称待补"
    assert render.stock_label("600519", "") == "600519 名称待补"
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
    """顶部固定状态栏布局规范：主内容区与侧边栏预留 60px 顶距不遮挡首屏；
    状态栏本体固定悬浮（z-index 999）、width 100% 撑满视口、左右内边距对称
    8px 24px（无单侧大 padding）、align-items center 统一垂直居中、line-height 1.5、
    背景 #0f1115 + 底部 1px 描边 rgba(60,80,120,0.25)；
    信息按「账户资产」「大盘指数」分组展示。CSS 注入点唯一（top_status_bar）"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert '[data-testid="stMain"] { padding-top: 60px; }' in src
    assert '[data-testid="stSidebarContent"] { padding-top: 60px; }' in src
    assert "position: fixed" in src and "z-index: 999" in src
    assert "width: 100%" in src and "box-sizing: border-box" in src
    assert "line-height: 1.5" in src
    assert "align-items: center" in src
    assert "padding: 8px 24px" in src  # 左右对称，无单侧大 padding
    assert "background: #0f1115" in src  # 与全局主题同色板
    assert "border-bottom: 1px solid rgba(60, 80, 120, 0.25)" in src
    assert "29.9rem" not in src and "line-height: 2.45" not in src  # 不再出现异常参数
    assert "bar-group" in src and "bar-group-label" in src  # 分组展示 + 组标签


# ================= 全局深色科技感主题（2026-08-05 前端视觉体系升级） =================

def test_global_theme_css_components():
    """全局主题落地：CSS 变量色板 / 徽章 / 溯源行 / 懒加载列表组件齐备"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert "_GLOBAL_THEME_CSS" in src and "def apply_global_theme" in src
    for var in ("--bg-base", "--bg-card", "--primary", "--up", "--down",
                "--tier-a", "--tier-b", "--tier-c", "--text-dim"):
        assert var in src, f"缺少 CSS 变量: {var}"
    assert "def badge" in src and "badge-tier-a" in src
    assert "def trace_line" in src and "trace-line" in src
    assert "def record_list" in src and "def empty_state" in src
    assert "tabular-nums" in src  # 数字等宽对齐


def test_all_pages_apply_global_theme():
    """全部页面（含首页）均调用全局主题注入，无遗漏"""
    pages = [p for p in PAGES_DIR.glob("*.py")]
    assert pages, "未找到任何页面"
    for p in pages:
        src = p.read_text(encoding="utf-8")
        assert "render.apply_global_theme()" in src, f"{p.name} 缺少全局主题注入"


def test_streamlit_theme_config():
    """config.toml 深色主题配置（原生控件深色兜底）"""
    cfg = (PAGES_DIR.parent / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'base = "dark"' in cfg
    assert "primaryColor" in cfg and "backgroundColor" in cfg


def test_score_page_debounce_query_button():
    """评分报告页筛选防抖：输入后点「查询」才过滤，查询/清除按钮存在；
    搜索区单行排布：代码/名称搜索 + 日期筛选"""
    at = AppTest.from_file(str(PAGES_DIR / "2_评分报告.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"评分报告页渲染异常: {at.exception}"
    labels = [b.label for b in at.button]
    assert "查询" in labels, f"缺少查询按钮: {labels}"
    assert "清除筛选" in labels, f"缺少清除按钮: {labels}"
    assert at.text_input[0].label == "按代码或名称搜索（留空显示全部，输入后点查询）"
    assert at.selectbox[0].label == "选择日期" and at.selectbox[0].options[0] == "全部"


def test_score_page_master_detail_linkage():
    """列表-详情联动：默认选中第一行；程序化选中第二行 → 详情切换（AppTest 无法模拟
    真实表格点击，但 session_state 程序化选中与前端点击走同一 value_changed 链路）"""
    at = AppTest.from_file(str(PAGES_DIR / "2_评分报告.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"评分报告页渲染异常: {at.exception}"
    assert at.dataframe, "评分页应渲染总览表格"
    dfv = at.dataframe[0].value  # 总览表（详情内的五维分项表在下方）
    if len(dfv) < 2:
        pytest.skip("评分数据不足 2 行，跳过联动断言")

    def _detail_text() -> str:
        return "\n".join(m.value for m in at.markdown if m.value)

    first, second = dfv.iloc[0]["股票"], dfv.iloc[1]["股票"]
    assert first in _detail_text(), "默认应选中第一行（详情区展示第一行）"
    # 程序化选中第二行（等价于用户点击第 2 行）
    at.session_state["_score_table"] = {"selection": {"rows": [1], "columns": [], "cells": []}}
    at.run()
    assert not at.exception, f"选中第二行后异常: {at.exception}"
    assert second in _detail_text(), "选中第二行后详情应切换"
    assert first not in _detail_text(), "详情区应只展示当前选中行"


# ================= Agent 对话页（10_Agent对话.py） =================

def test_agent_chat_page_renders():
    """Agent 对话页渲染：标题 / 左侧 Agent 导航列表（radio 高亮）/ 四个交互标签 / 历史区"""
    at = AppTest.from_file(str(PAGES_DIR / "10_Agent对话.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"10_Agent对话.py 渲染异常: {at.exception}"
    assert at.title[0].value == "Agent 专属对话（调教 · 答疑 · 知识沉淀）"
    tabs = [t.label for t in at.tabs]
    for name in ("文字提问", "规则调教", "多模态学习", "对话历史"):
        assert name in tabs, f"缺少标签页: {name}"
    options = at.radio[0].options
    for agent in ("选股发现 Agent", "评分分析 Agent", "建仓方案 Agent",
                  "持仓监控 Agent", "卖出决策 Agent", "复盘迭代 Agent"):
        assert agent in options, f"缺少 Agent 选项: {agent}"
    # 切换 Agent（radio 选中高亮，独立上下文）不报错
    at.radio[0].set_value("持仓监控 Agent")
    at.run()
    assert not at.exception, f"Agent 切换后异常: {at.exception}"


def test_holding_page_tabs():
    """持仓监控页 3 Tab 结构：当前持仓 / 告警记录 / 历史持仓"""
    at = AppTest.from_file(str(PAGES_DIR / "4_持仓监控.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"4_持仓监控.py 渲染异常: {at.exception}"
    tabs = [t.label for t in at.tabs]
    for name in ("当前持仓", "告警记录", "历史持仓"):
        assert name in tabs, f"缺少标签页: {name}"


def test_hot_money_page_renders():
    """游资追踪页渲染：标题 / 五大折叠模块标题（权重迭代/档案/龙虎榜/席位监控/留痕）"""
    at = AppTest.from_file(str(PAGES_DIR / "5_游资追踪.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"5_游资追踪.py 渲染异常: {at.exception}"
    assert at.title[0].value == "游资追踪（Hot Money）"
    # fold_module 标题渲染为 markdown（折叠开关是「收起/展开」按钮），按标题文本断言
    texts = " ".join(str(m.value) for m in at.markdown)
    for name in ("游资胜率迭代（自进化 · 人工审核后生效）",
                 "游资档案", "龙虎榜原始流水（今日/按日筛选）",
                 "游资席位监控（最近操作追踪）",
                 "游资研判留痕（ai_reasoning_trace · 跨模块联查）"):
        assert name in texts, f"缺少折叠模块标题: {name}"
    assert any("收起" in b.label or "展开" in b.label for b in at.button), "缺少折叠开关按钮"


def test_knowledge_page_tabs():
    """交易知识库页顶部 Tab 操作区：新增条目 / 批量导入 / 知识条目"""
    at = AppTest.from_file(str(PAGES_DIR / "9_交易知识库.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"9_交易知识库.py 渲染异常: {at.exception}"
    tabs = [t.label for t in at.tabs]
    for name in ("新增条目", "批量导入", "知识条目"):
        assert name in tabs, f"缺少标签页: {name}"
    src = (PAGES_DIR / "9_交易知识库.py").read_text(encoding="utf-8")
    assert src.count('st.form("') >= 2  # 新增 + 批量导入表单
    assert "按适用 Agent 过滤" in [s.label for s in at.selectbox]


def test_review_page_expander():
    """交易复盘页：策略闭环建议区一级折叠模块存在（待审核条数实时展示）"""
    at = AppTest.from_file(str(PAGES_DIR / "6_交易复盘.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"6_交易复盘.py 渲染异常: {at.exception}"
    labels = [b.label for b in at.button] + [e.label for e in at.expander]
    labels += [str(m.value) for m in at.markdown]
    assert any("策略闭环" in lb for lb in labels), "缺少策略闭环建议区折叠模块"


def test_enterprise_list_components():
    """企业级列表行/分区卡片/指标卡/告警行组件与 CSS 类齐备"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    for fn in ("list_item", "list_item_toggle", "section_title", "stat_cards",
               "svc_cards", "alert_list"):
        assert f"def {fn}" in src, f"缺少组件函数: {fn}"
    for css in ("item-main", "item-title", "item-sub", "item-meta",
                "section-title", "stat-card", "stat-grid", "dot-tier-a",
                "st-key-lrow_"):
        assert css in src, f"缺少 CSS 类: {css}"
    assert "actions: tuple" in src and "enumerate(actions)" in src  # 列表行操作按钮组
    assert ".item-meta .up" in src and ".item-meta .down" in src  # 盈亏着色


def test_agent_radio_nav_css():
    """Agent 对话页左侧列表（radio 增强为导航样式）：选中高亮 + hover 反馈"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert "radiogroup" in src and "label:has(input:checked)" in src


def test_navigation_app_groups():
    """app.py 导航分组：4 组（系统概览/选股决策/持仓风控/策略沉淀）+ 全部页面挂载"""
    src = (Path(__file__).resolve().parents[2] / "streamlit" / "app.py").read_text(encoding="utf-8")
    for group in ("系统概览", "选股决策", "持仓风控", "策略沉淀"):
        assert group in src, f"缺少导航分组: {group}"
    for page in ("0_系统概览.py", "1_每日候选池.py", "2_评分报告.py", "3_建仓计划.py",
                 "4_持仓监控.py", "5_游资追踪.py", "6_交易复盘.py", "8_告警日志.py",
                 "9_交易知识库.py", "10_Agent对话.py"):
        assert page in src, f"导航未挂载页面: {page}"


# ================= 统一错误提示系统（4 级分级：阻断/提醒/成功/空状态） =================

def test_error_components_exist():
    """错误提示组件体系齐备：4 级提示卡片/原位字段错误/汇总条/空状态/字段合法值判定"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    for fn in ("msg_card", "error_card", "field_error", "field_summary", "field_ok",
               "set_field_errors", "get_field_error", "get_field_errors", "empty_state"):
        assert f"def {fn}" in src, f"缺少错误提示组件函数: {fn}"
    for css in ("msg-card", "field-err", "field-summary", "empty-state", "empty-icon"):
        assert css in src, f"缺少错误提示组件 CSS 类: {css}"
    # 视觉分级色板：阻断 err / 提醒 warn / 成功 ok / 中性 info
    for tone in ("err", "warn", "ok", "info"):
        assert tone in src, f"缺少提示分级色: {tone}"


def test_field_ok_clearing_is_valid():
    """field_ok 纯函数：0（清仓股数）是合法值，None/NaN/空串不合法——OCR 清仓=正常 硬性规则"""
    spec = importlib.util.spec_from_file_location("render", PAGES_DIR.parent / "render.py")
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)

    assert render.field_ok(0) is True, "0（清仓）必须是合法值"
    assert render.field_ok(0.0) is True
    assert render.field_ok(100) is True
    assert render.field_ok("600519") is True
    assert render.field_ok("") is False
    assert render.field_ok(None) is False
    assert render.field_ok(float("nan")) is False


def test_no_bare_st_error_in_pages():
    """页面禁止裸 st.error：阻断错误一律经 render.error_card/msg_card（原因+重试/折叠）"""
    bad = [p.name for p in PAGES_DIR.glob("*.py") if "st.error(" in p.read_text(encoding="utf-8")]
    assert not bad, f"以下页面仍直接使用 st.error（应改用 render.error_card/msg_card）: {bad}"


def test_field_error_usage_in_forms():
    """表单字段校验页面统一使用 fld_ 容器 + field_error 原位标记 + field_summary 汇总条"""
    pages = ["3_建仓计划.py", "4_持仓监控.py", "6_交易复盘.py", "9_交易知识库.py"]
    for name in pages:
        src = (PAGES_DIR / name).read_text(encoding="utf-8")
        assert 'render.field_error(' in src, f"{name} 缺少原位字段错误标记"
        assert 'render.get_field_error(' in src, f"{name} 缺少字段错误读取"
    # 汇总条：提交校验表单需展示错误汇总（不整段报错）
    assert "field_summary" in (PAGES_DIR / "4_持仓监控.py").read_text(encoding="utf-8")
    assert "field_summary" in (PAGES_DIR / "9_交易知识库.py").read_text(encoding="utf-8")


def test_top_bar_sidebar_adapt_css():
    """顶部状态栏侧边栏动态适配：:has 监听 aria-expanded（展开 300px 偏移/收起回落 24px）
    + 0.2s 平滑过渡；原固定悬浮/垂直居中/底部描边规则保持不变"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert 'body:has([data-testid="stSidebar"][aria-expanded="true"]) .top-status-bar' in src
    assert "padding-left: calc(300px + 24px)" in src  # 展开态与主内容区左缘对齐
    assert "transition: padding-left 0.2s ease" in src  # 切换平滑不跳动
    # 原有样式规则保持：固定悬浮/垂直居中/底部描边
    assert "position: fixed" in src and "z-index: 999" in src
    assert "align-items: center" in src
    assert "border-bottom: 1px solid rgba(60, 80, 120, 0.25)" in src


def test_error_card_right_side_actions():
    """错误卡片操作按钮渲染在卡片右侧（重试无需滚到页面底部）"""
    src = (PAGES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert "def error_card" in src
    assert "actions: tuple[tuple[str, str], ...]" in src  # (按钮key, 按钮文案) 序列
    assert "st.columns([5, 1.3], vertical_alignment" in src  # 左卡片右按钮布局
    # 候选池页使用右侧重试按钮 + 分类错误提示
    cand_src = (PAGES_DIR / "1_每日候选池.py").read_text(encoding="utf-8")
    assert "render.classify_api_error(" in cand_src
    assert "retry_key=\"retry_candidates\"" in cand_src


def test_classify_api_error():
    """API 失败分类纯函数：连接失败/超时/HTTP 数据库异常/未知 → 对应文案与技术日志摘要"""
    import requests

    spec = importlib.util.spec_from_file_location("render", PAGES_DIR.parent / "render.py")
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)

    title, hint, tech = render.classify_api_error(requests.exceptions.ConnectionError())
    assert "连接失败" in title and "重试" in hint and "ConnectionError" in tech
    assert "20" in tech  # 技术日志含时间戳

    title, hint, tech = render.classify_api_error(requests.exceptions.Timeout())
    assert "超时" in title and "重试" in hint

    resp = requests.Response()
    resp.status_code = 500
    resp.encoding = "utf-8"
    resp._content = b"database connection lost: pool exhausted"
    req = requests.Request("GET", "http://localhost:8000/api/candidates").prepare()
    err = requests.exceptions.HTTPError("500 Server Error", response=resp, request=req)
    title, hint, tech = render.classify_api_error(err)
    assert "数据库" in title and "重试" in hint and "HTTP 500" in tech

    title, hint, tech = render.classify_api_error(ValueError("boom"))
    assert "加载失败" in title and "重试" in hint and "ValueError" in tech


def test_frontend_cache_roundtrip(monkeypatch, tmp_path):
    """离线缓存模块：保存/读取回环（含保存时间戳），无缓存/损坏返回 None"""
    import frontend_cache as fc

    monkeypatch.setattr(fc, "_CACHE_DIR", tmp_path)
    assert fc.load("cands") is None  # 无缓存
    fc.save("cands", {"date": "2026-08-05", "rows": [{"id": 1}]})
    data = fc.load("cands")
    assert data is not None and data["data"]["date"] == "2026-08-05"
    assert "saved_at" in data  # 标注缓存时间
    # 损坏文件 → None 不抛错
    (tmp_path / "frontend_cache_bad.json").write_text("{broken", encoding="utf-8")
    assert fc.load("bad") is None


# ================= 假绿修复专项（2026-08-06：测试通过但列表从未渲染的事件复盘沉淀） =================

def test_candidate_page_try_scope():
    """候选池页错误处理必须限定在数据获取边界（假绿根因修复）：
    try 正常路径块内禁止列表渲染调用（list_item_toggle/record_list），
    防整页 try 吞异常把列表崩溃掩盖为错误卡片；except 块内 error_card 属合理错误处理"""
    lines = (PAGES_DIR / "1_每日候选池.py").read_text(encoding="utf-8").splitlines()
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if not re.match(r"^\s*try:", line):
            continue
        indent = len(line) - len(line.lstrip())
        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if re.match(r"^\s*(except|else|finally)\b", ln):
                break  # try 正常路径结束，except 内的错误展示不检查
            if ln.strip() and len(ln) - len(ln.lstrip()) > indent:
                if re.search(r"\b(list_item_toggle|record_list)\s*\(", ln):
                    bad.append((j + 1, ln.strip()))
            j += 1
    assert not bad, f"try 块内发现列表渲染调用（错误处理越界）: {bad}"


def test_candidate_row_contract():
    """候选池 API 行契约（假绿根因修复）：行必须含页面渲染依赖的 8 键、且无 id
    （前端用 代码+日期+rank 组合键，页面曾假设 id 字段导致列表崩溃被掩盖）；
    API 不可达或无数据时跳过（防御性契约校验，不依赖后端常驻）"""
    import api_client

    try:
        rows = api_client.candidates(limit=5)
    except Exception:  # noqa: BLE001
        pytest.skip("API 不可达，跳过候选行契约断言")
    if not rows:
        pytest.skip("无候选数据，跳过契约断言")
    required = ("stock_code", "stock_name", "trade_date", "rank",
                "reasons", "risk_notice", "detail", "created_at")
    missing = [k for k in required if k not in rows[0]]
    assert not missing, f"候选行缺少契约字段: {missing}"
    assert "id" not in rows[0], "候选行不应含 id（页面使用组合键，出现 id 说明结构漂移）"


# ================= AI 研判留痕交互全链路（2026-08-06 验证沉淀） =================
# 断言要点：expander 标签不出现在 markdown（此前在 markdown 找「最终结论（默认展开）」
# 必然失败）；全局主题 CSS 含 .rule-*/.trace-* 类名（markdown 断言须剔除首个 CSS，
# 否则「规则徽章出现」恒真）；at.session_state 不支持 .get()/迭代（用 in 判断）；
# expander 展开状态读 proto.expanded（AppTest 元素不暴露 expanded 属性）。

def test_candidate_trace_chain():
    """候选池页留痕全链路：触发按钮 → 留痕列表 → 详情卡片
    （结论卡默认展开 + 推理分层折叠 + 结论内容渲染 + 头部徽章）"""
    at = AppTest.from_file(str(PAGES_DIR / "1_每日候选池.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"候选池页渲染异常: {at.exception}"

    detail_toggle = [b for b in at.button if b.label == "查看详情"]
    if not detail_toggle:
        pytest.skip("当日无候选详情，跳过留痕链路断言")
    detail_toggle[0].click().run()
    assert not at.exception, f"展开候选详情异常: {at.exception}"

    btns = [b for b in at.button if "AI 研判留痕" in b.label]
    assert btns, "未找到留痕按钮"
    btns[0].click().run()
    assert not at.exception, f"点击留痕后异常: {at.exception}"

    row_btns = [b for b in at.button if b.label.startswith("查看 ") and "留痕" in b.label]
    captions = [c.value for c in at.caption]
    if not row_btns:
        if any("暂无留痕记录" in c for c in captions):
            pytest.skip("该标的本交易日无留痕数据，跳过详情断言")
        assert any("留痕接口暂不可用" in c for c in captions), \
            "留痕列表未出现且非空态/降级态（接口或渲染异常被吞）"
        pytest.skip("留痕接口暂不可用，跳过详情断言")

    row_btns[0].click().run()
    assert not at.exception, f"打开留痕详情后异常: {at.exception}"

    # 结论卡默认展开（acceptance：先给结论）
    concl = [e for e in at.expander if "最终结论" in e.label]
    assert concl, "结论卡未渲染（无「最终结论」expander）"
    assert concl[0].proto.expanded is True, "结论卡未默认展开"

    # 推理分层折叠渲染
    layers = [e for e in at.expander
              if e.label in ("事实依据（输入数据快照）", "技术面推理", "资金面推理",
                             "基本面推理", "风险推理")]
    assert len(layers) >= 3, f"推理分层渲染不足（{len(layers)} 层）"
    assert all(e.proto.expanded is False for e in layers), "推理层必须默认折叠"

    # 结论内容与头部徽章实际渲染（剔除 CSS 后的真实 markdown）
    md_text = "\n".join(m.value for m in at.markdown if m.value
                        and not m.value.lstrip().startswith("<style>"))
    assert any(k in md_text for k in ("confidence_tier", "stock_type", "score",
                                      "grade", "action", "plan_id", "lesson")), \
        "结论卡内容未渲染"
    assert 'class="badge badge-info"' in md_text, "留痕头部徽章未渲染"
    assert 'class="trace-layer' in md_text, "推理层内容未渲染"
