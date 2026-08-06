"""建仓计划：PositionAgent 分批建仓方案（自然语言分段展示）

企业级列表行范式：左=状态色圆点+代码名称(加粗)+仓位与状态(副标题)，
右=生成时间+「查看详情」；详情分区卡片化，分批方案表格展示，原始 JSON 折叠在最底部。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("建仓计划（PositionAgent）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

STATUS_MAP = {"proposed": "待评估", "accepted": "已采纳", "abandoned": "已放弃"}
STATUS_DOT = {"proposed": "warn", "accepted": "ok", "abandoned": "mute"}

# 筛选防抖：输入后点「查询」才过滤（避免每敲一个字符全页 rerun + 全量请求）
f_code = st.text_input("按股票代码筛选（留空显示全部，输入后点查询）",
                       value=st.session_state.get("_plan_filter", ""),
                       key="_plan_filter_input")
c1, c2, c3 = st.columns([1, 5, 5])
with c1:
    if st.button("查询", use_container_width=True):
        st.session_state["_plan_filter"] = f_code.strip()
        st.session_state.pop("_plan_list_vis", None)
        st.rerun()
with c2:
    if st.session_state.get("_plan_filter"):
        if st.button("清除筛选"):
            st.session_state["_plan_filter"] = ""
            st.session_state.pop("_plan_list_vis", None)
            st.rerun()
code = st.session_state.get("_plan_filter", "")

try:
    rows = api.plans(code=code or None)
    if not rows:
        render.empty_state("暂无建仓方案。可在「每日候选池」「评分报告」页对标的生成，"
                           "或在下方输入代码手动生成。")
    else:
        def _plan_detail(r: dict, _i: int) -> None:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            status = STATUS_MAP.get(r["status"], r["status"])
            dot = STATUS_DOT.get(r["status"], "mute")
            subtitle = f"总仓位上限 {r['total_pct']}% · {status}"
            meta = f"生成 {str(r.get('created_at') or '')[:16]}"
            key = f"plan_{r['id']}"
            if render.list_item_toggle(key, label, subtitle=subtitle, dot=dot, meta=meta):
                with st.container(border=True):
                    render.trace_line("方案生成时间", r.get("created_at"), source="LLM 生成")
                    with st.container(border=True):
                        render.section_title("市场强弱判断与建仓逻辑")
                        st.markdown(r["rationale"] or "（无）")
                    with st.container(border=True):
                        render.section_title("仓位与风控参考")
                        st.markdown(f"- 总仓位上限：{r['total_pct']}%")
                        st.markdown(f"- 止损参考：{r['stop_loss']}　|　止盈参考：{r['take_profit']}")
                    with st.container(border=True):
                        render.section_title("分批建仓方案")
                        if r["batches"]:
                            batch_df = pd.DataFrame([
                                {"批次": b.get("tranche"), "价格区间": b.get("price_zone"),
                                 "资金占比%": b.get("ratio_pct"), "触发条件": b.get("trigger_note")}
                                for b in r["batches"]
                            ])
                            st.dataframe(batch_df, width="stretch", hide_index=True)
                        else:
                            st.markdown("（该轮未输出分批明细）")
                    render.raw_json_expander(
                        {"status": r["status"], "batches": r["batches"]},
                        key=f"raw_plan_{r['id']}")

        render.record_list(rows, _plan_detail, batch=20, key="_plan_list_vis",
                           empty_text="无匹配的建仓方案。")

    # 手动生成：代码格式原位校验（6 位数字，不合法时阻断提交并标红）
    with st.container(key="fld_manual_plan"):
        manual = st.text_input("手动生成建仓方案代码（6 位数字）", "")
    manual_name = st.text_input("股票名称（可选）", "")
    render.field_error("manual_plan", render.get_field_error("manual_plan"),
                       "请输入 6 位数字股票代码，如 603993")
    if st.button("生成建仓方案", disabled=not manual):
        if not manual.strip().isdigit() or len(manual.strip()) != 6:
            render.set_field_errors({"manual_plan": "股票代码格式不正确"})
            st.rerun()
        else:
            render.set_field_errors({})
            api.submit_task("position", {"stock_code": manual.strip(),
                                         "stock_name": manual_name.strip()})
            st.toast("建仓方案生成任务已提交后台，完成后顶部任务状态区会提示，可切换页面继续操作")
except Exception as exc:
    render.error_card("建仓计划加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key="retry_plans")
