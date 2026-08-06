"""交易复盘：ReviewAgent 输出 + 交易偏好优化建议（一键采纳/驳回，人工审核后生效）

企业级列表行范式：左=盈亏色圆点+代码名称(加粗)+离场日·持仓天数·建议状态(副标题)，
右=盈亏%+生成时间+「查看详情」；详情分区卡片化（计划兑现度/经验教训/偏好微调/优化建议），
原始 JSON 永久折叠在最底部。策略闭环建议区统一使用「查看详情/采纳/驳回」操作按钮组。
"""
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("交易复盘（ReviewAgent）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

STATUS_MAP = {"pending": "待审核", "adopted": "已采纳", "rejected": "已驳回"}

# ================= 策略闭环 · Agent 优化建议（人工审核后生效） =================
try:
    pending = api.agent_suggestions(status="pending")
except Exception:  # noqa: BLE001 后端未起时降级为空态，不阻断页面
    pending = []
with st.expander(f"策略闭环 · Agent 优化建议（待审核 {len(pending)} 条 · 人工审核后生效）",
                 expanded=bool(pending)):
    st.caption("复盘进化Agent 持续跟踪全链路各 Agent 方案落地表现后提出以下建议。"
               "⚠️ 所有建议必须经你人工审核确认后才生效，系统严格禁止自动、无监督修改任何策略参数。")
    if not pending:
        st.info("暂无待审核的策略优化建议。平仓并复盘后，复盘进化Agent 会自动提出建议。")
    for s in pending:
        key = f"sug_{s['id']}"
        opened = st.session_state.get(f"open_{key}", False)
        clicked = render.list_item(
            key, f"[{s['target_agent']}] {s['rule_name']}",
            subtitle=f"当前 {s['current_value'] or '（空）'} → 建议 {s['suggested_value']}",
            dot="warn", meta=str(s.get("created_at") or "")[:16],
            actions=("查看详情", "采纳", "驳回"))
        if clicked == 1:
            api.approve_suggestion(s["id"])
            st.success("已采纳，偏好档案已更新。")
            st.rerun()
        elif clicked == 2:
            api.reject_suggestion(s["id"])
            st.info("已驳回，不修改任何配置。")
            st.rerun()
        elif clicked == 0:
            opened = not opened
            st.session_state[f"open_{key}"] = opened
            st.rerun()
        if st.session_state.get(f"open_{key}"):
            with st.container(border=True):
                render.trace_line("建议提交时间", s.get("created_at"))
                with st.container(border=True):
                    render.section_title("建议内容")
                    st.markdown(f"- 当前值：{s['current_value'] or '（空）'}")
                    st.markdown(f"- 建议值：{s['suggested_value']}")
                    st.markdown(f"- 理由：{s['reason']}")
                    st.markdown(f"- 事实依据：{s['evidence']}")
                with st.container(border=True):
                    render.section_title("生效方式")
                    if s["target_kind"] == "profile":
                        st.markdown("采纳后直接写入「个人交易偏好」档案（版本号+1，全部 Agent 立即生效）。")
                    else:
                        st.markdown("提示词/硬性规则类，采纳后需人工在 agent_prompts/ 对应文件"
                                    "或 common.py 的 HARD_RULES 中修改。")

# ===== 筛选防抖：输入后点「查询」才过滤（避免每敲一个字符全页 rerun + 全量请求） =====
f_code = st.text_input("按股票代码筛选（留空显示全部，输入后点查询）",
                       value=st.session_state.get("_rev_filter", ""),
                       key="_rev_filter_input")
c1, c2 = st.columns([1, 5])
with c1:
    if st.button("查询", use_container_width=True):
        st.session_state["_rev_filter"] = f_code.strip()
        st.session_state.pop("_rev_list_vis", None)
        st.rerun()
with c2:
    if st.session_state.get("_rev_filter"):
        if st.button("清除筛选"):
            st.session_state["_rev_filter"] = ""
            st.session_state.pop("_rev_list_vis", None)
            st.rerun()
code = st.session_state.get("_rev_filter", "")

try:
    rows = api.reviews(code=code or None)
    if not rows:
        render.empty_state("暂无复盘记录。在「持仓监控」页录入人工卖出（全部卖出）后自动触发复盘。")
    else:
        def _review_detail(r: dict, _i: int) -> None:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            pnl = float(r.get("pnl_pct") or 0)
            # A股配色：盈利红（tier-a）、亏损绿（ok），与全站涨跌色一致
            dot = "tier-a" if pnl >= 0 else "ok"
            suggest = STATUS_MAP.get(r.get("suggest_status") or "pending", "待审核")
            meta = (f'<span class="{"up" if pnl >= 0 else "down"}">'
                    f'{"+" if pnl >= 0 else ""}{r["pnl_pct"]}%</span>　'
                    f'生成 {str(r.get("created_at") or "")[:16]}')
            key = f"review_{r['id']}"
            if render.list_item_toggle(key, label,
                                       subtitle=f"离场 {r['exit_date']} · 持仓 {r['hold_days']} 天"
                                                f" · 偏好建议 {suggest}",
                                       dot=dot, meta=meta):
                with st.container(border=True):
                    render.trace_line("复盘生成时间", r.get("created_at"), source="LLM 生成")
                    # 分区一：计划兑现度（入场逻辑 vs 实际走势）
                    with st.container(border=True):
                        render.section_title("计划兑现度")
                        render.render_dict(r["plan_vs_actual"])
                        render.raw_json_expander(r["plan_vs_actual"], key=f"raw_pva_{r['id']}")
                    # 分区二：经验教训
                    with st.container(border=True):
                        render.section_title("经验教训")
                        st.markdown(r["lesson"] or "（无）")
                    # 分区三：筛选偏好微调建议
                    with st.container(border=True):
                        render.section_title("筛选偏好微调建议")
                        render.render_dict(r["feedback"])
                        render.raw_json_expander(r["feedback"], key=f"raw_fb_{r['id']}")

                    # 分区四：交易偏好优化建议（版本迭代 + 采纳/驳回，人工审核后生效）
                    suggestion = (r["feedback"] or {}).get("profile_suggestion")
                    adopted = r.get("suggest_status") == "adopted"
                    if suggestion:
                        with st.container(border=True):
                            render.section_title("交易偏好优化建议（人工审核后生效）")
                            st.markdown(f"第 {r.get('suggest_iteration', 1)} 版 · "
                                        f"状态：{suggest}：修改 `{suggestion['field']}` → "
                                        f"{suggestion['value']}")
                            st.caption(f"理由：{suggestion['reason']}")

                            history = r.get("suggest_history") or []
                            if history:
                                with st.expander(f"查看迭代历史（共 {len(history)} 轮，默认收起）"):
                                    for h in reversed(history):
                                        it = h.get("suggestion") or {}
                                        if it:
                                            st.markdown(f"**第 {h.get('iteration')} 版**：修改 "
                                                        f"`{it.get('field')}` → {it.get('value')}")
                                            st.caption(f"建议理由：{it.get('reason')}")
                                        else:
                                            st.markdown(f"**第 {h.get('iteration')} 版**：无字段建议")
                                        st.warning(f"驳回原因：{h.get('reject_reason')}")
                                        st.divider()

                            if adopted:
                                st.success("该建议已采纳并写入偏好档案，全部 Agent 立即生效。")
                            else:
                                c1, c2 = st.columns(2)
                                with c1:
                                    if st.button("采纳建议并更新偏好档案", key=f"adopt_{r['id']}"):
                                        result = api.adopt_review(r["id"])
                                        st.success(f"已采纳：{result['field']}，"
                                                   f"偏好档案版本 v{result['version']}，立即生效")
                                        st.rerun()
                                with c2:
                                    if st.button("驳回", key=f"reject_btn_{r['id']}"):
                                        st.session_state[f"show_reject_{r['id']}"] = True
                                        st.rerun()
                                if st.session_state.get(f"show_reject_{r['id']}"):
                                    with st.form(key=f"reject_form_{r['id']}"):
                                        reason = st.text_area(
                                            "驳回原因（必填，多行）",
                                            placeholder="例如：不认可该结论 / 不符合我的交易风格"
                                                        " / 规则过于严格",
                                            key=f"reject_reason_{r['id']}")
                                        # 驳回原因必填：原位标红 + 填写指引，不整段报错
                                        render.field_error(
                                            f"reject_{r['id']}",
                                            render.get_field_error(f"reject_{r['id']}"),
                                            "驳回原因必填，请说明不认可的具体理由")
                                        if st.form_submit_button("提交驳回，让 AI 重新思考",
                                                                 type="primary"):
                                            if not reason.strip():
                                                render.set_field_errors(
                                                    {f"reject_{r['id']}": "驳回原因不能为空"})
                                            else:
                                                render.set_field_errors({})
                                                res = api.reject_review(r["id"], reason.strip())
                                                st.success("已驳回，AI 重思考任务已提交后台"
                                                           f"（{res.get('task_id')}），"
                                                           "完成后顶部任务状态区会提示。")
                                                st.session_state.pop(f"show_reject_{r['id']}", None)
                                                st.rerun()

        render.record_list(rows, _review_detail, batch=20, key="_rev_list_vis",
                           empty_text="无匹配的复盘记录。")
except Exception as exc:
    render.error_card("交易复盘加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key="retry_reviews")
