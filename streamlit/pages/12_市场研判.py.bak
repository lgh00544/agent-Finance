"""市场研判底座（Market Intel）：阶段定性 / 核心矛盾 / 风险偏好 / 板块量比 / 操作含义 /
次日盯盘点 / 一句话总结 —— 作为全部 Agent 的参考维度（独立触发、独立查看）

- 每日收盘后（16:20）自动生成 1 次，也可手动「立即研判」（异步后台任务）；
- 展示当日研判全部结论 + 原始数据折叠（可追溯）；
- 数据缺失时页面与研判文本均明确标注，不编造。
"""
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("市场研判底座（Market Intel）")
st.caption("每日收盘后自动研判 1 次（16:20，独立于每日挖掘），也可手动触发；"
           "结论作为 discover/score/position/monitor/sell/review 全部 Agent 的参考维度注入，"
           "不强制改变任何判级。")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ================= 手动触发 + 日期选择 =================
try:
    dates = api.market_intel_dates()
except Exception:  # noqa: BLE001 后端未起时降级为空
    dates = []

c1, c2, c3 = st.columns([2, 1.5, 1.2])
with c1:
    sel_date = st.selectbox("选择研判日期", dates or ["（暂无）"], index=0,
                            disabled=not dates)
with c2:
    if st.button("立即研判", type="primary", use_container_width=True):
        render.submit_task("market_intel", label="市场研判")
with c3:
    if st.button("刷新", use_container_width=True):
        st.rerun()

if not dates:
    render.empty_state("当日暂无市场研判，可点击上方「立即研判」生成（后台约 1-2 分钟）。",
                       icon="🧠", action_label="立即研判",
                       action_key="mi_empty_run")
    if st.session_state.get("mi_empty_run"):
        render.submit_task("market_intel", label="市场研判")
        st.session_state["mi_empty_run"] = False
    st.stop()

# ================= 当日研判展示 =================
try:
    row = api.market_intel(sel_date)
except Exception as exc:  # noqa: BLE001
    title, hint, tech = render.classify_api_error(exc)
    render.error_card(title, hint, detail=tech, retry_key="retry_mi")
    st.stop()

mi = row or {}
phase = str(mi.get("phase") or "")
core = str(mi.get("core_conflict") or "")
appetite = str(mi.get("risk_appetite") or "")
_APPETITE_TONE = {"进取": "up", "中性": "mute", "避险": "warn"}
summary = str(mi.get("summary") or "")

# ---- 顶部核心结论（阶段定性 + 风险偏好 + 总结） ----
st.markdown(
    f'<div class="advice-card"><div class="advice-title">'
    f'阶段定性 · <span class="badge badge-{_APPETITE_TONE.get(appetite, "mute")}">'
    f'风险偏好：{appetite or "（无）"}</span></div>'
    f'<div class="advice-body">{phase or "（该轮未输出）"}</div>'
    f'<div class="trace-line" style="margin-top:6px">一句话总结：{summary}</div></div>',
    unsafe_allow_html=True)

with render.fold_module("mi_conflict", "核心矛盾", default_open=True):
    st.markdown(core or "（该轮未输出）")

# ---- 板块量比表（放量 TopN + 缩量 TopN + 分布） ----
with render.fold_module("mi_volume", "板块量能信号（量比）", default_open=True):
    vs = mi.get("volume_signal") or {}
    if not vs:
        st.caption("（该轮未输出量能信号）")
    else:
        expand = st.expander("查看放量 / 缩量板块明细", expanded=True)
        with expand:
            st.markdown(f"**放量板块**：{vs.get('放量板块') or '（无/数据缺失）'}")
            st.markdown(f"**缩量板块**：{vs.get('缩量板块') or '（无/数据缺失）'}")
            if vs.get("极端量能"):
                st.markdown(f"**极端量能**：{vs['极端量能']}")
            if vs.get("缺失标注"):
                st.caption(f"数据缺失标注：{vs['缺失标注']}")
        if vs.get("分布") is not None:
            st.markdown(f"**放量/缩量分布**：{vs['分布']}")

# ---- 操作含义 ----
with render.fold_module("mi_operative", "操作含义（参考维度，不强制）", default_open=True):
    op = mi.get("operative_meaning") or {}
    if not op:
        st.caption("（该轮未输出操作含义）")
    else:
        for k, v in op.items():
            st.markdown(f"- **{k}**：{v}")

# ---- 次日盯盘点 ----
with render.fold_module("mi_watch", "次日盯盘点（前向可验证）", default_open=True):
    nw = mi.get("next_day_watch") or {}
    if not nw:
        st.caption("（该轮未输出次日盯盘点）")
    else:
        for k, v in nw.items():
            st.markdown(f"- **{k}**：{v}")

render.trace_line("研判生成时间", mi.get("created_at"), source="LLM 研判（5 大思考维度）")

# ---- 原始数据折叠（可追溯，不编造） ----
render.raw_json_expander({"研判结论": {k: mi.get(k) for k in
                                    ("phase", "core_conflict", "risk_appetite",
                                     "volume_signal", "operative_meaning", "next_day_watch",
                                     "summary")},
                          "输入原始数据": mi.get("raw") or {}},
                         key="mi_raw")
