"""经验沉淀：自动经验识别与分层审核（M1 沉淀队列 / M2 每日 Digest / M3 高影响审核 / M4 经验库 / M5 设置）

- 后端就绪：/api/experience/* 9 端点（自动识别 → 分层审核 → 检索注入）；
- 5 模块用 segmented_control + session_state 自定义 Tab 状态机（st.tabs 无法程序化激活指定 Tab，
  M2→M3 跳转依赖 session_state["exp_tab"] + query_params["eid"] + rerun）；
- 前端红线：自动合并仅沉淀观测类经验，绝不触碰交易规则/研判标准/Agent 建议表；
  M3 高影响两步确认（checkbox 按 eid 隔离 + 驳回空理由按钮 disabled + 提交后重置）；
  所有回滚/清理操作 st.dialog 二次确认；实时任务路径绝不弹审核界面。
"""
import requests
import streamlit as st

import api_client as api
import render

render.apply_global_theme()
render.top_status_bar()

render.page_header(
    "经验沉淀",
    caption="自动经验识别与分层审核：热路径零分析 → 离线 Worker 识别 → 人工/自动分层生效，全部可追溯可回滚。",
    compliance="红线：自动合并仅沉淀观测类经验，绝不触碰交易规则/研判标准/Agent 建议表；"
               "高影响经验必须人工两步确认，无自动绕过。",
)

# ================= Tab 状态机（segmented_control + session_state，支持程序化跨模块跳转） =================
# 关键：segmented_control 用独立 key（exp_tab_sc），导航变量用 exp_tab（非 widget key）。
# 用户点击 → widget 值更新 → exp_tab 跟随；程序化跳转（M2→M3 / M3→M2）设 exp_tab + _exp_jump 标记，
# 在下一轮 segmented_control 渲染前把 exp_tab_sc 同步为跳转目标（widget key 渲染前可写）。
_TABS = ["M1 沉淀队列", "M2 每日 Digest", "M3 高影响审核", "M4 经验库", "M5 设置"]
st.session_state.setdefault("exp_tab", _TABS[0])
st.session_state.setdefault("exp_tab_sc", st.session_state["exp_tab"])
# 程序化跳转：_exp_jump 标记时让 widget 跟随 exp_tab（渲染前设置 widget key，Streamlit 允许）
if st.session_state.pop("_exp_jump", False):
    st.session_state["exp_tab_sc"] = st.session_state["exp_tab"]
cur = st.segmented_control("模块", _TABS, key="exp_tab_sc", label_visibility="collapsed")
# 用户点击 → widget 值更新 → exp_tab 跟随（无跳转标记时 cur 即用户最新选择）
if cur is not None:
    st.session_state["exp_tab"] = cur
_active_tab = st.session_state.get("exp_tab", _TABS[0])

# ================= 通用展示辅助 =================
_STATUS_LABEL = {"pending": "待识别", "processing": "识别中", "done": "已完成",
                 "pending_review": "待审核", "active": "已生效",
                 "rejected": "已驳回", "rolled_back": "已回滚"}
_STATUS_DOT = {"pending": "mute", "processing": "info", "done": "ok",
               "pending_review": "warn", "active": "ok", "rejected": "err",
               "rolled_back": "mute"}


def _stage_badge(stage: str) -> str:
    tone = {"选股": "info", "建仓": "warn", "持仓": "ok"}.get(stage, "mute")
    return f'<span class="badge badge-{tone}">{stage}</span>'


def _impact_badge(impact: str) -> str:
    return ('<span class="badge badge-err">高影响</span>' if impact == "high"
            else '<span class="badge badge-mute">低影响</span>')


def _conf_bar(conf: float) -> str:
    """置信度进度条：≥0.85 绿 / 0.5-0.85 琥珀 / <0.5 灰"""
    cls = "high" if conf >= 0.85 else ("mid" if conf >= 0.5 else "low")
    pct = max(0.0, min(100.0, conf * 100))
    return (f'<div class="conf-bar"><div class="conf-bar-fill {cls}" '
            f'style="width:{pct:.0f}%"></div></div>'
            f'<span style="font-size:12px;color:var(--text-mute)">置信度 {conf:.2f}</span>')


# ================= M1 沉淀队列（只读看板） =================
def _render_m1() -> None:
    st.markdown("**沉淀队列**：热路径零分析单行写入，离线 Worker 逐条识别；识别在闲时（02:00）/"
                "限流下进行，不加剧本地算力。")
    stage_f = st.selectbox("阶段筛选", ["全部", "选股", "建仓", "持仓"], key="m1_stage")
    try:
        rows = api.get_experience_pending(
            stage=None if stage_f == "全部" else stage_f, limit=100)
    except Exception as exc:  # noqa: BLE001 接口失败展示错误卡而非白屏
        render.error_card("沉淀队列加载失败", "后端接口异常，经验沉淀队列暂不可用。",
                          detail=exc, retry_key="retry_m1")
        return
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    render.stat_cards([
        {"label": "待识别", "value": sum(1 for r in rows if r["status"] == "pending"),
         "sub": "pending", "tone": "warn"},
        {"label": "识别中", "value": sum(1 for r in rows if r["status"] == "processing"),
         "sub": "processing", "tone": "info"},
        {"label": "今日已完成", "value": sum(1 for r in rows if r["status"] == "done"
                                          and str(r.get("created_at") or "")[:10] == today),
         "sub": "done（今日）", "tone": "ok"},
        {"label": "队列总量", "value": len(rows), "sub": "按阶段筛选", "tone": "mute"},
    ])
    if not rows:
        render.empty_state("沉淀队列为空。任务执行完成后，经验摘要会自动进入队列等待识别。", icon="📭")
    else:
        for r in rows:
            key = f"m1row_{r['id']}"
            status = r.get("status") or "pending"
            meta = (f'{_stage_badge(r.get("stage", ""))}　'
                    f'<span class="badge badge-{_STATUS_DOT.get(status, "mute")}">'
                    f'{_STATUS_LABEL.get(status, status)}</span>　'
                    f'{str(r.get("created_at") or "")[:16]}')
            if render.list_item_toggle(
                    key, r.get("summary") or f"任务 {r.get('task_id') or '—'}",
                    subtitle=f"任务 {r.get('task_id') or '—'} · 阶段 {r.get('stage') or '—'}",
                    dot=_STATUS_DOT.get(status, "mute"), meta=meta, scope="m1"):
                with st.container(border=True):
                    render.trace_line("入队时间", r.get("created_at"))
                    if r.get("artifacts_ref"):
                        st.markdown(f"- 产物引用：{r['artifacts_ref']}")
                    if r.get("error"):
                        render.msg_card("err", "识别失败", r["error"])
                    render.raw_json_expander(r, key=f"raw_m1_{r['id']}")
    if st.button("立即触发识别（识别当前 pending 队列）", type="primary", key="m1_run"):
        try:
            res = api.run_experience_worker()
            st.toast(f"已提交识别任务（{res.get('task_id')}），完成后待审核数自动更新")
            st.rerun()
        except api.ConflictError as exc:
            st.toast(str(exc), icon="⚠️")
        except Exception as exc:  # noqa: BLE001
            render.msg_card("err", "提交失败", "未能提交识别任务，可稍后重试。", detail=exc)


# ================= M2 每日 Digest（批量过目，低影响） =================
def _render_m2() -> None:
    st.markdown("**每日 Digest**：低影响经验批量过目（前端循环单条审核，后端无 batch 端点）；"
                "高影响项必须转 M3 硬审核，不可在此批量通过。")
    try:
        rows = api.get_experience_list(status="pending_review", limit=500)
    except Exception as exc:  # noqa: BLE001
        render.error_card("Digest 加载失败", "后端接口异常，Digest 暂不可用。",
                          detail=exc, retry_key="retry_m2")
        return
    if not rows:
        render.empty_state("当前无待过目经验。识别 Worker 产出新经验后会出现在这里。", icon="📭")
        return
    high = [r for r in rows if r.get("impact") == "high"]
    digest = [r for r in rows if r.get("impact") != "high"]

    if high:
        st.markdown(f'<span class="badge badge-err">⛔ 高影响 {len(high)} 条</span>　'
                    "高影响经验涉及规则/标准修改，必须走 M3 硬审核（两步确认），不可在此批量通过。",
                    unsafe_allow_html=True)
        for r in high[:20]:
            if st.button(f"前往硬审核 → {r.get('title', '未命名')[:36]}",
                         key=f"m2high_{r['id']}"):
                st.session_state["exp_tab"] = "M3 高影响审核"
                st.session_state["_exp_jump"] = True
                st.query_params["eid"] = str(r["id"])
                st.rerun()

    if not digest:
        render.empty_state("暂无低影响待过目经验（高影响项已在上方转 M3）。", icon="✅")
        return

    # 批量操作条（仅对低影响生效）
    act = render.quick_actions("m2_batch", [
        {"label": "✅ 全部通过", "type": "primary"},
        {"label": "🗑 全部驳回", "type": "secondary"},
        {"label": "👁 全部标记已查看", "type": "secondary"},
    ])
    if act == 0:
        _batch_approve(digest)
    elif act == 1:
        _m2_reject_all_dialog(digest)
    elif act == 2:
        viewed = st.session_state.setdefault("m2_viewed", set())
        for r in digest:
            viewed.add(r["id"])
        st.toast(f"已标记 {len(digest)} 条为已查看（状态不变，仍需通过/驳回处理）")
        st.rerun()

    # 按日期分组
    from collections import OrderedDict
    by_date: "OrderedDict[str, list]" = OrderedDict()
    for r in digest:
        d = str(r.get("created_at") or "")[:10] or "未知日期"
        by_date.setdefault(d, []).append(r)
    for date, items in by_date.items():
        st.markdown(f"**{date}**（{len(items)} 条）")
        for r in items:
            _digest_card(r)


def _batch_approve(items: list) -> None:
    ok = 0
    for r in items:
        try:
            api.review_experience(r["id"], "approve")
            ok += 1
        except Exception:  # noqa: BLE001 单条失败不中断批量
            pass
    st.toast(f"批量通过 {ok}/{len(items)} 条")
    st.rerun()


@st.dialog("批量驳回")
def _m2_reject_all_dialog(items: list) -> None:
    st.markdown(f"将驳回 {len(items)} 条低影响经验（reason 必填留痕，全部生效）。")
    reason = st.text_area("统一驳回理由（必填）", key="m2_reject_all_reason")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("确认全部驳回", type="primary",
                     disabled=not (reason or "").strip(), key="m2_reject_all_confirm"):
            ok = 0
            for r in items:
                try:
                    api.review_experience(r["id"], "reject", note=reason.strip())
                    ok += 1
                except Exception:  # noqa: BLE001
                    pass
            st.toast(f"批量驳回 {ok}/{len(items)} 条")
            st.rerun()
    with c2:
        if st.button("取消", key="m2_reject_all_cancel"):
            st.rerun()


def _digest_card(r: dict) -> None:
    eid = r["id"]
    viewed = st.session_state.get("m2_viewed", set())
    is_new = eid not in viewed
    conf = float(r.get("confidence") or 0.0)
    meta = (f'{_stage_badge(r.get("stage", ""))}　'
            f'{"🤖 自动" if r.get("auto_merged") else "👤 人工"}　'
            + (f'<span class="badge badge-warn">新</span>' if is_new else ""))
    key = f"m2c_{eid}"
    if render.list_item_toggle(
            key, r.get("title", "未命名经验"),
            subtitle=(r.get("body") or "")[:60] + ("…" if len(r.get("body") or "") > 60 else ""),
            dot="warn" if is_new else "mute", meta=meta, scope="m2"):
        with st.container(border=True):
            st.markdown(r.get("body", "（无正文）"))
            st.markdown(_conf_bar(conf), unsafe_allow_html=True)
            render.trace_line("创建时间", r.get("created_at"))
            c1, c2 = st.columns(2)
            with c1:
                if st.button("通过", key=f"m2a_{eid}"):
                    try:
                        api.review_experience(eid, "approve")
                        st.session_state.setdefault("m2_viewed", set()).add(eid)
                        st.toast(f"已通过：{r.get('title', '')[:20]}")
                        st.rerun()
                    except api.ConflictError as exc:
                        st.toast(str(exc), icon="⚠️")
            with c2:
                if st.button("驳回", key=f"m2r_{eid}"):
                    st.session_state[f"m2_reject_open_{eid}"] = True
            if st.session_state.get(f"m2_reject_open_{eid}"):
                reason = st.text_area("驳回理由（必填，留痕可追溯）", key=f"m2_reason_{eid}")
                if st.button("确认驳回", key=f"m2_reject_{eid}",
                             disabled=not (reason or "").strip()):
                    try:
                        api.review_experience(eid, "reject", note=reason.strip())
                        st.toast(f"已驳回：{r.get('title', '')[:20]}")
                        st.session_state.pop(f"m2_reject_open_{eid}", None)
                        st.rerun()
                    except api.ConflictError as exc:
                        st.toast(str(exc), icon="⚠️")


# ================= M3 高影响审核（硬闸门两步确认） =================
def _render_m3(eid) -> None:
    st.markdown("**高影响审核**：涉及交易规则/研判标准/Agent 建议的修改，硬闸门两步确认，不可误跳过。")
    try:
        rows = api.get_experience_list(status="pending_review", limit=100)
    except Exception as exc:  # noqa: BLE001
        render.error_card("待审列表加载失败", "后端接口异常。", detail=exc, retry_key="retry_m3")
        return
    high = [r for r in rows if r.get("impact") == "high"]
    if not high:
        render.empty_state("当前无高影响经验待审核。", icon="🛡️")
        return
    high_ids = [r["id"] for r in high]
    title_map = {r["id"]: r.get("title", "未命名") for r in high}
    sel_eid = None
    if eid:
        try:
            cand = int(str(eid))
            if cand in high_ids:
                sel_eid = cand
        except (TypeError, ValueError):
            pass
    if sel_eid is None:
        sel_eid = st.selectbox("选择待审核高影响经验", high_ids,
                               format_func=lambda i: title_map.get(i, "?"), key="m3_sel")
    try:
        item = api.get_experience_detail(sel_eid)
    except Exception as exc:  # noqa: BLE001
        render.error_card("经验详情加载失败", "后端接口异常。", detail=exc, retry_key="retry_m3_det")
        return

    render.msg_card("err", "⚠️ 高影响经验审核 — 此操作可能修改交易规则或研判标准，请谨慎确认",
                    "批准后该经验将注入全部相关 Agent；驳回必须填写理由（留痕可追溯）。")
    with st.container(border=True):
        st.markdown(f"**{item.get('title', '未命名')}**")
        st.markdown(item.get("body", "（无正文）"))
        st.markdown(f"{_stage_badge(item.get('stage', ''))}　{_impact_badge(item.get('impact', ''))}"
                    f"　置信度 {item.get('confidence', '—')}", unsafe_allow_html=True)
        with st.expander("来源产物"):
            st.markdown(item.get("source_summary") or "（无来源摘要）")
            st.markdown(f"来源任务：{item.get('source_task_id') or '—'}")
            st.markdown(f"创建时间：{item.get('created_at') or '—'}")
        with st.expander("审核留痕"):
            st.markdown(f"最后审核时间：{item.get('last_reviewed_at') or '（尚未审核）'}")
            st.caption("完整审核历史待后端补独立查询端点（已知 gap）。")

    # 两步确认（三重安全：checkbox 按 eid 隔离 + 驳回空理由按钮 disabled + 提交后重置）
    action = st.radio("选择操作", ["批准", "驳回"], key=f"m3_action_{sel_eid}", horizontal=True)
    reason = ""
    if action == "驳回":
        reason = st.text_area("驳回理由（必填，留痕可追溯）", key=f"m3_reason_{sel_eid}")
    confirm = st.checkbox("我已确认上述操作后果", key=f"m3_confirm_{sel_eid}")
    can_submit = confirm and (action != "驳回" or bool((reason or "").strip()))
    if st.button("确认提交", type="primary", disabled=not can_submit, key=f"m3_submit_{sel_eid}"):
        act = "reject" if action == "驳回" else "approve"
        try:
            api.review_experience(sel_eid, act, note=(reason or "").strip())
            st.toast(f"审核已提交：{title_map.get(sel_eid, '')[:20]} → "
                     f"{'已驳回' if act == 'reject' else '已生效'}")
            for k in (f"m3_action_{sel_eid}", f"m3_reason_{sel_eid}",
                      f"m3_confirm_{sel_eid}", f"m3_submit_{sel_eid}"):
                st.session_state.pop(k, None)
            st.query_params.pop("eid", None)  # 清理跳转参数，防残留
            st.session_state["exp_tab"] = "M2 每日 Digest"
            st.session_state["_exp_jump"] = True
            st.rerun()
        except api.ConflictError as exc:
            st.toast(str(exc), icon="⚠️")
        except Exception as exc:  # noqa: BLE001
            render.msg_card("err", "提交失败", "审核提交失败。", detail=exc)


# ================= M4 经验库（检索 + 回滚） =================
def _render_m4() -> None:
    st.markdown("**经验库**：已生效经验检索与回滚（仅自动合并项可回滚，st.dialog 二次确认）。")
    c1, c2, c3, c4, c5 = st.columns([3, 1.2, 1.3, 1, 1])
    with c1:
        q = st.text_input("全文搜索（FTS5，仅已生效经验）", key="m4_q", placeholder="输入关键词检索…")
    with c2:
        stage_f = st.selectbox("阶段", ["全部", "选股", "建仓", "持仓"], key="m4_stage")
    with c3:
        tag_f = st.text_input("标签过滤", key="m4_tag", placeholder="如 放量")
    with c4:
        only_auto = st.checkbox("仅自动合并", key="m4_auto")
    with c5:
        inc_rolled = st.checkbox("含已回滚", key="m4_rolled")
    try:
        if (q or "").strip():
            rows = api.search_experience(
                stage=None if stage_f == "全部" else stage_f, query=q.strip(), k=50)
        else:
            rows = api.get_experience_list(
                stage=None if stage_f == "全部" else stage_f, limit=100)
            if inc_rolled:  # search 只返回 active，已回滚走 list 单独拉取合并
                rows = rows + api.get_experience_list(
                    status="rolled_back", stage=None if stage_f == "全部" else stage_f, limit=100)
        if (tag_f or "").strip():
            rows = [r for r in rows if tag_f.strip() in str(r.get("tags") or "")]
        if only_auto:
            rows = [r for r in rows if r.get("auto_merged") == 1]
    except Exception as exc:  # noqa: BLE001
        render.error_card("经验库加载失败", "后端接口异常。", detail=exc, retry_key="retry_m4")
        return
    if not rows:
        render.empty_state("无匹配经验。调整搜索/筛选条件，或等待识别 Worker 产出新经验。", icon="🔍")
        return
    st.caption(f"共 {len(rows)} 条 · 搜索仅覆盖已生效经验；含已回滚项经列表单独拉取合并展示。")
    for r in rows:
        _exp_card(r)


def _exp_card(r: dict) -> None:
    eid = r["id"]
    conf = float(r.get("confidence") or 0.0)
    status = r.get("status") or "active"
    meta = (f'{_stage_badge(r.get("stage", ""))}　'
            f'{"🤖 自动" if r.get("auto_merged") else "👤 人工"}　'
            f'<span class="dot dot-{_STATUS_DOT.get(status, "mute")}"></span> '
            f'{_STATUS_LABEL.get(status, status)}　{str(r.get("created_at") or "")[:10]}')
    if render.list_item_toggle(
            f"m4c_{eid}", r.get("title", "未命名经验"),
            subtitle=(r.get("body") or "")[:60] + ("…" if len(r.get("body") or "") > 60 else ""),
            dot="mute", meta=meta, scope="m4"):
        with st.container(border=True):
            render.detail_tabs([
                ("正文", lambda: _exp_body_tab(r, conf)),
                ("来源与留痕", lambda: _exp_src_tab(r)),
            ], key=f"m4tabs_{eid}", default_index=0)
            if r.get("auto_merged") == 1 and status == "active":
                if st.button("回滚该经验（不再注入 Agent）", key=f"m4rb_{eid}"):
                    _rollback_dialog(r)


def _exp_body_tab(r: dict, conf: float) -> None:
    st.markdown(r.get("body", "（无正文）"))
    st.markdown(_conf_bar(conf), unsafe_allow_html=True)
    render.trace_line("创建时间", r.get("created_at"))
    st.markdown(f"- 影响：{r.get('impact', '—')}　置信度：{r.get('confidence', '—')}"
                f"　阶段：{r.get('stage', '—')}")


def _exp_src_tab(r: dict) -> None:
    st.markdown(f"- 来源摘要：{r.get('source_summary') or '（无）'}")
    st.markdown(f"- 来源任务：{r.get('source_task_id') or '—'}")
    st.markdown(f"- 状态：{_STATUS_LABEL.get(r.get('status', ''), r.get('status', '—'))}"
                f"　最后审核：{r.get('last_reviewed_at') or '—'}")
    if r.get("tags"):
        st.markdown(f"- 标签：{str(r.get('tags'))}")


@st.dialog("回滚确认")
def _rollback_dialog(r: dict) -> None:
    st.markdown(f"回滚后该经验将**不再注入 Agent**：\n\n**{r.get('title', '')}**"
                f"\n\n（自动合并项误合并可恢复；回滚写入 review_log 留痕）")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("确认回滚", type="primary", key=f"m4rb_confirm_{r['id']}"):
            try:
                api.rollback_experience(r["id"])
                st.toast("已回滚，该经验不再注入 Agent")
                st.rerun()
            except api.ConflictError as exc:
                st.toast(str(exc), icon="⚠️")
            except Exception as exc:  # noqa: BLE001
                render.msg_card("err", "回滚失败", "回滚操作失败。", detail=exc)
    with c2:
        if st.button("取消", key=f"m4rb_cancel_{r['id']}"):
            st.rerun()


# ================= M5 设置中心（热加载） =================
def _render_m5() -> None:
    st.markdown("**设置中心**：key-value 热加载，保存后无需重启即生效。")
    try:
        cfg = api.get_experience_config()
    except Exception as exc:  # noqa: BLE001
        render.error_card("设置加载失败", "后端接口异常。", detail=exc, retry_key="retry_m5")
        return
    conf_val = float(cfg.get("confidence_threshold", "0.85"))   # 接口返回全 str → float 化
    auto_val = cfg.get("auto_merge_enabled", "1") == "1"        # "1"/"0" → bool
    sleep_val = int(float(cfg.get("worker_sleep_sec", "3")))
    backlog_val = int(float(cfg.get("digest_backlog_threshold", "50")))
    with render.fold_module("m5_cron", "调度设置", default_open=True):
        st.markdown(f"调度 cron：`{cfg.get('worker_cron', '0 2 * * *')}`"
                    "（每日 02:00 主跑 + 每 30 分钟积压探针，与现有任务零冲突）")
        backlog_in = st.number_input("积压触发阈值（pending 数 > 该值即触发识别）",
                                     min_value=1, max_value=1000, value=backlog_val,
                                     key="m5_backlog")
    with render.fold_module("m5_model", "识别模型", default_open=True):
        st.markdown(f"Worker 模型：`{cfg.get('worker_model', 'flash')}` — "
                    "deepseek-v4-flash 云端轻量模型，零本地算力占用。")
    with render.fold_module("m5_policy", "分流策略", default_open=True):
        conf_slider = st.slider("自动合并置信阈值", 0.5, 0.95, conf_val, 0.05, key="m5_conf")
        auto_toggle = st.toggle("自动合并开关（低影响 + 置信达标 + 无冲突 → 直接生效可回滚）",
                                auto_val, key="m5_auto")
        sleep_in = st.number_input("Worker 批间限流（秒）", min_value=0, max_value=60,
                                   value=sleep_val, key="m5_sleep")
        try:
            pending_rev = api.get_experience_list(status="pending_review", limit=500)
            low_ready = sum(1 for r in pending_rev if r.get("impact") != "high"
                            and float(r.get("confidence") or 0) >= conf_slider)
        except Exception:  # noqa: BLE001 预览失败不阻塞设置
            pending_rev, low_ready = [], 0
        st.caption(f"影响预览：当前待审核 {len(pending_rev)} 条，阈值 {conf_slider:.2f} 下"
                   f"有 {low_ready} 条低影响项将满足自动合并条件。")
    with render.fold_module("m5_data", "数据管理", default_open=False):
        try:
            auto_items = api.get_experience_list(auto_merged=1, status="active", limit=100)
        except Exception:  # noqa: BLE001
            auto_items = []
        if not auto_items:
            st.caption("当前无自动合并已生效经验可回滚。")
        else:
            st.caption(f"自动合并已生效 {len(auto_items)} 条（回滚需二次确认，逐条生效）")
            for r in auto_items[:30]:
                if st.button(f"回滚：{r.get('title', '未命名')[:40]}", key=f"m5rb_{r['id']}"):
                    _rollback_dialog(r)
    if st.button("保存设置（热加载生效，无需重启）", type="primary", key="m5_save"):
        try:
            api.set_experience_config({
                "confidence_threshold": str(conf_slider),
                "auto_merge_enabled": "1" if auto_toggle else "0",
                "worker_sleep_sec": str(int(sleep_in)),
                "digest_backlog_threshold": str(int(backlog_in)),
            })
            st.toast("设置已保存，热加载生效（无需重启）")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            render.msg_card("err", "保存失败", "设置写入失败，请检查后端服务。", detail=exc)


# ================= 模块分发 =================
if _active_tab == "M1 沉淀队列":
    _render_m1()
elif _active_tab == "M2 每日 Digest":
    _render_m2()
elif _active_tab == "M3 高影响审核":
    _eid_param = st.query_params.get("eid", "")
    _render_m3(_eid_param[0] if isinstance(_eid_param, list) else _eid_param)
elif _active_tab == "M4 经验库":
    _render_m4()
elif _active_tab == "M5 设置":
    _render_m5()
