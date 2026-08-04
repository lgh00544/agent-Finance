"""
首页看板：系统运行状态 / 今日操作提示 / 持仓与操作建议 / 今日候选与建仓机会 / 近期复盘动态 / 紧急告警日志
纯展示：全部内容来自 backend API 的原始数据与 LLM 输出结论，不内置任何二次判断。
强时效规范：每条业务数据均标注生成/检测时间（北京时间 YYYY-MM-DD HH:mm，浅色小字）。
"""
from datetime import datetime, timedelta, timezone

import streamlit as st

import api_client as api
import render

CN_TZ = timezone(timedelta(hours=8))

st.set_page_config(page_title="股票决策 Agent 系统", page_icon="📊", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("单人 A 股全生命周期决策 Agent 系统")

# 监管红线（顶部显著标注）
st.warning("本系统为个人研究辅助工具：只输出分析报告、打分、仓位建议与预警信号，"
           "**不包含任何自动下单/实盘交易功能，所有交易必须由你人工执行**。")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ============ 顶部：整体数据更新时间 + 手动刷新 ============
top1, top2 = st.columns([5, 1])
with top1:
    render.time_text("当前数据更新于", datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M"))
with top2:
    if st.button("手动刷新全部数据", use_container_width=True):
        st.rerun()

SEVERITY_MAP = {"info": "一般", "warning": "警告", "critical": "严重"}
ACTION_MAP = {"hold": "持有", "reduce": "减仓", "exit": "清仓"}
SEV_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


def _sev_icon(a: dict) -> str:
    return SEV_ICON.get(a.get("severity"), "⚪")


def _fail(module_name: str, exc: Exception) -> None:
    """友好错误提示：中文文案 + 异常类型名，不向页面暴露原始 Python 报错"""
    st.error(f"{module_name}加载失败，请确认后端服务正常运行后点击"
             f"「手动刷新全部数据」重试（{type(exc).__name__}）")


# ============ 模块1：系统运行状态看板 ============
st.subheader("系统运行状态")
try:
    stt = api.system_status()
    render.time_text("页面数据整体刷新时间", stt.get("checked_at"))
    cols = st.columns(len(stt["connections"]))
    for col, conn in zip(cols, stt["connections"]):
        with col:
            mark = "✅" if conn.get("ok") else "❌"
            st.markdown(f"{mark} **{conn['name']}**\n\n{conn.get('detail', '')}")
            render.time_text("最后检测时间", conn.get("checked_at"))
except Exception as exc:
    _fail("系统运行状态", exc)

# ---- 子模块 1.1：LLM 运行统计（当日累计，手动刷新） ----
@st.fragment
def llm_stats_board() -> None:
    """LLM 运行统计（当日累计）：请求次数 / 缓存命中·未命中 token / 整体缓存命中率 /
    模型调用分布（轻量 flash 与深度推理模型各自次数占比）+ 统计截止时间，支持手动刷新。
    数据来源：LLM 调用层每次成功响应记录的服务端 usage（命中/未命中 token）。"""
    try:
        ls = api.llm_stats()
    except Exception as exc:  # noqa: BLE001 统计不可达不阻塞页面
        st.error(f"LLM 运行统计加载失败，请确认后端服务正常运行（{type(exc).__name__}）")
        return
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("请求总次数（当日）", f"{ls['requests']} 次")
    with m2:
        hit_rate = ls.get("hit_rate_pct")
        st.metric("整体缓存命中率", f"{hit_rate}%" if hit_rate is not None else "—（暂无调用）")
    with m3:
        st.metric("缓存命中 / 未命中 token",
                  f"{ls['hit_tokens']:,} / {ls['miss_tokens']:,}")
    dist = "　".join(
        f"**{m['model']}** {m['calls']} 次（{m['pct']}%）" for m in (ls.get("models") or []))
    st.markdown(f"模型调用分布：{dist or '—（当日暂无 LLM 调用）'}")
    render.time_text("统计截止时间", ls.get("checked_at"))
    if st.button("刷新统计", use_container_width=False):
        st.rerun(scope="fragment")


llm_stats_board()

st.divider()

# ============ 模块1.5：今日操作提示（v2.0 市况评分） ============
st.subheader("今日操作提示")
try:
    mc = api.market_condition()
    if not mc:
        st.info("暂无市况评分。每日挖掘运行时自动生成市况评分，也可点击下方「手动触发每日挖掘」。")
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
        render.time_text("市况评分生成时间", mc.get("created_at"))
except Exception as exc:
    _fail("今日操作提示", exc)

st.divider()

# ============ 模块2：持仓与操作建议 ============
st.subheader("持仓与操作建议")
try:
    holdings = api.holdings(status="holding")
    if not holdings:
        st.info("暂无持仓。在「持仓监控」页录入已人工建仓的标的。")
    else:
        latest_by_code = {}
        for a in api.alerts(limit=100):
            latest_by_code.setdefault(a["stock_code"], a)
        for h in holdings:
            label = render.stock_label(h["stock_code"], h["stock_name"])
            sig = latest_by_code.get(h["stock_code"])
            if sig:
                urgent = sig["severity"] in ("warning", "critical") or sig["action"] != "hold"
                st.markdown(f"{_sev_icon(sig)} **{label}** `{sig['alert_type']}` "
                            f"建议: **{ACTION_MAP.get(sig['action'], sig['action'])}**\n\n{sig['message']}")
                render.time_text("信号生成时间", sig["created_at"], highlight=urgent)
            else:
                st.markdown(f"- **{label}**：暂无最新信号（监控在交易时段自动运行）")
except Exception as exc:
    _fail("持仓与操作建议", exc)

st.divider()

# ============ 模块2.5：今日热门板块（涨幅前5 客观排序；点击板块筛选当日同行业候选） ============
st.subheader("今日热门板块")


@st.fragment(run_every="30m")
def hot_sector_board() -> None:
    """今日涨幅前 5 行业板块看板：板块名称/板块涨幅/领涨龙头（代码+名称）+ 数据生成时间；
    默认每 30 分钟自动更新，页面顶部「手动刷新全部数据」可立即刷新；
    点击「筛选该行业」跳转候选池页，按行业筛选当日候选股（详情行业字段子串匹配）。"""
    try:
        data = api.market_hot_sectors()
    except Exception as exc:  # noqa: BLE001 不向页面抛原始报错
        st.error(f"热门板块加载失败，请确认后端服务正常运行（{type(exc).__name__}）")
        return
    sectors = data.get("sectors") or []
    if not sectors:
        st.info(f"热门板块数据暂不可用：{data.get('error') or '无板块数据'}，稍后自动重试。")
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


hot_sector_board()

st.divider()

# ============ 模块3：今日候选与建仓机会 ============
st.subheader("今日候选与建仓机会")
try:
    cands = api.candidates(limit=5)
    if cands:
        render.time_text("本轮挖掘执行时间", cands[0].get("created_at"))
        score_map = {s["stock_code"]: s for s in api.scores(limit=200)}
        for c in cands:
            label = render.stock_label(c["stock_code"], c["stock_name"])
            sc = score_map.get(c["stock_code"])
            suffix = f" — {sc['score']}分 {sc['grade']}级" if sc else ""
            st.markdown(f"#{c['rank']} **{label}**{suffix}")
            for reason in (c.get("reasons") or [])[:2]:
                st.markdown(f"　· {reason}")
            if sc:
                render.time_text("评分生成时间", sc.get("created_at"))
        plan_rows = api.plans(limit=3)
        if plan_rows:
            st.markdown("**最新建仓方案**")
            for p in plan_rows:
                label = render.stock_label(p["stock_code"], p["stock_name"])
                st.markdown(f"- {label}：总仓位上限 {p['total_pct']}%"
                            f"（止损 {p['stop_loss']} / 止盈 {p['take_profit']}）")
                render.time_text("方案生成时间", p.get("created_at"))
    else:
        st.info("暂无候选数据。可点击下方「手动触发每日挖掘」，或等待每日定时任务。")
except Exception as exc:
    _fail("今日候选与建仓机会", exc)

st.divider()

# ============ 模块4：近期复盘动态 ============
st.subheader("近期复盘动态")
try:
    revs = api.reviews(limit=3)
    if revs:
        for r in revs:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            st.markdown(f"- **{label}** 离场 {r['exit_date']}"
                        f"（持仓 {r['hold_days']} 天，盈亏 {r['pnl_pct']}%）")
            render.time_text("复盘生成时间", r.get("created_at"))
    else:
        st.info("暂无复盘记录。在「持仓监控」页录入人工卖出后自动触发复盘。")

    pending = api.agent_suggestions(status="pending")
    if pending:
        st.markdown("**待审核优化建议**（经你人工确认后生效）")
        for s in pending[:3]:
            st.markdown(f"- [{s['target_agent']}] {s['rule_name']}")
            render.time_text("建议提交时间", s.get("created_at"))
except Exception as exc:
    _fail("近期复盘动态", exc)

st.divider()

# ============ 模块5：紧急告警日志 ============
st.subheader("紧急告警日志")
try:
    urgent_alerts = [a for a in api.alerts(limit=20) if a["action"] != "hold"]
    if urgent_alerts:
        render.time_text("告警统计时间范围",
                         f"{urgent_alerts[0]['created_at'][:16]} ~ {urgent_alerts[-1]['created_at'][:16]}")
        for a in urgent_alerts[:3]:
            urgent = a["severity"] in ("warning", "critical")
            label = render.stock_label(a["stock_code"], a["stock_name"])
            st.markdown(f"{_sev_icon(a)} **{label}** `{a['alert_type']}` "
                        f"建议: **{ACTION_MAP.get(a['action'], a['action'])}**\n\n{a['message']}")
            render.time_text("告警触发时间", a["created_at"], highlight=urgent)
    else:
        st.info("暂无紧急告警。持仓监控在交易时段自动运行，触发信号实时推送飞书。")
except Exception as exc:
    _fail("紧急告警日志", exc)

st.divider()

# ============ 手动任务入口 ============
st.subheader("手动任务")
c1, c2 = st.columns([2, 2])
with c1:
    if st.button("手动触发每日挖掘（Discover → 候选打分）", type="primary", use_container_width=True):
        api.submit_task("daily_pipeline")
        st.toast("每日挖掘任务已提交后台，可切换页面继续操作")
with c2:
    try:
        jobs = api.job_status()["jobs"]
        for job in jobs[:4]:
            st.markdown(f"- **{job['name']}**: {job.get('next_run') or '未运行'}")
    except Exception as exc:
        st.error(f"调度状态获取失败: {exc}")

st.caption("页面导航：每日候选池 / 评分报告 / 建仓计划 / 持仓监控 / 交易复盘 / "
           "个人交易偏好 / 告警日志 / 交易知识库")
