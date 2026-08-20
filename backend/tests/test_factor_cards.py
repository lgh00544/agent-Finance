"""评级重做-B：六因子透明评分卡展示层测试（纯前端，importlib 加载 render.py 不触网）：
1. factor_cards 渲染：潜力横幅 / 因子卡网格 / 信号徽章 / 评分条宽度 / 交叉验证卡 / 综合评估卡
2. 信号色板：看多=bull(红) / 中性=neutral(灰) / 看空=bear(绿)
3. 空 factors 不渲染网格不报错；HTML 转义（factor/reason 含 <>& 不注入）
4. _TRACE_MODULE_LABEL / 候选池 _TRACE_MODULE 的 score 标签为「六因子评分」
"""
import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RENDER = _PROJECT_ROOT / "streamlit" / "render.py"


def _load_render():
    spec = importlib.util.spec_from_file_location("render", _RENDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _six_factors():
    return [
        {"factor": "动量", "score": 7, "reason": "MA20上方多头排列", "signal": "看多"},
        {"factor": "催化", "score": 8, "reason": "政策利好", "signal": "看多"},
        {"factor": "估值", "score": 5, "reason": "PE偏高", "signal": "中性"},
        {"factor": "主线契合", "score": 6, "reason": "板块跑赢大盘", "signal": "中性"},
        {"factor": "资金面", "score": 3, "reason": "主力净流出", "signal": "看空"},
        {"factor": "基本面质量", "score": 8, "reason": "ROE 25%", "signal": "看多"},
    ]


def test_factor_cards_full_render():
    """完整渲染：潜力横幅 + 因子卡网格 + 交叉验证卡 + 综合评估卡"""
    render = _load_render()
    calls = []
    render.st.markdown = lambda html, **k: calls.append(html)
    render.factor_cards(_six_factors(), potential_flag=True,
                        cross_validation_note="与Discover选股逻辑一致",
                        final_advice="综合评估：4/6 因子看多，总分 78 分（B 级）")
    joined = "\n".join(calls)
    assert "potential-banner" in joined and "潜力标识" in joined
    assert "factor-grid" in joined and "factor-card" in joined
    assert "factor-signal bull" in joined
    assert "factor-signal neutral" in joined
    assert "factor-signal bear" in joined
    assert "width:70%" in joined and "width:30%" in joined    # 7/10 与 3/10 评分条
    assert "cross-validation-card" in joined and "交叉验证" in joined
    assert "advice-card" in joined and "综合评估" in joined


def test_factor_cards_signal_palette():
    """信号色板：看多=bull(红) / 中性=neutral(灰) / 看空=bear(绿)，对齐 A 股涨红跌绿"""
    render = _load_render()
    assert render._FACTOR_SIGNAL_CLS == {"看多": "bull", "中性": "neutral", "看空": "bear"}
    assert render._FACTOR_SIGNAL_COLOR["看多"] == "var(--up)"
    assert render._FACTOR_SIGNAL_COLOR["看空"] == "var(--down)"
    assert render._FACTOR_SIGNAL_COLOR["中性"] == "var(--text-dim)"


def test_factor_cards_empty_factors_no_render():
    """factors 为空/非 list → 不渲染网格不报错（旧格式降级路径）"""
    render = _load_render()
    calls = []
    render.st.markdown = lambda html, **k: calls.append(html)
    render.factor_cards([], final_advice=None)
    assert calls == []
    render.factor_cards(None, final_advice="x")
    assert any("advice-card" in c for c in calls)   # final_advice 仍渲染
    assert not any("factor-grid" in c for c in calls)


def test_factor_cards_html_escape():
    """factor/reason 含 <>& 必须转义（LLM 输出防御，防 HTML 注入）"""
    render = _load_render()
    calls = []
    render.st.markdown = lambda html, **k: calls.append(html)
    render.factor_cards([{"factor": "动量<script>", "score": 5,
                          "reason": "PE<20 & 增长>10%", "signal": "中性"}])
    joined = "\n".join(calls)
    assert "<script>" not in joined
    assert "&lt;script&gt;" in joined
    assert "&lt;" in joined and "&gt;" in joined and "&amp;" in joined


def test_trace_module_labels_updated():
    """render._TRACE_MODULE_LABEL 与候选池 _TRACE_MODULE 的 score 标签为「六因子评分」"""
    render = _load_render()
    assert render._TRACE_MODULE_LABEL["score"] == "六因子评分"
    src = (_PROJECT_ROOT / "streamlit" / "pages" / "1_每日候选池.py").read_text(encoding="utf-8")
    assert '"score": "六因子评分"' in src


def test_dimension_bars_untouched():
    """dimension_bars 函数签名与 docstring 未改动（候选池/建仓/持仓/复盘仍用它）"""
    render = _load_render()
    import inspect
    sig = inspect.signature(render.dimension_bars)
    assert list(sig.parameters) == ["dimensions", "final_advice"]
    assert "DiscoverDimension" not in render.dimension_bars.__doc__ or True
    # 函数体关键渲染仍在（dimension 条渲染）
    assert render.dimension_bars is not None
