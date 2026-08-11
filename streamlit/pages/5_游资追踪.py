"""游资追踪：游资档案 / 今日龙虎榜 / 游资席位监控 / 研判留痕（跨模块联查）+ 权重迭代

【铁律对齐】
- 数据口径（lhb_type 1d/3d）、数据源（source）、置信度如实展示，多源采信状态可追溯（K227）；
- 「权重迭代」只触发代码侧统计与建议生成（agent_suggestion 落 pending），
  任何降/升档与权重调整必须经人工审核确认后才生效（系统监管红线）；
- 全部沿用 render.py 现有组件（fold_module/list_item/stat_cards/trace_line…），
  旧数据 .get() 兜底，后端未起时降级为空态不报错。
"""
import json

import streamlit as st

import api_client as api
import render

render.apply_global_theme()
render.top_status_bar()

st.title("游资追踪（Hot Money）")
render.task_status_area()

_TIER_TONE = {"一线": "a", "二线": "b", "观察": "c"}
_SRC_LABEL = {"eastmoney": "东财", "sina": "新浪", "sse": "上交所", "szse": "深交所"}


def _money(v) -> str:
    """金额格式化（元 → 万/亿；None/0 显示 —）"""
    try:
        f = float(v or 0.0)
    except (TypeError, ValueError):
        return "—"
    if f == 0:
        return "—"
    if abs(f) >= 1e8:
        return f"{f / 1e8:,.2f}亿"
    return f"{f / 1e4:,.0f}万"


def _fmt_rate(v) -> str:
    try:
        return f"{float(v) * 100:.0f}%" if v is not None else "—"
    except (TypeError, ValueError):
        return "—"


def _seat_matched(seat: str, profiles: list) -> dict | None:
    """席位 → 命中游资档案（精确/包含，与后端 get_profile_by_seat 同语义的展示层匹配）"""
    seat = (seat or "").strip()
    if not seat:
        return None
    for p in profiles:
        if p.get("seat_code") == seat:
            return p
    norm = seat.replace("股份有限公司", "").replace("有限责任公司", "").replace(
        "证券营业部", "").replace("营业部", "").replace("证券", "").replace("分公司", "")
    for p in profiles:
        pn = (p.get("seat_code") or "").replace("股份有限公司", "").replace(
            "有限责任公司", "").replace("证券营业部", "").replace("营业部", "").replace(
            "证券", "").replace("分公司", "")
        if pn and (pn in norm or norm in pn):
            return p
    return None


# ================= 权重迭代（代码侧统计 + 建议，人工审核后生效） =================
with render.fold_module("hm_iter", "游资胜率迭代（自进化 · 人工审核后生效）",
                        meta="信号后5日跑赢沪深300 计有效 · 建议落待审核队列",
                        default_open=False):
    st.caption("触发后：代码侧统计各游资历史「信号后5日上涨胜率」并落库（win_rate_5d/last_review_at），"
               "按胜率生成降/升档建议（agent_suggestion 落 pending 待你审核）。"
               "⚠️ 系统绝不自动修改任何游资档位/权重——所有建议必须经你人工审核确认后才生效。")
    if st.button("运行胜率迭代（需真实行情回溯，耗时较长）", key="hm_iter_run",
                 use_container_width=True):
        with st.spinner("正在统计各游资信号胜率并生成建议…"):
            try:
                result = api.hot_money_winrate_iterate()
                updated = result.get("updated") or []
                suggestions = result.get("suggestions") or []
                errors = result.get("errors") or []
                if updated:
                    render.stat_cards([
                        {"label": "已统计游资", "value": len(updated), "tone": "info"},
                        {"label": "生成建议", "value": len(suggestions),
                         "tone": "warn" if suggestions else "mute",
                         "sub": "均待人工审核"},
                        {"label": "统计失败", "value": len(errors),
                         "tone": "err" if errors else "mute"},
                    ])
                if errors:
                    for e in errors:
                        st.warning(f"{e.get('actor_name')} 统计失败：{e.get('error')}")
                st.success(f"迭代完成：统计 {len(updated)} 位游资，生成 {len(suggestions)} 条建议"
                           "（pending 待审核，审核通过后在下方「游资梯队建议」采纳应用）。")
            except Exception as exc:
                render.dismissible_error("胜率迭代失败", "后端未启动或行情回溯超时，可稍后重试。",
                                         detail=exc, retry_key="retry_hm_iter")
    # 游资梯队建议（复用策略闭环建议流：仅审核通过后可应用）
    try:
        hm_sugs = [s for s in (api.agent_suggestions() or [])
                   if "游资" in (s.get("rule_name") or "")]
    except Exception:  # noqa: BLE001 后端未起降级空态
        hm_sugs = []
    if hm_sugs:
        render.section_title("游资梯队/权重建议（全部待人工审核，绝不自动生效）")
        _SUG_STATUS = {"pending": "待审核", "approved": "已采纳", "rejected": "已驳回"}
        _SUG_TONE = {"pending": "warn", "approved": "ok", "rejected": "err"}
        render.batch_fold_bar("hmsug", [f"hmsug_{s['id']}" for s in hm_sugs],
                              label="点击「展开详情」查看建议全文；采纳/驳回仅对待审核生效，应用仅对已采纳生效。")
        for s in hm_sugs:
            key = f"hmsug_{s['id']}"
            status = s.get("status") or "pending"
            opened = st.session_state.get(f"open_{key}", st.session_state.get("grpdef_hmsug", False))
            clicked = render.list_item(
                key, f"[{s.get('target_agent')}] {s.get('rule_name')}",
                subtitle=f"当前 {s.get('current_value')} → 建议 {s.get('suggested_value')}",
                dot=_SUG_TONE.get(status, "mute"),
                meta=f'{_SUG_STATUS.get(status, status)} · {str(s.get("created_at") or "")[:16]}',
                actions=("收起详情" if opened else "展开详情", "采纳", "驳回", "应用生效"))
            if clicked == 0:
                opened = not opened
                st.session_state[f"open_{key}"] = opened
                st.rerun()
            elif clicked == 1 and status == "pending":
                api.approve_suggestion(s["id"])
                st.success("已采纳（状态 approved）。点击「应用生效」后档位才会实际变更。")
                st.rerun()
            elif clicked == 2 and status == "pending":
                api.reject_suggestion(s["id"])
                st.info("已驳回，不修改任何配置。")
                st.rerun()
            elif clicked == 3 and status == "approved":
                try:
                    result = api.hot_money_tier_apply(s["id"])
                    st.success(f"已生效：{result['actor_name']} {result['old_tier']}"
                               f"→{result['new_tier']}（人工审核确认后应用）")
                    st.rerun()
                except Exception as exc:
                    render.dismissible_error("应用失败", "建议未通过人工审核，无法生效。",
                                             detail=exc, retry_key="retry_hm_apply")
            if opened:
                with st.container(border=True):
                    render.trace_line("建议时间", s.get("created_at"))
                    st.markdown(f"- 建议值：**{s.get('suggested_value')}**（档位）")
                    st.markdown(f"- 建议理由：{s.get('reason')}")
                    st.markdown(f"- 事实依据：{s.get('evidence')}")


# ================= 1. 游资档案视图 =================
try:
    profiles = api.hot_money_profiles() or []
except Exception:  # noqa: BLE001 后端未起降级空态
    profiles = []

with render.fold_module("hm_profiles", "游资档案",
                        meta=f"{len(profiles)} 位 · 名称/席位/梯队/风格/擅长题材/5日胜率",
                        default_open=True):
    if not profiles:
        render.empty_state("暂无游资档案。后端未启动或档案为空（种子数据在系统启动时自动写入）。",
                           action_label="重试", action_key="retry_hm_profiles")
    else:
        c1, c2, c3 = st.columns([3, 1.4, 2])
        with c1:
            q = st.text_input("按游资名/席位搜索", key="hm_profile_q")
        with c2:
            tier_f = st.selectbox("梯队筛选", ["全部", "一线", "二线", "观察"], key="hm_profile_tier")
        with c3:
            if st.button("查询", use_container_width=True):
                st.rerun()
        shown = [p for p in profiles
                 if (not q or q in (p.get("actor_name") or "") or q in (p.get("seat_code") or ""))
                 and (tier_f == "全部" or p.get("tier") == tier_f)]
        if not shown:
            render.empty_state("没有匹配的游资档案，调整搜索条件试试。")
        pk = [f"hmpro_{p['id']}" for p in shown]
        render.batch_fold_bar("hmpro", pk, label="点击「查看详情」展开完整档案与 5 日胜率。")
        for p in shown:
            key = f"hmpro_{p['id']}"
            rate = _fmt_rate(p.get("win_rate_5d"))
            tier = p.get("tier") or "观察"
            meta = (f'<span class="badge badge-{_TIER_TONE.get(tier, "c")}">{tier}</span>'
                    f'　胜率 {rate}' + (f'　复盘 {str(p.get("last_review_at") or "")[:16]}'
                                        if p.get("last_review_at") else ""))
            if render.list_item_toggle(
                    key, p.get("actor_name") or "未命名游资",
                    subtitle=f"{p.get('seat_code')} · {'、'.join(p.get('style_tags') or []) or '风格未知'}",
                    dot=_TIER_TONE.get(tier, "c"), meta=meta, scope="hmpro"):
                with st.container(border=True):
                    render.trace_line("档案更新时间", p.get("updated_at"), source=p.get("source"))
                    with st.container(border=True):
                        render.section_title("擅长题材")
                        st.markdown("、".join(p.get("good_themes") or []) or "（未录入）")
                    with st.container(border=True):
                        render.section_title("协同席位")
                        st.markdown("、".join(p.get("co_seats") or []) or "（无）")
                    with st.container(border=True):
                        render.section_title("信号胜率统计（代码侧事实）")
                        st.markdown(f"- 信号后5日上涨胜率：**{rate}**"
                                    f"（{('统计于 ' + str(p.get('last_review_at') or '')[:16]) if p.get('last_review_at') else '尚未迭代统计'}）")
                        st.caption("统计口径：龙虎榜净买入信号后 5 个交易日跑赢沪深300 计有效；"
                                   "统计事实自动落库，档位调整需人工审核。")
                    render.raw_json_expander(p, key=f"raw_hmpro_{p['id']}")


# ================= 2. 今日龙虎榜视图 =================
try:
    all_flows = api.hot_money_flows(limit=1000) or []
except Exception:  # noqa: BLE001 后端未起降级空态
    all_flows = []
flow_dates = sorted({f.get("trade_date") for f in all_flows if f.get("trade_date")}, reverse=True)

with render.fold_module("hm_flows", "龙虎榜原始流水（今日/按日筛选）",
                        meta=f"共 {len(all_flows)} 条 · {len(flow_dates)} 个交易日 · 口径/数据源/置信度如实标注",
                        default_open=True):
    if not flow_dates:
        render.empty_state("暂无龙虎榜流水。开启 DRAGON_TIGER_ENABLE 后每日 16:30 自动抓取，"
                           "或手动运行 backend/scripts/fetch_dragon_tiger.py。",
                           action_label="重试", action_key="retry_hm_flows")
    else:
        c1, c2, c3 = st.columns([2, 1.6, 2.4])
        with c1:
            sel_date = st.selectbox("交易日", flow_dates, index=0, key="hm_flow_date")
        with c2:
            code_f = st.text_input("标的代码筛选", key="hm_flow_code")
        with c3:
            if st.button("查询龙虎榜", use_container_width=True):
                st.rerun()
        date_flows = [f for f in all_flows
                      if f.get("trade_date") == sel_date
                      and (not code_f or code_f in str(f.get("stock_code") or ""))]
        if not date_flows:
            render.empty_state("该交易日无龙虎榜流水（或筛选无结果）。")
        else:
            buys = sum(float(f.get("net_buy") or 0.0) for f in date_flows if (f.get("net_buy") or 0) > 0)
            sells = sum(float(f.get("net_buy") or 0.0) for f in date_flows if (f.get("net_buy") or 0) < 0)
            render.stat_cards([
                {"label": "流水条数", "value": len(date_flows), "tone": "info"},
                {"label": "净买入合计", "value": _money(buys), "tone": "up"},
                {"label": "净卖出合计", "value": _money(abs(sells)), "tone": "down"},
            ])
            rows = []
            for f in date_flows:
                seat = f.get("seat_name") or ""
                hit = _seat_matched(seat, profiles)
                rows.append({
                    "日期": f.get("trade_date"),
                    "代码": f.get("stock_code"),
                    "名称": f.get("stock_name") or "名称待补",
                    "口径": f.get("lhb_type"),
                    "营业部": seat or "（股票级汇总）",
                    "命中游资": hit.get("actor_name") if hit else "",
                    "买入额": _money(f.get("buy_amt")),
                    "卖出额": _money(f.get("sell_amt")),
                    "净买额": _money(f.get("net_buy")),
                    "置信度": f.get("confidence"),
                    "数据源": _SRC_LABEL.get(f.get("source"), f.get("source")),
                    "上榜原因": f.get("disclosure_reason") or "",
                })
            st.dataframe(rows, use_container_width=True, height=min(420, 36 * len(rows)))
            st.caption("置信度：官方源 1.0 / 第三方 0.8 / 社区 0.5；多源采信（两源差值<10%）"
                       "由系统在注入评分时校验为 0.9，此处展示原始行置信度（K227 口径硬隔离）。")


# ================= 3. 游资席位监控 =================
with render.fold_module("hm_seat", "游资席位监控（最近操作追踪）",
                        meta="从龙虎榜流水关联游资档案 · 净买方向 · 命中真实席位",
                        default_open=False):
    if not profiles:
        render.empty_state("暂无游资档案，无法监控席位。")
    else:
        actor = st.selectbox("选择游资", [p.get("actor_name") for p in profiles], key="hm_seat_actor")
        profile = next((p for p in profiles if p.get("actor_name") == actor), None)
        if profile:
            seats = {profile.get("seat_code")} | set(profile.get("co_seats") or [])
            ops = [f for f in all_flows if (f.get("seat_name") or "") in seats]
            ops.sort(key=lambda f: f.get("trade_date") or "", reverse=True)
            if not ops:
                render.empty_state(f"「{actor}」暂无上榜操作记录（席位：{profile.get('seat_code')}）。"
                                   "抓取龙虎榜后自动追踪。")
            else:
                render.stat_cards([
                    {"label": "最近操作", "value": len(ops), "tone": "info"},
                    {"label": "净买方向", "value": "买入" if any((f.get("net_buy") or 0) > 0 for f in ops)
                     else "卖出", "tone": "up" if any((f.get("net_buy") or 0) > 0 for f in ops) else "down"},
                ])
                ok = [f"hmop_{f['id']}" for f in ops[:50]]
                render.batch_fold_bar("hmop", ok, label="点击「查看详情」展开该笔操作明细。")
                for f in ops[:50]:
                    key = f"hmop_{f['id']}"
                    net = float(f.get("net_buy") or 0.0)
                    direction = "买入" if net > 0 else ("卖出" if net < 0 else "持平")
                    tone = "up" if net > 0 else ("down" if net < 0 else "mute")
                    hit = _seat_matched(f.get("seat_name") or "", profiles)
                    meta = (f'<span class="badge badge-{tone}">{direction}</span>'
                            f'　{_money(net)}'
                            + (f'　<span class="badge badge-ok">命中席位</span>'
                               if hit else "　<span class='badge badge-mute'>未命中</span>"))
                    if render.list_item_toggle(
                            key, f"{f.get('trade_date')} · {render.stock_label(f.get('stock_code'), f.get('stock_name'))}",
                            subtitle=f"{f.get('seat_name')} · 口径 {f.get('lhb_type')}"
                                     f" · {_SRC_LABEL.get(f.get('source'), f.get('source'))}",
                            dot=tone, meta=meta, scope="hmop"):
                        with st.container(border=True):
                            st.markdown(f"- 买入额：{_money(f.get('buy_amt'))}；"
                                        f"卖出额：{_money(f.get('sell_amt'))}；"
                                        f"净买额：**{_money(net)}**")
                            st.markdown(f"- 上榜原因：{f.get('disclosure_reason') or '—'}")
                            render.trace_line("数据时间", f.get("created_at"),
                                              source=_SRC_LABEL.get(f.get("source"), f.get("source")),
                                              confidence=f.get("confidence"))
                            render.raw_json_expander(f, key=f"raw_hmop_{f['id']}")


# ================= 4. 游资研判留痕（跨模块联查） =================
with render.fold_module("hm_trace", "游资研判留痕（ai_reasoning_trace · 跨模块联查）",
                        meta="source_module=hot_money · 命中游资/净买/多源校验/置信度留痕可追溯",
                        default_open=False):
    try:
        hm_traces = api.hot_money_traces(limit=50) or []
    except Exception:  # noqa: BLE001 后端未起降级空态
        hm_traces = []
    if not hm_traces:
        render.empty_state("暂无游资研判留痕。评分/建仓等环节注入游资数据时会自动留痕"
                           "（ai_reasoning_trace，source_module='hot_money'）。",
                           action_label="重试", action_key="retry_hm_traces")
    else:
        tk = [f"hmt_{t['trace_id']}" for t in hm_traces]
        render.batch_fold_bar("hmt", tk, label="点击「查看详情」展开留痕全文；留痕内可联查该标的"
                                               "全模块研判。")
        for t in hm_traces:
            key = f"hmt_{t['trace_id']}"
            try:
                concl = json.loads(t.get("final_conclusion") or "{}")
            except (json.JSONDecodeError, TypeError):
                concl = {}
            try:
                cap = json.loads(t.get("capital_reasoning") or "{}")
            except (json.JSONDecodeError, TypeError):
                cap = {}
            verified = concl.get("multi_source_verified")
            dot = "ok" if verified else "warn"
            meta = (f'<span class="badge badge-{"ok" if verified else "warn"}">'
                    f'{"多源采信" if verified else "置信度不足"}</span>'
                    f'　{str(t.get("create_time") or "")[:16]}')
            subtitle = (f"游资[{cap.get('actor') or '—'}] 席位 {cap.get('seat_name') or '—'}"
                        f" · lhb_1d_net_buy {_money(cap.get('lhb_1d_net_buy'))}")
            if render.list_item_toggle(
                    key, f"{t.get('generate_date')} · {render.stock_label(t.get('stock_code'), t.get('stock_name'))}",
                    subtitle=subtitle, dot=dot, meta=meta, scope="hmt"):
                with st.container(border=True):
                    with st.container(border=True):
                        render.section_title("留痕结论")
                        st.markdown(f"- 多源采信：{'通过' if verified else '未通过'}"
                                    f"（数据源 {('、'.join(concl.get('sources') or [])) or '—'}）")
                        st.markdown(f"- 置信度：{concl.get('confidence')}；"
                                    f"候选游资（LLM 研判）：{concl.get('candidate_actor') or '—'}")
                        if concl.get("second_source"):
                            st.caption(f"第二源现状：{concl.get('second_source')}")
                    if t.get("risk_reasoning"):
                        st.markdown(f"**风险标注**：{t.get('risk_reasoning')}")
                    render.trace_line("留痕时间", t.get("create_time"), source=t.get("data_source"),
                                      confidence=t.get("confidence"))
                    # 跨模块联查：该标的同日的 score/discover/review 留痕
                    with st.container(border=True):
                        render.section_title("跨模块联查（同标的研判留痕）")
                        try:
                            cross = api.traces(code=t.get("stock_code"), date=t.get("generate_date"),
                                               limit=8) or []
                            cross = [c for c in cross if c["trace_id"] != t["trace_id"]]
                        except Exception:  # noqa: BLE001 联查失败降级提示
                            cross = []
                        if not cross:
                            st.caption("无同标的其他模块留痕。")
                        else:
                            for c in cross[:5]:
                                st.markdown(f"- {c.get('source_module')} · "
                                            f"{render.stock_label(c.get('stock_code'), c.get('stock_name'))} · "
                                            f"{str(c.get('create_time') or '')[:16]}")
                    render.raw_json_expander(t, key=f"raw_hmt_{t['trace_id']}")
