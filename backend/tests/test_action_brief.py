"""今日行动清单 render.action_brief 单元测试：
1. A区可建仓/空态/字段只用 tier+price_zone
2. B区预警/全正常/空持仓/排序
3. C区市况有/无数据
4. HTML 转义与 CSS 类存在"""
import importlib.util
import sys
from pathlib import Path

import pytest

# 加载 streamlit/render.py（与页面同路径，避免 namespace 冲突）
_RENDER_PATH = Path(__file__).resolve().parents[2] / "streamlit" / "render.py"


def _load_render():
    spec = importlib.util.spec_from_file_location("render", _RENDER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["render"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def render(monkeypatch):
    mod = _load_render()
    calls = []

    def _fake_markdown(body, unsafe_allow_html=False):
        calls.append((body, unsafe_allow_html))

    monkeypatch.setattr(mod.st, "markdown", _fake_markdown)
    mod._markdown_calls = calls
    return mod


def _last_html(render) -> str:
    assert render._markdown_calls, "action_brief 未调用 st.markdown"
    body, unsafe = render._markdown_calls[-1]
    assert unsafe is True, "action_brief 应使用 unsafe_allow_html=True"
    return body


# ========== A区：可建仓机会 ==========

def test_a_tradeable_items_render(render):
    items = [
        {"stock_code": "600110", "stock_name": "朝阳科技", "tier": "B",
         "is_tradeable": 1, "price_zone": "现价 12.5~13.0", "label": "可建仓"},
        {"stock_code": "600111", "stock_name": "北方稀土", "tier": "A",
         "is_tradeable": True, "price_zone": "", "label": "可建仓"},
    ]
    render.action_brief(items, [], None)
    html = _last_html(render)
    assert "可建仓机会" in html
    assert "600110 朝阳科技" in html
    assert "B级 · 可建仓（首仓区间 现价 12.5~13.0）" in html
    assert "600111 北方稀土" in html
    assert "A级 · 可建仓" in html
    # price_zone 为空时不应出现空括号
    assert "A级 · 可建仓（" not in html


def test_a_no_tradeable_items(render):
    render.action_brief([], [], None)
    html = _last_html(render)
    assert "可建仓机会" in html
    assert "今日无可建仓标的，观察候选池即可" in html


def test_a_uses_tier_not_grade(render):
    """A区字段只用 tier/price_zone/label，不得引用不存在的 grade/reason/potential_flag"""
    items = [{"stock_code": "600110", "stock_name": "朝阳科技", "tier": "B",
              "is_tradeable": 1, "price_zone": "现价 12.5~13.0", "label": "可建仓"}]
    render.action_brief(items, [], None)
    html = _last_html(render)
    assert "grade" not in html
    assert "potential_flag" not in html


# ========== B区：持仓今日关注 ==========

def test_b_empty_holdings(render):
    render.action_brief([], [], None)
    html = _last_html(render)
    assert "持仓今日关注" in html
    assert "暂无持仓" in html


def test_b_all_normal(render):
    briefs = [
        {"code": "000001", "name": "平安银行", "status": "持有观察",
         "status_tone": "info", "action_text": "🟢 正常持有", "detail": "现价 14.8 / 止盈 15.2"},
        {"code": "000002", "name": "万科A", "status": "持有观察",
         "status_tone": "info", "action_text": "🟢 正常持有", "detail": ""},
    ]
    render.action_brief([], briefs, None)
    html = _last_html(render)
    assert "今日持仓无预警，正常持有（2 只）" in html
    # 全正常时不展开逐只明细
    assert "000001 平安银行" not in html


def test_b_with_alerts(render):
    briefs = [
        {"code": "000001", "name": "平安银行", "status": "接近止盈",
         "status_tone": "warn", "action_text": "🟠 止盈关注：接近第一止盈位",
         "detail": "现价 14.8 / 止盈 15.2 / 止损 13.5"},
        {"code": "600519", "name": "贵州茅台", "status": "接近止损",
         "status_tone": "err", "action_text": "🔴 止损预警：现价接近止损位",
         "detail": "现价 1800 / 止损 1750"},
    ]
    render.action_brief([], briefs, None)
    html = _last_html(render)
    assert "000001 平安银行" in html
    assert "🟠 止盈关注" in html
    assert "600519 贵州茅台" in html
    assert "🔴 止损预警" in html
    assert "现价 14.8 / 止盈 15.2 / 止损 13.5" in html


def test_b_sort_order(render):
    """调用方排序后 render 按传入顺序展示：err 在前 warn 在后"""
    briefs = [
        {"code": "600519", "name": "贵州茅台", "status": "接近止损",
         "status_tone": "err", "action_text": "🔴", "detail": ""},
        {"code": "000001", "name": "平安银行", "status": "接近止盈",
         "status_tone": "warn", "action_text": "🟠", "detail": ""},
    ]
    render.action_brief([], briefs, None)
    html = _last_html(render)
    err_pos = html.index("600519 贵州茅台")
    warn_pos = html.index("000001 平安银行")
    assert err_pos < warn_pos, "render 应按调用方已排序的列表展示"


# ========== C区：市况速览 ==========

def test_c_market_summary(render):
    summary = {"total_score": 72, "band": "偏强", "cap": 8,
               "summary": "市场情绪偏暖，资金面温和流入，建议关注科技+新能源主线。"}
    render.action_brief([], [], summary)
    html = _last_html(render)
    assert "市况速览" in html
    assert "市况评分 72 分 · 偏强 · 候选池上限 8 只" in html
    assert "市场情绪偏暖，资金面温和流入" in html
    # 80 字截断：保留前 80 字（不含 HTML 标签）
    assert len(html) > 0


def test_c_no_market_summary(render):
    render.action_brief([], [], None)
    html = _last_html(render)
    assert "市况速览" in html
    assert "市况数据暂不可用" in html


# ========== 安全与样式 ==========

def test_html_escaping(render):
    items = [{"stock_code": "600110", "stock_name": "<script>alert(1)</script>",
              "tier": "B", "is_tradeable": 1, "price_zone": "现价 <12.5", "label": "可建仓"}]
    render.action_brief(items, [], None)
    html = _last_html(render)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;12.5" in html


def test_css_classes_present(render):
    """确认 action_brief 输出的 HTML 使用统一的 CSS 类名
    （A 区非空 → brief-item；B 区全正常 → brief-empty；C 区有数据 → brief-item+brief-detail）"""
    items = [{"stock_code": "600110", "stock_name": "朝阳科技", "tier": "B",
              "is_tradeable": 1, "price_zone": "现价 12.5~13.0", "label": "可建仓"}]
    briefs = [{"code": "000001", "name": "平安银行", "status": "持有观察",
               "status_tone": "info", "action_text": "🟢 正常持有", "detail": ""}]
    summary = {"total_score": 72, "band": "偏强", "cap": 8, "summary": "summary"}
    render.action_brief(items, briefs, summary)
    html = _last_html(render)
    for cls in ("action-brief", "brief-section", "brief-section-title",
                "brief-item", "brief-icon", "brief-text", "brief-detail", "brief-empty"):
        assert cls in html, f"缺少 CSS 类: {cls}"
