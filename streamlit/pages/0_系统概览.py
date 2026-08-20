"""系统概览首页：企业级后台范式
顶部操作行（更新时间 + 高频按钮）→ 3 个 Tab：
- 运行状态：5 系统服务横向卡片 + 定时任务调度；
- 今日概览：核心指标卡（候选/持仓/告警/今日盈亏/市况）+ 持仓建议/紧急告警展开 + 次要模块收纳；
- 性能统计：LLM 运行统计 + 数据源状态（当日累计，可手动刷新）。
底部：任务执行记录列表（状态圆点 + 失败一键重试）。
纯展示：全部内容来自 backend API 的原始数据与 LLM 输出结论，不内置任何二次判断。
强时效规范：每条业务数据均标注生成/检测时间（北京时间，浅色小字）。
"""
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

import api_client as api
import render

CN_TZ = timezone(timedelta(hours=8))

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次2：页面头部收敛为 page_header 单行范式（合规降级为单行细条）=====
_hdr = render.page_header(
    "单人 A 股全生命周期决策 Agent 系统",
    caption="系统服务 / 今日概览 / 性能统计 · 数据聚合看板",
    primary_actions=[{"label": "⛏ 手动触发每日挖掘", "key": "hdr_dig"}],
    secondary_actions=[{"label": "🔄 手动刷新全部数据", "key": "hdr_refresh"}],
    compliance="本系统为个人研究辅助工具：只输出分析报告、打分、仓位建议与预警信号，"
               "不包含任何自动下单/实盘交易功能，所有交易必须由你人工执行。",
)
if _hdr["primary"] == 0:
    render.submit_task("daily_pipeline", label="每日挖掘")
if _hdr["secondary"] == 0:
    # 击穿前端 60s 短缓存（后端另有 60s dbq / 10min 止盈计划缓存）
    st.session_state.pop("_dash_cache", None)
    st.session_state.pop("_tp_cache", None)
    st.rerun()

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()
render.time_text("当前数据更新于", datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M"))

SEVERITY_MAP = {"info": "一般", "warning": "警告", "critical": "严重"}
ACTION_MAP = {"hold": "持有", "reduce": "减仓", "exit": "清仓"}
SEV_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}
# 今日行动清单 · 持仓状态 → 行动文案（B 区核心；alerts 告警 message 可覆盖）
_STATUS_ACTION = {
    "接近止损": "🔴 止损预警：现价接近止损位，关注是否触发 C3 硬止损",
    "减仓预警": "🔴 减仓预警：跌破 MA10，建议减仓规避波段调整",
    "接近止盈": "🟠 止盈关注：接近第一止盈位，准备按分档锁利减仓",
    "持有观察": "🟢 正常持有",
}


def _sev_icon(a: dict) -> str:
    return SEV_ICON.get(a.get("severity"), "⚪")


def _fail(module_name: str, exc: Exception) -> None:
    """模块级失败错误卡（阻断级）：友好文案 + 一键重试，原始异常折叠收纳不展示"""
    render.error_card(f"{module_name}加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key=f"retry_{module_name}")


# ============ 首页聚合数据源：session_state 60s 短缓存（折叠交互零网络请求） ============
# 折叠/展开为纯前端交互：st.rerun 全页重跑时直接复用缓存，不发请求；
# 60s TTL 与行情缓存同量级保证数据不过期，手动刷新按钮击穿。
_DASH_TTL = 60


def _load_dashboard(force: bool = False) -> dict | None:
    """首页聚合数据：60s 短缓存；失败不写缓存（rerun 自动重试）"""
    cached = st.session_state.get("_dash_cache")
    if not force and cached and time.time() - cached.get("ts", 0) < _DASH_TTL:
        return cached.get("data")
    try:
        data = api.dashboard()
    except Exception:  # noqa: BLE001 失败不缓存，重试按钮 rerun 自动重试
        return None
    st.session_state["_dash_cache"] = {"ts": time.time(), "data": data}
    return data


def _tp_plans() -> list:
    """止盈/仓位计划：60s 短缓存（服务端另有 10min 缓存）；失败降级用旧缓存"""
    cached = st.session_state.get("_tp_cache")
    if cached and time.time() - cached.get("ts", 0) < _DASH_TTL:
        return cached.get("rows", [])
    try:
        data = api.take_profit_plan()
    except Exception:  # noqa: BLE001 失败降级旧缓存
        return cached.get("rows", []) if cached else []
    st.session_state["_tp_cache"] = {"ts": time.time(), "rows": data.get("rows") or []}
    return data.get("rows") or []


_dash = _load_dashboard()
if _dash is None:
    render.error_card("首页数据加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      retry_key="retry_dashboard")
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


# ============ 持仓与操作建议：单标的 4 固定信息模块（与持仓监控页同源） ============


def _render_position_plan(key: str, label: str, h: dict, plan: dict, sig: dict | None) -> None:
    """单只持仓：4 固定信息模块渲染（共享 render.position_plan_card）；
    核心操作建议优先取最新 LLM 信号动作，缺省按状态标签推导。"""
    action = ACTION_MAP.get((sig or {}).get("action"), "") if sig else ""
    render.position_plan_card(key, label, plan, core_action=action)


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
    # ---- 一级模块（fragment 隔离：折叠/展开仅重跑自身模块，零网络请求） ----
    @st.fragment
    def _module_action_brief() -> None:
        """今日行动清单（置顶）：可建仓机会 + 持仓今日关注 + 市况速览"""
        with render.fold_module("ov_action", "今日行动清单",
                                meta="每日一屏看全 · 可建仓 / 持仓关注 / 市况速览",
                                default_open=True):
            try:
                # A区：可建仓机会（dashboard 只读模块，is_tradeable=True 的标的）
                ct = _module("candidate_tradeable") or {}
                tradeable_items = [i for i in (ct.get("items") or [])
                                   if i.get("is_tradeable")]

                # B区：持仓今日关注
                holdings = _module("holdings") or []
                alerts = _module("alerts") or []
                # 取止盈计划（已有 _tp_plans() 60s 缓存函数，与模块3同源复用）
                tp_plans = _tp_plans()
                plan_by_code = {p["stock_code"]: p for p in tp_plans}
                alert_by_code = {}
                for a in alerts:
                    if a.get("action") != "hold":
                        alert_by_code.setdefault(a["stock_code"], a)

                position_briefs = []
                for h in holdings:
                    code = h["stock_code"]
                    plan = plan_by_code.get(code)
                    mv_est = float(h.get("shares") or 0) * float(
                        (plan or {}).get("current_price") or h.get("entry_price") or 0)
                    if not plan:
                        # 无止盈计划：降级用 alerts 判定
                        a = alert_by_code.get(code)
                        if a:
                            position_briefs.append({
                                "code": code, "name": h.get("stock_name", ""),
                                "status": "告警", "status_tone": "err",
                                "action_text": f"⚠️ {a.get('alert_type','')}",
                                "detail": str(a.get("message",""))[:60],
                                "_mv": mv_est,
                            })
                        else:
                            position_briefs.append({
                                "code": code, "name": h.get("stock_name",""),
                                "status": "无数据", "status_tone": "mute",
                                "action_text": "暂无止盈计划（行情未就绪）",
                                "detail": "", "_mv": mv_est,
                            })
                    else:
                        status = plan.get("status", "持有观察")
                        tone = plan.get("status_tone", "info")
                        action_text = _STATUS_ACTION.get(status, "🟢 正常持有")
                        # 补充信号：有 action != hold 的告警时，告警 message 覆盖行动建议
                        a = alert_by_code.get(code)
                        if a:
                            action_text = f"⚠️ {a.get('alert_type','')}"
                        detail_parts = []
                        if plan.get("current_price"):
                            detail_parts.append(f"现价 {plan['current_price']}")
                        if plan.get("tp1"):
                            detail_parts.append(f"止盈 {plan['tp1']}")
                        if plan.get("current_stop"):
                            detail_parts.append(f"止损 {plan['current_stop']}")
                        position_briefs.append({
                            "code": code, "name": h.get("stock_name",""),
                            "status": status, "status_tone": tone,
                            "action_text": action_text,
                            "detail": " / ".join(detail_parts),
                            "_mv": mv_est,
                        })

                # 排序：err > warn > info > mute，同类按估算市值降序
                _TONE_ORDER = {"err": 0, "warn": 1, "info": 2, "mute": 3}
                position_briefs.sort(
                    key=lambda x: (_TONE_ORDER.get(x["status_tone"], 9), -x.get("_mv", 0)))
                for b in position_briefs:
                    b.pop("_mv", None)

                # C区：市况速览
                mc = None
                try:
                    mc = _module("market_condition")
                except Exception:
                    mc = None

                render.action_brief(tradeable_items, position_briefs, mc)
            except Exception as exc:
                _fail("今日行动清单", exc)

    @st.fragment
    def _module_overview() -> None:
        """模块1：顶部数据概览组（5 张指标卡：候选/持仓/告警/盈亏/市况评分）"""
        with render.fold_module("ov_overview", "顶部数据概览",
                                meta="账户实时估算 · 数据源：行情快照 + LLM 研判",
                                default_open=True):
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

    @st.fragment
    def _module_market() -> None:
        """模块2：今日操作提示（市况五维，折叠后标题栏仍显示总分）"""
        with render.fold_module("ov_market", "今日操作提示（市况五维）",
                                meta=_mc_meta, default_open=True):
            try:
                if not _mc:
                    render.empty_state("暂无市况评分。每日挖掘运行时自动生成市况评分，"
                                       "也可点击顶部「手动触发每日挖掘」。", icon="📈")
                else:
                    dims = _mc.get("dims") or {}
                    dim_labels = [("index", "指数位置"), ("sector", "板块结构"), ("money", "资金方向"),
                                  ("sentiment", "情绪指标"), ("risk", "风险维度")]
                    cols = st.columns(len(dim_labels))
                    for col, (key, label) in zip(cols, dim_labels):
                        with col:
                            st.metric(label, dims.get(key, "—"))
                    st.markdown(_mc.get("summary", ""))
                    render.trace_line("市况评分生成时间", _mc.get("created_at"), source="LLM 生成")
            except Exception as exc:
                _fail("今日操作提示", exc)

    # 模块3：持仓与操作建议（分档止盈 + 仓位管理，独立计算服务；与持仓监控页 100% 同源）
    # 数据预取在页面级（读 60s 缓存，折叠交互零请求）；fragment 闭包引用
    holdings = []
    plan_by_hid: dict = {}
    latest_by_code: dict = {}
    try:
        holdings = _module("holdings") or []
        for a in _module("alerts") or []:
            latest_by_code.setdefault(a["stock_code"], a)
        try:
            tp_plans = api.take_profit_plan().get("rows") or []
        except Exception:  # noqa: BLE001 止盈计划接口失败降级为 LLM 信号展示
            tp_plans = []
        plan_by_hid = {p["holding_id"]: p for p in tp_plans if p.get("holding_id")}
    except Exception:
        pass
    @st.fragment
    def _module_positions() -> None:
        """模块3：持仓与操作建议（止盈仓位 4 模块卡片，与持仓监控页同源）"""
        with render.fold_module(
                "ov_positions", "持仓与操作建议",
                meta=f"持仓 {len(holdings)} 只 · 与持仓监控页同源",
                default_open=True,
                batch=("ovpos", [f"ovpos_{h['id']}" for h in holdings]) if holdings else None):
            try:
                if not holdings:
                    render.empty_state("暂无持仓。在「持仓监控」页录入已人工建仓的标的。", icon="💼")
                else:
                    st.caption("止盈位/仓位建议由独立计算服务生成（与持仓监控页同源，零 LLM 消耗），"
                               "每次计算自动写入推理留痕供纠察追溯；⚠️ 所有建议仅作参考，"
                               "最终交易由人工判断。")
                    for h in holdings:
                        key = f"ovpos_{h['id']}"
                        label = render.stock_label(h["stock_code"], h["stock_name"])
                        plan = plan_by_hid.get(h["id"])
                        sig = latest_by_code.get(h["stock_code"])
                        if plan:
                            _render_position_plan(key, label, h, plan, sig)
                        else:
                            # 降级：止盈计划不可用时回退最新 LLM 信号展示
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

    # 模块4：紧急告警日志（单条告警 = 二级折叠项，默认摘要）
    urgent_alerts = []
    try:
        urgent_alerts = [a for a in _module("alerts")[:20] if a["action"] != "hold"]
    except Exception:
        pass
    @st.fragment
    def _module_alerts() -> None:
        """模块4：紧急告警日志（单条告警二级折叠项）"""
        with render.fold_module(
                "ov_alerts", "紧急告警日志",
                meta=f"紧急信号 {len(urgent_alerts)} 条 · 实时推送飞书",
                default_open=bool(urgent_alerts),
                batch=("oval", [f"oval_{a['id']}" for a in urgent_alerts]) if urgent_alerts else None):
            try:
                if urgent_alerts:
                    render.time_text("告警统计时间范围",
                                     f"{urgent_alerts[0]['created_at'][:16]} ~ "
                                     f"{urgent_alerts[-1]['created_at'][:16]}")
                    _SEV_DOT = {"critical": "err", "warning": "warn", "info": "info"}
                    for a in urgent_alerts[:3]:
                        key = f"oval_{a['id']}"
                        label = render.stock_label(a["stock_code"], a["stock_name"])
                        sev = a.get("severity") or "info"
                        if render.list_item_toggle(
                                key, f"{label} · {a.get('alert_type', '')}",
                                subtitle=str(a.get("message") or "")[:90],
                                dot=_SEV_DOT.get(sev, "mute"),
                                meta=f"触发 {str(a.get('created_at') or '')[:16]}",
                                default_open=False, scope="oval"):
                            with st.container(border=True):
                                st.markdown(a["message"])
                                act = a.get("action")
                                if act:
                                    st.markdown(f"- **处置建议**：{ACTION_MAP.get(act, act)}")
                                if a.get("signal"):
                                    st.markdown("**LLM 研判结论**")
                                    render.render_dict(a.get("signal"))
                                render.time_text("告警触发时间", a.get("created_at"),
                                                 highlight=sev in ("warning", "critical"))
                else:
                    render.empty_state("暂无紧急告警。持仓监控在交易时段自动运行，"
                                       "触发信号实时推送飞书。", icon="🛡️")
            except Exception as exc:
                _fail("紧急告警日志", exc)

    # 模块5：今日热门板块（涨幅前 5 客观排序；点击板块筛选当日同行业候选；
    # 内部 @st.fragment 每 30 分钟自动刷新，折叠按钮走全页 rerun）
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
                    color = "var(--up)" if pct > 0 else "var(--down)" if pct < 0 else "var(--text-mute)"
                    st.markdown(f"<span style='color:{color};font-weight:600'>{pct:+.2f}%</span>",
                                unsafe_allow_html=True)
            with c3:
                lead = render.stock_label(b.get("leading_code"), b.get("leading_stock"))
                st.markdown(f"领涨龙头：{lead}")
            with c4:
                if st.button("筛选该行业", key=f"sector_btn_{b['board_name']}"):
                    st.query_params["sector"] = b["board_name"]
                    st.switch_page("pages/1_每日候选池.py")

    @st.fragment
    def _module_cands() -> None:
        """模块6：今日候选与建仓机会"""
        with render.fold_module("ov_cands", "今日候选与建仓机会", default_open=False):
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

        # 模块7：近期复盘动态（次要信息，默认收纳）
    @st.fragment
    def _module_reviews() -> None:
        """模块7：近期复盘动态"""
        with render.fold_module("ov_reviews", "近期复盘动态", default_open=False):
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


    # 批次2：今日概览模块按关注度重排——顶部数据概览 → 持仓与操作建议 → 紧急告警日志
    #         → 今日操作提示（市况五维）→ 今日热门板块 → 今日候选与建仓机会 → 近期复盘动态
    # 今日概览 8 个模块 key（模块级，供「全部展开/收起」批量栏使用；
    # 批次2 修复：原定义在 _module_overview fragment 内部导致模块级引用 NameError）
    _MOD_KEYS = ("ov_action", "ov_overview", "ov_market", "ov_positions", "ov_alerts",
                 "ov_sectors", "ov_cands", "ov_reviews")
    # 今日行动清单（置顶，首屏第一眼）
    _module_action_brief()
    # 模块1：顶部数据概览组（5 张指标卡：候选/持仓/告警/盈亏/市况评分）
    _module_overview()
    _m1, _m2, _m3 = st.columns([1.1, 1.1, 4], vertical_alignment="center")
    with _m1:
        if st.button("全部展开", key="ov_open_all", use_container_width=True):
            for k in _MOD_KEYS:
                st.session_state[f"mod_{k}"] = True
            st.toast("全部模块已展开")
            st.rerun()
    with _m2:
        if st.button("全部收起", key="ov_fold_all", use_container_width=True):
            for k in _MOD_KEYS:
                st.session_state[f"mod_{k}"] = False
            st.toast("全部模块已收起，仅保留标题栏")
            st.rerun()
    with _m3:
        st.caption("模块默认展开，点击标题栏可单独收起/展开；刷新页面恢复默认。")

    # 市况数据预取（供「今日操作提示」模块标题栏显示总分；模块调用前就绪）
    _mc = None
    try:
        _mc = _module("market_condition")
    except Exception:
        _mc = None
    _mc_meta = ""
    if _mc:
        _mc_meta = (f"市况评分 {_mc['total_score']} 分 · {_mc.get('band', '')}"
                    f" · 候选池上限 {_mc['cap']} 只")

    # 模块3：持仓与操作建议（批次2 上移为第 2 个模块）
    _module_positions()
    # 模块4：紧急告警日志
    _module_alerts()
    # 模块2：今日操作提示（市况五维）——折叠后标题栏仍显示总分
    _module_market()
    # 模块5：今日热门板块
    with render.fold_module("ov_sectors", "今日热门板块", default_open=False):
        hot_sector_board()

    # 模块6：今日候选与建仓机会（次要信息，默认收纳）
    _module_cands()
    # 模块7：近期复盘动态
    _module_reviews()
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
    TASK_DOT = {"done": "ok", "running": "warn", "pending": "warn", "failed": "err"}
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
