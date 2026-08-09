"""交易复盘：ReviewAgent 输出 + 交易偏好优化建议（一键采纳/驳回，人工审核后生效）

企业级列表行范式：左=盈亏色圆点+代码名称(加粗)+离场日·持仓天数·建议状态(副标题)，
右=盈亏%+生成时间+「查看详情」；详情分区卡片化（计划兑现度/止盈比对/经验教训/偏好微调/优化建议），
原始 JSON 永久折叠在最底部。策略闭环建议区统一使用「展开详情/采纳/驳回」操作按钮组。
"""
import json

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
_SUG_STATUS = {"pending": "待审核", "approved": "已采纳", "rejected": "已驳回"}
_SUG_TONE = {"pending": "warn", "approved": "ok", "rejected": "err"}

# ================= 策略闭环 · Agent 优化建议（人工审核后生效） =================
sug_filter = st.session_state.get("_sug_filter", "pending")  # all/pending/approved/rejected
try:
    sug_status = None if sug_filter == "all" else sug_filter
    suggestions = api.agent_suggestions(status=sug_status)
except Exception:  # noqa: BLE001 后端未起时降级为空态，不阻断页面
    suggestions = []
sug_keys = [f"sug_{s['id']}" for s in suggestions]
with render.fold_module("strategy_loop", "策略闭环 · Agent 优化建议",
                        meta=f"当前 {len(suggestions)} 条 · 人工审核后生效",
                        default_open=bool(suggestions)):
    st.caption("复盘进化Agent 持续跟踪全链路各 Agent 方案落地表现后提出以下建议。"
               "⚠️ 所有建议必须经你人工审核确认后才生效，系统严格禁止自动、无监督修改任何策略参数。")
    # 状态筛选下拉（API 已支持 status 过滤，零后端改动）
    _FILT_LABEL = {"all": "全部", "pending": "待审核", "approved": "已采纳", "rejected": "已驳回"}
    sel = st.selectbox("状态筛选", list(_FILT_LABEL), index=list(_FILT_LABEL).index(sug_filter),
                       format_func=lambda v: _FILT_LABEL[v], key="_sug_filter_sel")
    if sel != sug_filter:
        st.session_state["_sug_filter"] = sel
        st.rerun()
    if not suggestions:
        st.info("当前筛选条件下暂无策略优化建议。平仓并复盘后，复盘进化Agent 会自动提出建议。")
    else:
        render.batch_fold_bar("sug", sug_keys, label="点击行内「展开详情」查看完整建议；"
                                                    "采纳/驳回仅对待审核建议生效。")
        for s in suggestions:
            key = f"sug_{s['id']}"
            opened = st.session_state.get(f"open_{key}", False)
            status = s.get("status") or "pending"
            meta = f'{_SUG_STATUS.get(status, status)} · {str(s.get("created_at") or "")[:16]}'
            clicked = render.list_item(
                key, f"[{s['target_agent']}] {s['rule_name']}",
                subtitle=f"当前 {s['current_value'] or '（空）'} → 建议 {s['suggested_value']}",
                dot=_SUG_TONE.get(status, "mute"), meta=meta,
                actions=("展开详情", "采纳", "驳回"))
            if clicked == 0:  # 展开/收起详情
                opened = not opened
                st.session_state[f"open_{key}"] = opened
                st.rerun()
            elif clicked == 1 and status == "pending":
                api.approve_suggestion(s["id"])
                st.success("已采纳，偏好档案已更新。")
                st.rerun()
            elif clicked == 2 and status == "pending":
                st.session_state[f"show_reject_sug_{s['id']}"] = True
                st.rerun()
            if opened or st.session_state.get(f"show_reject_sug_{s['id']}"):
                with st.container(border=True):
                    render.trace_line("建议提交时间", s.get("created_at"))
                    with st.container(border=True):
                        render.section_title("建议内容")
                        st.markdown(f"- 当前值：{s['current_value'] or '（空）'}")
                        st.markdown(f"- 建议值：{s['suggested_value']}")
                        st.markdown(f"- 问题背景与根因分析：{s['reason']}")
                        st.markdown(f"- 事实数据依据：{s['evidence']}")
                    with st.container(border=True):
                        render.section_title("生效方式")
                        if s["target_kind"] == "profile":
                            st.markdown("采纳后直接写入「个人交易偏好」档案（版本号+1，全部 Agent 立即生效）。")
                        else:
                            st.markdown("提示词/硬性规则类，采纳后需人工在 agent_prompts/ 对应文件"
                                        "或 common.py 的 HARD_RULES 中修改。")
                    if status == "rejected" and s.get("reject_reason"):
                        st.caption(f"已驳回 · 驳回原因：{s['reject_reason']}")
                    # 驳回强制原因输入（审核留痕，落库可追溯）
                    if status == "pending" and st.session_state.get(f"show_reject_sug_{s['id']}"):
                        with st.form(key=f"reject_sug_form_{s['id']}"):
                            reason = st.text_area(
                                "驳回原因（必填，多行）",
                                placeholder="例如：不认可该结论 / 不符合我的交易风格 / 规则过于严格",
                                key=f"reject_sug_reason_{s['id']}")
                            render.field_error(f"reject_sug_{s['id']}",
                                                render.get_field_error(f"reject_sug_{s['id']}"),
                                                "驳回原因必填，请说明不认可的具体理由")
                            if st.form_submit_button("提交驳回（驳回原因留痕）", type="primary"):
                                if not reason.strip():
                                    render.set_field_errors({f"reject_sug_{s['id']}": "驳回原因不能为空"})
                                else:
                                    render.set_field_errors({})
                                    api.reject_suggestion(s["id"], reason.strip())
                                    st.success("已驳回，原因已留痕；不修改任何配置。")
                                    st.session_state.pop(f"show_reject_sug_{s['id']}", None)
                                    st.rerun()

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
        rev_keys = [f"review_{r['id']}" for r in rows]
        render.batch_fold_bar("rev", rev_keys, label="点击行内「查看详情」展开完整复盘分区内容。")

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
                                       dot=dot, meta=meta, scope="rev"):
                with st.container(border=True):
                    render.trace_line("复盘生成时间", r.get("created_at"), source="LLM 生成")
                    # 分区一：计划兑现度（入场逻辑 vs 实际走势）
                    with st.container(border=True):
                        render.section_title("计划兑现度")
                        render.render_dict(r["plan_vs_actual"])
                        render.raw_json_expander(r["plan_vs_actual"], key=f"raw_pva_{r['id']}")
                    # 分区一·补：止盈计划兑现比对（预判止盈位 vs 实际卖出价，留痕追溯）
                    with st.container(border=True):
                        render.section_title("止盈计划兑现比对（留痕追溯）")
                        tp_trace = None
                        try:
                            for t in api.traces(code=r["stock_code"], date=r["exit_date"],
                                                limit=5) or []:
                                if t.get("source_module") == "position_monitor":
                                    tp_trace = t
                                    break
                        except Exception:  # noqa: BLE001 留痕接口失败降级提示
                            tp_trace = None
                        if tp_trace:
                            try:
                                concl = json.loads(tp_trace.get("final_conclusion") or "{}")
                            except (json.JSONDecodeError, TypeError):
                                concl = {}
                            tp1, tp2 = concl.get("tp1"), concl.get("tp2")
                            st.markdown(f"- 预判第一止盈位：**{tp1 or '—'} 元**；"
                                        f"第二止盈位：**{tp2 or '—'} 元**"
                                        f"（留痕 {str(tp_trace.get('create_time') or '')[:16]}，"
                                        "source_module=position_monitor）")
                            exit_prices = []
                            try:
                                for tr in api.holding_trades(r.get("holding_id") or 0) or []:
                                    if tr.get("side") == "sell" and tr.get("price"):
                                        exit_prices.append(float(tr["price"]))
                            except Exception:  # noqa: BLE001 流水失败降级提示
                                pass
                            if exit_prices:
                                avg = sum(exit_prices) / len(exit_prices)
                                if tp1 and tp2 and avg >= tp2:
                                    verdict = f"实际卖出均价 {avg:,.2f} ≥ 第二止盈位 {tp2}：" \
                                              "到达波段目标，超预期兑现"
                                elif tp1 and avg >= tp1:
                                    verdict = f"实际卖出均价 {avg:,.2f} ≥ 第一止盈位 {tp1}：" \
                                              "分档锁利生效"
                                else:
                                    verdict = (f"实际卖出均价 {avg:,.2f} 低于第一止盈位 "
                                               f"{tp1 or '—'}：未触发止盈分档")
                                st.markdown(f"- 实际卖出：{len(exit_prices)} 笔，"
                                            f"均价 {avg:,.2f} 元")
                                st.markdown(f"- **比对结论**：{verdict}")
                            else:
                                st.caption("无卖出流水记录，无法比对实际卖出价。")
                        else:
                            st.caption("离场日无 position_monitor 留痕（止盈计划功能上线前的"
                                       "历史离场，无法回溯预判止盈位；留痕数据可供复盘进化"
                                       "Agent 后续做止盈准确率统计）。")
                    # 分区二：离场决策维度归因（v3.0 白盒；回溯 SellAgent 离场决策的维度依据）
                    with st.container(border=True):
                        render.section_title("离场决策维度归因（白盒追溯）")
                        sell_hist = []
                        try:
                            sell_hist = api.sell_decisions(r.get("holding_id") or 0) or []
                        except Exception:  # noqa: BLE001 决策接口失败降级提示，不阻塞复盘
                            sell_hist = []
                        sell_d = (sell_hist[0].get("decision") or {}) if sell_hist else {}
                        if sell_d:
                            render.dimension_bars(sell_d.get("dimensions"),
                                                  final_advice=sell_d.get("final_advice"))
                            if sell_d.get("reasons"):
                                st.markdown("**决策依据**")
                                for i, rr in enumerate(sell_d["reasons"], 1):
                                    st.markdown(f"{i}. {rr}")
                            render.time_text("决策时间", sell_hist[0].get("created_at"))
                        else:
                            st.caption("无离场卖出决策记录（手动卖出或历史数据），"
                                       "维度归因留痕在「持仓监控」页生成卖出决策后自动记录。")

                    # 分区三：经验教训
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
    render.dismissible_error("交易复盘加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                             detail=exc, retry_key="retry_reviews",
                             dismiss_key="rev_list")
