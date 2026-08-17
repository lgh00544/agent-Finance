"""Agent 专属对话：与六个核心 Agent 直接对话交互（规则调教 / 提问答疑 / 多模态学习）

企业级左右布局：左=Agent 导航列表（radio 高亮选中态 + 职责/知识库来源卡片），
右=对话主区域（文字提问/规则调教/多模态学习/对话历史 4 Tab）。
对话历史用统一列表行范式，详情分区展示完整内容/信心度/依据来源。

- 分 Agent 独立对话上下文，仅对应该领域能力，不串扰其他 Agent 规则体系；
- 文字提问：基于专属知识库 + 全局通用知识库回答，标注依据来源与信心度，不越界；
- 规则调教：不盲从，按验证流程给出「采纳/部分采纳/维持原规则」结论与依据；
  采纳规则自动沉淀到对应 Agent 知识库；硬性规则与核心方法论只读，对话无权修改；
- 多模态学习：上传 K线图/战法文档/交易心得 → 识别提炼 → 确认摘要 → 修正标签 → 沉淀知识库；
- 对话历史留存，可回溯每次提问/调教/学习的完整记录。

所有回复遵循：数据标源、无绝对化表述、标注信心度、风控底线不突破。
"""
import json
import time

import streamlit as st

import api_client as api
import chat_cards
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次3：页面头部收敛为 page_header 单行范式（对话看板化在 chat_cards.py，不改） =====
render.page_header(
    "Agent 专属对话（调教 · 答疑 · 知识沉淀）",
    caption="与各核心 Agent 直接对话：规则调教（经校验后生效）、领域答疑（标源+信心度）、"
            "图片学习（K线图/战法文档/交易心得 → 自动提炼沉淀知识库）。"
            "硬性规则与核心方法论只读，任何对话不得修改；重要规则修改必须经校验后生效。",
)

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ================= 六 Agent 元信息 =================
@st.cache_data(ttl=600)  # Agent 元信息几乎不变（名称/职责/知识库来源），10 分钟缓存减少重复请求
def _chat_agents_cached() -> list[dict]:
    return api.chat_agents()


try:
    AGENT_META = {m["agent"]: m for m in _chat_agents_cached()}
except Exception:  # noqa: BLE001 后端未起时降级为静态元信息
    AGENT_META = {
        "discover": {"agent": "discover", "name": "选股发现 Agent", "scope": "全市场候选挖掘",
                     "knowledge": "全局基线+硬性规则+偏好档案+私有知识库+战法知识库"},
        "score": {"agent": "score", "name": "评分分析 Agent", "scope": "单股五维评分",
                  "knowledge": "全局基线+硬性规则+偏好档案+私有知识库+战法知识库"},
        "position": {"agent": "position", "name": "建仓方案 Agent", "scope": "分批建仓方案",
                     "knowledge": "全局基线+硬性规则+偏好档案+私有知识库"},
        "monitor": {"agent": "monitor", "name": "持仓监控 Agent", "scope": "持仓实时监控",
                    "knowledge": "全局基线+硬性规则+偏好档案+私有知识库+战法知识库"},
        "sell": {"agent": "sell", "name": "卖出决策 Agent", "scope": "卖出决策",
                 "knowledge": "全局基线+硬性规则+偏好档案+私有知识库+战法知识库"},
        "review": {"agent": "review", "name": "复盘迭代 Agent", "scope": "卖出复盘与偏好回流",
                   "knowledge": "全局基线+硬性规则+偏好档案+私有知识库+战法知识库"},
    }
AGENTS = list(AGENT_META.keys())

# ================= 公告查询结果结构化卡片 =================
_ANN_SENTIMENT_RENDER = {"利好": "success", "利空": "error", "中性": "info"}


def _render_announcement(r: dict) -> None:
    """公告查询结果卡片：利好/利空/中性标签 + 交叉验证/风险提示 + 公告清单（官方链接可跳转）；
    无公告/抓取失败时明确提示，不输出空泛内容。"""
    ann = r.get("announcement") or {}
    verdict = r.get("announcement_verdict") or {}
    sentiment = str(verdict.get("sentiment") or "")
    with st.container(border=True):
        st.markdown(f"**最新公告查询** · {ann.get('stock_code', '')}"
                    f"（近 {ann.get('query_days', 7)} 日）")
        if verdict:
            kind = _ANN_SENTIMENT_RENDER.get(sentiment, "info")
            icon = {"利好": "📈", "利空": "📉", "中性": "➖"}.get(sentiment, "📋")
            st.markdown(f"{icon} **{sentiment or '待定'}**：{verdict.get('reason', '')}")
            if verdict.get("cross_check"):
                st.markdown(f"**交叉验证**：{verdict['cross_check']}")
            if verdict.get("risk_note"):
                st.markdown(f"**风险提示**：{verdict['risk_note']}")
        items = ann.get("items") or []
        if not items:
            st.warning(ann.get("message", "未查询到该标的近期公开公告"))
        else:
            st.caption(ann.get("message", ""))
            for it in items[:8]:
                url = it.get("url") or ""
                title = str(it["title"])
                if url and url != "链接未提供":
                    title = f"[{title}]({url})"
                st.markdown(f"- {str(it.get('published_at', ''))[:16]} **{title}**"
                            f"（{it.get('source', '') or '东财'} · {it.get('ann_type', '其他')}）")
                if it.get("summary"):
                    st.caption(str(it["summary"])[:120])
            if len(items) > 8:
                st.caption(f"… 共 {len(items)} 条，其余见对话历史 meta")

# ================= 左右布局：左=Agent 列表（选中高亮）+ 职责卡片；右=对话主区域 =================
left, right = st.columns([1, 2.8], gap="medium")
with left:
    st.caption("选择对话 Agent（每个 Agent 独立上下文，互不串扰）")
    sel = st.radio("Agent", AGENTS, format_func=lambda a: AGENT_META[a]["name"],
                   key="chat_agent_sel", label_visibility="collapsed")
    meta = AGENT_META[sel]
    with st.container(border=True):
        render.section_title("职责范围")
        st.markdown(meta["scope"])
    with st.container(border=True):
        render.section_title("知识库来源")
        st.markdown(meta["knowledge"])

with right:
    tab_ask, tab_rule, tab_learn, tab_history = st.tabs(
        ["文字提问", "规则调教", "多模态学习", "对话历史"])

    # ================= 文字提问答疑 =================
    with tab_ask:
        st.markdown(f"向 **{meta['name']}** 提问（基于其专属知识库 + 全局通用知识库回答；"
                    "答案标注依据来源与信心度，超出职责范围会明确说明）")
        with st.form("ask_form"):
            question = st.text_area("问题", height=90,
                                    placeholder="如：当前市况下发现候选后应该优先关注什么？")
            asked = st.form_submit_button("提问（后台处理，约需 10-60 秒）", type="primary")
        if asked and question.strip():
            try:
                resp = api.chat_ask(sel, question.strip())
                st.session_state["_chat_ask_tid"] = resp["task_id"]
                st.toast(f"已提交提问任务（{resp['task_id']}），处理完成后自动展示")
                time.sleep(1)
                st.rerun(scope="app")
            except Exception as exc:  # noqa: BLE001
                render.msg_card("err", "提交失败", "未能提交提问任务，可稍后重试或检查后端服务。",
                                detail=exc)
        tid = st.session_state.get("_chat_ask_tid")
        if tid:
            try:
                task = api.task_detail(tid)
            except Exception:  # noqa: BLE001
                task = None
            if task and task.get("status") == "done" and task.get("result"):
                r = task["result"]
                with st.container(border=True):
                    st.markdown(f"**回答**（信心度 **{r.get('confidence', 0)}/100**）")
                    st.markdown(r.get("answer", ""))
                    if r.get("sources"):
                        render.trace_line("依据来源", source=str(r["sources"]))
                    if r.get("scope_note"):
                        st.info(f"职责边界：{r['scope_note']}")
                    if r.get("announcement"):
                        _render_announcement(r)
                    if st.button("清空本次回答"):
                        st.session_state.pop("_chat_ask_tid", None)
                        st.rerun(scope="app")
            elif task and task.get("status") == "failed":
                render.msg_card("err", "提问处理失败", "后台处理未完成，可重新提问重试。",
                                detail=task.get("error", ""))
                st.session_state.pop("_chat_ask_tid", None)
            elif task and task.get("status") in ("pending", "running"):
                st.info(f"后台处理中（任务 {tid}）……")

    # ================= 规则调教 =================
    with tab_rule:
        st.markdown(f"向 **{meta['name']}** 提出规则修改/新增提案。"
                    "Agent **不盲从**：按验证流程核对硬性规则、核心方法论与现有知识冲突后，"
                    "给出「采纳 / 部分采纳 / 维持原规则」结论与依据。")
        st.markdown("> 硬性规则（HARD_RULES）与核心方法论只读：涉及它们的提案一律维持原规则，"
                    "只能由人工在 `common.py` 中修改。采纳的合理规则自动沉淀到本 Agent 知识库并立即生效。")
        with st.form("rule_form"):
            proposal = st.text_area("规则提案", height=110,
                                    placeholder="如：建议把评分 Agent 对换手率的关注阈值从 >15% 调整为 >12%")
            ruled = st.form_submit_button("提交校验（后台处理）", type="primary")
        if ruled and proposal.strip():
            try:
                resp = api.chat_rule(sel, proposal.strip())
                st.session_state["_chat_rule_tid"] = resp["task_id"]
                st.toast(f"已提交规则校验任务（{resp['task_id']}）")
                time.sleep(1)
                st.rerun(scope="app")
            except Exception as exc:  # noqa: BLE001
                render.msg_card("err", "提交失败", "未能提交规则校验任务，可稍后重试或检查后端服务。",
                                detail=exc)
        rtid = st.session_state.get("_chat_rule_tid")
        if rtid:
            try:
                task = api.task_detail(rtid)
            except Exception:  # noqa: BLE001
                task = None
            if task and task.get("status") == "done" and task.get("result"):
                r = task["result"]
                with st.container(border=True):
                    label = r.get("verdict_label", r.get("verdict", ""))
                    if r.get("verdict") == "adopted":
                        st.success(f"校验结论：**{label}**（已沉淀到 {meta['name']} 知识库，立即生效）")
                    elif r.get("verdict") == "partial":
                        st.warning(f"校验结论：**{label}**（调整后沉淀到知识库，立即生效）")
                    else:
                        st.info(f"校验结论：**{label}**（未修改任何规则）")
                    st.markdown(f"**依据**：{r.get('reason', '')}")
                    if r.get("conflict_note"):
                        st.markdown(f"**冲突核查**：{r['conflict_note']}")
                    if r.get("rule_title"):
                        st.markdown(f"**沉淀标题**：{r['rule_title']}")
                    if r.get("knowledge_id"):
                        st.caption(f"已写入知识库条目 ID：{r['knowledge_id']}"
                                   "（可在「交易知识库」页查看/删除）")
                    if st.button("清空本次校验结果"):
                        st.session_state.pop("_chat_rule_tid", None)
                        st.rerun(scope="app")
            elif task and task.get("status") == "failed":
                render.msg_card("err", "规则校验失败", "后台处理未完成，可重新提交校验重试。",
                                detail=task.get("error", ""))
                st.session_state.pop("_chat_rule_tid", None)
            elif task and task.get("status") in ("pending", "running"):
                st.info(f"校验处理中（任务 {rtid}）……")

    # ================= 多模态上传学习 =================
    with tab_learn:
        st.markdown(f"上传 K线图 / 战法文档 / 交易心得图片，**{meta['name']}** 将自动识别内容、"
                    "提炼核心知识点并建议标签；**确认（可修正标签）后才写入知识库**。")
        st.markdown("> 识别引擎：MiniMax 多模态优先，失败自动降级本地 PaddleOCR。图片上限 15MB。")
        uploaded = st.file_uploader("选择图片（jpg/png）", type=["jpg", "jpeg", "png"])
        ltid = st.session_state.get("_chat_learn_tid")
        task = None
        if ltid:
            try:
                task = api.task_detail(ltid)
            except Exception:  # noqa: BLE001
                task = None
        busy = bool(task and task.get("status") in ("pending", "running"))
        desc = st.text_area("补充说明（可选，≤500字；可描述图片关键要点，识别时辅助聚焦）",
                            key="_chat_learn_desc", height=90, max_chars=500,
                            placeholder="例如：这是某标的周线放量突破形态，重点提炼突破信号与止损位…",
                            disabled=busy)
        st.caption(f"已输入 {len(desc)}/500 字")
        if uploaded is not None and st.button("开始识别与提炼", type="primary", disabled=busy):
            try:
                resp = api.chat_learn(sel, uploaded.getvalue(), uploaded.name, description=desc)
                st.session_state["_chat_learn_tid"] = resp["task_id"]
                st.toast(f"已提交识别任务（{resp['task_id']}），完成后可预览提炼结果")
                time.sleep(1)
                st.rerun(scope="app")
            except Exception as exc:  # noqa: BLE001
                render.msg_card("err", "提交失败", "未能提交识别任务，可稍后重试或检查后端服务。",
                                detail=exc)
        if ltid:
            if task and task.get("status") == "done" and task.get("result"):
                r = task["result"]
                with st.container(border=True):
                    st.markdown(f"**识别与提炼结果**（引擎：{r.get('engine', 'minimax')}）")
                    r_desc = r.get("description") or ""
                    if r_desc:
                        st.markdown(f"**用户补充说明**：{r_desc}")
                    st.markdown(f"**确认摘要**：{r.get('summary', '')}")
                    try:
                        points = json.loads(r.get("points_json") or "[]")
                    except (json.JSONDecodeError, TypeError):
                        points = []
                    if points:
                        st.markdown("**知识点评定**（可修正标题/标签/目标 Agent）")
                        st.session_state.setdefault("_learn_points", {})
                        store = st.session_state["_learn_points"]
                        for i, p in enumerate(points):
                            key = f"_lp_{i}"
                            with st.expander(f"知识点 {i + 1}：{p.get('title', '')}",
                                             expanded=(i == 0)):
                                title = st.text_input(f"标题 {i + 1}", value=p.get("title", ""),
                                                      key=f"{key}_t")
                                content = st.text_area(f"正文 {i + 1}", value=p.get("content", ""),
                                                       height=100, key=f"{key}_c")
                                tags = st.text_input(f"标签 {i + 1}（逗号分隔）",
                                                     value=", ".join(p.get("tags", [])),
                                                     key=f"{key}_g")
                                agent_tag = st.selectbox(f"目标 Agent {i + 1}",
                                                         ["all"] + AGENTS, index=0,
                                                         key=f"{key}_a")
                                store[key] = {"title": title.strip(), "content": content.strip(),
                                              "tags": [t.strip() for t in tags.split(",")
                                                       if t.strip()],
                                              "agent_tag": agent_tag}
                        if st.button("确认并沉淀到知识库（写入后立即生效）", type="primary"):
                            entries = [v for v in store.values()
                                       if v.get("title") and v.get("content")]
                            if not entries:
                                render.msg_card("warn", "没有可保存的有效知识点",
                                                "请补全标题与正文后再确认沉淀。")
                            else:
                                try:
                                    saved = api.chat_learn_confirm(sel, entries)
                                    st.success(f"已沉淀 {saved.get('count', len(entries))} 个知识点"
                                               f"到知识库：{'、'.join(e['title'] for e in
                                                                     saved.get('saved', []))}")
                                    st.session_state.pop("_chat_learn_tid", None)
                                    st.session_state.pop("_learn_points", None)
                                except Exception as exc:  # noqa: BLE001
                                    render.msg_card("err", "沉淀失败",
                                                    "未能写入知识库，可稍后重试。", detail=exc)
                    else:
                        render.msg_card("warn", "未提炼出有效知识点",
                                        "可更换更清晰的图片后重试。")
                    if st.button("丢弃本次识别结果（不落库）"):
                        st.session_state.pop("_chat_learn_tid", None)
                        st.session_state.pop("_learn_points", None)
                        st.rerun(scope="app")
            elif task and task.get("status") == "failed":
                render.msg_card("err", "识别失败", "后台处理未完成，可更换图片后重新上传。",
                                detail=task.get("error", ""))
                st.session_state.pop("_chat_learn_tid", None)
            elif task and task.get("status") in ("pending", "running"):
                st.info(f"识别处理中（任务 {ltid}，大图可能需要 1-2 分钟）……")

    # ================= 对话历史（看板化：摘要卡片 + 状态流转 + 看板/线性双视图） =================
    with tab_history:
        st.markdown(f"**{meta['name']} 对话历史**（最新在前；未展开卡片展示"
                    "结论/风险/待办摘要，可标记跟进状态，看板/线性双视图）")
        chat_cards.render_dashboard(sel, meta["name"])
