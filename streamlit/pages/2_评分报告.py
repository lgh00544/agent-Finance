"""评分报告：ScoreAgent 五维评分（A/B/C 分级 + 风险清单，自然语言分段展示）

列表-详情联动范式：上方总览表格（on_select 单选行，点击行详情立即切换，行高亮+左侧色条），
下方仅渲染当前选中标的的详情卡片（数据全部来自本地已加载 rows，切换零请求）；
详情分区卡片化（五维/K202/派发期/三维/操作建议/风险），原始 JSON 永久折叠在最底部。
名称缺失的标的经只读补名接口自动补全（不写库），仍缺失的显示「名称待补」。
纯展示层，不含任何二次判断逻辑。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("评分报告（ScoreAgent）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

TABLE_KEY = "_score_table"       # st.dataframe 控件 key（原生选中/高亮）
SEL_KEY = "_score_selected_id"   # 逻辑选中 record id（筛选后行变，id 不失效）
FP_KEY = "_score_table_fp"       # 当前 rows 的 id 指纹（数据集合变化时重置选中）
NAME_KEY = "_score_names_cache"  # 补名结果缓存（防每轮 rerun 重复请求）

# 评级 → 徽章 tone 与表格列色（与全局 --tier-a/b/c 同源：A 红 / B 橙 / C 蓝）
_GRADE_TONE = {"A": "a", "B": "b", "C": "c"}
_GRADE_COLOR = {"A": "#ef4444", "B": "#f59e0b", "C": "#3b82f6"}


def _score_detail_card(r: dict) -> None:
    """选中记录详情卡片：数据全部来自本地 rows，切换标的零请求"""
    label = render.stock_label(r["stock_code"], r["stock_name"])
    grade = str(r.get("grade") or "")
    badge_tone = _GRADE_TONE.get(grade, "mute")
    d = r.get("detail") or {}
    with st.container(border=True):
        hl, hr = st.columns([3.4, 1.2], vertical_alignment="center")
        with hl:
            st.markdown(f'<div class="item-title">{label}　{r["trade_date"]}</div>',
                        unsafe_allow_html=True)
            render.trace_line("评分生成时间", r.get("created_at"), source="LLM 生成")
        with hr:
            render.stat_cards([{"label": "综合分", "value": r["score"]}])
            render.badge(f"{grade} 级" if grade else "未评级", badge_tone)

        # 分区一：五维分项评分（结构为 {维度: {score, comment}} 的字段才进表）
        with st.container(border=True):
            render.section_title("五维分项评分")
            dims = {k: v for k, v in d.items() if isinstance(v, dict) and "score" in v}
            if dims:
                dim_df = pd.DataFrame([
                    {"维度": name, "得分": v.get("score", ""),
                     "研判依据": v.get("comment", "")} for name, v in dims.items()
                ])
                st.dataframe(dim_df, width="stretch", hide_index=True)
            else:
                st.markdown("（该轮未输出分项明细）")

        # 分区二：候选研判附属区（评分记录内嵌候选结论时展示；缺失则整段不渲染）
        if d.get("confidence_tier"):
            with st.container(border=True):
                render.section_title("K202 信心度检查")
                st.markdown(f"- 信心度档位：{d['confidence_tier']}"
                            + (f"（参考 {d.get('confidence_pct')}%）"
                               if d.get("confidence_pct") else ""))
        if d.get("stock_type"):
            with st.container(border=True):
                render.section_title("派发期校验（标的类型定位）")
                st.markdown(f"- {d['stock_type']}")
        if any(d.get(k) for k in ("macro_view", "meso_view", "micro_view")):
            with st.container(border=True):
                render.section_title("三维验证（宏观 / 中观 / 微观）")
                st.markdown(f"- 宏观：{d.get('macro_view') or '（无）'}")
                st.markdown(f"- 中观：{d.get('meso_view') or '（无）'}")
                st.markdown(f"- 微观：{d.get('micro_view') or '（无）'}")
        if d.get("position_hint") or d.get("focus_type"):
            with st.container(border=True):
                render.section_title("操作建议")
                if d.get("focus_type"):
                    st.markdown(f"- 关注类型：{d['focus_type']}")
                if d.get("position_hint"):
                    st.markdown(f"- 参考建议：{d['position_hint']}")

        # 分区三：风险清单
        with st.container(border=True):
            render.section_title("风险清单")
            risks = r.get("risk_list") or []
            if risks:
                for risk in risks:
                    st.markdown(f"- {risk}")
            else:
                st.markdown("（无）")

        # 原始数据永久折叠在最底部
        render.raw_json_expander(
            {"detail": r["detail"], "risk_list": r["risk_list"]},
            key=f"raw_score_{r['id']}")
        if st.button("生成建仓方案", key=f"scoreplan_{r['id']}"):
            api.submit_task("position", {"stock_code": r["stock_code"],
                                         "stock_name": r["stock_name"]})
            st.toast("建仓方案生成任务已提交后台，可切换页面继续操作")


try:
    # 预取全量评分（后端 _dbq 60s 缓存）：日期选项列表 + 代码/名称筛选都基于该数据集，
    # 名称筛选在前端做子串匹配（数据量小，无需额外接口），代码筛选同理本地完成
    all_rows = api.scores()

    # ---- 补名（展示层只读回填，不写库；一次请求 + session_state 缓存；失败静默降级为「名称待补」）----
    names = st.session_state.setdefault(NAME_KEY, {})
    missing = sorted({r["stock_code"] for r in all_rows
                      if not (r.get("stock_name") or "").strip()
                      or r.get("stock_name") == r["stock_code"]})
    need = [c for c in missing if c not in names]
    if need:
        try:
            names.update(api.stock_names(need))
        except Exception:  # noqa: BLE001 补名失败不阻塞页面（旧后端 404 等）
            pass
    for r in all_rows:
        nm = names.get(r["stock_code"])
        if nm:
            r["stock_name"] = nm

    dates = sorted({r["trade_date"] for r in all_rows}, reverse=True)

    # ---- 搜索筛选区：代码/名称搜索 + 日期筛选 单行排布，点「查询」才生效（防抖） ----
    q1, q2, q3, q4 = st.columns([3, 2, 1, 1])
    with q1:
        f_code = st.text_input("按代码或名称搜索（留空显示全部，输入后点查询）",
                               value=st.session_state.get("_score_filter", ""),
                               key="_score_filter_input")
    with q2:
        f_date = st.selectbox("选择日期", ["全部"] + dates, key="_score_date")
    with q3:
        if st.button("查询", use_container_width=True):
            st.session_state["_score_filter"] = f_code.strip()
            st.session_state.pop(SEL_KEY, None)  # 筛选后默认选中第一行
            st.rerun()
    with q4:
        active = bool(st.session_state.get("_score_filter")) or f_date != "全部"
        if st.button("清除筛选", use_container_width=True, disabled=not active):
            st.session_state["_score_filter"] = ""
            st.session_state["_score_date"] = "全部"
            st.session_state.pop(SEL_KEY, None)
            st.rerun()

    code = st.session_state.get("_score_filter", "")
    date = st.session_state.get("_score_date", "全部")
    rows = [r for r in all_rows
            if (not code or code in (r["stock_code"] or "")
                or code in (r.get("stock_name") or ""))
            and (date == "全部" or r["trade_date"] == date)]

    if not rows:
        render.empty_state("暂无匹配的评分数据。可输入代码/名称或切换日期，"
                           "也可在页面底部输入代码手动触发打分。")
    else:
        row_by_id = {r["id"]: r for r in rows}
        fp = tuple(r["id"] for r in rows)

        # ---- 数据集合变化（查询/清除/日期/后台刷新）→ 重置原生选中（仍存在的选中保留）----
        if fp != st.session_state.get(FP_KEY):
            cur = st.session_state.get(SEL_KEY)
            if cur in row_by_id:
                pos = next(i for i, r in enumerate(rows) if r["id"] == cur)
            else:
                st.session_state[SEL_KEY] = rows[0]["id"]
                pos = 0
            st.session_state[TABLE_KEY] = {"selection": {"rows": [pos], "columns": [], "cells": []}}
            st.session_state[FP_KEY] = fp

        # ---- 点击分支：预读 widget 值（用户点击在脚本运行前已写入 session_state，零滞后）----
        sel_rows = (st.session_state.get(TABLE_KEY) or {}).get("selection", {}).get("rows") or []
        if sel_rows and 0 <= sel_rows[0] < len(rows):
            st.session_state[SEL_KEY] = rows[sel_rows[0]]["id"]
        sel_id = st.session_state.get(SEL_KEY)
        if sel_id not in row_by_id:  # 兜底：默认选中第一行
            sel_id = rows[0]["id"]
            st.session_state[SEL_KEY] = sel_id
        sel_row = row_by_id[sel_id]

        # 列表固定列：股票（代码+名称）/日期/综合分/评级/生成时间
        overview = pd.DataFrame([
            {"股票": render.stock_label(r["stock_code"], r["stock_name"]),
             "日期": r["trade_date"], "综合分": r["score"], "评级": r["grade"],
             "生成时间": str(r.get("created_at") or "")[:16]} for r in rows
        ])

        def _tbl_style(df: pd.DataFrame) -> pd.DataFrame:
            """评级彩色（A 红/B 橙/C 蓝，与全局色板同值）+ 选中行背景高亮 + 首列左侧蓝色色条"""
            css = pd.DataFrame("", index=df.index, columns=df.columns)
            for i, g in enumerate(df["评级"]):
                if g in _GRADE_COLOR:
                    css.loc[df.index[i], "评级"] = f"color: {_GRADE_COLOR[g]}"
            pos = next((i for i, r in enumerate(rows) if r["id"] == sel_row["id"]), None)
            if pos is not None:
                for c in df.columns:
                    css.loc[df.index[pos], c] = "background-color: rgba(59, 130, 246, 0.14);"
                css.loc[df.index[pos], df.columns[0]] += "border-left: 3px solid #3b82f6;"
            return css

        # 表格固定高度内部滚动；详情区随页滚动，总览始终可见
        st.dataframe(overview.style.apply(_tbl_style, axis=None),
                     key=TABLE_KEY, on_select="rerun", selection_mode="single-row",
                     hide_index=True, width="stretch", height=360)

        _score_detail_card(sel_row)

    # 手动打分：代码格式原位校验（6 位数字，不合法时阻断提交并标红）
    with st.container(key="fld_manual_score"):
        manual = st.text_input("手动打分股票代码（6 位数字）", "")
    render.field_error("manual_score", render.get_field_error("manual_score"),
                       "请输入 6 位数字股票代码，如 603993")
    if st.button("触发打分", disabled=not manual):
        if not manual.strip().isdigit() or len(manual.strip()) != 6:
            render.set_field_errors({"manual_score": "股票代码格式不正确"})
            st.rerun()
        else:
            render.set_field_errors({})
            api.submit_task("score", {"stock_code": manual.strip(), "stock_name": ""})
            st.toast("打分任务已提交后台，完成后顶部任务状态区会提示，可切换页面继续操作")
except Exception as exc:
    render.error_card("评分报告加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key="retry_scores")
