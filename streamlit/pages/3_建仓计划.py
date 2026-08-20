"""建仓计划：PositionAgent 分批建仓方案（数据同源联动 + 分级缓存）

数据链路（与评分报告/每日候选池 100% 同源）：
- 标的来源唯一：仅综合评级 ≥B 的标的可生成（后端强校验）；C 级及以下拒绝并提示「评级不足」；
- 三级同源联动：每日候选 B+ 自动生成入库 / 手动输入自动先评分再判级；
- 去重：同一标的同一交易日仅保留最新一份计划。

分级缓存：A 级实时数据（每次生成重新计算）；B 级 30 分钟缓存（30 分钟内复用，零 LLM 消耗）；
每条计划标注「实时数据 / 30分钟缓存」时效标签，右侧可手动刷新击穿缓存。

页面结构：顶部选标（候选池下拉 + 手动输入）+ 日期/评级筛选 → 二级折叠列表（默认折叠，
轻量展开按钮 + 批量操作栏）→ 展开详情分层（分档买入 → 仓位分配 → 止损止盈 → 风险提示 →
生成依据）→ 底部保留手动生成代码入口。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次2：页面头部收敛为 page_header 单行范式 =====
render.page_header(
    "建仓计划（PositionAgent）",
    caption="PositionAgent 分批建仓方案：A 级实时数据 / B 级 30 分钟缓存；仅综合评级 ≥B 级可生成。",
)

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

STATUS_MAP = {"proposed": "待评估", "accepted": "已采纳", "abandoned": "已放弃"}
STATUS_DOT = {"proposed": "warn", "accepted": "ok", "abandoned": "mute"}
GRADE_TONE = {"A": "tier-a", "B": "tier-b", "C": "tier-c"}
FRESHNESS_LABEL = {"realtime": "实时数据", "cache30m": "30分钟缓存"}
FRESHNESS_TONE = {"realtime": "ok", "cache30m": "warn"}
SOURCE_LABEL = {"candidate": "每日候选池", "manual": "手动生成"}
SOURCE_TONE = {"candidate": "info", "manual": "mute"}
_TP_RED = "#EF4444"    # 止损价红
_TP_GREEN = "#10B981"  # 止盈价绿

# ================= 顶部选标与生成区 =================
# 数据源与页面数据同源：最新一轮候选池 + 全量评分（评级映射）
score_map: dict = {}
try:
    for s in api.scores(limit=500) or []:
        score_map.setdefault(s["stock_code"], s)
except Exception:  # noqa: BLE001 评分数据失败降级：评级显示「—」，不阻断页面
    pass

pool_options = []
try:
    cand_rows = api.candidates(limit=50) or []
    if cand_rows:
        latest_date = cand_rows[0].get("trade_date") or ""
        pool_options = [r for r in cand_rows if r.get("trade_date") == latest_date]
except Exception:  # noqa: BLE001 候选池失败降级：下拉为空，手动输入仍可用
    pool_options = []

with st.expander("➕ 新建建仓计划", expanded=False):
    st.markdown("**生成建仓计划**（仅综合评级 ≥B 级标的可生成；C 级及以下会提示「评级不足」）")
    sel_col, man_col, btn_col = st.columns([2.2, 1.6, 1.2], vertical_alignment="center")
    with sel_col:
        _pool_labels = ["（从候选池选择）"] + [
            f"{r['stock_code']} {r['stock_name']}（{score_map.get(r['stock_code'], {}).get('grade', '—')} 级）"
            for r in pool_options]
        sel = st.selectbox("候选池标的（最新一轮）", _pool_labels, key="_plan_pool_sel",
                           label_visibility="collapsed")
    with man_col:
        manual = st.text_input("或手动输入代码（6 位数字）", key="_plan_manual_input",
                               label_visibility="collapsed",
                               placeholder="或手动输入 6 位股票代码")
    with btn_col:
        # C 级选中 → 生成按钮置灰 + 提示（手动输入不受下拉限制，后端仍强校验）
        _sel_grade = None
        if not sel.startswith("（"):
            _sel_grade = score_map.get(sel.split(" ")[0], {}).get("grade")
        _disabled = not (manual.strip() or (not sel.startswith("（") and _sel_grade in ("A", "B")))
        if st.button("生成建仓计划", type="primary", use_container_width=True,
                     disabled=_disabled):
            target = None
            if manual.strip().isdigit() and len(manual.strip()) == 6:
                target = {"stock_code": manual.strip(), "source": "manual"}
            elif not sel.startswith("（"):
                code = sel.split(" ")[0]
                name = next((r["stock_name"] for r in pool_options
                             if r["stock_code"] == code), "")
                target = {"stock_code": code, "stock_name": name, "source": "manual"}
            if target is None:
                render.msg_card("warn", "请选择候选池标的或输入 6 位数字股票代码")
            else:
                render.submit_task("position", target, label="建仓方案生成")
                st.toast(f"建仓方案生成任务已提交后台（{target['stock_code']}），"
                         "评级校验与生成完成后顶部任务状态区会提示；B 级标的 30 分钟内复用缓存")
        if not manual.strip() and not sel.startswith("（") and _sel_grade not in ("A", "B"):
            render.msg_card("warn", "评级不足 B 级（建议谨慎建仓）：生成按钮已置灰；"
                            "如需强制生成可手动输入代码提交（后端仍会按评级强校验）")

# ================= 日期 / 评级筛选（前端过滤，零额外接口） =================
try:
    rows = api.plans(limit=200)
except Exception:  # noqa: BLE001 后端未起时降级空态
    rows = []

if rows:
    dates = sorted({str(r.get("plan_date") or (r.get("created_at") or "")[:10]) for r in rows},
                   reverse=True)
    f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.3, 3.5])
    with f1:
        date_sel = st.selectbox("日期筛选", ["全部日期"] + dates, key="_plan_date_sel")
    with f2:
        grade_sel = st.selectbox("评级筛选", ["全部评级", "A 级", "B 级", "C 级", "未评级"],
                                 key="_plan_grade_sel")
    with f3:
        source_sel = st.selectbox("来源筛选", ["全部来源", "每日候选池", "手动生成"],
                                  key="_plan_source_sel")
    with f4:
        _plan_cap_txt = ""
        try:
            _tv = api.candidate_tradeable(limit=100)
            _plan_cap_txt = (f" · 今日可自动生成建仓计划的标的 "
                             f"{int(_tv.get('plan_candidate_count') or 0)} 只")
        except Exception:  # noqa: BLE001 联动数字失败仅降级，不影响计划展示
            _plan_cap_txt = ""
        st.caption(f"共 {len(rows)} 条计划 · 仅 B 级及以上标的可生成（后端强校验）{_plan_cap_txt}")
    if date_sel != "全部日期":
        rows = [r for r in rows if str(r.get("plan_date") or "") == date_sel]
    if grade_sel != "全部评级":
        if grade_sel == "未评级":
            rows = [r for r in rows
                    if not score_map.get(r["stock_code"], {}).get("grade")]
        else:
            target = grade_sel[0]
            rows = [r for r in rows
                    if score_map.get(r["stock_code"], {}).get("grade") == target]
    if source_sel != "全部来源":
        _src_key = {"每日候选池": "candidate", "手动生成": "manual"}[source_sel]
        rows = [r for r in rows if (r.get("source") or "manual") == _src_key]

# ================= 建仓计划列表（二级折叠卡片 + 批量操作） =================
if not rows:
    render.empty_state("暂无建仓方案。可在上方从候选池选择或手动输入代码生成；"
                       "每日候选 B 级及以上标的会自动生成入库。")
else:
    plan_keys = [f"plan_{r['id']}" for r in rows]
    render.batch_fold_bar("plan", plan_keys,
                          label="点击行内「查看详情」展开完整建仓内容；单条右侧可手动刷新击穿缓存。")

    def _plan_detail(r: dict, _i: int) -> None:
        label = render.stock_label(r["stock_code"], r["stock_name"])
        status = STATUS_MAP.get(r["status"], r["status"])
        dot = STATUS_DOT.get(r["status"], "mute")
        grade = score_map.get(r["stock_code"], {}).get("grade") or "—"
        source = r.get("source") or "manual"
        detail = r.get("detail") or {}
        quant = detail.get("quant") or {}
        freshness = detail.get("freshness")
        # 默认折叠态：标的名称 + 评级 + 来源 + 总仓位上限 + 止损止盈价
        sub_parts = [f"总仓位上限 {r['total_pct']}%", f"评级 {grade}",
                     SOURCE_LABEL.get(source, source), status]
        if freshness:
            sub_parts.append(FRESHNESS_LABEL.get(freshness, ""))
        sl, tp = r.get("stop_loss") or "—", r.get("take_profit") or "—"
        sub_parts.append(f"止损 {sl} / 止盈 {tp}")
        meta = (f'<span class="badge badge-{GRADE_TONE.get(grade, "mute")}">{grade} 级</span>'
                f'<span class="badge badge-{SOURCE_TONE.get(source, "mute")}">'
                f'{SOURCE_LABEL.get(source, source)}</span>'
                + (f'<span class="badge badge-{FRESHNESS_TONE.get(freshness, "mute")}">'
                   f'{FRESHNESS_LABEL.get(freshness, "")}</span>' if freshness else "")
                + f"　生成 {str(r.get('created_at') or '')[:16]}")
        key = f"plan_{r['id']}"
        if render.list_item_toggle(key, label, subtitle=" · ".join(sub_parts),
                                   dot=dot, meta=meta, scope="plan"):
            with st.container(border=True):
                render.trace_line("方案生成时间", r.get("created_at"), source="LLM 生成")
                # 批次2：操作前置——手动刷新（击穿缓存重算）提到详情首行
                _act = render.quick_actions(f"plan_act_{key}", [
                    {"label": "🔄 手动刷新本计划（击穿缓存重算）", "type": "primary"},
                ])
                if _act == 0:
                    render.submit_task("position", {"stock_code": r["stock_code"],
                                                    "stock_name": r["stock_name"]},
                                       label="建仓方案重算")
                    st.toast("已提交建仓方案重算任务，完成后顶部任务状态区会提示")
                # 批次2：5 分区垂直堆叠 → detail_tabs（默认停「分档买入」；字段与文案零删减仅换容器）
                def _tab_batches():
                    # 分档买入明细（表格化：价格/金额/股数/累计占比）
                    render.section_title("分档买入明细")
                    qb = quant.get("batches") if quant else None
                    if qb:
                        batch_df = pd.DataFrame([
                            {"批次": b.get("tranche"), "价格区间": b.get("price_zone"),
                             "触发条件": b.get("trigger_note"), "投入金额": b.get("amount"),
                             "买入股数": b.get("shares"), "累计仓位占比%": b.get("cum_pct")}
                            for b in qb
                        ])
                        st.dataframe(batch_df, width="stretch", hide_index=True)
                        st.markdown(f"**合计**：总投入 **{quant.get('total_amount') or '—'} 元**，"
                                    f"总持股 **{quant.get('total_shares') or '—'} 股**，"
                                    f"不突破 C1 单票上限 {quant.get('position_cap_pct', '—')}%")
                    elif r["batches"]:
                        # 旧数据降级：LLM 比例明细
                        batch_df = pd.DataFrame([
                            {"批次": b.get("tranche"), "价格区间": b.get("price_zone"),
                             "资金占比%": b.get("ratio_pct"), "触发条件": b.get("trigger_note")}
                            for b in r["batches"]
                        ])
                        st.dataframe(batch_df, width="stretch", hide_index=True)
                    else:
                        st.markdown("（该轮未输出分批明细）")

                def _tab_allocation():
                    # 核心信息总览（仓位分配量化数值，6 项一眼看懂）
                    render.section_title("核心信息总览（量化数值，可直接对照执行）")
                    q = quant
                    if q:
                        be = q.get("breakeven_ratio")
                        be_txt = (f"**{be}:1**" + ("　✅ 满足 ≥3:1 硬性要求" if q.get("breakeven_ok")
                                                   else "　⚠️ 不足 3:1，仓位已自动降低"))
                        st.markdown(
                            f"- **当前股价**：{q.get('current_price') or '—'} 元"
                            f"（数据日期 {q.get('price_date') or '—'}）\n"
                            f"- **单票总仓位上限**：{q.get('position_cap_pct', '—')}%（评级分级 C1）"
                            f" → 金额 **{q.get('position_amount') or '—'} 元**"
                            f"（可买 {q.get('position_shares') or '—'} 股，100 股整数倍）\n"
                            f"- **账户可用资金**：{q.get('available_capital') or '—'} 元"
                            f"（总资产 {q.get('total_capital') or '—'} 元，C2 总仓 60% 约束）\n"
                            f"- <span style='color:{_TP_RED};font-weight:600'>**初始止损价**："
                            f"{q.get('initial_stop') or '—'} 元</span>"
                            f"（C3 成本×0.92 与 LLM 止损取更严）\n"
                            f"- <span style='color:{_TP_GREEN};font-weight:600'>**第一止盈价**："
                            f"{q.get('take_profit') or '—'} 元</span>（波段目标/前高压力综合）\n"
                            f"- **盈亏比**：{be_txt}")
                        if q.get("expected_total_pct") is not None:
                            st.markdown(f"- **建仓后预计总仓位**：{q['expected_total_pct']}%"
                                        f"（C2 上限 60%，{'未突破' if q['expected_total_pct'] <= 60 else '**已接近上限**'}）")
                        for note in q.get("notes") or []:
                            render.msg_card("warn" if "不足" in note or "缩减" in note else "info",
                                            "量化提示", note)
                    else:
                        st.caption("该计划为旧数据（量化功能上线前生成），仅展示 LLM 原始数值："
                                   f"当前价与金额量化不可用；止损 {sl} / 止盈 {tp} 为参考值。")

                def _tab_rules():
                    # 止盈止损与风控规则
                    render.section_title("止盈止损与风控规则")
                    init_stop = (quant.get("initial_stop") if quant else None) or r["stop_loss"]
                    st.markdown(f"- **止损规则**：初始止损位 **{init_stop}**（C3 硬止损，跌破无条件离场）；"
                                "阶梯上移：到达第一止盈位后止损上移至成本价")
                    st.markdown(f"- **止盈规则**：第一目标位 **{quant.get('take_profit') if quant else r['take_profit']}**"
                                " 减仓 1/3 锁利 → 第二目标位再减仓 1/3 → 剩余仓位移动止盈持有")
                    st.markdown(f"- **仓位红线**：单票不超过 C1 上限"
                                f"（{quant.get('position_cap_pct', '—')}%，评级分级）；"
                                f"总仓位不超过 C2 上限 60%；本计划建仓后预计总仓位 "
                                f"{quant.get('expected_total_pct') if quant else '—'}%")
                    st.markdown("⚠️ 标的自身风险与大盘系统性风险请结合评分风险清单综合判断；"
                                "**所有建议仅作参考，最终交易由人工判断**。")

                def _tab_logic():
                    # 市场强弱判断与建仓逻辑（分档买入依据）
                    render.section_title("市场强弱判断与建仓逻辑")
                    st.markdown(detail.get("market_regime") or "（无）")
                    st.markdown(r["rationale"] or "（无）")

                def _tab_evidence():
                    # 生成依据（评级依据：评分 + 风险清单，与评分报告同源）
                    sc = score_map.get(r["stock_code"], {})
                    if sc:
                        render.section_title("生成依据（评级依据）")
                        st.markdown(f"- 综合评级：**{sc.get('grade', '—')} 级**"
                                    f"（{sc.get('score', '—')} 分，评分报告同源数据）")
                        risks = sc.get("risk_list") or []
                        if risks:
                            st.markdown("- 风险提示：")
                            for risk in risks:
                                st.markdown(f"  - {risk}")
                        else:
                            st.markdown("- 风险提示：（该轮未输出）")
                    # v3.0 白盒维度归因：维度数组 + 综合评估（主结论；旧数据缺省自动跳过）
                    render.section_title("维度归因（六因子白盒，主结论）")
                    render.dimension_bars(detail.get("dimensions"),
                                          final_advice=detail.get("final_advice"))

                render.detail_tabs([
                    ("分档买入", _tab_batches),
                    ("仓位分配", _tab_allocation),
                    ("止盈止损", _tab_rules),
                    ("建仓逻辑", _tab_logic),
                    ("生成依据", _tab_evidence),
                ], key=f"plan_tabs_{key}", default_index=0)
                render.raw_json_expander(
                    {"status": r["status"], "batches": r["batches"]},
                    key=f"raw_plan_{r['id']}")

    render.record_list(rows, _plan_detail, batch=20, key="_plan_list_vis",
                       empty_text="无匹配的建仓方案。")

# ================= 底部：手动生成建仓方案代码（保留原功能入口） =================
with st.container(key="fld_manual_plan"):
    manual_code = st.text_input("手动生成建仓方案代码（6 位数字）", "")
manual_name = st.text_input("股票名称（可选）", "")
render.field_error("manual_plan", render.get_field_error("manual_plan"),
                   "请输入 6 位数字股票代码，如 603993")
if st.button("生成建仓方案", disabled=not manual_code):
    if not manual_code.strip().isdigit() or len(manual_code.strip()) != 6:
        render.set_field_errors({"manual_plan": "股票代码格式不正确"})
        st.rerun()
    else:
        render.set_field_errors({})
        render.submit_task("position", {"stock_code": manual_code.strip(),
                                        "stock_name": manual_name.strip()},
                           label="建仓方案生成")
        st.toast("建仓方案生成任务已提交后台（无评分将自动先评分），"
                 "完成后顶部任务状态区会提示，可切换页面继续操作")
