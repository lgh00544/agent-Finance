"""每日候选池：DiscoverAgent 输出（候选理由/技术面研判/量价与资金/关键价位/风险点/操作建议）

企业级列表行范式：左=评级色圆点+代码名称(加粗)+标的类型与核心理由(副标题)，
右=生成时间+「查看详情」；详情分区卡片化展示，原始 JSON 永久折叠在最底部。
纯展示层：评级映射/排序/颜色仅为字段映射与展示，不含任何二次判断逻辑。

错误处理：接口失败按类型分类提示（后端服务/超时/数据库/解析），重试按钮在卡片右侧；
有离线缓存时降级展示最近一次成功数据（标注缓存时间，灰色弱化），避免完全不可用。
"""
import streamlit as st

import api_client as api
import frontend_cache as fc
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("每日候选池（DiscoverAgent）")
st.caption("筛选标准由 LLM 综合量能/趋势/行业热度/基本面研判，每日 16:10 自动生成，也可手动触发。")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# 评级映射（LLM 信心度档位 → 展示评级；纯展示层转换，不含任何研判）
TIER_MAP = {"强烈推荐": "A", "建议关注": "B", "谨慎观察": "C"}
TIER_LABEL = {"A": "A 强烈推荐", "B": "B 建议关注", "C": "C 谨慎观察"}
TIER_DOT = {"A": "tier-a", "B": "tier-b", "C": "tier-c"}
_SORT = {"A": 0, "B": 1, "C": 2}
_TRACE_MODULE = {"discover": "选股研判", "score": "五维评分", "position": "建仓方案",
                 "alert": "监控预警", "review": "交易复盘", "sell": "卖出决策"}

CACHE_KEY = "candidates"
_cached = fc.load(CACHE_KEY)  # 离线兜底缓存（接口失败时降级展示）
_stale = False  # 当前是否处于离线缓存降级模式

# ===== 日期列表：接口失败 → 缓存降级或分类报错（不阻塞顶部状态栏等其余模块） =====
try:
    dates = api.candidate_dates()
except Exception as exc:  # noqa: BLE001 接口异常全链路捕获，绝不出现无反馈空白
    if _cached and _cached["data"].get("date"):
        dates = [_cached["data"]["date"]]
        _stale = True
    else:
        title, hint, tech = render.classify_api_error(exc)
        render.error_card(title, hint, detail=tech, retry_key="retry_candidates")
        st.stop()
if not dates:
    render.empty_state("当日暂无生成结果。可点击下方按钮手动触发每日挖掘，或等待每日定时任务（工作日 16:10）。",
                       icon="🔍", action_label="手动触发每日挖掘",
                       action_key="empty_trigger_discover")
    if st.session_state.get("empty_trigger_discover"):
        render.submit_task("daily_pipeline", label="每日挖掘")
        st.session_state["empty_trigger_discover"] = False
    st.stop()

# 顶部操作行：左=日期选择 + 评级筛选（Tab 样式），右=高频主按钮
f1, f2, f3 = st.columns([1.2, 2.6, 1.2])
with f1:
    date = st.selectbox("选择日期", dates, index=0)
with f2:
    filter_opt = st.segmented_control("评级筛选", ["全部候选", "可建仓 A+B", "观察 C"],
                                      default="全部候选")
with f3:
    if st.button("手动触发每日挖掘", type="primary", use_container_width=True):
        render.submit_task("daily_pipeline", label="每日挖掘")
st.caption("评级：A 强烈推荐 / B 建议关注 / C 谨慎观察（LLM 信心度档位映射，纯展示）")

# ===== 可建仓统计卡（顶部；0 只也明确显示，接口失败降级 caption 不阻塞页面） =====
tradeable_view = None
trade_map: dict[str, dict] = {}
try:
    tradeable_view = api.candidate_tradeable(date=date, limit=200)
    for _it in (tradeable_view.get("items") or []):
        trade_map[_it["stock_code"]] = _it
except Exception as exc:  # noqa: BLE001 统计卡失败仅降级提示，不阻塞候选浏览
    st.caption("可建仓判定暂不可用（不影响候选浏览与筛选），可稍后刷新重试。")
if tradeable_view:
    t_count = int(tradeable_view.get("count") or 0)
    p_count = int(tradeable_view.get("plan_candidate_count") or 0)
    render.stat_cards([
        {"label": "今日可建仓标的", "value": t_count,
         "sub": "评级≥B 且现价在首仓区间且无重大利空", "tone": "ok" if t_count > 0 else "mute"},
        {"label": "可自动生成建仓计划的标的", "value": p_count,
         "sub": "评级 A/B 且暂无建仓方案", "tone": "info"},
    ])
    if t_count == 0:
        render.msg_card("warn", "今日可建仓标的 0 只", "今日无符合买入条件的标的，建议观望。")

# ===== 当日候选：接口失败 → 缓存降级（灰色弱化）或分类报错卡片 =====
try:
    rows = api.candidates(date=date, limit=300)
    fc.save(CACHE_KEY, {"date": date, "rows": rows})  # 成功即刷新离线缓存
except Exception as exc:  # noqa: BLE001
    if _cached and _cached["data"].get("rows"):
        rows = _cached["data"]["rows"]
        _stale = True
    else:
        title, hint, tech = render.classify_api_error(exc)
        render.error_card(title, hint, detail=tech, retry_key="retry_candidates")
        st.stop()

if _stale:
    # 离线缓存模式：明确标注缓存时间与数据日期，非最新
    render.msg_card("warn", "离线缓存模式（数据非最新）",
                    f"接口暂不可用，以下展示最近一次成功缓存：{_cached['saved_at']}"
                    f"（{_cached['data']['date']} 数据），恢复后自动更新。")
    st.markdown('<style>[class*="st-key-cached_rows"]{opacity:.62;filter:saturate(.75)}</style>',
                unsafe_allow_html=True)
    rows_area = st.container(key="cached_rows")
else:
    rows_area = st.container()

with rows_area:
    # 同日同股按最新版本覆盖（created_at 最大），历史版本不参与渲染
    latest: dict[tuple, dict] = {}
    for r in rows:
        key = (r["stock_code"], r["trade_date"])
        if key not in latest or (r.get("created_at") or "") > (latest[key].get("created_at") or ""):
            latest[key] = r
    day_rows = list(latest.values())

    def _tier(r: dict) -> str:
        t = ((r.get("detail") or {}).get("confidence_tier") or "")
        return TIER_MAP.get(t, "")

    if filter_opt == "可建仓 A+B":
        day_rows = [r for r in day_rows
                    if (trade_map.get(r["stock_code"]) or {}).get("is_tradeable") == 1]
    elif filter_opt == "观察 C":
        day_rows = [r for r in day_rows if _tier(r) == "C"]

    # ===== 板块行业筛选（来自首页「今日热门板块」点击跳转，query param 传递） =====
    sector = st.query_params.get("sector", "")
    if isinstance(sector, list):
        sector = sector[0] if sector else ""
    sector = str(sector or "").strip()
    if sector:
        st.info(f"行业筛选：**{sector}**（按候选详情行业字段子串匹配）")
        if st.button("清除行业筛选"):
            st.query_params.pop("sector", None)
            st.rerun()
        matched = []
        for r in day_rows:
            industry = str(((r.get("detail") or {}).get("enriched") or {}).get("industry") or "")
            if sector in industry or (industry and industry in sector):
                matched.append(r)
        if not matched:
            render.msg_card("warn", f"当日候选池中没有行业包含「{sector}」的候选股",
                            "候选行业字段来自个股基本信息，可能与板块名称不完全一致，可清除筛选后浏览全部候选。")
        day_rows = matched

    # 可建仓置顶：A→B→C，组内按 rank 升序
    day_rows.sort(key=lambda r: (_SORT.get(_tier(r), 3), int(r.get("rank") or 999)))

    def _cand_detail(r: dict, _i: int) -> None:
        label = render.stock_label(r["stock_code"], r["stock_name"])
        detail = r.get("detail") or {}
        tier = _tier(r)
        tier_label = TIER_LABEL.get(tier, "未评级")
        dot = TIER_DOT.get(tier, "mute")
        stock_type = detail.get("stock_type", "")
        reasons = r.get("reasons") or []
        core = reasons[0] if reasons else (detail.get("meso_view") or "")
        subtitle = "　·　".join(x for x in (stock_type, core) if x)
        meta = f"生成 {str(r.get('created_at') or '')[:16]}"
        # API 行不含 ORM id：用 代码+日期+rank 组成稳定唯一键（同日同股已按最新版去重）
        key = f"cand_{r['stock_code']}_{r['trade_date']}_{r.get('rank')}"
        if render.list_item_toggle(key, f"#{r.get('rank', '-')} {label}　{tier_label}",
                                   subtitle=subtitle, dot=dot, meta=meta, scope="cand"):
            with st.container(border=True):
                render.trace_line("本轮挖掘执行时间", r.get("created_at"),
                                  source="行情快照 + LLM 研判", confidence=detail.get("confidence"))
                # v3.0 白盒维度归因：维度数组 + 综合评估（主结论，置顶展示）
                with st.container(border=True):
                    render.section_title("维度归因（五维白盒，主结论）")
                    render.dimension_bars(detail.get("dimensions"),
                                          final_advice=detail.get("final_advice"))
                with st.container(border=True):
                    render.section_title("候选理由")
                    if reasons:
                        for i, reason in enumerate(reasons, 1):
                            st.markdown(f"{i}. {reason}")
                    else:
                        st.markdown("（该轮未输出）")
                with st.container(border=True):
                    render.section_title("技术面研判（威科夫/量价/K线形态/谐波交叉验证）")
                    st.markdown(detail.get("tech_view") or detail.get("meso_view")
                                or "（该轮未输出，可重新触发挖掘生成）")
                with st.container(border=True):
                    render.section_title("量价与资金结论（主力动向/量能结构）")
                    st.markdown(detail.get("volume_analysis") or "（无）")
                with st.container(border=True):
                    render.section_title("关键价位（支撑位/压力位/建议关注区间）")
                    st.markdown(detail.get("price_levels") or "（未输出）")
                with st.container(border=True):
                    render.section_title("核心风险点（≥2 项）")
                    risks = detail.get("risks") or []
                    if risks:
                        for i, risk in enumerate(risks, 1):
                            st.markdown(f"{i}. {risk}")
                    else:
                        st.markdown("（无）")
                with st.container(border=True):
                    render.section_title("操作建议（标的类型 + 关注类型 + 参考仓位）")
                    focus = detail.get("focus_type", "")
                    st.markdown(f"- 标的类型：{stock_type or '（未输出）'}（威科夫阶段定位，参考权重）")
                    st.markdown(f"- 关注类型：{focus or '观察'}")
                    hint = detail.get("position_hint") or ""
                    st.markdown(f"- 参考建议：{hint}" if hint else "- 参考建议：（该轮未输出）")
                with st.container(border=True):
                    render.section_title("三维验证（宏观 / 中观 / 微观）")
                    st.markdown(f"- 宏观：{detail.get('macro_view', '（无）')}")
                    st.markdown(f"- 中观：{detail.get('meso_view', '（无）')}")
                    st.markdown(f"- 微观：{detail.get('micro_view', '（无）')}")
                with st.container(border=True):
                    render.section_title("风险初判")
                    risk_notice = r.get("risk_notice") or []
                    if risk_notice:
                        for risk in risk_notice:
                            st.markdown(f"- {risk}")
                    else:
                        st.markdown("（无）")
                code, name = r["stock_code"], r["stock_name"]
                if st.button("生成建仓方案", key=f"plan_{code}_{r['trade_date']}"):
                    render.submit_task("position", {"stock_code": code, "stock_name": name},
                                       label="建仓方案生成")
                # ===== AI 研判留痕（推理链路可溯源）：按钮触发真懒加载，未点击零接口调用 =====
                tk = f"traces_{code}_{r['trade_date']}"
                if st.button("AI 研判留痕（推理链路可溯源）", key=f"trbtn_{key}",
                             use_container_width=True):
                    st.session_state[tk] = "open"
                    st.rerun()
                if st.session_state.get(tk) == "open":
                    if f"{tk}_rows" not in st.session_state:
                        try:
                            st.session_state[f"{tk}_rows"] = api.traces(
                                code=code, date=r["trade_date"], limit=10)
                        except Exception:  # noqa: BLE001 留痕接口异常不阻塞候选展示
                            st.session_state[f"{tk}_rows"] = False
                    trace_rows = st.session_state.get(f"{tk}_rows")
                    if trace_rows is False:
                        st.caption("留痕接口暂不可用，可点击下方重试。")
                        if st.button("重试", key=f"retry_trace_{key}"):
                            st.session_state.pop(f"{tk}_rows", None)
                            st.rerun()
                    elif not trace_rows:
                        st.caption("该标的本交易日暂无留痕记录（历史快照或留痕启用前数据）。")
                    else:
                        for t in trace_rows:
                            dk = f"trace_open_{t['trace_id']}"
                            opened = st.session_state.get(dk, False)
                            mlabel = _TRACE_MODULE.get(t.get("source_module", ""),
                                                       t.get("source_module", ""))
                            if st.button(f"查看 {mlabel} 留痕（{str(t.get('create_time') or '')[:16]}）",
                                         key=f"trace_btn_{t['trace_id']}",
                                         use_container_width=True):
                                opened = not opened
                                st.session_state[dk] = opened
                                st.rerun()
                            if opened:
                                try:
                                    render.trace_card(api.trace_detail(t["trace_id"]),
                                                      key=f"tc_{t['trace_id']}")
                                except Exception as exc:  # noqa: BLE001 详情失败只降级为提示
                                    st.caption(f"留痕详情暂不可用：{exc}")
                render.raw_json_expander(
                    {"reasons": r.get("reasons"), "risk_notice": r.get("risk_notice"),
                     "detail": detail},
                    key=f"raw_cand_{code}_{r['trade_date']}")

    # 详情懒加载：首屏 20 条，点「加载更多」增量展示；切换日期/筛选自动回首屏
    cand_keys = [f"cand_{r['stock_code']}_{r['trade_date']}_{r.get('rank')}" for r in day_rows]
    render.batch_fold_bar("cand", cand_keys,
                          label="点击行内「查看详情」展开完整研判（维度归因/理由/风险/操作建议）。")
    render.record_list(day_rows, _cand_detail, batch=20,
                       key=f"_cand_vis_{date}_{filter_opt}_{sector}",
                       empty_text="当日无候选：可切换日期，或点击上方「手动触发每日挖掘」重新生成。")
