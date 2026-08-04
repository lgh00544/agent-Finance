"""交易复盘：ReviewAgent 输出 + 交易偏好优化建议（一键采纳/驳回）
计划兑现度/筛选偏好等 JSON 字段拆解为自然语言段落，原始 JSON 折叠查看。"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="交易复盘", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("交易复盘（ReviewAgent）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ================= 策略闭环·Agent 优化建议（人工审核后生效） =================
st.subheader("策略闭环 · Agent 优化建议（待审核）")
st.caption("复盘进化Agent 持续跟踪全链路各 Agent 方案落地表现后提出以下建议。"
           "⚠️ 所有建议必须经你人工审核确认后才生效，系统严格禁止自动、无监督修改任何策略参数。")
try:
    pending = api.agent_suggestions(status="pending")
    if pending:
        for s in pending:
            with st.expander(f"[{s['target_agent']}] {s['rule_name']}"):
                render.time_text("建议提交时间", s.get("created_at"))
                st.markdown(f"**当前值**：{s['current_value'] or '（空）'}")
                st.markdown(f"**建议值**：{s['suggested_value']}")
                st.caption(f"理由：{s['reason']}")
                st.caption(f"事实依据：{s['evidence']}")
                if s["target_kind"] == "profile":
                    st.caption("生效方式：采纳后直接写入「个人交易偏好」档案（版本号+1，全部 Agent 立即生效）。")
                else:
                    st.caption("生效方式：提示词/硬性规则类，采纳后需人工在 agent_prompts/ 对应文件"
                               "或 common.py 的 HARD_RULES 中修改。")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("采纳", key=f"app_{s['id']}"):
                        res = api.approve_suggestion(s["id"])
                        st.success("已采纳。" + res.get("hint", ""))
                with c2:
                    if st.button("驳回", key=f"rej_{s['id']}"):
                        api.reject_suggestion(s["id"])
                        st.info("已驳回，不修改任何配置。")
    else:
        st.info("暂无待审核的策略优化建议。平仓并复盘后，复盘进化Agent 会自动提出建议。")
except Exception as exc:
    st.error(f"建议获取失败: {exc}")

st.divider()
code = st.text_input("按股票代码筛选（留空显示全部）", "")

try:
    rows = api.reviews(code=code or None)
    if not rows:
        st.info("暂无复盘记录。在「持仓监控」页录入人工卖出（全部卖出）后自动触发复盘。")
    else:
        status_map = {"pending": "待审核", "adopted": "已采纳", "rejected": "已驳回"}
        overview = pd.DataFrame([
            {"股票": render.stock_label(r["stock_code"], r["stock_name"]),
             "离场日": r["exit_date"], "持仓天数": r["hold_days"], "盈亏%": r["pnl_pct"],
             "建议状态": status_map.get(r.get("suggest_status") or "pending", "待审核")} for r in rows
        ])
        st.dataframe(overview, width="stretch", hide_index=True)

        for r in rows[:10]:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            with st.expander(f"{label}　离场 {r['exit_date']} — 持仓 {r['hold_days']} 天 "
                             f"盈亏 {r['pnl_pct']}%"):
                render.time_text("复盘生成时间", r.get("created_at"))
                st.markdown("**计划兑现度**")
                render.render_dict(r["plan_vs_actual"])
                render.raw_json_expander(r["plan_vs_actual"], key=f"raw_pva_{r['id']}")
                st.markdown(f"**经验教训**：{r['lesson']}")
                st.markdown("**筛选偏好微调建议**")
                render.render_dict(r["feedback"])
                render.raw_json_expander(r["feedback"], key=f"raw_fb_{r['id']}")

                suggestion = (r["feedback"] or {}).get("profile_suggestion")
                status_map = {"pending": "待审核", "adopted": "已采纳", "rejected": "已驳回"}
                status_label = status_map.get(r.get("suggest_status") or "pending", "待审核")
                adopted = r.get("suggest_status") == "adopted"

                if suggestion:
                    st.markdown("---")
                    st.markdown(f"**交易偏好优化建议**（第 {r.get('suggest_iteration', 1)} 版 · "
                                f"状态：{status_label}）：修改 `{suggestion['field']}` "
                                f"→ {suggestion['value']}")
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
                        with c2:
                            if st.button("驳回", key=f"reject_btn_{r['id']}"):
                                st.session_state[f"show_reject_{r['id']}"] = True
                        if st.session_state.get(f"show_reject_{r['id']}"):
                            with st.form(key=f"reject_form_{r['id']}"):
                                reason = st.text_area(
                                    "驳回原因（必填，多行）",
                                    placeholder="例如：不认可该结论 / 不符合我的交易风格 / 规则过于严格",
                                    key=f"reject_reason_{r['id']}")
                                if st.form_submit_button("提交驳回，让 AI 重新思考", type="primary"):
                                    if not reason.strip():
                                        st.error("驳回原因不能为空，请填写后再提交")
                                    else:
                                        res = api.reject_review(r["id"], reason.strip())
                                        st.success("已驳回，AI 重思考任务已提交后台"
                                                   f"（{res.get('task_id')}），完成后顶部任务状态区会提示。")
                                        st.session_state.pop(f"show_reject_{r['id']}", None)
except Exception as exc:
    st.error(f"复盘获取失败: {exc}")
