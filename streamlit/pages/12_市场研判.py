"""市场研判底座（Market Intel）：阶段定性 / 核心矛盾 / 风险偏好 / 板块量比 / 操作含义 /
次日盯盘点 / 一句话总结 —— 作为全部 Agent 的参考维度（独立触发、独立查看）

- 每日收盘后（16:20）自动生成 1 次，也可手动「立即研判」（异步后台任务）；
- 展示当日研判全部结论 + 原始数据折叠（可追溯）；
- 数据缺失时页面与研判文本均明确标注，不编造。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次2：页面头部收敛为 page_header（立即研判/刷新 进操作按钮组）=====
_hdr = render.page_header(
    "市场研判底座（Market Intel）",
    caption="每日收盘后自动研判 1 次（16:20，独立于每日挖掘），也可手动触发；"
            "结论作为 discover/score/position/monitor/sell/review 全部 Agent 的参考维度注入，"
            "不强制改变任何判级。",
    primary_actions=[{"label": "🧠 立即研判", "key": "mi_run"}],
    secondary_actions=[{"label": "🔄 刷新", "key": "mi_refresh"}],
)
if _hdr["primary"] == 0:
    render.submit_task("market_intel", label="市场研判")
if _hdr["secondary"] == 0:
    st.rerun()

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ================= 手动触发 + 日期选择 =================
try:
    dates = api.market_intel_dates()
except Exception:  # noqa: BLE001 后端未起时降级为空
    dates = []

sel_date = st.selectbox("选择研判日期", dates or ["（暂无）"], index=0,
                        disabled=not dates)

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

# ---- 顶部核心结论（阶段定性 + 风险偏好 + 总结）置顶保留（默认即「研判结论」）----
st.markdown(
    f'<div class="advice-card"><div class="advice-title">'
    f'阶段定性 · <span class="badge badge-{_APPETITE_TONE.get(appetite, "mute")}">'
    f'风险偏好：{appetite or "（无）"}</span></div>'
    f'<div class="advice-body">{phase or "（该轮未输出）"}</div>'
    f'<div class="trace-line" style="margin-top:6px">一句话总结：{summary}</div></div>',
    unsafe_allow_html=True)

# 批次3：4 个垂直堆叠分区（核心矛盾/板块量能/操作含义/次日盯盘点）fold_module → detail_tabs，
# 结论卡保持在 Tab 上方；内容与兜底文案零删减，仅换容器
def _tab_conflict():
    st.markdown(core or "（该轮未输出）")

def _tab_volume():
    # 板块量比表（放量 TopN + 缩量 TopN + 分布）
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

def _tab_operative():
    # 操作含义（参考维度，不强制；dict/list 值结构化渲染，防 Python repr 泄漏）
    op = mi.get("operative_meaning") or {}
    if not op:
        st.caption("（该轮未输出操作含义）")
    else:
        for k, v in op.items():
            if isinstance(v, dict):
                # 箱位理解等嵌套 dict：逐项展平为可读文本（内层仍是 dict 时再展平一层）
                parts = []
                for kk, vv in v.items():
                    if isinstance(vv, dict):
                        inner = "，".join(f"{x}: {y}" for x, y in vv.items())
                        parts.append(f"{kk}({inner})")
                    else:
                        parts.append(f"{kk}: {vv}")
                st.markdown(f"- **{k}**：{'；'.join(parts)}")
            elif isinstance(v, list):
                st.markdown(f"- **{k}**：{len(v)} 条（详见下方「个股三维验证」模块）")
            else:
                st.markdown(f"- **{k}**：{v}")

def _tab_watch():
    # 次日盯盘点（前向可验证）
    nw = mi.get("next_day_watch") or {}
    if not nw:
        st.caption("（该轮未输出次日盯盘点）")
    else:
        for k, v in nw.items():
            st.markdown(f"- **{k}**：{v}")

render.detail_tabs([
    ("核心矛盾", _tab_conflict),
    ("板块量能信号", _tab_volume),
    ("操作含义", _tab_operative),
    ("次日盯盘点", _tab_watch),
], key="mi_tabs", default_index=0)

# ===== 市场研判深度化：量能成色 / 主线结构 / 箱位理解 / 个股三维验证 =====
# （4 个新维度已并入 volume_signal / operative_meaning 合并列，此处只读展示；缺失显示空态）
_vs = mi.get("volume_signal") or {}
_om = mi.get("operative_meaning") or {}

# 模块 A：量能成色（蓝信息块）
_vc = _vs.get("量能成色")
if _vc:
    st.info(f"**量能成色**：{_vc}")
else:
    st.caption("（该轮未输出量能成色）")

# 模块 B：主线结构三分类（只对有内容的分类显示色块，无内容跳过）
_ms = _vs.get("主线结构")
if isinstance(_ms, dict):
    for _key, _fn in (("进攻主线", st.success), ("接力方向", st.info), ("退潮方向", st.error)):
        _val = _ms.get(_key)
        if _val:
            _fn(f"**{_key}**：{_val}")
else:
    st.caption("（今日无该类方向数据）")

# 模块 C：箱位理解表（主升初期绿行 / 真出货红行，参考权重）
_bv = _om.get("箱位理解")
if isinstance(_bv, dict) and _bv:
    st.markdown("**箱位理解**（主箱位/60日箱位组合解读）")
    _box_rows = []
    for _bname, _bdata in _bv.items():
        if not isinstance(_bdata, dict):
            continue
        _box_rows.append({"板块": _bname, "主箱位%": _bdata.get("main_box"),
                          "60日箱位%": _bdata.get("box60"),
                          "解读": _bdata.get("interpretation", "")})
    if _box_rows:
        def _box_style(row):
            mb, b60 = row["主箱位%"], row["60日箱位%"]
            if isinstance(mb, (int, float)) and isinstance(b60, (int, float)):
                if mb >= 90 and b60 < 40:    # 短箱贴顶 + 60日箱位低 → 主升初期
                    return ["background-color: rgba(16, 185, 129, 0.12)"] * len(row)
                if mb >= 90 and b60 >= 90:   # 长短双高 → 真出货风险
                    return ["background-color: rgba(239, 68, 68, 0.12)"] * len(row)
            return [""] * len(row)
        st.dataframe(pd.DataFrame(_box_rows).style.apply(_box_style, axis=1),
                     width="stretch", hide_index=True)
else:
    st.caption("（该轮未输出箱位理解）")

# 模块 D：个股强度三维验证表（真强绿 / 加速后段橙 / 放量滞涨黄 / 弱势红）
_sv = _om.get("个股验证")
if isinstance(_sv, list) and _sv:
    st.markdown("**个股强度三维验证**（主线板块内抽样，涨幅前5）")
    _ver_style = {"真强": "rgba(16, 185, 129, 0.12)", "加速后段": "rgba(245, 158, 11, 0.12)",
                  "放量滞涨": "rgba(234, 179, 8, 0.12)", "弱势": "rgba(239, 68, 68, 0.12)"}
    _ver_rows = []
    for _s in _sv:
        if not isinstance(_s, dict):
            continue
        _ver_rows.append({"名称": _s.get("name", ""), "涨幅%": _s.get("change_pct"),
                          "量比": _s.get("volume_ratio"), "60日箱位%": _s.get("box60"),
                          "判定": _s.get("verdict", ""), "依据": _s.get("basis", "")})
    if _ver_rows:
        def _ver_style(row):
            _color = _ver_style.get(row["判定"])
            return [f"background-color: {_color}"] * len(row) if _color else [""] * len(row)
        st.dataframe(pd.DataFrame(_ver_rows).style.apply(_ver_style, axis=1),
                     width="stretch", hide_index=True)
else:
    st.caption("（该轮未输出个股验证）")

render.trace_line("研判生成时间", mi.get("created_at"), source="LLM 研判（5 大思考维度）")

# ---- 原始数据折叠（可追溯，不编造） ----
render.raw_json_expander({"研判结论": {k: mi.get(k) for k in
                                    ("phase", "core_conflict", "risk_appetite",
                                     "volume_signal", "operative_meaning", "next_day_watch",
                                     "summary")},
                          "输入原始数据": mi.get("raw") or {}},
                         key="mi_raw")
