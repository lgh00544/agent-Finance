"""Agent 对话历史：问答配对 + 单轮对话单元卡片渲染

【核心逻辑】「用户提问 + AI 回答」永久绑定为单轮对话单元，一一对应：
- 后端落库时 assistant 记录 meta.user_msg_id 已指向配对 user 记录（qa/rule 类型），
  本模块纯前端按此字段精确配对，不改数据库、不改 Agent 调用；
- learn 类型未写 user_msg_id，按 id 相邻顺序配对（上传 → 摘要为连续写入）；
- 无关联的旧数据（迁移前历史）fallback 相邻顺序配对；
- 孤儿 user 记录独立成卡（状态「无回答」）；孤儿 assistant（如 learn 确认追加记录）
  并入最近一个同类单元，保证不丢记录。

【交互】默认全部展开、回答完整可见；单条收起/展开 + 批量「全部展开/全部收起」；
收起状态存 session_state（刷新即恢复默认展开；加载更多的新单元天然默认展开）。
状态键均带 agent 前缀，切换 Agent 互不串扰。
"""
import re

import streamlit as st

# ==================== 问答配对（纯函数，可单测） ====================

_TYPE_LABEL = {"qa": ("提问", "info"), "rule": ("调教", "warn"), "learn": ("学习", "ok"),
               "batch": ("批量验证", "info")}
_VERDICT_LABEL = {"adopted": "采纳", "partial": "部分采纳", "maintained": "维持原规则"}
_VERDICT_TONE = {"adopted": "ok", "partial": "warn", "maintained": "info"}


def pair_messages(messages: list[dict]) -> list[dict]:
    """对话历史消息列表（id 降序）→ 单轮对话单元列表（最新在前）。

    单元结构: {key, user(提问记录|None), answers(回答记录列表), kind, status, max_id, created_at}
    status: ok=有回答 / orphan=无回答的提问或游离回答。
    """
    if not messages:
        return []
    ordered = sorted(messages, key=lambda m: m.get("id") or 0)  # id 升序重建时序
    user_by_id = {m["id"]: m for m in ordered if m.get("role") == "user"}
    assistants = [m for m in ordered if m.get("role") != "user"]

    units: list[dict] = []
    used_user: set[int] = set()
    pending: list[dict] = []  # 未能精确配对的 assistant

    # 1) meta.user_msg_id 精确配对（qa/rule 标准路径）
    for a in assistants:
        uid = (a.get("meta") or {}).get("user_msg_id")
        u = user_by_id.get(uid) if uid is not None else None
        if u is not None and u["id"] not in used_user:
            units.append(_make_unit(u, [a]))
            used_user.add(u["id"])
        else:
            pending.append(a)

    # 2) 相邻配对 fallback：剩余 assistant 就近绑定前置未配对 user（旧数据/learn）
    for a in pending[:]:
        prev = None
        for m in ordered:
            if (m.get("role") == "user" and m["id"] not in used_user
                    and m["id"] < a["id"]):
                prev = m
        if prev is not None:
            units.append(_make_unit(prev, [a]))
            used_user.add(prev["id"])
            pending.remove(a)

    # 3) 孤儿 user：独立成卡（无回答）
    for m in ordered:
        if m.get("role") == "user" and m["id"] not in used_user:
            units.append(_make_unit(m, []))

    # 4) 孤儿 assistant：并入最近一个同类单元（如 learn 确认追加），否则独立成卡
    for a in pending:
        same = [u for u in units if u["kind"] == a.get("message_type")]
        if same:
            same[-1]["answers"].append(a)
        else:
            units.append(_make_unit(None, [a]))

    units.sort(key=lambda u: u["max_id"], reverse=True)  # 最新在前
    return units


def _make_unit(user: dict | None, answers: list[dict]) -> dict:
    """组装单轮对话单元（id 有序写入，answers 保持时序）"""
    ids = [m["id"] for m in ((user,) if user else ()) + tuple(answers) if m.get("id")]
    first = user or (answers[0] if answers else {})
    return {
        "key": f"cu_{first.get('agent', '')}_{max(ids) if ids else 0}",
        "user": user,
        "answers": answers,
        "kind": first.get("message_type") or (answers[0].get("message_type") if answers else "qa"),
        "status": "ok" if answers else "orphan",
        "max_id": max(ids) if ids else 0,
        "created_at": first.get("created_at") or "",
    }


# ==================== 展开/收起状态管理 ====================

def _collapsed() -> set[str]:
    """当前收起的单元 key 集合（默认空 = 全部展开；刷新页面自动恢复默认）"""
    return st.session_state.setdefault("chat_collapsed", set())


def _unit_key(agent: str, unit: dict) -> str:
    return f"cu_{agent}_{unit['max_id']}"


# ==================== 渲染 ====================

def _esc(text: str) -> str:
    """HTML 转义（摘要等纯文本进 HTML 容器时防注入）"""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _preview(text: str, limit: int = 120) -> str:
    """回答首行摘要：取第一个非空行，剥离代码围栏/列表符/标题符，超长截断"""
    line = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^(```+|\*\*\s*|\#+\s*|\>\s*|\-\s+|\d+\.\s+)", "", line).strip()
        if line:
            break
    if len(line) > limit:
        line = line[:limit] + "…"
    return line or "（无文字内容）"


def render_batch_bar(agent: str, units: list[dict]) -> None:
    """批量操作栏（列表顶部）：全部展开 / 全部收起，操作后轻量反馈"""
    collapsed = _collapsed()
    c1, c2, c3 = st.columns([1.1, 1.1, 4], vertical_alignment="center")
    with c1:
        if st.button("全部展开", key=f"chat_open_all_{agent}", use_container_width=True):
            collapsed.clear()
            st.toast(f"已全部展开（{len(units)} 条对话）")
            st.rerun()
    with c2:
        if st.button("全部收起", key=f"chat_fold_all_{agent}", use_container_width=True):
            for u in units:
                collapsed.add(_unit_key(agent, u))
            st.toast(f"已全部收起（{len(units)} 条对话，仅保留提问与回答摘要）")
            st.rerun()
    with c3:
        st.caption("点击卡片右上角可单独收起/展开；刷新页面恢复默认全部展开。")


def render_conversation_unit(agent: str, unit: dict) -> None:
    """单轮对话单元卡片：顶部操作栏 + 提问区 + 回答区（完整富文本）+ 底部辅助信息"""
    key = _unit_key(agent, unit)
    collapsed = _collapsed()
    folded = key in collapsed
    with st.container(border=True, key=f"chat_unit_{agent}_{unit['max_id']}"):
        # ---- 顶部操作栏：左侧标签+时间+状态，右侧单条收起/展开 ----
        top_left, top_right = st.columns([5, 1.2], vertical_alignment="center")
        with top_left:
            st.markdown(_top_chips(unit), unsafe_allow_html=True)
        with top_right:
            if st.button("展开 ▼" if folded else "收起 ▲", key=f"chat_tg_{key}",
                         use_container_width=True):
                if key in collapsed:
                    collapsed.discard(key)
                else:
                    collapsed.add(key)
                st.rerun()

        # ---- 提问区：右对齐 + 浅一级背景，完整原文 ----
        if unit["user"]:
            with st.container(key=f"chat_q_{key}"):
                st.markdown(unit["user"]["content"])
            if unit["kind"] == "learn":
                u_desc = (unit["user"].get("meta") or {}).get("description") or ""
                if u_desc:
                    st.markdown(f'<div class="learn-desc"><b>用户补充说明</b>：{_esc(u_desc)}</div>',
                                unsafe_allow_html=True)

        # ---- 回答区 ----
        if unit["status"] == "orphan":
            st.caption("（暂无回答记录）")
        elif folded:
            # 收起：回答首行摘要 + 底部渐隐遮罩
            st.markdown(f'<div class="chat-preview">{_esc(_preview(unit["answers"][0]["content"]))}'
                        "</div>", unsafe_allow_html=True)
        else:
            # 展开：完整富文本渲染（与详情页一致，代码块/列表/表格正常显示）
            for a in unit["answers"]:
                st.markdown(a["content"])
            foot = _foot_parts(unit)
            if foot:
                st.markdown(f'<div class="chat-foot">{"　·　".join(foot)}</div>',
                            unsafe_allow_html=True)


def _top_chips(unit: dict) -> str:
    """顶部徽章行：类型 + 状态（裁决/沉淀/信心/无回答）+ 时间（弱化小字）"""
    label, tone = _TYPE_LABEL.get(unit["kind"], ("记录", "mute"))
    parts = [f'<span class="badge badge-{tone}">{label}</span>']
    if unit["status"] == "orphan":
        parts.append('<span class="badge badge-err">无回答</span>')
    elif unit["answers"]:
        a = unit["answers"][0]
        meta = a.get("meta") or {}
        if unit["kind"] == "rule":
            verdict = a.get("verdict") or ""
            parts.append(f'<span class="badge badge-{_VERDICT_TONE.get(verdict, "mute")}">'
                         f'裁决：{_VERDICT_LABEL.get(verdict, verdict or "未知")}</span>')
            if a.get("knowledge_id"):
                parts.append(f'<span class="badge badge-ok">已沉淀 #{a["knowledge_id"]}</span>')
        elif unit["kind"] == "learn":
            if meta.get("point_count"):
                parts.append(f'<span class="badge badge-info">提炼 {meta["point_count"]} 知识点</span>')
            if meta.get("saved"):
                parts.append(f'<span class="badge badge-ok">已沉淀 {len(meta["saved"])} 条</span>')
        elif unit["kind"] == "qa" and meta.get("confidence") is not None:
            parts.append(f'<span class="badge badge-info">信心 {meta["confidence"]}</span>')
    ts = str(unit.get("created_at") or "")[:16]
    if ts:
        parts.append(f'<span class="t">{ts}</span>')
    return f'<div class="chat-top-chips">{"".join(parts)}</div>'


def _foot_parts(unit: dict) -> list[str]:
    """底部辅助信息（弱化小字，不抢核心内容注意力）"""
    if unit["status"] != "ok":
        return []
    a = unit["answers"][0]
    meta = a.get("meta") or {}
    parts: list[str] = []
    if unit["kind"] == "qa":
        if meta.get("sources"):
            parts.append("依据来源：" + "；".join(str(s) for s in meta["sources"]))
        if meta.get("scope_note"):
            parts.append(f"职责边界：{meta['scope_note']}")
    elif unit["kind"] == "rule":
        if meta.get("conflict_note"):
            parts.append(f"冲突核查：{meta['conflict_note']}")
        if meta.get("rule_title"):
            parts.append(f"沉淀标题：{meta['rule_title']}")
    elif unit["kind"] == "learn" and meta.get("saved"):
        parts.append("沉淀：" + "、".join(str(s.get("title", "")) for s in meta["saved"]))
    return parts


def render_history(agent: str, messages: list[dict], batch: int = 20) -> None:
    """历史区统一入口：批量操作栏 + 懒加载列表（首屏 batch 条，点「加载更多」增量展示）。

    新加载的单元不在收起集合中 → 天然默认展开，不改变已有单元状态。
    """
    units = pair_messages(messages)
    if not units:
        st.caption("暂无历史记录。")
        return
    visible = st.session_state.get(f"_chat_vis_{agent}", batch)
    render_batch_bar(agent, units)
    for u in units[:visible]:
        render_conversation_unit(agent, u)
    if len(units) > visible:
        if st.button(f"加载更多（已显示 {visible} / {len(units)}）", key=f"more_chat_{agent}"):
            st.session_state[f"_chat_vis_{agent}"] = visible + batch
            st.rerun()
