"""系统概览首页：企业级后台范式
顶部操作行（更新时间 + 高频按钮）→ 3 个 Tab：
- 运行状态：5 系统服务横向卡片 + 定时任务调度；
- 今日概览：核心指标卡（候选/持仓/告警/今日盈亏/市况）+ 持仓建议/紧急告警展开 + 次要模块收纳；
- 性能统计：LLM 运行统计 + 数据源状态（当日累计，可手动刷新）。
底部：任务执行记录列表（状态圆点 + 失败一键重试）。
纯展示：全部内容来自 backend API 的原始数据与 LLM 输出结论，不内置任何二次判断。
强时效规范：每条业务数据均标注生成/检测时间（北京时间，浅色小字）。
"""
from datetime import datetime, timedelta, timezone

import streamlit as st

import api_client as api
import render

CN_TZ = timezone(timedelta(hours=8))

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("单人 A 股全生命周期决策 Agent 系统")

# 合规风险提示条（业务规则级警示，顶部显著标注；不阻断任何操作）
render.msg_card("warn", "本系统为个人研究辅助工具：只输出分析报告、打分、仓位建议与预警信号，"
                "不包含任何自动下单/实盘交易功能，所有交易必须由你人工执行。")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ============ 顶部操作行：左=数据更新时间，右=高频操作按钮 ============
top1, top2, top3 = st.columns([3, 1, 1])
with top1:
    render.time_text("当前数据更新于", datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M"))
with top2:
    if st.button("手动刷新全部数据", use_container_width=True):
        st.rerun()
with top3:
    if st.button("手动触发每日挖掘", type="primary", use_container_width=True):
        render.submit_task("daily_pipeline", label="每日挖掘")

SEVERITY_MAP = {"info": "一般", "warning": "警告", "critical": "严重"}
ACTION_MAP = {"hold": "持有", "reduce": "减仓", "exit": "清仓"}
SEV_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


def _sev_icon(a: dict) -> str:
    return SEV_ICON.get(a.get("severity"), "⚪")


def _fail(module_name: str, exc: Exception) -> None:
    """模块级失败错误卡（阻断级）：友好文案 + 一键重试，原始异常折叠收纳不展示"""
    render.error_card(f"{module_name}加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key=f"retry_{module_name}")


# ============ 首页聚合数据源：一次请求并行拉取全部模块（替代多次串行请求） ============
_dash = None
try:
    _dash = api.dashboard()
except Exception as exc:  # noqa: BLE001 后端整体不可达时统一提示，不再逐模块重复报错
    render.error_card("首页数据加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key="retry_dashboard")
_dash_modules = (_dash or {}).get("modules", {})


def _module(key: str):
    """取聚合模块数据；单模块失败（error 标注）抛异常交给 _fail 统一渲染"""
    m = _dash_modules.get(key)
    if isinstance(m, dict) and m.get("error"):
        raise RuntimeError(m["error"])
    return m


def _pnl_tone(value) -> str:
    """盈亏色调映射（A 股习惯：正红负绿；纯展示）"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "mute"
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "mute"


def _money(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


# ============ 3 个 Tab：运行状态 / 今日概览 / 性能统计 ============
tab_status, tab_overview, tab_perf = st.tabs(["运行状态", "今日概览", "性能统计"])

# ---------------- Tab 1：运行状态 ----------------
with tab_status:
    st.subheader("系统服务")
    try:
        stt = _module("system")
        render.time_text("页面数据整体刷新时间", stt.get("checked_at"))
        render.svc_cards(stt["connections"])
    except Exception as exc:
        _fail("系统运行状态", exc)
    st.subheader("定时任务调度")
    try:
        jobs = api.job_status()["jobs"]
        if jobs:
            for job in jobs[:4]:
                st.markdown(f"- **{job['name']}**：{job.get('next_run') or '未运行'}")
        else:
            st.caption("无已注册的定时任务。")
    except Exception as exc:
        _fail("定时任务调度", exc)

# ---------------- Tab 2：今日概览 ----------------
with tab_overview:
    # 核心指标卡：候选数 / 持仓数 / 告警数 / 今日盈亏 / 市况评分
    try:
        cands = _module("candidates") or []
        holds = _module("holdings") or []
        alerts = _module("alerts") or []
        acc = st.session_state.get("_bar_account") or {}
        pnl = acc.get("pnl_amount")
        pnl_txt = f"{_money(pnl)}" + (f"（{acc.get('pnl_pct', 0)}%）" if pnl is not None else "")
        metrics = [
            {"label": "今日候选", "value": len(cands), "sub": "最新一轮候选池", "tone": "ok"},
            {"label": "当前持仓", "value": len(holds), "sub": "有效持仓标的", "tone": "info"},
            {"label": "告警记录", "value": len(alerts), "sub": "全部信号记录", "tone": "warn"},
            {"label": "今日盈亏", "value": pnl_txt, "sub": "账户实时估算", "tone": _pnl_tone(pnl)},
        ]
        try:
            mc = _module("market_condition")
            if mc:
                band = str(mc.get("band") or "")
                tone = "up" if "强" in band else ("down" if "弱" in band else "warn")
                metrics.append({"label": "市况评分", "value": f"{mc['total_score']} 分",
                                "sub": f"{band} · 候选池上限 {mc['cap']} 只", "tone": tone})
        except Exception:
            pass  # 市况缺失不影响其余指标卡
        render.stat_cards(metrics)
    except Exception as exc:
        _fail("核心指标", exc)

    # 今日操作提示（v2.0 市况评分详情）
    with st.expander("今日操作提示（市况五维）", expanded=True):
        try:
            mc = _module("market_condition")
            if not mc:
                render.empty_state("暂无市况评分。每日挖掘运行时自动生成市况评分，"
                                   "也可点击顶部「手动触发每日挖掘」。", icon="📈")
            else:
                st.markdown(f"**市况评分 {mc['total_score']} 分（{mc.get('band', '')}，"
                            f"候选池上限 {mc['cap']} 只）**")
                dims = mc.get("dims") or {}
                dim_labels = [("index", "指数位置"), ("sector", "板块结构"), ("money", "资金方向"),
                              ("sentiment", "情绪指标"), ("risk", "风险维度")]
                cols = st.columns(len(dim_labels))
                for col, (key, label) in zip(cols, dim_labels):
                    with col:
                        st.metric(label, dims.get(key, "—"))
                st.markdown(mc.get("summary", ""))
                render.trace_line("市况评分生成时间", mc.get("created_at"), source="LLM 生成")
        except Exception as exc:
            _fail("今日操作提示", exc)

    # 持仓与操作建议（最新 LLM 信号）
    with st.expander("持仓与操作建议", expanded=True):
        try:
            holdings = _module("holdings")
            if not holdings:
                render.empty_state("暂无持仓。在「持仓监控」页录入已人工建仓的标的。", icon="💼")
            else:
                latest_by_code = {}
                for a in _module("alerts"):
                    latest_by_code.setdefault(a["stock_code"], a)
                for h in holdings:
                    label = render.stock_label(h["stock_code"], h["stock_name"])
                    sig = latest_by_code.get(h["stock_code"])
                    if sig:
                        urgent = sig["severity"] in ("warning", "critical") or sig["action"] != "hold"
                        st.markdown(f"{_sev_icon(sig)} **{label}** `{sig['alert_type']}` "
                                    f"建议: **{ACTION_MAP.get(sig['action'], sig['action'])}**\n\n"
                                    f"{sig['message']}")
                        render.trace_line("信号生成时间", sig["created_at"], source="LLM 生成",
                                          confidence=sig.get("confidence"), highlight=urgent)
                    else:
                        st.markdown(f"- **{label}**：暂无最新信号（监控在交易时段自动运行）")
        except Exception as exc:
            _fail("持仓与操作建议", exc)

    # 紧急告警日志（有紧急信号时默认展开）
    urgent_alerts = []
    try:
        urgent_alerts = [a for a in _module("alerts")[:20] if a["action"] != "hold"]
    except Exception:
        pass
    with st.expander("紧急告警日志", expanded=bool(urgent_alerts)):
        try:
            if urgent_alerts:
                render.time_text("告警统计时间范围",
                                 f"{urgent_alerts[0]['created_at'][:16]} ~ "
                                 f"{urgent_alerts[-1]['created_at'][:16]}")
                for a in urgent_alerts[:3]:
                    urgent = a["severity"] in ("warning", "critical")
                    label = render.stock_label(a["stock_code"], a["stock_name"])
                    st.markdown(f"{_sev_icon(a)} **{label}** `{a['alert_type']}` "
                                f"建议: **{ACTION_MAP.get(a['action'], a['action'])}**\n\n{a['message']}")
                    render.time_text("告警触发时间", a["created_at"], highlight=urgent)
            else:
                render.empty_state("暂无紧急告警。持仓监控在交易时段自动运行，"
                                   "触发信号实时推送飞书。", icon="🛡️")
        except Exception as exc:
            _fail("紧急告警日志", exc)

    # 今日热门板块（涨幅前 5 客观排序；点击板块筛选当日同行业候选）
    @st.fragment(run_every="30m")
    def hot_sector_board() -> None:
        """今日涨幅前 5 行业板块看板：板块名称/板块涨幅/领涨龙头（代码+名称）+ 数据生成时间；
        默认每 30 分钟自动更新；点击「筛选该行业」跳转候选池页按行业筛选当日候选股。"""
        try:
            data = api.market_hot_sectors()
        except Exception as exc:  # noqa: BLE001 不向页面抛原始报错
            render.error_card("热门板块加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                              detail=exc, retry_key="retry_hot_sector")
            return
        sectors = data.get("sectors") or []
        if not sectors:
            render.empty_state(f"热门板块数据暂不可用：{data.get('error') or '无板块数据'}，"
                               "稍后自动重试。", icon="📊")
            return
        render.time_text("板块数据生成时间", data.get("updated_at"))
        st.caption("涨幅为板块指数当日涨跌幅（客观排序），领涨龙头为该板块当日涨幅最大个股；"
                   "点击「筛选该行业」可查看当日同行业候选股。")
        for b in sectors:
            c1, c2, c3, c4 = st.columns([2.2, 1.2, 3, 1.4])
            with c1:
                st.markdown(f"**{b['board_name']}**")
            with c2:
                pct = b.get("change_pct")
                if pct is None:
                    st.markdown("—")
                else:
                    color = "#F87171" if pct > 0 else "#4ADE80" if pct < 0 else "#9CA3AF"
                    st.markdown(f"<span style='color:{color};font-weight:600'>{pct:+.2f}%</span>",
                                unsafe_allow_html=True)
            with c3:
                lead = render.stock_label(b.get("leading_code"), b.get("leading_stock"))
                st.markdown(f"领涨龙头：{lead}")
            with c4:
                if st.button("筛选该行业", key=f"sector_btn_{b['board_name']}"):
                    st.query_params["sector"] = b["board_name"]
                    st.switch_page("pages/1_每日候选池.py")

    with st.expander("今日热门板块"):
        hot_sector_board()

    # 今日候选与建仓机会（次要信息，默认收纳）
    with st.expander("今日候选与建仓机会"):
        try:
            cands = _module("candidates")
            if cands:
                render.time_text("本轮挖掘执行时间", cands[0].get("created_at"))
                score_map = {s["stock_code"]: s for s in _module("scores")}
                for c in cands:
                    label = render.stock_label(c["stock_code"], c["stock_name"])
                    sc = score_map.get(c["stock_code"])
                    suffix = f" — {sc['score']}分 {sc['grade']}级" if sc else ""
                    st.markdown(f"#{c['rank']} **{label}**{suffix}")
                    for reason in (c.get("reasons") or [])[:2]:
                        st.markdown(f"　· {reason}")
                    if sc:
                        render.time_text("评分生成时间", sc.get("created_at"))
                plan_rows = _module("plans")
                if plan_rows:
                    st.markdown("**最新建仓方案**")
                    for p in plan_rows:
                        label = render.stock_label(p["stock_code"], p["stock_name"])
                        st.markdown(f"- {label}：总仓位上限 {p['total_pct']}%"
                                    f"（止损 {p['stop_loss']} / 止盈 {p['take_profit']}）")
                        render.time_text("方案生成时间", p.get("created_at"))
            else:
                render.empty_state("暂无候选数据。可点击顶部「手动触发每日挖掘」，"
                                   "或等待每日定时任务。", icon="🔍")
        except Exception as exc:
            _fail("今日候选与建仓机会", exc)

    # 近期复盘动态（次要信息，默认收纳）
    with st.expander("近期复盘动态"):
        try:
            revs = _module("reviews")
            if revs:
                for r in revs:
                    label = render.stock_label(r["stock_code"], r["stock_name"])
                    st.markdown(f"- **{label}** 离场 {r['exit_date']}"
                                f"（持仓 {r['hold_days']} 天，盈亏 {r['pnl_pct']}%）")
                    render.time_text("复盘生成时间", r.get("created_at"))
            else:
                render.empty_state("暂无复盘记录。在「持仓监控」页录入人工卖出后自动触发复盘。",
                                   icon="🔁")
            pending = _module("pending_suggestions")
            if pending:
                st.markdown("**待审核优化建议**（经你人工确认后生效）")
                for s in pending[:3]:
                    st.markdown(f"- [{s['target_agent']}] {s['rule_name']}")
                    render.time_text("建议提交时间", s.get("created_at"))
        except Exception as exc:
            _fail("近期复盘动态", exc)

# ---------------- Tab 3：性能统计 ----------------
with tab_perf:
    @st.fragment
    def llm_stats_board() -> None:
        """LLM 运行统计（当日累计）：请求次数 / 缓存命中·未命中 token / 整体缓存命中率 /
        模型调用分布（轻量 flash 与深度推理模型各自次数占比）+ 统计截止时间，支持手动刷新。"""
        try:
            ls = api.llm_stats()
        except Exception as exc:  # noqa: BLE001 统计不可达不阻塞页面
            render.error_card("LLM 运行统计加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                              detail=exc, retry_key="retry_llm_stats")
            return
        hit_rate = ls.get("hit_rate_pct")
        dist = "　".join(
            f"**{m['model']}** {m['calls']} 次（{m['pct']}%）" for m in (ls.get("models") or []))
        render.stat_cards([
            {"label": "请求总次数（当日）", "value": f"{ls['requests']} 次", "tone": "info"},
            {"label": "整体缓存命中率",
             "value": f"{hit_rate}%" if hit_rate is not None else "—（暂无调用）", "tone": "ok"},
            {"label": "缓存命中 / 未命中 token",
             "value": f"{ls['hit_tokens']:,} / {ls['miss_tokens']:,}", "tone": "mute"},
        ])
        st.markdown(f"模型调用分布：{dist or '—（当日暂无 LLM 调用）'}")
        render.time_text("统计截止时间", ls.get("checked_at"))
        if st.button("刷新统计", use_container_width=False):
            st.rerun(scope="fragment")

    @st.fragment
    def datasource_stats_board() -> None:
        """行情数据源状态（当日累计）：主源调用/失败/降级次数、主源成功率、
        当前使用主源还是备用源（tick 实时行情 / snapshot 全市场快照）+ 统计截止时间。"""
        try:
            ds = api.datasource_stats()
        except Exception as exc:  # noqa: BLE001 统计不可达不阻塞页面
            render.error_card("数据源状态加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                              detail=exc, retry_key="retry_ds_stats")
            return
        rate = ds.get("success_rate_pct")
        kinds = "　".join(
            f"**{('实时行情' if k['kind'] == 'tick' else '全市场快照')}**："
            f"{'🟢 主源正常' if k['current_source'] == 'primary' else '🟠 临时降级·备用源'}"
            for k in (ds.get("kinds") or []))
        render.stat_cards([
            {"label": "主源调用次数（当日）", "value": f"{ds['requests']} 次", "tone": "info"},
            {"label": "主源失败次数", "value": f"{ds['failures']} 次",
             "tone": "err" if ds.get("failures") else "ok"},
            {"label": "主源成功率",
             "value": f"{rate}%" if rate is not None else "—（暂无调用）",
             "tone": "ok" if (rate or 0) >= 95 else "warn"},
            {"label": "降级 / 恢复", "value": f"{ds['degraded_use']} / {ds['recoveries']} 次",
             "tone": "mute"},
        ])
        st.markdown(f"当前数据源：{kinds or '—'}")
        render.time_text("统计截止时间", ds.get("checked_at"))
        if st.button("刷新数据源状态", use_container_width=False):
            st.rerun(scope="fragment")

    st.subheader("LLM 运行统计")
    llm_stats_board()
    st.subheader("数据源状态")
    datasource_stats_board()

st.divider()

# ============ 底部：任务执行记录列表（图二列表范式：状态圆点+标题+副标题+右侧操作） ============
st.subheader("任务执行记录")
try:
    tasks = api.recent_tasks(limit=8) or []
except Exception:  # noqa: BLE001 后端不可达不阻塞页面
    tasks = []
if not tasks:
    render.empty_state("暂无任务执行记录。提交任意后台任务后在此展示执行状态。")
else:
    TASK_DOT = {"done": "ok", "running": "warn", "pending": "mute", "failed": "err"}
    TASK_META = {"done": "完成", "running": "执行中", "pending": "排队中", "failed": "失败"}
    for t in tasks:
        status = t.get("status") or ""
        sub = f"{t.get('kind', '')} · 提交于 {str(t.get('submitted_at') or '')[:16]}"
        if t.get("error"):
            sub += f" · {str(t['error'])[:90]}"
        key = f"task_{t.get('task_id', 'x')}"
        if status == "failed":
            clicked = render.list_item(key, t.get("label") or key, subtitle=sub,
                                       dot=TASK_DOT.get(status, "mute"), meta="失败", actions=("重试",))
            if clicked == 0:
                api.retry_task(t["task_id"])
                st.rerun()
        else:
            render.list_item(key, t.get("label") or key, subtitle=sub,
                             dot=TASK_DOT.get(status, "mute"),
                             meta=TASK_META.get(status, status), actions=())
