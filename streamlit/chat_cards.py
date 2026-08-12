"""Agent 对话历史：问答配对 + 单轮对话单元卡片渲染 + 对话看板化

【核心逻辑】「用户提问 + AI 回答」永久绑定为单轮对话单元，一一对应：
- 后端落库时 assistant 记录 meta.user_msg_id 已指向配对 user 记录（qa/rule 类型），
  本模块纯前端按此字段精确配对，不改数据库、不改 Agent 调用；
- learn 类型未写 user_msg_id，按 id 相邻顺序配对（上传 → 摘要为连续写入）；
- 无关联的旧数据（迁移前历史）fallback 相邻顺序配对；
- 孤儿 user 记录独立成卡（状态「无回答」）；孤儿 assistant（如 learn 确认追加记录）
  并入最近一个同类单元，保证不丢记录。

【交互】默认全部展开、回答完整可见；单条收起/展开 + 批量「全部展开/全部收起」；
收起状态存 session_state（刷新即恢复默认展开；加载更多的新单元天然默认展开）。

【看板化（v2）】对话历史双视图：
- 摘要卡片：未展开时展示 结论/风险/待办 三行缩写（关键词提取，纯前端）；
- 状态流转：待确认 → 已完成 → 归档（按钮流转，存 session_state 按 agent 隔离，
  纯前端状态不落库，刷新保留于本会话）；
- 双视图：看板（待确认/已完成/归档三列）/ 线性列表，可切换，数据不丢；
- 惰性加载：历史 tab 首次点击才拉取（进页面零请求），30s 内复用会话缓存。

状态键均带 agent 前缀，切换 Agent 互不串扰。
"""
import re
import time

import streamlit as st

# ==================== 问答配对（纯函数，可单测） ====================

_TYPE_LABEL = {"qa": ("提问", "info"), "rule": ("调教", "warn"), "learn": ("学习", "ok"),
               "batch": ("批量验证", "info")}
_VERDICT_LABEL = {"adopted": "采纳", "partial": "部分采纳", "maintained": "维持原规则"}
_VERDICT_TONE = {"adopted": "ok", "partial": "warn", "maintained": "mute"}


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


# ================= 看板化：摘要三行 + 状态流转（纯函数/会话状态，不落库） =================

_RISK_KEYWORDS = ("风险", "回调", "警惕", "注意", "止损", "跌破", "谨慎", "负")
_ACTION_KEYWORDS = ("等待", "观察", "建议", "加仓", "减仓", "关注", "操作", "执行", "可", "待")
_STATUS_LABEL = {"todo": "待确认", "done": "已完成", "archived": "归档"}
_STATUS_TONE = {"todo": "badge-warn", "done": "badge-ok", "archived": "badge-mute"}


def unit_summary(unit: dict) -> dict:
    """卡片正面三行缩写（纯函数，可单测）：
    conclusion=回答首行摘要；risk=含风险关键词的首句；action=含待办动作关键词的首句。
    关键词提取仅做文本筛选，不含任何研判语义。"""
    text = "\n".join((a.get("content") or "") for a in (unit.get("answers") or []))
    if not text and unit.get("user"):
        text = unit["user"].get("content") or ""
    conclusion = _preview(text)
    risk = action = ""
    seen_first = False
    for raw in (text or "").splitlines():
        line = re.sub(r"^(```+|\*\*\s*|\#+\s*|\>\s*|\-\s+|\d+\.\s+)", "", raw).strip()
        if not line:
            continue
        if not seen_first:
            seen_first = True
            if unit.get("answers"):
                continue  # 有回答：首行已作结论，风险/待办从后续行提取
            # 孤儿单元（无回答）信息贫乏：允许复用首行提取风险/待办
        if not risk and any(k in line for k in _RISK_KEYWORDS):
            risk = line[:60] + ("…" if len(line) > 60 else "")
        if not action and any(k in line for k in _ACTION_KEYWORDS):
            action = line[:60] + ("…" if len(line) > 60 else "")
    return {"conclusion": conclusion, "risk": risk or "（无明显风险提示）",
            "action": action or "（无明显待办动作）"}


def card_status(agent: str, unit: dict) -> str:
    """对话单元跟进状态（会话内，按 agent+max_id 隔离；默认待确认）"""
    return st.session_state.setdefault(
        f"chat_status_{agent}_{unit['max_id']}", "todo")


def set_card_status(agent: str, unit: dict, status: str) -> None:
    st.session_state[f"chat_status_{agent}_{unit['max_id']}"] = status


def _status_badge_html(status: str) -> str:
    """状态徽章 HTML（看板/线性共用）"""
    return (f'<span class="badge {_STATUS_TONE.get(status, "badge-mute")}">'
            f'{_STATUS_LABEL.get(status, status)}</span>')


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
        # ---- 顶部操作栏：左侧标签+时间+跟进状态，右侧单条收起/展开 ----
        top_left, top_right = st.columns([5, 1.2], vertical_alignment="center")
        with top_left:
            st.markdown(_top_chips(unit) + _status_badge_html(card_status(agent, unit)),
                        unsafe_allow_html=True)
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
        _render_status_buttons(agent, unit)


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


# ================= 看板化：摘要卡片 + 状态流转 + 双视图（惰性加载） =================

_HIST_TTL = 30  # 历史会话缓存秒数（按需加载：进页面零请求，30s 内复用）


def _load_units_lazy(agent: str, name: str) -> tuple[list[dict], list[dict]] | None:
    """惰性加载对话历史：首次点击才拉取（进页面零请求），30s 内复用会话缓存；
    返回 (units, msgs)；未加载或加载失败返回 None（占位/提示已渲染）。"""
    key = f"_hist_cache_{agent}"
    if key not in st.session_state:
        st.caption("对话历史为按需加载（进页面零请求、交互更流畅），"
                   f"点击下方按钮拉取 {name} 最近 50 条对话。")
        if st.button("加载对话历史", key=f"hist_load_{agent}", use_container_width=True):
            try:
                import api_client

                msgs = api_client.chat_history(agent, limit=50)
                st.session_state[key] = (time.time(), msgs)
                st.rerun()
            except Exception as exc:  # noqa: BLE001 后端不可达时给出提示，不抛原始报错
                st.error(f"历史加载失败：{exc}")
        return None
    ts, msgs = st.session_state[key]
    if time.time() - ts > _HIST_TTL:  # 缓存过期自动重拉；失败沿用旧数据不打断浏览
        try:
            import api_client

            msgs = api_client.chat_history(agent, limit=50)
            st.session_state[key] = (time.time(), msgs)
            st.rerun()
        except Exception:  # noqa: BLE001
            pass
    units = pair_messages(msgs)
    if not units:
        st.caption("暂无历史记录。")
    return units, msgs


def _render_full_content(unit: dict) -> None:
    """看板卡展开区：完整提问 + 回答 + 底部辅助信息（不含状态按钮，避免重复）"""
    if unit["user"]:
        with st.container(key=f"chat_q_{unit['key']}"):
            st.markdown(unit["user"]["content"])
        if unit["kind"] == "learn":
            u_desc = (unit["user"].get("meta") or {}).get("description") or ""
            if u_desc:
                st.markdown(f'<div class="learn-desc"><b>用户补充说明</b>：{_esc(u_desc)}</div>',
                            unsafe_allow_html=True)
    if unit["status"] == "orphan":
        st.caption("（暂无回答记录）")
        return
    for a in unit["answers"]:
        st.markdown(a["content"])
    foot = _foot_parts(unit)
    if foot:
        st.markdown(f'<div class="chat-foot">{"　·　".join(foot)}</div>',
                    unsafe_allow_html=True)


def _render_status_buttons(agent: str, unit: dict) -> None:
    """状态流转按钮行（待确认 → 确认完成/归档；已完成 → 恢复/归档；归档 → 恢复）"""
    status = card_status(agent, unit)
    if status == "todo":
        labels, targets = ("✓ 确认完成", "📁 归档"), ("done", "archived")
    elif status == "done":
        labels, targets = ("↩ 恢复待确认", "📁 归档"), ("todo", "archived")
    else:
        labels, targets = ("↩ 恢复待确认", ""), ("todo", "")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(labels[0], key=f"chat_st_{agent}_{unit['max_id']}_{targets[0]}",
                     use_container_width=True):
            set_card_status(agent, unit, targets[0])
            st.rerun()
    with c2:
        if labels[1] and st.button(labels[1], key=f"chat_st_{agent}_{unit['max_id']}_{targets[1]}",
                                   use_container_width=True):
            set_card_status(agent, unit, targets[1])
            st.rerun()


def _render_board_card(agent: str, unit: dict) -> None:
    """看板摘要卡：类型/时间徽章 + 跟进状态 + 结论/风险/待办三行 + 展开完整对话 + 状态流转"""
    key = _unit_key(agent, unit)
    collapsed = _collapsed()
    folded = key in collapsed
    with st.container(border=True, key=f"chat_board_{agent}_{unit['max_id']}"):
        st.markdown(_top_chips(unit) + _status_badge_html(card_status(agent, unit)),
                    unsafe_allow_html=True)
        s = unit_summary(unit)
        st.markdown(
            f'<div class="board-sum">'
            f'<div class="board-line"><b class="sum-k">结论</b>：{_esc(s["conclusion"])}</div>'
            f'<div class="board-line board-risk"><b class="sum-k">风险</b>：{_esc(s["risk"])}</div>'
            f'<div class="board-line board-act"><b class="sum-k">待办</b>：{_esc(s["action"])}</div>'
            f"</div>", unsafe_allow_html=True)
        if st.button("展开完整对话 ▼" if folded else "收起对话 ▲",
                     key=f"chat_board_tg_{key}", use_container_width=True):
            if key in collapsed:
                collapsed.discard(key)
            else:
                collapsed.add(key)
            st.rerun()
        if not folded:
            _render_full_content(unit)
        _render_status_buttons(agent, unit)


def render_board_view(agent: str, units: list[dict]) -> None:
    """看板视图：待确认 / 已完成 / 归档 三列（st.columns(3)，状态按钮流转，不做真拖拽）"""
    groups = {"todo": [], "done": [], "archived": []}
    for u in units:
        groups[card_status(agent, u)].append(u)
    cols = st.columns(3, gap="medium")
    for col, status in zip(cols, ("todo", "done", "archived")):
        items = groups[status]
        with col:
            st.markdown(
                f'<div class="board-col-head"><span class="badge {_STATUS_TONE[status]}">'
                f'{_STATUS_LABEL[status]}</span><span class="t">　{len(items)} 条</span></div>',
                unsafe_allow_html=True)
            if not items:
                st.caption("（空）")
            for u in items:
                _render_board_card(agent, u)


def render_dashboard(agent: str, name: str) -> None:
    """对话历史看板化主入口：惰性加载 → 视图切换（看板/线性）→ 状态筛选 → 刷新"""
    loaded = _load_units_lazy(agent, name)
    if loaded is None:
        return
    units, msgs = loaded
    c1, c2, c3 = st.columns([1, 1, 4], vertical_alignment="center")
    with c1:
        view = st.segmented_control("视图", ["看板", "线性"], default="看板",
                                    key=f"chat_view_{agent}", label_visibility="collapsed")
    with c2:
        status_f = st.segmented_control("筛选", ["全部", "待确认", "已完成", "归档"],
                                        default="全部", key=f"chat_filter_{agent}",
                                        label_visibility="collapsed")
    with c3:
        if st.button("刷新历史", key=f"hist_refresh_{agent}"):
            try:
                import api_client

                msgs = api_client.chat_history(agent, limit=50)
                st.session_state[f"_hist_cache_{agent}"] = (time.time(), msgs)
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"刷新失败：{exc}")
    if status_f != "全部":
        want = {"待确认": "todo", "已完成": "done", "归档": "archived"}[status_f]
        units = [u for u in units if card_status(agent, u) == want]
    if not units:
        st.caption(f"当前筛选（{status_f}）下暂无对话，可切换筛选或视图查看。")
        return
    if view == "看板":
        render_board_view(agent, units)
    else:
        render_history(agent, msgs)  # 线性复用现有列表（批量展开/收起/懒加载）
