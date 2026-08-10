"""路由入口：企业级左侧分组导航（st.navigation）
分组：系统概览 / 选股决策 / 持仓风控 / 策略沉淀；每项带图标 + 中文名称，
选中项自动高亮（配合 render.py 全局 CSS 的左侧色条与 hover 反馈）。
页面脚本全部位于 pages/ 下，仅在此统一注册；全局主题与顶部状态栏由各页面自行注入。
"""
import streamlit as st

st.set_page_config(page_title="A股决策 Agent 系统", page_icon="📊", layout="wide")

pages = st.navigation({
    "系统概览": [
        st.Page("pages/0_系统概览.py", title="系统概览", icon="🏠", default=True),
    ],
    "选股决策": [
        st.Page("pages/1_每日候选池.py", title="每日候选池", icon="📈"),
        st.Page("pages/2_评分报告.py", title="评分报告", icon="⭐"),
        st.Page("pages/3_建仓计划.py", title="建仓计划", icon="🧭"),
    ],
    "持仓风控": [
        st.Page("pages/4_持仓监控.py", title="持仓监控", icon="🛡️"),
        st.Page("pages/5_游资追踪.py", title="游资追踪", icon="🐉"),
        st.Page("pages/8_告警日志.py", title="告警日志", icon="🚨"),
    ],
    "策略沉淀": [
        st.Page("pages/6_交易复盘.py", title="交易复盘", icon="🔁"),
        st.Page("pages/9_交易知识库.py", title="交易知识库", icon="📚"),
        st.Page("pages/10_Agent对话.py", title="Agent 对话", icon="💬"),
        st.Page("pages/11_规则变更记录.py", title="规则变更记录", icon="📜"),
    ],
})
pages.run()
