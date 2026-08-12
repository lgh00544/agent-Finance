"""前端渲染工具：LLM 结构化 JSON → 自然语言展示；原始 JSON 折叠查看

【刚性代码逻辑】仅做字段映射与格式化展示，不产生任何研判内容；
后端存储与 LLM 交互保持结构化 JSON 不变，仅在此层做渲染转换。
时间统一展示格式 YYYY-MM-DD HH:mm（北京时间），浅色小字标注数据生成/检测时间。
"""
import contextlib
import json
from collections.abc import Iterator

import streamlit as st

# 时效标注配色：普通浅灰 / 紧急琥珀（深色主题下均清晰可读）
_TIME_COLOR = "#9CA3AF"
_TIME_HIGHLIGHT = "#F59E0B"


def stock_label(code: str, name: str) -> str:
    """统一股票标识：代码在前、名称紧随（如 600519 贵州茅台）；
    名称缺失或等于代码（后端未补全到）时显示「名称待补」，禁止只显示纯代码。"""
    name = (name or "").strip()
    code = str(code or "").strip()
    if name and name != code:
        return f"{code} {name}"
    return f"{code} 名称待补"


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


# ================= 全局深色科技感主题（全站唯一视觉体系，纯 CSS 无外部资源） =================
# 色板全部收敛为 CSS 变量（:root 单点），换肤只改一处；徽章/卡片/溯源行/空态为通用组件；
# 数字一律等宽对齐（tabular-nums）；核心数据微发光；微动效 0.2s 过渡，无大面积动画。
_GLOBAL_THEME_CSS = """
<style>
:root {
  /* 背景分层：页面 < 卡片 < 悬浮层 */
  --bg-base: #0f1115; --bg-card: #171a21; --bg-hover: #1e242e; --bg-input: #12151b;
  /* 边框：极细 1px 描边（用户规范 rgba(60,80,120,0.25)） */
  --border: rgba(60, 80, 120, 0.25); --border-hi: rgba(96, 130, 190, 0.35);
  /* 主色科技蓝 */
  --primary: #3b82f6; --primary-dim: #1e3a5f;
  /* 状态色：成功/警告/风险 */
  --up: #ef4444; --down: #10b981; --ok: #10b981; --warn: #f59e0b; --err: #ef4444; --info: #3b82f6;
  /* 评级色：A 红 / B 橙 / C 蓝 */
  --tier-a: #ef4444; --tier-b: #f59e0b; --tier-c: #3b82f6;
  /* 文字：正文 / 次要 / 禁用 */
  --text: #e5e7eb; --text-dim: #9ca3af; --text-mute: #6b7280;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: var(--bg-base); }
/* 数字等宽对齐 + 字号体系（页标题 24 / 模块标题 16 / 正文 14 / 辅助 12） */
html, body, .stMarkdown, [data-testid="stMetricValue"], input, textarea, select, button {
  font-variant-numeric: tabular-nums;
}
[data-testid="stHeading"] h1 { font-size: 24px; font-weight: 600; }
[data-testid="stHeading"] h2 { font-size: 16px; font-weight: 600;
                               border-left: 3px solid var(--primary); padding-left: 0.5rem; }
.stMarkdown p, .stMarkdown li { font-size: 14px; line-height: 1.7; }
[data-testid="stCaptionContainer"] p { font-size: 12px; }
/* 卡片容器（st.container(border=True)）：圆角 8px + 内边距 16px 20px + 极细描边 + 轻内阴影 */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--bg-card); border: 1px solid var(--border-hi); border-radius: 8px;
  padding: 16px 20px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition: background 0.2s ease, border-color 0.2s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: var(--primary-dim); }
[data-testid="stVerticalBlockBorderWrapper"] + [data-testid="stVerticalBlockBorderWrapper"] {
  margin-top: 16px;
}
/* 徽章：评级 A/B/C + 状态 ok/warn/err/info/mute */
.badge {
  display: inline-block; padding: 0.05rem 0.5rem; border-radius: 4px;
  font-size: 0.78em; font-weight: 600; line-height: 1.6;
}
.badge-tier-a { color: var(--tier-a); background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.45); }
.badge-tier-b { color: var(--tier-b); background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.45); }
.badge-tier-c { color: var(--tier-c); background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.45); }
.badge-ok    { color: var(--ok);    background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.45); }
.badge-warn  { color: var(--warn);  background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.45); }
.badge-err   { color: var(--err);   background: rgba(239, 68, 68, 0.15);  border: 1px solid rgba(239, 68, 68, 0.45); }
.badge-info  { color: var(--info);  background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.45); }
.badge-mute  { color: var(--text-dim); background: rgba(156, 163, 175, 0.12); border: 1px solid var(--border); }
/* 徽章别名（游资追踪等页面直接发 badge-a/badge-up 等）：评级 a/b/c 对齐 tier 刻度，方向 up/down 对齐涨跌 */
.badge-a   { color: var(--tier-a); background: rgba(239, 68, 68, 0.15);  border: 1px solid rgba(239, 68, 68, 0.45); }
.badge-b   { color: var(--tier-b); background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.45); }
.badge-c   { color: var(--tier-c); background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.45); }
.badge-up   { color: var(--up);   background: rgba(239, 68, 68, 0.15);    border: 1px solid rgba(239, 68, 68, 0.45); }
.badge-down { color: var(--down); background: rgba(16, 185, 129, 0.15);  border: 1px solid rgba(16, 185, 129, 0.45); }
/* 溯源行：时间/数据源/置信度统一浅色小字，紧急信号琥珀高亮 */
.trace-line { color: var(--text-dim); font-size: 12px; margin: 0.25rem 0; }
.trace-line .hl { color: var(--warn); }
/* 核心数据高亮（顶部栏与核心指标卡）：16px/600 + 状态色 */
.core-num { font-size: 16px; font-weight: 600; color: var(--text);
            text-shadow: 0 0 12px rgba(59, 130, 246, 0.35); }
/* 空态：图标 + 说明 + 可选按钮，虚线框居中（与错误态严格区分） */
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 6px;
               color: var(--text-dim); text-align: center; padding: 1.6rem 0;
               border: 1px dashed var(--border); border-radius: 8px; font-size: 14px; }
.empty-state .empty-icon { font-size: 22px; }
/* ===== 统一提示体系（阻断/提醒/成功/一般 4 级：左侧色条 + 图标 + 标题 + 正文） ===== */
.msg-card { display: flex; gap: 10px; align-items: flex-start; margin: 0.5rem 0;
            padding: 10px 14px; border-radius: 8px; border: 1px solid;
            font-size: 14px; line-height: 1.6; }
.msg-card .msg-ic { line-height: 1.5; }
.msg-card.err  { background: rgba(239, 68, 68, 0.08);  border-color: rgba(239, 68, 68, 0.45);
                 border-left: 3px solid var(--err); }
.msg-card.warn { background: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.45);
                 border-left: 3px solid var(--warn); }
.msg-card.ok   { background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.45);
                 border-left: 3px solid var(--ok); }
.msg-card.info { background: rgba(59, 130, 246, 0.08); border-color: rgba(59, 130, 246, 0.45);
                 border-left: 3px solid var(--info); }
.msg-card .msg-title { font-weight: 600; }
.msg-card .msg-body { color: var(--text-dim); font-size: 13px; margin-top: 2px; }
/* 表单字段原位错误：字段容器（st.container key="fld_*"）内输入框标红边框 */
[class*="st-key-fld_"] input, [class*="st-key-fld_"] textarea,
[class*="st-key-fld_"] [data-baseweb="input"] > div,
[class*="st-key-fld_"] [data-baseweb="select"] > div {
  border-color: var(--err) !important;
}
.field-err { color: var(--err); font-size: 12px; margin-top: 4px; }
.field-err .field-hint { color: var(--text-dim); }
/* 表单错误汇总条：X 项需修正（配合字段原位红框定位） */
.field-summary { margin: 0.5rem 0; padding: 8px 12px; border-radius: 8px; font-size: 13px;
                 color: var(--err); background: rgba(239, 68, 68, 0.08);
                 border: 1px solid rgba(239, 68, 68, 0.45); }
/* 主按钮：深蓝底白字圆角 6px，悬停变亮 0.2s；次按钮：透明+细描边 */
[data-testid="stBaseButton-primary"] {
  background: var(--primary); color: #ffffff; border-radius: 6px;
  transition: filter 0.2s ease;
}
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.15); }
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-tertiary"] {
  background: transparent; border: 1px solid var(--border-hi); border-radius: 6px;
  color: var(--text-dim); transition: filter 0.2s ease;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-tertiary"]:hover {
  filter: brightness(1.25);
}
/* 表格：深色主题底色（表头/斑马纹/hover 由 config.toml dark 主题提供，此处兜底主色强调） */
[data-testid="stDataFrame"] { background: var(--bg-card); }
/* ===== 企业级列表行（图二范式）：左=状态圆点+主标题(加粗)+副标题(灰)，右=辅助信息+操作按钮 ===== */
[data-testid="stVerticalBlockBorderWrapper"][class*="st-key-lrow_"] {
  padding: 10px 16px; margin-bottom: 8px; box-shadow: none;
}
.item-main { display: flex; align-items: center; gap: 10px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.dot-tier-a, .dot-err { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.5); }
.dot-tier-b, .dot-warn { background: #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.5); }
.dot-tier-c, .dot-info { background: #3b82f6; box-shadow: 0 0 6px rgba(59, 130, 246, 0.5); }
.dot-ok { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.5); }
.dot-mute { background: #6b7280; }
/* 状态点别名（游资追踪等页面直接发 dot-a/dot-up 等）：评级 a/b/c 对齐 tier 刻度，方向 up/down 对齐涨跌 */
.dot-a { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.5); }
.dot-b { background: #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.5); }
.dot-c { background: #3b82f6; box-shadow: 0 0 6px rgba(59, 130, 246, 0.5); }
.dot-up { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.5); }
.dot-down { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.5); }
.item-title { font-size: 14px; font-weight: 600; color: var(--text); }
.item-sub { font-size: 12px; color: var(--text-dim); margin-top: 3px; line-height: 1.6; }
.item-meta { font-size: 12px; color: var(--text-dim); text-align: right; margin-bottom: 6px; }
.item-meta .up { color: var(--up); } .item-meta .down { color: var(--down); }
/* 详情分区小标题（左侧主色竖条 + 浅弱底色 + 统一字号，L2 子分区弱底色规范） */
.section-title { font-size: 13px; font-weight: 600; color: var(--text);
                 border-left: 3px solid var(--primary); padding-left: 8px;
                 background: rgba(59, 130, 246, 0.06);
                 padding-top: 3px; padding-bottom: 3px;
                 margin: 10px 0 8px; }
/* 详情内关键词高亮 / 数字强调（L4 详情栏目可复用，重点栏目按需包裹） */
.kw { color: var(--primary); font-weight: 600;
      background: rgba(59, 130, 246, 0.12); padding: 0 2px; border-radius: 2px; }
.num { font-variant-numeric: tabular-nums; color: var(--primary); font-weight: 600; }
/* 嵌套卡片（详情内分区）：更紧凑的次级卡片 */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {
  padding: 12px 16px; margin-top: 10px; background: rgba(255, 255, 255, 0.02);
  box-shadow: none;
}
/* 指标卡网格（首页概览/性能统计） */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
             gap: 16px; margin: 4px 0 12px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border);
             border-radius: 8px; padding: 14px 18px; }
.stat-label { font-size: 12px; color: var(--text-dim); }
.stat-value { font-size: 22px; font-weight: 600; margin-top: 4px; color: var(--text);
              font-variant-numeric: tabular-nums; }
.stat-value.up { color: var(--up); } .stat-value.down { color: var(--down); }
.stat-value.ok { color: var(--ok); } .stat-value.warn { color: var(--warn); }
.stat-value.err { color: var(--err); }
.stat-sub { font-size: 12px; color: var(--text-mute); margin-top: 2px; }
/* 左侧导航：分组 + 图标 + 选中高亮（左侧色条）+ hover 反馈；侧边栏深于主背景 */
[data-testid="stSidebar"] { background: #0d0f13; }
[data-testid="stSidebarNav"] { padding: 0.4rem 0.6rem; }
[data-testid="stSidebarNav"] a {
  border-radius: 6px; margin: 2px 0; transition: background 0.15s ease;
}
[data-testid="stSidebarNav"] a:hover { background: rgba(59, 130, 246, 0.12); }
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: rgba(59, 130, 246, 0.18); border-left: 3px solid var(--primary);
}
[data-testid="stSidebarNavLink"], .stSidebarNavLink {
  border-radius: 6px; margin: 2px 0; transition: background 0.15s ease;
}
[data-testid="stSidebarNavLink"]:hover, .stSidebarNavLink:hover {
  background: rgba(59, 130, 246, 0.12);
}
[data-testid="stSidebarNavLink"][aria-current="page"], .stSidebarNavLink[aria-current="page"] {
  background: rgba(59, 130, 246, 0.18); border-left: 3px solid var(--primary);
}
[data-testid="stSidebarNavSectionHeader"], .stSidebarNavSectionHeader {
  color: var(--text-mute); font-size: 12px; letter-spacing: 0.06em;
  padding: 0.2rem 0.4rem;
}
/* Agent 对话页：左侧 Agent 列表（radio 增强为导航列表样式，选中高亮 + hover 反馈） */
[data-testid="stRadio"] > div[role="radiogroup"] > label {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; margin: 2px 0; border-radius: 8px;
  border: 1px solid transparent; cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
  background: rgba(59, 130, 246, 0.12);
}
[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
  background: rgba(59, 130, 246, 0.18); border-left: 3px solid var(--primary);
  border-color: var(--border-hi);
}
/* ===== 推理留痕卡片（结论卡默认展开 + 推理分层折叠，可解释化展示） ===== */
/* 推理层：左侧色条 + 浅一级文字 + 悬停 0.2s 过渡；五类色对应五维推理 */
.trace-layer { font-size: 13px; color: var(--text-dim); line-height: 1.7;
               border-left: 3px solid var(--info); padding: 4px 10px;
               margin: 2px 0 6px; white-space: pre-wrap;
               transition: color 0.2s ease, border-color 0.2s ease; }
.trace-layer:hover { color: var(--text); }
.trace-layer.fact    { border-color: var(--info); }
.trace-layer.tech    { border-color: #8b5cf6; }
.trace-layer.capital { border-color: #f59e0b; }
.trace-layer.fund    { border-color: #10b981; }
.trace-layer.risk    { border-color: #ef4444; }
/* 规则徽章行：引用规则 chip，深色描边 */
.rule-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 2px; }
.rule-chip { font-size: 12px; color: var(--text-dim); padding: 1px 10px;
             border-radius: 999px; border: 1px solid var(--border-hi);
             background: rgba(59, 130, 246, 0.08); transition: color 0.2s ease; }
.rule-chip:hover { color: var(--text); }
/* 留痕头部：模块徽章 + 元信息小字 */
.trace-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
              margin-bottom: 4px; }
.trace-meta { font-size: 12px; color: var(--text-mute); }
/* ===== Agent 对话历史：单轮对话单元卡片 ===== */
/* 顶部徽章行：类型/状态徽章 + 弱化时间小字 */
.chat-top-chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
                  font-size: 12px; color: var(--text-dim); }
.chat-top-chips .t { color: var(--text-mute); }
/* 提问区：右对齐 + 浅一级背景，模拟用户发送视角（key 前缀 chat_q_） */
[class*="st-key-chat_q_"] {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  margin: 4px 0 10px;
  margin-left: auto;
  max-width: 94%;
}
[class*="st-key-chat_q_"] p { margin: 0; }
/* 收起态摘要：首行文字 + 底部渐隐遮罩，直观提示内容未完全展示 */
.chat-preview {
  font-size: 13px; color: var(--text-dim); line-height: 1.7;
  padding: 8px 12px; margin: 4px 0;
  border: 1px dashed var(--border); border-radius: 8px;
  max-height: 64px; overflow: hidden;
  -webkit-mask-image: linear-gradient(180deg, #000 55%, transparent 100%);
  mask-image: linear-gradient(180deg, #000 55%, transparent 100%);
}
/* 底部辅助信息：弱化小字，不抢占核心内容注意力 */
.chat-foot { font-size: 12px; color: var(--text-mute); margin-top: 6px; }
/* 多模态学习·用户补充说明：弱化信息块，与提问原文区分 */
.learn-desc { font-size: 12px; color: var(--text-dim); line-height: 1.6;
  padding: 6px 10px; margin: 4px 0;
  border: 1px dashed var(--border); border-radius: 6px; background: var(--bg-input); }
.learn-desc b { color: var(--text); }
/* ===== Agent 对话看板化：摘要卡三行缩写 + 看板列头 ===== */
.board-col-head { display: flex; align-items: center; gap: 6px; margin: 4px 0 10px; }
.board-col-head .t { color: var(--text-mute); font-size: 12px; }
.board-sum { margin: 6px 0 4px; font-size: 12px; color: var(--text-dim); line-height: 1.7; }
.board-line { margin: 2px 0; }
.board-line .sum-k { color: var(--info); font-weight: 600; }
.board-risk .sum-k { color: var(--warn); }
.board-act .sum-k { color: var(--ok); }
/* ===== 维度归因条（v3.0 白盒框架）：维度名 + 评分条 + 结论色点 + 建议文本 ===== */
.dim-summary { margin: 0.3rem 0 0.6rem; }
.dim-block { margin: 0.45rem 0; }
.dim-head { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.dim-name { color: var(--text); font-weight: 600; min-width: 5.5em; white-space: nowrap; }
.dim-track { flex: 1; height: 8px; background: var(--bg-input); border: 1px solid var(--border);
             border-radius: 4px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 4px; transition: width 0.3s ease; }
.dim-score { font-size: 12px; color: var(--text-dim); min-width: 2.8em; text-align: right; }
.dim-verdict { font-size: 11px; padding: 0 0.45rem; border-radius: 3px; font-weight: 600;
               white-space: nowrap; }
.dim-verdict.support { color: var(--up); background: rgba(239, 68, 68, 0.12);
                       border: 1px solid rgba(239, 68, 68, 0.35); }
.dim-verdict.neutral { color: var(--text-dim); background: rgba(156, 163, 175, 0.12);
                       border: 1px solid var(--border); }
.dim-verdict.risk { color: var(--warn); background: rgba(245, 158, 11, 0.12);
                    border: 1px solid rgba(245, 158, 11, 0.35); }
.dim-advice { font-size: 12px; color: var(--text-dim); line-height: 1.6;
              margin: 2px 0 0 5.5em; }
/* 综合评估高亮卡（v3.0 主结论） */
.advice-card { border: 1px solid var(--primary-dim); border-left: 3px solid var(--primary);
               background: rgba(59, 130, 246, 0.06); border-radius: 8px;
               padding: 10px 14px; margin: 0.5rem 0; }
.advice-card .advice-title { font-size: 12px; color: var(--info); font-weight: 600; }
.advice-card .advice-body { font-size: 14px; color: var(--text); line-height: 1.7; margin-top: 4px; }
/* ===== 通用折叠规范：一级模块卡片（对齐对话历史页卡片标准） ===== */
/* 模块标题：加粗主色高亮居左 + 左侧主色竖条（与 h2 子标题视觉签名统一，L1 大模块） */
.fold-title { font-size: 15px; font-weight: 700; color: var(--primary);
              border-left: 3px solid var(--primary); padding-left: 8px; }
/* 卡片紧凑内边距：减少标题栏无效空白，纵向更紧凑 */
[class*="st-key-foldcard_"] { padding-top: 12px; padding-bottom: 14px; }
</style>
"""


def apply_global_theme() -> None:
    """全站深色科技感主题注入（每个页面标题前调用一次，幂等）"""
    st.markdown(_GLOBAL_THEME_CSS, unsafe_allow_html=True)


_BADGE_TONES = {"a": "badge-tier-a", "b": "badge-tier-b", "c": "badge-tier-c",
                "ok": "badge-ok", "warn": "badge-warn", "err": "badge-err",
                "info": "badge-info", "mute": "badge-mute"}


def badge(text: str, tone: str = "info") -> None:
    """徽章：评级 a/b/c、状态 ok/warn/err/info/mute（纯展示样式，无任何研判语义）"""
    st.markdown(f'<span class="badge {_BADGE_TONES.get(tone, "badge-info")}">{text}</span>',
                unsafe_allow_html=True)


def kw(text: str) -> str:
    """关键词高亮 HTML 片段（L4 详情栏目）：主色加粗浅底，拼入 unsafe_allow_html 的 markdown 字符串"""
    return f'<span class="kw">{text}</span>'


def num(text) -> str:
    """数字强调 HTML 片段（L4 详情栏目）：等宽主色加粗，拼入 unsafe_allow_html 的 markdown 字符串"""
    return f'<span class="num">{text}</span>'


def trace_line(label: str, time_str: str | None = None, source: str | None = None,
               confidence=None, highlight: bool = False) -> None:
    """强制追溯项统一呈现：时间 + 数据源 + 置信度 一行浅色小字；
    紧急信号（highlight=True）时间琥珀色高亮。缺失字段不渲染，但字段级数据不删减。"""
    parts = []
    if time_str:
        parts.append(f"{label}：{str(time_str)[:16]}")
    if source:
        parts.append(f"数据源：{source}")
    if confidence is not None and str(confidence).strip():
        parts.append(f"置信度：{confidence}")
    if not parts:
        return
    cls = " class='hl'" if highlight else ""
    st.markdown(f'<div class="trace-line"><span{cls}>{"　·　".join(parts)}</span></div>',
                unsafe_allow_html=True)


def empty_state(text: str, icon: str = "📭", action_label: str = "",
                action_key: str = "") -> None:
    """统一空态提示（虚线框居中）：图标 + 说明文案 + 可选下一步操作按钮（点击刷新）。
    禁止空白一片；空状态与错误状态样式严格区分。"""
    st.markdown(f'<div class="empty-state"><span class="empty-icon">{icon}</span>'
                f'<div>{text}</div></div>', unsafe_allow_html=True)
    if action_label and action_key:
        if st.button(action_label, key=action_key):
            st.rerun()


# ================= 统一提示体系（4 级：阻断/提醒/成功/空态，全站唯一规范） =================
_MSG_ICON = {"err": "⛔", "warn": "⚠️", "ok": "✅", "info": "ℹ️"}


def msg_card(tone: str, title: str, message: str = "", detail=None) -> None:
    """业务规则/状态提示条：左侧色条 + 图标 + 标题 + 可选正文；
    detail（原始错误/技术日志）折叠收纳默认不展示，用户只读友好文案。
    tone: err 阻断 / warn 提醒 / ok 成功 / info 一般（色值对齐全局体系）"""
    html = (f'<div class="msg-card {tone}"><span class="msg-ic">{_MSG_ICON.get(tone, "ℹ️")}</span>'
            f'<div><span class="msg-title">{title}</span>')
    if message:
        html += f'<div class="msg-body">{message}</div>'
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)
    if detail:
        with st.expander("技术日志（排查用，默认收起）", expanded=False):
            st.code(str(detail), language=None)


def error_card(title: str, message: str = "", detail=None, retry_key: str = "",
               retry_label: str = "重试", actions: tuple[tuple[str, str], ...] = ()) -> None:
    """数据加载/提交失败局部错误卡片（阻断级）：友好文案 + 原因 + 卡片右侧操作按钮 + 技术日志折叠。
    actions 为 ((按钮key, 按钮文案), ...)，渲染在卡片右侧（重试无需滚到页面底部）；
    传 retry_key 时自动生成重试按钮。用于列表/详情等模块级失败，不整页报错；
    原始异常只进折叠日志，不展示给用户。"""
    if retry_key:
        actions = ((retry_key, retry_label),) + tuple(a for a in actions if a[0] != retry_key)
    if actions:
        c_left, c_right = st.columns([5, 1.3], vertical_alignment="center")
        with c_left:
            msg_card("err", title, message, detail=detail)
        with c_right:
            for key, label in actions:
                if st.button(label, key=key, use_container_width=True):
                    st.rerun()
    else:
        msg_card("err", title, message, detail=detail)


def classify_api_error(exc: Exception) -> tuple[str, str, str]:
    """API 调用失败分类（数据页加载用）：返回 (标题, 具体原因+建议操作, 技术日志摘要)。
    仅前端展示层分类，按异常类型区分后端服务/网络超时/数据库/解析/未知，
    便于用户判断下一步操作；原始异常完整信息进折叠日志供排查。"""
    import json  # noqa: PLC0415 局部导入避免顶部加重全局依赖
    from datetime import datetime  # noqa: PLC0415

    import requests  # noqa: PLC0415

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(exc, requests.exceptions.ConnectionError):
        return ("后端服务连接失败", "请确认后端服务已启动后点击「重试」；持续失败时检查 8000 端口服务状态。",
                f"{ts} · ConnectionError（无法连接后端服务）\n{exc}")
    if isinstance(exc, requests.exceptions.Timeout):
        return ("请求超时", "网络波动或后端繁忙，请稍后点击「重试」。",
                f"{ts} · Timeout（超过 60s 未响应）\n{exc}")
    if isinstance(exc, requests.exceptions.HTTPError):
        resp = exc.response
        status = resp.status_code if resp is not None else "?"
        body = (resp.text or "")[:500] if resp is not None else ""
        req_desc = f"{exc.request.method} {exc.request.url}" if exc.request is not None else "?"
        if any(kw in body.lower() for kw in ("database", "sql", "query")):
            return ("数据库查询失败", "后端数据连接异常，请稍后点击「重试」，或查看后端日志。",
                    f"{ts} · HTTP {status} · {req_desc}\n{body or exc}")
        return (f"后端服务异常（HTTP {status}）", "后端处理出错，可点击「重试」，或展开技术日志排查。",
                f"{ts} · HTTP {status} · {req_desc}\n{body or exc}")
    if isinstance(exc, json.JSONDecodeError):
        return ("数据解析失败", "后端返回了无法解析的数据，请点击「重试」或检查后端版本。",
                f"{ts} · JSONDecodeError\n{exc}")
    return ("加载失败", "发生未知错误，可点击「重试」或展开技术日志排查。",
            f"{ts} · {type(exc).__name__}\n{exc}")


def set_field_errors(errors: dict) -> None:
    """记录表单字段校验错误（field → 原因），表单提交逻辑写入，渲染时原位展示"""
    st.session_state["_fld_errs"] = errors


def get_field_error(field: str) -> str:
    """读取指定字段的错误原因（无错误返回空串）"""
    return (st.session_state.get("_fld_errs") or {}).get(field, "")


def get_field_errors() -> dict:
    """读取当前全部字段错误（表单汇总条用）"""
    return dict(st.session_state.get("_fld_errs") or {})


def field_error(field: str, message: str = "", hint: str = "") -> None:
    """表单字段原位错误标记：字段容器（st.container(key=f"fld_{field}")）内的输入框
    自动标红框，字段下方显示原因 + 填写示例。message 为空（无错误）则不渲染。
    禁止只在页面底部堆一段纯文字错误说明。"""
    if not message:
        return
    html = f'<div class="field-err">⚠️ {message}'
    if hint:
        html += f' <span class="field-hint">（{hint}）</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def field_summary(errors: dict | None = None, label_map: dict | None = None) -> None:
    """表单错误汇总条「X 项需修正」：列明需修正字段（配合各字段原位红框逐一定位）；
    errors 缺省时读取当前 session 错误集（提交后 rerun 仍保持展示）"""
    if errors is None:
        errors = get_field_errors()
    if not errors:
        return
    names = [label_map.get(k, k) for k in errors] if label_map else list(errors)
    st.markdown(f'<div class="field-summary">⛔ 表单有 <b>{len(errors)}</b> 项需修正：'
                f'{"、".join(f"「{n}」" for n in names)}（红色字段已原位标出）</div>',
                unsafe_allow_html=True)


def field_ok(value) -> bool:
    """表单/OCR 字段有效性判定（纯展示层）：有值即有效；0 是合法数值（清仓记录，不标错误）"""
    if value is None:
        return False
    if isinstance(value, float) and value != value:  # NaN
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def record_list(items: list, render_fn, batch: int = 20, key: str = "rl",
                empty_text: str = "暂无数据。") -> None:
    """懒加载列表（全站统一分页）：首屏渲染前 batch 条，点「加载更多」增量展示；
    render_fn(item, index) 渲染单条；切换筛选条件时 key 变化自动回到首屏。"""
    if not items:
        empty_state(empty_text)
        return
    visible = st.session_state.get(key, batch)
    for i, item in enumerate(items[:visible]):
        render_fn(item, i)
    if len(items) > visible:
        if st.button(f"加载更多（已显示 {visible} / {len(items)}）", key=f"more_{key}"):
            st.session_state[key] = visible + batch
            st.rerun()


# ================= 企业级列表行 / 分区卡片 / 指标卡（图二范式） =================

def list_item(key: str, title: str, subtitle: str = "", dot: str = "mute",
              meta: str = "", actions: tuple[str, ...] = ("查看详情",)) -> int:
    """企业级列表行：左=状态圆点+主标题(加粗)+副标题(灰色小字)，右=辅助信息+操作按钮组；
    行高统一、分割线极淡。返回被点击操作按钮的下标（-1 表示无点击）。
    actions 多于 1 个时按钮横向等分（避免竖排过高）。"""
    with st.container(key=f"lrow_{key}", border=True):
        c1, c2 = st.columns([4.2, 1.5], vertical_alignment="center")
        with c1:
            if dot:
                st.markdown(f'<div class="item-main"><span class="dot dot-{dot}"></span>'
                            f'<span class="item-title">{title}</span></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="item-title">{title}</div>', unsafe_allow_html=True)
            if subtitle:
                st.markdown(f'<div class="item-sub">{subtitle}</div>', unsafe_allow_html=True)
        with c2:
            if meta:
                st.markdown(f'<div class="item-meta">{meta}</div>', unsafe_allow_html=True)
            clicked = -1
            if len(actions) > 1:
                cols = st.columns(len(actions))
                for i, (col, label) in enumerate(zip(cols, actions)):
                    with col:
                        if st.button(label, key=f"act_{key}_{i}", use_container_width=True):
                            clicked = i
            else:
                for i, label in enumerate(actions):
                    if st.button(label, key=f"act_{key}_{i}", use_container_width=True):
                        clicked = i
            return clicked


def list_item_toggle_actions(key: str, title: str, subtitle: str = "", dot: str = "mute",
                             meta: str = "",
                             actions: tuple[str, ...] = ("查看详情",),
                             default_open: bool = False,
                             scope: str | None = None) -> tuple[bool, bool]:
    """列表行 + 操作按钮组 + 「查看详情」展开管理，两个展开状态互不干扰：
    actions 末位按钮 = 查看详情（open_{key}），其余按钮 = 操作面板（op_{key}）。
    返回 (操作面板是否展开, 详情是否展开)，调用方按各自状态渲染对应内容。
    scope = 批量操作前缀：存在 grpdef_<scope> 时以其作为未操作项的默认展开态
    （配合 batch_fold_bar 的「全部展开/全部收起」，新加载项自动跟随组状态）。"""
    default = st.session_state.get(f"grpdef_{scope}") if scope else None
    if default is None:
        default = default_open
    opened = st.session_state.get(f"open_{key}", default)
    op_state = st.session_state.get(f"op_{key}", False)
    # 末位动作按钮双向标签：展开态切换为「收起详情」，收起态保持「查看详情」
    actions = (tuple(actions[:-1]) + (("收起详情" if opened else "查看详情"),)
               if actions else actions)
    clicked = list_item(key, title, subtitle, dot, meta, actions)
    if clicked == len(actions) - 1:  # 末位 = 查看详情
        opened = not opened
        st.session_state[f"open_{key}"] = opened
        st.rerun()
    elif clicked >= 0:               # 其余按钮 = 操作类
        op_state = not op_state
        st.session_state[f"op_{key}"] = op_state
        st.rerun()
    return st.session_state.get(f"op_{key}", False), st.session_state.get(f"open_{key}", default)


def list_item_toggle(key: str, title: str, subtitle: str = "", dot: str = "mute",
                     meta: str = "", default_open: bool = False,
                     scope: str | None = None) -> bool:
    """列表行 + 「查看详情」展开管理：点击自动切换展开/收起，返回当前是否展开；
    调用方在返回 True 时渲染详情卡片。
    scope 传入批量操作前缀后，默认展开态跟随该组「全部展开/全部收起」的组默认值
    （grpdef_<scope>，批量操作后新加载项自动跟随，刷新页面恢复 default_open）。"""
    _, opened = list_item_toggle_actions(key, title, subtitle, dot, meta, ("查看详情",),
                                         default_open=default_open, scope=scope)
    return opened


@contextlib.contextmanager
def fold_module(scope: str, title: str, meta: str = "", default_open: bool = True,
                batch: tuple[str, list] | None = None) -> Iterator[bool]:
    """一级模块卡片（全系统折叠规范，100% 对齐对话历史页卡片标准）：
    独立圆角卡片 + 顶部操作栏（左=模块主标题加粗主色高亮居左 + 辅助说明弱化小字，
    右=「收起 ▲/展开 ▼」轻量文字按钮，与对话历史页按钮同款）；
    batch=(prefix, keys) 时标题栏下方渲染模块内「全部展开/全部收起」；
    默认展开；会话内状态保留，刷新恢复默认。
    调用方模式：`with render.fold_module(scope, title, meta=...) as opened: 内容...`。"""
    sid = f"mod_{scope}"
    opened = st.session_state.get(sid, default_open)
    with st.container(border=True, key=f"foldcard_{scope}"):
        h1, h2 = st.columns([5, 1.1], vertical_alignment="center")
        with h1:
            st.markdown(f'<div class="chat-top-chips"><span class="fold-title">{title}</span>'
                        + (f'<span class="t">{meta}</span>' if meta else "")
                        + "</div>", unsafe_allow_html=True)
        with h2:
            if st.button("收起 ▲" if opened else "展开 ▼", key=f"foldtg_{scope}",
                         use_container_width=True):
                st.session_state[sid] = not opened
                st.rerun()
        if batch:
            prefix, keys = batch
            batch_fold_bar(prefix, keys, label="")
        yield opened


def batch_fold_bar(prefix: str, keys: list[str], label: str = "",
                   default_open: bool = False) -> None:
    """二级列表批量操作栏（全系统折叠规范）：「全部展开 / 全部收起」一键切换；
    同时写入组默认态 grpdef_<prefix>，之后新加载的列表项自动跟随批量状态；
    刷新页面恢复 default_open。"""
    c1, c2, c3 = st.columns([1.1, 1.1, 4], vertical_alignment="center")
    with c1:
        if st.button("全部展开", key=f"fold_open_{prefix}", use_container_width=True):
            for k in keys:
                st.session_state[f"open_{k}"] = True
            st.session_state[f"grpdef_{prefix}"] = True
            st.toast(f"已全部展开（{len(keys)} 项）")
            st.rerun()
    with c2:
        if st.button("全部收起", key=f"fold_close_{prefix}", use_container_width=True):
            for k in keys:
                st.session_state[f"open_{k}"] = False
            st.session_state[f"grpdef_{prefix}"] = False
            st.toast(f"已全部收起（{len(keys)} 项，仅保留摘要）")
            st.rerun()
    with c3:
        if label:
            st.caption(label)


def dismissible_error(title: str, message: str = "", detail=None,
                      retry_key: str = "", dismiss_key: str = "err",
                      retry_label: str = "重试") -> None:
    """可收起错误条（全系统折叠规范）：模块底部错误提示 + 「重试」+ 一键收起；
    收起后显示一条极弱提示与「重新显示」入口，不占用核心视觉区域。
    dismiss_key 同模块稳定值，刷新页面后自动重新展示。"""
    if st.session_state.get(f"err_hide_{dismiss_key}"):
        c1, c2 = st.columns([5, 1])
        with c1:
            st.caption("模块加载失败提示已收起。")
        with c2:
            if st.button("重新显示", key=f"err_show_{dismiss_key}"):
                st.session_state.pop(f"err_hide_{dismiss_key}", None)
                st.rerun()
        return
    actions = ()
    if retry_key:
        actions = ((retry_key, retry_label),)
    actions += ((f"err_x_{dismiss_key}", "收起"),)
    c_left, c_right = st.columns([5.5, 1.2], vertical_alignment="center")
    with c_left:
        msg_card("err", title, message, detail=detail)
    with c_right:
        for key, label in actions:
            if st.button(label, key=key, use_container_width=True):
                if key == f"err_x_{dismiss_key}":
                    st.session_state[f"err_hide_{dismiss_key}"] = True
                st.rerun()


def section_title(text: str) -> None:
    """详情分区小标题（左侧主色竖条 + 统一字号）"""
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


# ================= 持仓止盈/仓位计划卡片（与系统概览/持仓监控页共用，同源展示） =================
_TP_STATUS_TONE = {"持有观察": "mute", "接近止盈": "warn", "接近止损": "err", "减仓预警": "err"}
_TP_GREEN = "#10B981"   # 止盈位（绿，与全站 ok/down 色一致）
_TP_RED = "#EF4444"     # 止损位（红，与全站 up/err 色一致）
_TP_ACTION_DEFAULT = {"接近止损": "减仓/清仓", "减仓预警": "减仓", "接近止盈": "准备减仓",
                      "持有观察": "持有"}


def position_plan_card(key: str, label: str, plan: dict,
                       core_action: str = "", compact: bool = False) -> None:
    """单只持仓的止盈/仓位计划卡片（4 固定信息模块，与系统概览页同源）：
    标的头部（状态标签 + 异动标记 + 核心操作建议）→ 核心点位一行（默认直接展示）
    → 底部补充（时间/数据源/降级标注）→ 展开详情（分档止盈计划/止损与风控规则/
    仓位管理指引/计算依据说明）。展开态与批量栏共用 open_{key}。"""
    status = plan.get("status") or "持有观察"
    tone = _TP_STATUS_TONE.get(status, "info")
    action = core_action or _TP_ACTION_DEFAULT.get(status, "持有")
    anomaly = plan.get("anomaly")
    folded = not st.session_state.get(f"open_{key}", False)
    tl, tr = st.columns([5, 1.1], vertical_alignment="center")
    with tl:
        st.markdown(f'<div class="item-main"><span class="badge badge-{tone}">{status}</span>'
                    f'<span class="item-title">{label}</span>'
                    + (f'<span class="badge badge-warn">异动更新</span>' if anomaly else "")
                    + "</div>", unsafe_allow_html=True)
    with tr:
        if st.button("展开 ▼" if folded else "收起 ▲", key=f"tp_tg_{key}",
                     use_container_width=True):
            st.session_state[f"open_{key}"] = not st.session_state.get(f"open_{key}", False)
            st.rerun()
    parts = [f'<span style="color:{_TP_GREEN};font-weight:600">🟢 第一止盈位 '
             f'{plan.get("tp1") or "—"} 元</span>（触发减仓 1/3 锁利）',
             f'<span style="color:{_TP_GREEN};font-weight:600">🟢 第二止盈位 '
             f'{plan.get("tp2") or "—"} 元</span>（触发再减仓 1/3）',
             f'<span style="color:{_TP_RED};font-weight:600">🔴 止损位 '
             f'{plan.get("current_stop") or "—"} 元</span>（C3 硬止损线）',
             f'<span style="color:var(--text-dim)">📊 当前仓位 {plan.get("shares") or "—"} 股'
             f' / 占总仓位 {plan.get("single_pct") if plan.get("single_pct") is not None else "—"}%'
             "</span>"]
    st.markdown("　".join(parts), unsafe_allow_html=True)
    st.markdown(f'<div class="trace-line">核心操作建议：**{action}**'
                f'　·　{plan.get("calc_time", "")}　·　数据源：与持仓监控同源'
                + ('　·　K线降级模式（网络受限，固定比例估算）' if plan.get("degraded") else "")
                + "</div>", unsafe_allow_html=True)
    if folded:
        return
    with st.container(border=True):
        section_title("分档止盈计划")
        st.markdown(f"1. **第一目标止盈位 {plan.get('tp1') or '—'} 元**："
                    "取「近期前高压力位」与「成本+8~10%」较低值；触发条件：放量突破/触及前高；"
                    "操作：减仓 1/3 锁定部分利润，止损线上移至成本价 "
                    f"{plan.get('ladder_stop_1') or '—'} 元")
        st.markdown(f"2. **第二目标止盈位 {plan.get('tp2') or '—'} 元**："
                    "黄金分割扩展位（0.618）与前期重要压力位共振；"
                    "操作：再减仓 1/3，剩余仓位移动止盈持有")
        st.markdown(f"3. **终极止盈规则**：{plan.get('trailing_note')}；"
                    f"当前移动止盈线 {plan.get('trailing_line') or '—'} 元，跌破全部止盈离场")
    with st.container(border=True):
        section_title("止损与风控规则")
        st.markdown(f"- 初始 C3 止损位：成本 × 0.92 = **{plan.get('c3_stop') or '—'} 元**"
                    "（硬止损线，跌破无条件离场）；当前生效止损 "
                    f"**{plan.get('current_stop') or '—'} 元**")
        st.markdown(f"- 阶梯止损上移：到达第一止盈位后止损上移至成本价 "
                    f"（{plan.get('ladder_stop_1') or '—'} 元）；到达第二止盈位后上移至第一止盈位 "
                    f"（{plan.get('ladder_stop_2') or '—'} 元）")
    with st.container(border=True):
        section_title("仓位管理指引")
        st.markdown(f"- 当前持仓：{plan.get('shares') or '—'} 股，成本 "
                    f"{plan.get('cost') or '—'} 元，单票仓位 "
                    f"{plan.get('single_pct') if plan.get('single_pct') is not None else '—'}%"
                    f"（C1 单票上限 {plan.get('c1_cap_pct', 30)}%，"
                    f"{'符合' if plan.get('c1_ok') else '**超限需减仓**'}）")
        if plan.get("total_pct") is not None:
            st.markdown(f"- 总仓位约束：当前整体仓位 {plan['total_pct']}%"
                        f"（C2 总仓上限 {plan.get('c2_cap_pct', 60)}%"
                        f"，{'符合' if plan['total_pct'] <= plan.get('c2_cap_pct', 60) else '**超限**'}）")
        st.markdown(f"- 加仓条件：{plan.get('add_condition') or '（当前不满足加仓前提）'}")
        st.markdown(f"- 减仓条件：{plan.get('reduce_condition') or '（除止盈分档外暂无波段减仓触发）'}")
    with st.container(border=True):
        section_title("计算依据说明")
        st.markdown("- 止盈位计算逻辑：基于前期高点压力位、黄金分割位（0.618）、"
                    "成本加 8%~10% 保守区间综合得出，并结合量能/板块热度/游资动向动态调整")
        st.markdown("- 仓位建议依据：基于标的走势、市况评分与 C1 单票上限 / C2 总仓上限红线")
        st.markdown("- 引用规则：C1 单票仓位上限 30% / C2 总仓位上限 60% / C3 硬止损（成本×0.92）"
                    "/ 分档锁利与移动止盈 / 波段操作（跌破 MA10 且量能放大先减半）——"
                    "对应知识库风控与止盈仓位规则条目")
        st.caption("计算结果已写入推理留痕（source_module=position_monitor），"
                   "纠察/复盘 Agent 可追溯验证；建议仅作参考，最终交易由人工判断。")


def stat_cards(items: list[dict]) -> None:
    """指标卡网格：items=[{label, value, sub?, tone?}]；tone: up/down/ok/warn/err/mute"""
    cards = []
    for it in items:
        tone = it.get("tone") or "mute"
        sub = f'<div class="stat-sub">{it["sub"]}</div>' if it.get("sub") else ""
        cards.append(f'<div class="stat-card"><div class="stat-label">{it["label"]}</div>'
                     f'<div class="stat-value {tone}">{it["value"]}</div>{sub}</div>')
    st.markdown(f'<div class="stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


# ================= 维度归因白盒展示（v3.0） =================
_DIM_VERDICT_CLS = {"支持": "support", "中性": "neutral", "风险": "risk"}
_DIM_FILL_COLOR = {"支持": "#ef4444", "中性": "#9ca3af", "风险": "#f59e0b"}


def dimension_bars(dimensions: list[dict], final_advice: str | None = None) -> None:
    """维度归因白盒展示（v3.0 主结论）：每维 = 维度名 + 评分条（score/100）+ verdict 色点 + advice；
    自动统计「N/5 维支持」徽章；final_advice 用高亮卡展示。纯展示层映射，无任何研判语义；
    兼容旧数据（缺 dimensions 时仅展示 final_advice，两者都缺则不渲染）。"""
    dims = [d for d in (dimensions or []) if isinstance(d, dict)]
    if not dims:
        if final_advice:
            _advice_card(final_advice)
        return
    support_n = 0
    rows = []
    for d in dims:
        dim = str(d.get("dim") or d.get("name") or "维度")
        try:
            score = float(d.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(100.0, score))
        verdict = str(d.get("verdict") or "中性")
        advice = str(d.get("advice") or "")
        if verdict == "支持":
            support_n += 1
        vcls = _DIM_VERDICT_CLS.get(verdict, "neutral")
        color = _DIM_FILL_COLOR.get(verdict, "#9ca3af")
        width = f"{score:.0f}%"
        advice_html = f'<div class="dim-advice">{advice}</div>' if advice else ""
        rows.append(
            f'<div class="dim-block"><div class="dim-head">'
            f'<span class="dim-name">{dim}</span>'
            f'<span class="dim-track"><span class="dim-fill" '
            f'style="width:{width};background:{color}"></span></span>'
            f'<span class="dim-score">{score:.0f}</span>'
            f'<span class="dim-verdict {vcls}">{verdict}</span></div>{advice_html}</div>')
    support_html = (f'<span class="badge badge-info">{support_n}/{len(dims)} 维支持</span>'
                    if dims else "")
    st.markdown(f'<div class="dim-summary">{support_html}</div>{"".join(rows)}',
                unsafe_allow_html=True)
    if final_advice:
        _advice_card(final_advice)


def _advice_card(final_advice: str) -> None:
    """综合评估高亮卡（v3.0 主结论）"""
    st.markdown(f'<div class="advice-card"><div class="advice-title">综合评估（主结论）</div>'
                f'<div class="advice-body">{final_advice}</div></div>', unsafe_allow_html=True)


def svc_cards(connections: list[dict]) -> None:
    """系统服务状态横向卡片：状态圆点 + 服务名 + 状态说明 + 最后检测时间"""
    cards = []
    for c in connections:
        ok = bool(c.get("ok"))
        tone = "ok" if ok else "err"
        cards.append(
            f'<div class="stat-card"><div class="stat-label">'
            f'<span class="dot dot-{tone}"></span>　{c.get("name", "")}</div>'
            f'<div class="stat-value {tone}">{"运行正常" if ok else "异常"}</div>'
            f'<div class="stat-sub">{c.get("detail", "")}</div>'
            f'<div class="stat-sub">最后检测：{str(c.get("checked_at") or "")[:16]}</div></div>')
    st.markdown(f'<div class="stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def alert_list(rows: list[dict], key: str = "alert_list",
               empty_text: str = "暂无告警记录。", scope: str | None = None) -> None:
    """告警行列表（统一范式，供告警日志页与持仓监控页共用）：
    严重度圆点（严重红/警告橙/一般蓝）+ 股票代码+名称+类型 + 消息摘要 + 时间+推送状态 + 查看详情；
    scope 传入批量操作前缀后，展开态跟随「全部展开/全部收起」组默认值。"""
    SEV_DOT = {"critical": "err", "warning": "warn", "info": "info"}
    ACTION_MAP = {"hold": "持有", "reduce": "减仓", "exit": "清仓"}

    def _fn(a: dict, _i: int) -> None:
        sev = a.get("severity") or "info"
        label = stock_label(a["stock_code"], a["stock_name"])
        full = str(a.get("message") or "")
        msg = full[:90] + ("…" if len(full) > 90 else "")
        meta = (f'{str(a.get("created_at") or "")[:16]}　'
                f'飞书推送 {"✅" if a.get("pushed") else "—"}')
        if list_item_toggle(f"{key}_{a['id']}", f"{label} · {a.get('alert_type', '')}",
                            subtitle=msg, dot=SEV_DOT.get(sev, "mute"), meta=meta,
                            scope=scope):
            with st.container(border=True):
                trace_line("告警触发时间", a["created_at"], source="LLM 生成",
                           confidence=(a.get("signal") or {}).get("confidence"),
                           highlight=sev in ("warning", "critical") or a.get("action") != "hold")
                st.markdown(a["message"])
                act = a.get("action")
                if act:
                    st.markdown(f"- **建议动作**：{ACTION_MAP.get(act, act)}")
                st.markdown("**LLM 研判结论**")
                render_dict(a.get("signal"))
                raw_json_expander(a.get("signal"), key=f"raw_{key}_{a['id']}")

    record_list(rows, _fn, batch=20, key=key, empty_text=empty_text)


def submit_task(kind: str, params: dict | None = None, label: str = "后台任务") -> bool:
    """提交后台任务：重复触发（后端 409）与后端不可达时显示中文提示，返回是否成功"""
    import requests

    from api_client import submit_task as api_submit
    try:
        api_submit(kind, params)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 409:
            msg_card("warn", f"{label}正在执行中", "请等待其完成后再试，避免重复触发。")
        else:
            msg_card("err", f"{label}提交失败", "请确认后端服务正常运行后重试。",
                     detail=exc)
        return False
    except Exception as exc:  # noqa: BLE001 后端不可达统一提示，不向页面抛原始报错
        msg_card("err", f"{label}提交失败", "请确认后端服务正常运行后重试。", detail=exc)
        return False
    st.toast(f"{label}已提交后台，可切换页面继续操作")
    return True


def time_text(label: str, time_str: str | None, highlight: bool = False) -> None:
    """时效标注：浅色小字（YYYY-MM-DD HH:mm）；紧急信号时间用琥珀色高亮"""
    if not time_str:
        return
    color = _TIME_HIGHLIGHT if highlight else _TIME_COLOR
    st.markdown(
        f'<span style="color:{color};font-size:0.85em">{label}：{str(time_str)[:16]}</span>',
        unsafe_allow_html=True)


@st.fragment(run_every="5s")
def task_status_area() -> None:
    """页面顶部统一后台任务状态区：每 5 秒轮询最近任务，任务全部结束自动消失

    - pending/running：琥珀色「后台任务执行中」明细 + 可切换页面继续操作提示；
    - failed：红色提示 + 一键重试（复用原任务ID重新入队）；
    - 任务完成/失败瞬间弹一次性 toast（session_state 标记，不重复弹）；
      任务完成时自动刷新整页（候选池等模块立即展示最新结果，无需手动刷新）；
    - 无未完成任务时本区域不渲染任何内容；
    - 节流：距上次请求 <5s 的 rerun（含用户交互触发的整页 rerun）直接复用
      会话内结果，不重复向后端打请求（fragment 定时刷新独立按 5s 调度）。
    """
    import time as _t

    from api_client import recent_tasks, retry_task

    now = _t.time()
    last = st.session_state.get("_task_fetch_ts", 0.0)
    if now - last >= 5:
        try:
            tasks = recent_tasks(limit=8) or []
            st.session_state["_task_fetch_ts"] = now
            st.session_state["_task_cache"] = tasks
        except Exception:  # noqa: BLE001 后端暂不可达时静默跳过，页面主体照常
            return
    else:
        tasks = st.session_state.get("_task_cache") or []
    active = [t for t in tasks if t["status"] in ("pending", "running")]
    failed = [t for t in tasks if t["status"] == "failed"]

    # 完成/失败一次性 toast（仅状态从进行中变为终态时弹一次）；
    # 完成瞬间自动刷新整页（scope=app），候选池/持仓等数据立即展示最新结果
    seen = st.session_state.setdefault("_task_seen", {})
    for t in tasks:
        prev = seen.get(t["task_id"])
        seen[t["task_id"]] = t["status"]
        if prev in ("pending", "running") and t["status"] == "done":
            st.toast(f"任务完成：{t['label']}")
            st.rerun(scope="app")
        elif prev in ("pending", "running") and t["status"] == "failed":
            st.toast(f"任务失败：{t['label']}，可点击重试", icon="⚠️")
    if len(seen) > 60:  # 只保留最近标记，防无限增长
        st.session_state["_task_seen"] = {k: v for k, v in list(seen.items())[-40:]}

    if not active and not failed:
        return
    if active:
        st.markdown(
            f'<span style="color:{_TIME_HIGHLIGHT}">⏳ 后台任务执行中（{len(active)} 个）</span>'
            f'<span style="color:{_TIME_COLOR};font-size:0.85em">　任务已提交后台，'
            f'可切换页面继续操作</span>',
            unsafe_allow_html=True)
        for t in active:
            st.markdown(f"- **{t['label']}**（提交于 {str(t['submitted_at'])[:16]}）")
    if failed:
        st.error(f"有 {len(failed)} 个后台任务执行失败：")
        for t in failed:
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{t['label']}**　`{t['task_id']}`\n\n{t['error']}")
            if c2.button("重试", key=f"retry_{t['task_id']}"):
                retry_task(t["task_id"])


# ================= 全局顶部常驻状态栏 =================
# 固定于原生顶部栏（stHeader，z-index 1000）之下、z-index 999，不随页面滚动消失；
# 布局规范：width 100% 撑满视口、左右内边距对称 8px 24px（无单侧大 padding）、
# align-items: center 全部内容统一垂直居中同一基线、line-height 1.5 紧凑行高；
# 背景 #0f1115 + 底部 1px 描边 rgba(60,80,120,0.25)，与全局主题同色板；
# 信息按「账户资产」「大盘指数」两组展示（组间竖线分隔 + 组标签），
# 核心数据（总资产/总盈亏/上证指数）加粗加大；
# 主内容区与侧边栏同步预留 60px 顶部内边距，保证首屏标题与核心操作区不被遮挡
_TOP_BAR_CSS = """
<style>
[data-testid="stMain"] { padding-top: 60px; }
[data-testid="stSidebarContent"] { padding-top: 60px; }
.top-status-bar {
  position: fixed; top: 2.95rem; left: 0; right: 0; z-index: 999;
  width: 100%; box-sizing: border-box;
  display: flex; align-items: center; flex-wrap: wrap;
  column-gap: 1rem; row-gap: 0.2rem;
  padding: 8px 24px; font-size: 0.92rem; line-height: 1.5;
  background: #0f1115; border-bottom: 1px solid rgba(60, 80, 120, 0.25);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
  transition: padding-left 0.2s ease;
}
/* 侧边栏展开（aria-expanded=true，默认宽 300px）时主内容区右移，顶部栏内容左缘
   同步右移与主内容区左缘对齐；收起（aria-expanded=false，侧边栏移出视口）自动回落 24px。
   侧边栏宽度可拖拽 200-600px，非默认宽度时仅存在拖拽差值内的微小偏差 */
body:has([data-testid="stSidebar"][aria-expanded="true"]) .top-status-bar {
  padding-left: calc(300px + 24px);
}
.top-status-bar .bar-label { color: #9ca3af; font-size: 0.82em; margin-right: 0.3rem; }
.top-status-bar .bar-group {
  display: inline-flex; align-items: center; flex-wrap: wrap;
  column-gap: 1.15rem; row-gap: 0.1rem;
  padding-left: 0.9rem; border-left: 1px solid rgba(60, 80, 120, 0.25);
}
.top-status-bar .bar-group-label {
  color: #6b7280; font-size: 0.76em; letter-spacing: 0.06em;
  margin-right: 0.15rem;
}
.top-status-bar b { font-weight: 700; color: #e5e7eb; }
.top-status-bar .bar-key { font-weight: 700; font-size: 1.08em; color: #ffffff; }
.top-status-bar .up { color: #ef4444; font-weight: 700; }
.top-status-bar .down { color: #10b981; font-weight: 700; }
.top-status-bar .flat { color: #9ca3af; }
.top-status-bar .stale { color: #f59e0b; font-size: 0.8em; }
</style>
"""
_COLOR_UP = "up"
_COLOR_DOWN = "down"
_COLOR_FLAT = "flat"


def _bar_money(value) -> str:
    """金额千分位（None 显示 —）"""
    if value is None:
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _bar_pct(value) -> str:
    """百分比显示（None 显示 —）"""
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _bar_sign(value) -> str:
    """正红负绿（A 股习惯）：>0 → up，<0 → down，其余 flat"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _COLOR_FLAT
    return _COLOR_UP if v > 0 else (_COLOR_DOWN if v < 0 else _COLOR_FLAT)


def _t_now() -> float:
    """当前时间戳（节流判定基准）"""
    import time

    return time.time()


def _bar_stale_fetch(state_key: str, fn):
    """接口失败时返回上次成功缓存值（标注「上次数据」）；无缓存返回 (None, 错误标记) 显示「数据加载中」"""
    try:
        data = fn()
        st.session_state[state_key] = data
        return data, ""
    except Exception as exc:  # noqa: BLE001 后端暂不可达时降级展示，不向页面抛原始报错
        return st.session_state.get(state_key), f"更新失败（{type(exc).__name__}）"


@st.fragment(run_every="60s")
def top_status_bar() -> None:
    """全局顶部常驻状态栏（所有页面固定显示，不随滚动消失）

    左=北京时间（每分钟自动刷新）；中=账户核心资产 5 项（双数据路径：有 OCR 账户基准
    用券商真实值，否则按总资金设定估算并标注「估算」；盈亏正红负绿）；
    右=三大指数（名称+点位+涨跌幅+更新时间）。
    「账户明细 / 指数详情」可点击展开查看详细数据；接口失败显示「数据加载中」或
    上次缓存值并标注，不向页面抛原始报错。
    """
    from datetime import datetime, timedelta, timezone

    import api_client as api

    st.markdown(_TOP_BAR_CSS, unsafe_allow_html=True)

    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    # 节流：距上次拉取 <60s 的 rerun 复用会话内结果（交互 rerun 不重复打后端；
    # 失败降级逻辑仍由 _bar_stale_fetch 的 session 缓存兜底）
    if _t_now() - st.session_state.get("_bar_fetch_ts", 0.0) >= 60:
        acc, acc_err = _bar_stale_fetch("_bar_account", api.account_summary)
        idx, idx_err = _bar_stale_fetch("_bar_indices", api.market_indices)
        st.session_state["_bar_fetch_ts"] = _t_now()
    else:
        acc = st.session_state.get("_bar_account")
        idx = st.session_state.get("_bar_indices")
        acc_err = idx_err = ""

    parts = [f'<span class="bar-label">北京时间</span><b>{now}</b>']

    # ---------- 中：账户资产组（组标签 + 组内分隔，核心数据加粗加大） ----------
    acc_parts = ['<span class="bar-group-label">账户资产</span>']
    if acc:
        total = acc.get("total_asset")
        estimate_tag = ('<span class="stale">估算</span>'
                        if (acc.get("source") == "estimate" and total is not None) else "")
        acc_parts.append(f'<span class="bar-label">总资产</span>'
                         f'<b class="bar-key">{_bar_money(total)}{estimate_tag}</b>')
        acc_parts.append(f'<span class="bar-label">总持仓成本</span><b>{_bar_money(acc.get("total_cost"))}</b>')
        pnl = acc.get("pnl_amount")
        if pnl is not None:
            acc_parts.append(f'<span class="bar-label">总盈亏</span>'
                             f'<b class="{_bar_sign(pnl)}">{_bar_money(pnl)}（{_bar_pct(acc.get("pnl_pct"))}）</b>')
        else:
            acc_parts.append(f'<span class="bar-label">总盈亏</span><b>—</b>')
        acc_parts.append(f'<span class="bar-label">整体仓位</span><b>{_bar_pct(acc.get("position_pct"))}</b>')
        acc_parts.append(f'<span class="bar-label">可用资金</span><b>{_bar_money(acc.get("available_cash"))}</b>')
        if acc_err:
            acc_parts.append(f'<span class="stale">账户数据{acc_err}，显示上次数据</span>')
    else:
        hint = "数据加载中" if acc_err else "—"
        acc_parts.append(f'<span class="bar-label">总资产</span><b>{hint}</b>')
        acc_parts.append(f'<span class="bar-label">可用资金</span><b>{hint}</b>')
        acc_parts.append(f'<span class="bar-label">整体仓位</span><b>{hint}</b>')
    parts.append(f'<span class="bar-group">{"".join(acc_parts)}</span>')

    # ---------- 右：大盘指数组（组标签 + 上证指数加粗） ----------
    idx_parts = ['<span class="bar-group-label">大盘指数</span>']
    if idx:
        for it in idx.get("indices") or []:
            label = it.get("name") or it.get("code") or ""
            pct = it.get("change_pct")
            key_cls = " bar-key" if label in ("上证指数", "上证综指") else ""
            if pct is None:
                idx_parts.append(f'<span class="bar-label">{label}</span><b>—</b>')
            else:
                idx_parts.append(f'<span class="bar-label">{label}</span>'
                                 f'<b class="{_bar_sign(pct)}{key_cls}">'
                                 f'{_bar_money(it.get("price"))} {pct:+.2f}%</b>')
        if idx.get("updated_at"):
            idx_parts.append(f'<span class="bar-label">更新时间</span>'
                             f'<span class="stale">{idx["updated_at"]}</span>')
        if idx_err:
            idx_parts.append(f'<span class="stale">指数{idx_err}，显示上次数据</span>')
    else:
        idx_parts.append(f'<span class="bar-label">指数</span><b>{"数据加载中" if idx_err else "—"}</b>')
    parts.append(f'<span class="bar-group">{"".join(idx_parts)}</span>')

    st.markdown(f'<div class="top-status-bar">{"".join(parts)}</div>', unsafe_allow_html=True)

    # ---------- 展开详情（默认收起：单行 expander 入口，不占多列挤压主区） ----------
    with st.expander("查看账户明细 / 指数详情", expanded=False):
        if acc is None:
            st.caption("暂无账户数据。")
        elif acc.get("source") == "estimate":
            st.caption("暂无券商账户基准：总资产/可用资金/整体仓位按「总资金设定 + 持仓实时盈亏」估算。"
                       "上传持仓截图 OCR 识别并经人工确认保存账户基准后，自动切换为券商真实值。")
        else:
            b = acc.get("baseline") or {}
            st.caption(f"账户基准来自券商持仓截图（人工确认，{b.get('trade_date', '')} 保存）；"
                       f"总盈亏/总持仓成本随持仓与实时行情自动计算。")
        # 账户数据可空（接口失败/未配置基准时 acc=None），明细渲染必须容忍 None（2026-08-06 修复）
        if acc is not None:
            pnl_sign = _bar_sign(acc.get("pnl_amount"))
            for label, value, colored in [
                ("总资产", _bar_money(acc.get("total_asset")), False),
                ("总持仓成本", _bar_money(acc.get("total_cost")), False),
                ("持仓市值", _bar_money(acc.get("market_value")), False),
                ("总盈亏", _bar_money(acc.get("pnl_amount")), True),
                ("总盈亏比例", _bar_pct(acc.get("pnl_pct")), True),
                ("整体仓位占比", _bar_pct(acc.get("position_pct")), False),
                ("可用资金", _bar_money(acc.get("available_cash")), False),
            ]:
                if colored:
                    st.markdown(f'- {label}：**<span class="{pnl_sign}">{value}</span>**',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f"- {label}：**{value}**")
            if acc.get("quote_error"):
                st.caption(f"⚠️ 行情刷新失败：{acc['quote_error']}（市价相关数值可能不准确）")

    if idx:
        st.markdown("**指数详情**")
        for it in idx.get("indices") or []:
            pct = it.get("change_pct")
            cls = _bar_sign(pct)
            if pct is None:
                st.markdown(f"- **{it.get('name', it.get('code', ''))}**："
                            f"{_bar_money(it.get('price'))}（—）")
            elif pct > 0:
                mark = "涨"
            elif pct < 0:
                mark = "跌"
            else:
                mark = "平"
            if pct is not None:
                st.markdown(f"- **{it.get('name', it.get('code', ''))}**：{_bar_money(it.get('price'))} "
                            f"（<span class='{cls}'>{mark} {pct:+.2f}%</span>）", unsafe_allow_html=True)
        st.caption(f"指数数据更新时间：{idx.get('updated_at', '—')}")
        if idx_err:
            st.caption(f"⚠️ 指数行情更新失败：{idx_err}（显示上次缓存值）")


# ================= 推理留痕卡片（结论卡默认展开 + 推理分层折叠，可解释化展示） =================

_TRACE_MODULE_LABEL = {"discover": "选股研判", "score": "五维评分", "position": "建仓方案",
                       "alert": "监控预警", "review": "交易复盘", "sell": "卖出决策"}
_TRACE_LAYERS = (
    ("fact_basis", "事实依据（输入数据快照）", "fact"),
    ("technical_reasoning", "技术面推理", "tech"),
    ("capital_reasoning", "资金面推理", "capital"),
    ("fundamental_reasoning", "基本面推理", "fund"),
    ("risk_reasoning", "风险推理", "risk"),
)


def _esc(text: str) -> str:
    """HTML 转义（LLM 输出含 <>& 时防止破坏布局）"""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _parse_json_text(raw) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, (dict, list)) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def trace_card(trace: dict, key: str) -> None:
    """AI 研判推理留痕卡（可解释化统一范式）：
    头部=模块徽章+标的+日期+置信度+数据源；结论卡默认展开；五层推理折叠（色条+浅一级文字）；
    引用规则徽章；原始报文折叠。trace 为 /api/traces/{id} 完整详情，纯展示无判断。"""
    module = _TRACE_MODULE_LABEL.get(trace.get("source_module", ""),
                                     trace.get("source_module", ""))
    conf = trace.get("confidence")
    conf_text = f"置信度 {conf:.0%}" if isinstance(conf, (int, float)) and conf > 0 else ""
    with st.container(border=True):
        st.markdown(
            f'<div class="trace-head"><span class="badge badge-info">{_esc(module)}</span>'
            f'<span class="item-title">{_esc(stock_label(trace.get("stock_code", ""), trace.get("stock_name", "")))}</span>'
            f'<span class="trace-meta">{_esc(trace.get("generate_date", ""))}'
            f'{(" · " + conf_text) if conf_text else ""}'
            f'{(" · " + _esc(trace.get("data_source", ""))) if trace.get("data_source") else ""}'
            f'　{_esc(trace.get("create_time", ""))}</span></div>',
            unsafe_allow_html=True)
        # 结论卡：默认展开（可解释化的核心：先给结论）
        with st.expander("最终结论（默认展开）", expanded=True, key=f"{key}_concl"):
            conclusion = _parse_json_text(trace.get("final_conclusion"))
            if conclusion:
                render_dict(conclusion if isinstance(conclusion, dict) else {"结论": conclusion})
            else:
                st.markdown("（该模块此轮未输出结构化结论）")
        # 推理分层：折叠展示，色条区分五维，浅一级文字
        for field, label, tone in _TRACE_LAYERS:
            text = (trace.get(field) or "").strip()
            if not text:
                continue
            with st.expander(label, expanded=False, key=f"{key}_{field}"):
                st.markdown(f'<div class="trace-layer {tone}">{_esc(text)}</div>',
                            unsafe_allow_html=True)
        # 引用规则徽章（rule_refs 逗号分隔文本 → chips）
        refs = [x.strip() for x in str(trace.get("rule_refs") or "").split(",") if x.strip()]
        if refs:
            chips = "".join(f'<span class="rule-chip">{_esc(x)}</span>' for x in refs)
            st.markdown(f'<div class="rule-chips">{chips}</div>', unsafe_allow_html=True)
        raw_json_expander(trace, key=f"{key}_raw")


# ================= 规则变更记录卡（一键采纳自动落地：变更对比 + 回滚，复盘页与记录页共用） =================

_RULE_TYPE_LABEL = {"soft": "提示词软规则", "hard": "代码硬规则"}
_RULE_PRIO_LABEL = {"high": "高优先级", "medium": "中优先级", "low": "低优先级"}


def rule_type_label(rule_type: str) -> str:
    return _RULE_TYPE_LABEL.get(rule_type, rule_type or "—")


def rule_priority_label(priority: str) -> str:
    return _RULE_PRIO_LABEL.get(priority, priority or "—")


def rule_change_card(rc: dict, key: str) -> None:
    """规则变更完整详情卡（全透明）：溯源行 + 变更前后对比 + 落地元数据 + 预期效果与风险；
    status=active 时附带「一键回滚」表单（原因必填留痕）。纯展示 + 人工回滚，无任何自动判断。"""
    active = rc.get("status") == "active"
    with st.container(border=True):
        render_meta = f'<span class="badge badge-{"ok" if active else "err"}">' \
                      f'{_esc("生效中" if active else "已回滚")}</span>' \
                      f'<span class="badge badge-info">{_esc(rule_type_label(rc.get("rule_type", "")))}</span>' \
                      f'<span class="item-title">{_esc(rc.get("rule_name", ""))}</span>' \
                      f'<span class="trace-meta">变更 {str(rc.get("created_at") or "")[:16]}'
        if rc.get("operator"):
            render_meta += f" · 操作人 {_esc(rc['operator'])}"
        if rc.get("rollback_time"):
            render_meta += f" · 回滚 {str(rc['rollback_time'])[:16]}"
        render_meta += "</span>"
        st.markdown(f'<div class="trace-head">{render_meta}</div>', unsafe_allow_html=True)

        # 变更前后对比（左右分栏）
        with st.container(border=True):
            st.markdown("**变更对比**")
            c1, c2 = st.columns(2)
            with c1:
                st.caption("变更前（此前生效状态）")
                st.markdown(f"<div class='trace-layer fact'>{_esc(rc.get('before_text') or '（无）')}</div>",
                            unsafe_allow_html=True)
            with c2:
                st.caption("变更后（采纳后生效内容）")
                st.markdown(f"<div class='trace-layer tech'>{_esc(rc.get('after_text') or '（无）')}</div>",
                            unsafe_allow_html=True)

        # 落地元数据与理由（全透明，文件路径仅展示）
        with st.container(border=True):
            st.markdown("**落地说明**")
            st.markdown(f"- 规则类型：{rule_type_label(rc.get('rule_type', ''))}（"
                        f"{'全局底线，全部 Agent 无条件遵守' if rc.get('rule_type') == 'hard' else '参考权重，非死条件'}）")
            st.markdown(f"- 归属模块：{_esc(rc.get('target_agent') or '—')} · "
                        f"标的：{_esc(rc.get('stock_name') or rc.get('stock_code') or '—')} · "
                        f"来源复盘 review_id={rc.get('review_id') or '—'}")
            if rc.get("file_path"):
                st.markdown(f"- 文件路径（仅展示元数据，系统不写源码文件）：{_esc(rc['file_path'])}")
            if rc.get("insert_position"):
                st.markdown(f"- 建议插入位置：{_esc(rc['insert_position'])}")
            st.caption("落地方式：系统自动注入（规则存库，全部 Agent 下次任务自动携带，LLM 缓存自动失效）。")
        if rc.get("reason") or rc.get("evidence"):
            with st.container(border=True):
                st.markdown("**建议理由与依据**")
                if rc.get("reason"):
                    st.markdown(f"- {_esc(rc['reason'])}")
                if rc.get("evidence"):
                    st.markdown(f"- 事实依据：{_esc(rc['evidence'])}")
        if rc.get("expected_effect") or rc.get("risk_note"):
            with st.container(border=True):
                st.markdown("**预期效果与风险**")
                if rc.get("expected_effect"):
                    st.markdown(f"- 预期效果：{_esc(rc['expected_effect'])}")
                if rc.get("risk_note"):
                    st.markdown(f"- 风险提示：{_esc(rc['risk_note'])}")
        if not active:
            if rc.get("rollback_reason"):
                st.caption(f"已回滚 · 原因：{_esc(rc['rollback_reason'])}")
            return
        # 一键回滚（原因必填留痕，全程可追溯）
        with st.expander("一键回滚（恢复变更前状态）", expanded=False, key=f"{key}_rollback"):
            with st.form(key=f"{key}_rb_form"):
                reason = st.text_area("回滚原因（必填，多行）",
                                      placeholder="例如：该规则与近期行情特征不匹配 / 规则过于激进，需要撤下",
                                      key=f"{key}_rb_reason")
                if st.form_submit_button("确认回滚并留痕", type="primary"):
                    if not reason.strip():
                        st.error("回滚原因不能为空")
                    else:
                        try:
                            api_rollback_rule_change(rc.get("id"), reason.strip())
                            st.success("已回滚并留痕，全部 Agent 立即停止携带该规则。")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001 回滚失败统一提示
                            msg_card("err", "回滚失败", "请确认后端服务正常运行后重试。", detail=exc)


def api_rollback_rule_change(rid: int, reason: str) -> dict:
    """延迟导入 api_client（与 submit_task 同模式，避免顶层循环依赖）"""
    from api_client import rollback_rule_change as _fn

    return _fn(rid, reason)
