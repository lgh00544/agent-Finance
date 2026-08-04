"""前端渲染工具：LLM 结构化 JSON → 自然语言展示；原始 JSON 折叠查看

【刚性代码逻辑】仅做字段映射与格式化展示，不产生任何研判内容；
后端存储与 LLM 交互保持结构化 JSON 不变，仅在此层做渲染转换。
时间统一展示格式 YYYY-MM-DD HH:mm（北京时间），浅色小字标注数据生成/检测时间。
"""
import streamlit as st

# 时效标注配色：普通浅灰 / 紧急琥珀（深色主题下均清晰可读）
_TIME_COLOR = "#9CA3AF"
_TIME_HIGHLIGHT = "#F59E0B"


def stock_label(code: str, name: str) -> str:
    """统一股票标识：代码在前、名称紧随（如 600519 贵州茅台）"""
    name = (name or "").strip()
    code = str(code or "").strip()
    if name and name != code:
        return f"{code} {name}"
    return code


def render_dict(data: dict | None) -> None:
    """JSON 字典 → 带小标题的正文段落（列表分点、嵌套字典递归展开）"""
    if not data:
        st.markdown("（无）")
        return
    for key, value in data.items():
        if isinstance(value, dict):
            st.markdown(f"**{key}**")
            _render_nested(value, 1)
        elif isinstance(value, list):
            st.markdown(f"**{key}**")
            for i, item in enumerate(value, 1):
                if isinstance(item, dict):
                    flat = "；".join(f"{k}：{v}" for k, v in item.items()
                                     if not isinstance(v, (dict, list)))
                    st.markdown(f"{i}. {flat or item}")
                else:
                    st.markdown(f"{i}. {item}")
        else:
            st.markdown(f"- **{key}**：{value}")


def _render_nested(data: dict, level: int) -> None:
    pad = "　" * level
    for key, value in data.items():
        if isinstance(value, dict):
            st.markdown(f"{pad}**{key}**")
            _render_nested(value, level + 1)
        elif isinstance(value, list):
            st.markdown(f"{pad}**{key}**")
            for i, item in enumerate(value, 1):
                if isinstance(item, dict):
                    flat = "；".join(f"{k}：{v}" for k, v in item.items()
                                     if not isinstance(v, (dict, list)))
                    st.markdown(f"{pad}{i}. {flat or item}")
                else:
                    st.markdown(f"{pad}{i}. {item}")
        else:
            st.markdown(f"{pad}- **{key}**：{value}")


def raw_json_expander(data, label: str = "查看原始数据", key: str | None = None) -> None:
    """原始 JSON 折叠查看：默认收起，用户主动点击才展开"""
    with st.expander(label, expanded=False, key=key):
        st.json(data)


def time_text(label: str, time_str: str | None, highlight: bool = False) -> None:
    """时效标注：浅色小字（YYYY-MM-DD HH:mm）；紧急信号时间用琥珀色高亮"""
    if not time_str:
        return
    color = _TIME_HIGHLIGHT if highlight else _TIME_COLOR
    st.markdown(
        f'<span style="color:{color};font-size:0.85em">{label}：{str(time_str)[:16]}</span>',
        unsafe_allow_html=True)
