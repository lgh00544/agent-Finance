"""持仓监控：MonitorAgent 持仓监控 + 人工录入买卖（系统不下单）

3 个 Tab：当前持仓（列表行：左侧代码名称+建仓信息，右侧现价/盈亏红绿+风控参考+查看详情）/
告警记录（与告警日志页同一套行范式）/ 历史持仓（已离场记录）。
「查看详情」内为操作卡：立即监控/生成卖出决策/卖出决策历史/录入人工卖出。
底部保留截图 OCR 快速录入与手动录入（功能与上一版完全一致）。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次2：页面头部收敛为 page_header 单行范式（标题+说明+操作按钮组）=====
_hdr = render.page_header(
    "持仓监控（MonitorAgent）",
    primary_actions=[{"label": "⚡ 立即刷新监控", "key": "hdr_mon"}],
    secondary_actions=[{"label": "🔄 手动刷新行情", "key": "hdr_refresh"}],
)
if _hdr["primary"] == 0:
    api.submit_task("monitor_all")
    st.toast("全量持仓监控已提交后台，完成后顶部任务状态区会提示；"
             "新信号会自动落库并在告警日志页展示")
if _hdr["secondary"] == 0:
    st.rerun()

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

ACTION_MAP = {"hold": "持有", "reduce": "减仓", "exit": "清仓",
              "partial": "部分减仓", "sell": "卖出清仓"}
SEVERITY_MAP = {"info": "一般", "warning": "警告", "critical": "严重"}
CONF_MAP = {"high": "高", "medium": "中", "low": "低"}


def render_monitor_signal(sig: dict) -> None:
    """监控信号 → 自然语言分段（含关键价位）"""
    if not sig:
        st.info("无信号内容。")
        return
    action = ACTION_MAP.get(sig.get("action"), sig.get("action"))
    severity = SEVERITY_MAP.get(sig.get("severity"), sig.get("severity"))
    st.markdown(f"**研判结论：{action}**（严重度 {severity} · 触发类型：{sig.get('alert_type', '—')}）")
    if sig.get("message"):
        st.markdown(sig["message"])
    if sig.get("reasons"):
        st.markdown("**研判依据**")
        for i, r in enumerate(sig["reasons"], 1):
            st.markdown(f"{i}. {r}")
    if sig.get("key_levels"):
        st.markdown("**关注价位**")
        for k, v in sig["key_levels"].items():
            st.markdown(f"- {k}：{v}")


def _now_min() -> str:
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def _throttle_load(key: str, fn, ttl: float = 30.0):
    """非红线数据会话内 TTL 缓存（按需加载：未加载返回 None 由调用方渲染加载按钮；
    ttl=0 强制立即拉取）。红线数据（持仓行情/评分等）禁止使用本 helper。"""
    import time as _t

    if st.session_state.get(f"{key}_ts", 0.0) + ttl > _t.time():
        return st.session_state.get(key)
    try:
        data = fn()
        st.session_state[key] = data
        st.session_state[f"{key}_ts"] = _t.time()
        return data
    except Exception:  # noqa: BLE001 拉取失败返回旧缓存或 None；不记时间戳（下次 rerun 自动重试）
        st.session_state.pop(f"{key}_ts", None)
        return st.session_state.get(key)


def _signal_time(label: str, time_str: str | None, signal: dict) -> None:
    """信号生成时间标注：紧急信号（减仓/清仓建议或高严重度）时间琥珀色高亮"""
    urgent = bool(signal) and (signal.get("action") != "hold"
                               or signal.get("severity") in ("warning", "critical"))
    render.trace_line(label, time_str, source="LLM 生成",
                      confidence=signal.get("confidence") if signal else None,
                      highlight=urgent)


def render_sell_decision(d: dict, shares: int | None = None) -> None:
    """卖出决策 → 自然语言分段（v3.0：维度归因 + 综合评估置顶，旧数据缺省自动跳过）
    shares: 当前持仓股数（合并展示口径）；仅 action=partial 且 reduce_ratio 有效时展示减仓建议，
    持仓股数缺失或为 0 时不展示、不报错。"""
    action = ACTION_MAP.get(d.get("action"), d.get("action"))
    conf = CONF_MAP.get(d.get("confidence"), d.get("confidence"))
    st.markdown(f"**卖出决策：{action}**（置信度 {conf}）")
    # 减仓比例建议（仅 action=partial；持仓股数缺失/为 0 不展示不报错）
    ratio = d.get("reduce_ratio")
    if d.get("action") == "partial" and isinstance(ratio, (int, float)) and 0 < float(ratio) <= 1:
        hold_shares = int(shares or 0)
        if hold_shares > 0:
            sell_shares, remain = render.reduce_share_plan(float(ratio), hold_shares)
            pct = round(float(ratio) * 100)
            st.markdown(
                f"**建议减仓：{pct}%**（约 {sell_shares:,} 股 / {sell_shares // 100} 手）\n\n"
                f"当前持仓 {hold_shares:,} 股 → 建议卖出 {sell_shares:,} 股 → "
                f"减仓后剩余 {remain:,} 股（{remain // 100} 手）"
            )
    # v3.0 白盒维度归因：维度数组 + 综合评估（主结论）
    render.dimension_bars(d.get("dimensions"), final_advice=d.get("final_advice"))
    if d.get("reasons"):
        st.markdown("**研判依据**")
        for i, r in enumerate(d["reasons"], 1):
            st.markdown(f"{i}. {r}")
    if d.get("exit_price_zone"):
        st.markdown(f"**卖出价位区间**：{d['exit_price_zone']}")
    if d.get("risk_warning"):
        st.markdown(f"**风险提示**：{d['risk_warning']}")
    if d.get("check_list"):
        st.markdown("**卖出前检查清单**")
        for i, item in enumerate(d["check_list"], 1):
            st.markdown(f"- {item}")


def _dedupe_and_merge(rows: list[dict]) -> list[dict]:
    """同代码去重合并（仅展示层，数据库原始记录完整保留，不删除任何数据）：
    - 同建仓日期的重复录入 → 仅保留录入时间最晚一条；
    - 去重后同代码多笔建仓 → 合并展示：总股数 + 加权平均成本；
    - 「当前有效」= 去重后建仓日期最新、录入时间最晚的一条（绑定操作与风控参考字段）。"""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["stock_code"], []).append(r)

    merged = []
    for code, items in groups.items():
        items.sort(key=lambda x: (x.get("entry_date") or "", x.get("created_at") or ""))
        by_date: dict[str, list[dict]] = {}
        for it in items:
            by_date.setdefault(it.get("entry_date"), []).append(it)
        keep = [max(g, key=lambda x: x.get("created_at") or "") for g in by_date.values()]
        keep.sort(key=lambda x: (x.get("entry_date") or "", x.get("created_at") or ""))
        current = keep[-1]

        total_shares = sum(int(k.get("shares") or 0) for k in keep)
        weighted = None
        if total_shares:
            weighted = sum(float(k.get("entry_price") or 0) * int(k.get("shares") or 0)
                           for k in keep) / total_shares

        dup_dates = {d for d, g in by_date.items() if len(g) > 1}
        for it in items:
            if it["id"] == current["id"]:
                it["_dedupe_status"] = "当前有效"
            elif it.get("entry_date") in dup_dates:
                it["_dedupe_status"] = "重复录入（已自动忽略）"
            else:
                it["_dedupe_status"] = "历史买入"

        merged.append({"code": code, "records": items, "keep": keep, "current": current,
                       "total_shares": total_shares, "weighted_price": weighted})
    merged.sort(key=lambda m: (m["current"].get("entry_date") or "", m["current"].get("created_at") or ""))
    return merged


def _fmt_signed(value) -> str:
    """带符号金额（如 +3,030.00 / -1,234.50）"""
    if value is None or (isinstance(value, float) and value != value):
        return "—"
    return f"{value:+,.2f}"


def _pnl_cls(value) -> str:
    """盈亏色调映射（A 股习惯：正红负绿）"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return ""


# ================= 手动持仓操作编辑（风控规则遵循持仓知识库 v1.0） =================
_SIDE_LABEL = {"buy": "加仓", "sell": "减仓/卖出", "adjust": "成本修正"}
C3_LOSS_PCT = 0.92  # 知识库红线：C3 止损 = 成本 × 0.92（永久红线）
C1_CAP_PCT = 60.0   # C1：总仓位上限
C2_CAP_PCT = 30.0   # C2：单票仓位上限
E2_INDEX_BAR = 4000.0  # E2：沪指 < 4000 = 防御期，仓位软上限 20%


def _today_str() -> str:
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _price_limit_pct(code: str) -> float:
    """涨跌幅限制：创业板(300/301)/科创板(688) ±20%，主板 ±10%（仅前端黄色提醒，不阻断）"""
    return 20.0 if (code.startswith("300") or code.startswith("301")
                    or code.startswith("688")) else 10.0


def _risk_preview(cost_price: float, current_price) -> dict:
    """风控档位实时预览（展示层纯计算不入库）：C3 止损 / +5% / +10% 减仓档 / 移动止盈"""
    return {"c3": round(cost_price * C3_LOSS_PCT, 2),
            "tp5": round(cost_price * 1.05, 2),
            "tp10": round(cost_price * 1.10, 2),
            "trail": (round(cost_price + (current_price - cost_price) * 0.5, 2)
                      if isinstance(current_price, (int, float)) else None)}


def _shanghai_index() -> float | None:
    """上证指数（E2 防御期判断），60 秒内复用缓存；拉取失败返回 None（不阻塞操作面板）"""
    import time
    now = time.time()
    if st.session_state.get("_e2_idx_ts", 0) + 60 < now:
        val = None
        try:
            for i in (api.market_indices().get("indices") or []):
                if "上证" in str(i.get("name") or ""):
                    val = float(i.get("price"))
                    break
        except Exception:  # noqa: BLE001 指数拉取失败不影响手动操作
            pass
        st.session_state["_e2_idx"] = val
        st.session_state["_e2_idx_ts"] = now
    return st.session_state.get("_e2_idx")


def _position_warnings(code: str, mv_new: float, mv_total_new: float,
                       total_capital: float) -> list[str]:
    """加仓超限黄色警告（不阻断，确认后可执行）：C2 单票>30% / C1 总仓>60% / E2 防御期软上限"""
    if total_capital <= 0:
        return []
    c2 = mv_new / total_capital * 100
    c1 = mv_total_new / total_capital * 100
    warns = []
    if c2 > C2_CAP_PCT:
        warns.append(f"单票仓位将达 {c2:.1f}%，超过 C2 上限 {C2_CAP_PCT:.0f}%")
    if c1 > C1_CAP_PCT:
        warns.append(f"总仓位将达 {c1:.1f}%，超过 C1 上限 {C1_CAP_PCT:.0f}%")
    idx = _shanghai_index()
    if idx is not None and idx < E2_INDEX_BAR and c1 > 20.0:
        warns.append(f"防御期（沪指 {idx:.0f} < {E2_INDEX_BAR:.0f}）仓位软上限 20%，"
                     f"当前预计 {c1:.1f}%")
    return warns


def _trades_block(hid: int) -> None:
    """持仓操作流水（只读，最新在前）：加仓/减仓/清仓/成本修正，可追溯（K223）。
    流水含操作前后股数（before/after_shares，旧数据为 None 时省略）。"""
    try:
        trades = api.holding_trades(hid)
    except Exception as exc:
        render.error_card("操作流水加载失败", "请确认后端服务运行正常后重试。",
                          detail=exc, retry_key=f"retry_trades_{hid}")
        return
    if not trades:
        st.markdown("（暂无操作流水）")
        return
    for t in trades:
        side = _SIDE_LABEL.get(t.get("side"), t.get("side"))
        note = f"　{t.get('note')}" if t.get("note") else ""
        b, a = t.get("before_shares"), t.get("after_shares")
        if b is not None and a is not None and b != a:
            shares_txt = f"{b:,} → {a:,} 股"
        else:
            shares_txt = f"{t.get('shares')} 股"
        st.markdown(f"- **{side}**　{shares_txt} @ {t.get('price')}　"
                    f"日期 {t.get('trade_date')}{note}")
        render.time_text("记录时间", t.get("created_at"))


def _detail_row(r: dict) -> dict:
    """历史明细行：每笔原始记录（含被去重的重复录入），标注状态"""
    return {"ID": r["id"], "股票": render.stock_label(r["stock_code"], r["stock_name"]),
            "建仓日": r["entry_date"], "成本价": r["entry_price"], "股数": r["shares"],
            "状态": r.get("_dedupe_status", "")}


def _operation_card(g: dict, total_capital: float, total_market_value: float) -> None:
    """持仓详情操作卡：持仓操作编辑（加仓/减仓/清仓/成本修正）+ 立即监控/卖出决策 + 操作流水"""
    r = g["current"]
    hid = r["id"]
    label = render.stock_label(r["stock_code"], r["stock_name"])
    st.markdown(f"**操作 {label}**")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("立即执行监控", key=f"mon_{hid}"):
            with st.spinner("LLM 研判中..."):
                result = api.monitor_holding(hid)
                st.session_state[f"mon_result_{hid}"] = result.get("signal") or {}
                st.session_state[f"mon_time_{hid}"] = _now_min()
        mon_result = st.session_state.get(f"mon_result_{hid}")
        if mon_result:
            render_monitor_signal(mon_result)
            _signal_time("信号生成时间", st.session_state.get(f"mon_time_{hid}"), mon_result)
            render.raw_json_expander(mon_result, key=f"raw_mon_{hid}")
        if st.button("生成卖出决策", key=f"sell_{hid}"):
            api.submit_task("sell_decision", {"holding_id": hid})
            st.toast("卖出决策任务已提交后台，完成后顶部任务状态区会提示")
        sell_result = st.session_state.get(f"sell_result_{hid}")
        if sell_result:
            st.markdown("决策仅供参考，卖出必须由你人工执行。")
            render_sell_decision(sell_result, shares=g["total_shares"])
            _signal_time("信号生成时间", st.session_state.get(f"sell_time_{hid}"), sell_result)
            render.raw_json_expander(sell_result, key=f"raw_sell_{hid}")
        sell_hist = api.sell_decisions(hid)
        if sell_hist:
            with st.expander(f"卖出决策历史（{len(sell_hist)} 条，仅供参考）"):
                for h in sell_hist:
                    d = h.get("decision") or {}
                    action = ACTION_MAP.get(d.get("action"), d.get("action"))
                    conf = CONF_MAP.get(d.get("confidence"), d.get("confidence"))
                    st.markdown(f"- **{action}**（置信度 {conf}）："
                                f"{d.get('exit_price_zone') or d.get('risk_warning') or ''}")
                    # v3.0 综合评估摘要（主结论；旧数据缺省跳过）
                    if d.get("final_advice"):
                        st.markdown(f"　{d['final_advice']}")
                    render.time_text("信号生成时间", h["created_at"],
                                     highlight=d.get("action") != "hold"
                                     or d.get("severity") in ("warning", "critical"))
                    render.raw_json_expander(d, label="原始数据", key=f"raw_sellhist_{h['id']}")
    with c2:
        st.caption("交易时段监控每 3 分钟自动运行（实时行情 60 秒内缓存），"
                   "触发信号自动推送飞书并记录告警日志；收盘后 15:00-15:30 做收盘数据校验。"
                   "卖出决策由 SellAgent 独立研判，人工按需触发。")
    st.divider()
    _operation_panel(g, total_capital, total_market_value, pfx="det")
    with st.container(border=True):
        render.section_title("操作流水（加仓/减仓/清仓/成本修正，可追溯）")
        _trades_block(hid)


_OP_PANEL_KEYS = ("optype", "addp", "adds", "addd", "addn",
                  "redp", "reds", "redd", "redn",
                  "closep", "closed", "closen", "closeck", "costp", "costr")


def _clear_op_state(hid: int, pfx: str = "") -> None:
    """操作成功后清理面板输入（避免 rerun 后 widget 值与新边界冲突，如减仓后股数上限变小）；
    pfx 为面板 key 前缀（卡片行面板 "row" / 详情面板 "det"），两处面板互不干扰"""
    for k in _OP_PANEL_KEYS:
        st.session_state.pop(f"{pfx}{k}_{hid}", None)


def _operation_panel(g: dict, total_capital: float, total_market_value: float,
                     pfx: str = "") -> None:
    """手动持仓操作编辑：记录加仓/记录减仓/记录清仓/编辑成本。
    股数严格 100 整数倍（K32-3）；C3 止损=成本×0.92 自动重算（知识库红线）；
    超限/涨跌幅仅黄色警告不阻断，确认后执行并留痕；所有操作不触发实盘交易。
    pfx 为 widget key 前缀：卡片行快捷面板传 "row"，详情内面板传 "det"（或默认），
    两处面板可同时展开互不冲突。"""
    r = g["current"]
    hid = r["id"]
    code = r["stock_code"]
    price = r.get("current_price")
    total_shares = g["total_shares"]
    weighted = g["weighted_price"]
    cur_shares = int(r["shares"])  # 操作绑定「当前有效」记录行
    cur_entry = float(r.get("entry_price") or 0.0)
    base = weighted or cur_entry

    st.markdown("**持仓操作（手动同步实盘，系统不自动下单）**")
    # 风控档位最后更新标注（K223 可追溯：最新一次加仓/成本修正的时间与原因）
    try:
        _t = api.holding_trades(hid)
    except Exception:  # noqa: BLE001 流水拉取失败不阻塞操作面板
        _t = []
    _adj = next((x for x in _t if x.get("side") in ("buy", "adjust")), None)
    if _adj:
        st.caption(f"风控档位最后更新：{str(_adj.get('created_at') or '')[:16]}"
                   f"（{_adj.get('note') or '加仓/成本调整'}）")
    else:
        st.caption("风控档位自建仓后未调整，C3 = 成本 × 0.92 为初始值（建仓记录永久保留可追溯）")
    op = st.selectbox("选择操作类型", ("记录加仓", "记录减仓", "记录清仓", "编辑成本"),
                      key=f"{pfx}optype_{hid}")

    if op == "记录加仓":
        # 批次2：必填字段（价格/股数）首行 2 列，选填字段（日期/备注）收进「更多参数」折叠
        c1, c2 = st.columns(2)
        with c1:
            with st.container(key=f"{pfx}fld_add_price_{hid}"):
                add_price = st.number_input("成交价格 *", min_value=0.0, step=0.01,
                                            key=f"{pfx}addp_{hid}")
        with c2:
            add_shares = st.number_input("操作股数 *（100 整数倍）", min_value=0, step=100,
                                         key=f"{pfx}adds_{hid}")
        with st.expander("更多参数（日期/备注）", expanded=False):
            c3, c4 = st.columns(2)
            with c3:
                add_date = st.text_input("成交日期（YYYY-MM-DD，默认当日）", key=f"{pfx}addd_{hid}")
            with c4:
                add_note = st.text_input("操作备注（可选）", key=f"{pfx}addn_{hid}")

        errs = {}
        if add_price <= 0:
            errs["add_price"] = "成交价格必须大于 0"
        if add_shares <= 0 or int(add_shares) % 100 != 0:
            errs["add_shares"] = "股数必须为 100 的整数倍（K32-3）"
        render.field_error("add_price", errs.get("add_price", ""), "如 12.50")
        render.field_error("add_shares", errs.get("add_shares", ""), "如 100 / 200 / 300")

        warns = []
        if not errs:
            if isinstance(price, (int, float)) and add_price > 0:
                limit = _price_limit_pct(code)
                if (add_price > price * (1 + limit / 100)
                        or add_price < price * (1 - limit / 100)):
                    warns.append(f"成交价 {add_price:.2f} 超出当日涨跌幅范围"
                                 f"（现价 {price:.2f} ±{limit:.0f}%），请核对")
            if add_shares > 0:
                mv_old = (price or cur_entry) * total_shares
                mv_new = (price or add_price) * (total_shares + int(add_shares))
                warns += _position_warnings(code, mv_new, total_market_value - mv_old + mv_new,
                                            total_capital)
        for w in warns:
            render.msg_card("warn", "提示（可确认后继续执行）", w)

        if not errs and add_price > 0 and add_shares > 0:
            new_shares = total_shares + int(add_shares)
            new_entry = round((base * total_shares + add_price * int(add_shares)) / new_shares, 4)
            lv = _risk_preview(new_entry, price)
            pos_pct = ((price or add_price) * new_shares / total_capital * 100
                       if total_capital > 0 else None)
            render.stat_cards([
                {"label": "新加权成本", "value": f"{new_entry:,.2f}", "sub": f"共 {new_shares:,} 股",
                 "tone": "mute"},
                {"label": "C3 止损（自动重算）", "value": f"{lv['c3']:,.2f}",
                 "sub": "成本 × 0.92，不可手动修改", "tone": "err"},
                {"label": "+5% 减仓档", "value": f"{lv['tp5']:,.2f}", "tone": "mute"},
                {"label": "+10% 减仓档", "value": f"{lv['tp10']:,.2f}", "tone": "mute"},
                {"label": "移动止盈", "value": f"{lv['trail']:,.2f}" if lv["trail"] else "—",
                 "tone": "mute"},
                {"label": "单票仓位", "value": f"{pos_pct:.1f}%" if pos_pct is not None else "—",
                 "tone": "warn" if pos_pct is not None and pos_pct > C2_CAP_PCT else "mute"},
            ])

        if st.button("确认加仓（仅记录，不触发实盘交易）", key=f"{pfx}btnadd_{hid}",
                     disabled=bool(errs) or add_price <= 0 or add_shares <= 0):
            note = add_note or ""
            if warns:
                note = (note + "；" if note else "") + "超限加仓：" + "；".join(warns)
            try:
                api.holding_add(hid, {"price": float(add_price), "shares": int(add_shares),
                                      "trade_date": add_date or _today_str(), "note": note})
                st.toast("加仓已记录：加权成本与 C3 止损等风控档位已自动重算")
                _clear_op_state(hid, pfx)
                st.rerun()
            except Exception as exc:
                render.msg_card("err", "加仓记录失败", "请核对输入后重试。", detail=exc)

    elif op == "记录减仓":
        c1, c2 = st.columns(2)
        with c1:
            with st.container(key=f"{pfx}fld_red_price_{hid}"):
                red_price = st.number_input("成交价格 *", min_value=0.0, step=0.01,
                                            key=f"{pfx}redp_{hid}")
        with c2:
            red_shares = st.number_input("减仓股数 *（100 整数倍，≤ 持仓）", min_value=0,
                                         max_value=cur_shares, step=100, key=f"{pfx}reds_{hid}")
        with st.expander("更多参数（日期/备注）", expanded=False):
            c3, c4 = st.columns(2)
            with c3:
                red_date = st.text_input("成交日期（YYYY-MM-DD，默认当日）", key=f"{pfx}redd_{hid}")
            with c4:
                red_note = st.text_input("操作备注（可选）", key=f"{pfx}redn_{hid}")

        errs = {}
        if red_price <= 0:
            errs["red_price"] = "成交价格必须大于 0"
        if red_shares <= 0 or int(red_shares) % 100 != 0:
            errs["red_shares"] = "股数必须为 100 的整数倍（K32-3）"
        render.field_error("red_price", errs.get("red_price", ""), "如 12.50")
        render.field_error("red_shares", errs.get("red_shares", ""), "如 100 / 200 / 300")
        if not errs and int(red_shares) >= cur_shares:
            render.msg_card("info", "该股数等于持仓总量",
                            "将全部卖出（清仓），建议使用「记录清仓」入口（二次确认并触发复盘）。")

        if not errs and red_price > 0 and red_shares > 0:
            lock = (red_price - base) * int(red_shares)
            remain = total_shares - int(red_shares)
            render.stat_cards([
                {"label": "减仓后总股数", "value": f"{remain:,}", "tone": "mute"},
                {"label": "加权成本（不变）", "value": f"{base:,.2f}", "tone": "mute"},
                {"label": "C3 止损（不变）", "value": f"{_risk_preview(base, price)['c3']:,.2f}",
                 "sub": "成本 × 0.92", "tone": "err"},
                {"label": "本次实现盈亏", "value": f"{lock:+,.2f}",
                 "tone": "up" if lock > 0 else "down"},
            ])

        if st.button("确认减仓（仅记录，不触发实盘交易）", key=f"{pfx}btnred_{hid}",
                     disabled=bool(errs) or red_price <= 0 or red_shares <= 0):
            try:
                result = api.exit_holding(hid, {"price": float(red_price),
                                                "shares": int(red_shares),
                                                "trade_date": red_date or _today_str(),
                                                "note": red_note})
                st.toast(f"减仓已记录，剩余 {result['remain_shares']} 股")
                _clear_op_state(hid, pfx)
                st.rerun()
            except Exception as exc:
                render.msg_card("err", "减仓记录失败", "请核对输入后重试。", detail=exc)

    elif op == "记录清仓":
        with st.container(key=f"{pfx}fld_close_price_{hid}"):
            close_price = st.number_input("成交价格 *", min_value=0.0, step=0.01,
                                          key=f"{pfx}closep_{hid}")
        with st.expander("更多参数（日期/原因）", expanded=False):
            c3, c4 = st.columns(2)
            with c3:
                close_date = st.text_input("成交日期（YYYY-MM-DD，默认当日）", key=f"{pfx}closed_{hid}")
            with c4:
                close_note = st.text_input("清仓原因（可选）", key=f"{pfx}closen_{hid}")
        errs = {}
        if close_price <= 0:
            errs["close_price"] = "成交价格必须大于 0"
        render.field_error("close_price", errs.get("close_price", ""), "如 12.50")

        if not errs and close_price > 0:
            final_pnl = (close_price - base) * total_shares
            render.stat_cards([
                {"label": "清仓股数", "value": f"{total_shares:,}", "tone": "mute"},
                {"label": "加权成本", "value": f"{base:,.2f}", "tone": "mute"},
                {"label": "最终盈亏", "value": f"{final_pnl:+,.2f}",
                 "tone": "up" if final_pnl > 0 else "down"},
            ])
        confirm = st.checkbox("确认清仓：该标的将移入历史持仓，C3 风控与监控自动停止",
                              key=f"{pfx}closeck_{hid}")
        if st.button("确认清仓（仅记录，不触发实盘交易）", key=f"{pfx}btnclose_{hid}",
                     disabled=bool(errs) or close_price <= 0 or not confirm):
            try:
                result = api.exit_holding(hid, {"price": float(close_price),
                                                "shares": cur_shares,
                                                "trade_date": close_date or _today_str(),
                                                "note": close_note})
                extra = (f"，复盘任务已提交（{result['review_task_id']}）"
                         if result.get("review_task_id") else "")
                st.toast(f"已清仓并移入历史持仓{extra}")
                _clear_op_state(hid, pfx)
                st.rerun()
            except Exception as exc:
                render.msg_card("err", "清仓记录失败", "请核对输入后重试。", detail=exc)

    else:  # 编辑成本
        c1, c2 = st.columns(2)
        with c1:
            with st.container(key=f"{pfx}fld_cost_price_{hid}"):
                cost_price = st.number_input("修正后成本价 *", min_value=0.0, step=0.01,
                                             key=f"{pfx}costp_{hid}")
        with c2:
            with st.container(key=f"{pfx}fld_cost_reason_{hid}"):
                cost_reason = st.text_input("修正原因 *（必填留痕）", key=f"{pfx}costr_{hid}")
        errs = {}
        if cost_price <= 0:
            errs["cost_price"] = "成本价必须大于 0"
        if not (cost_reason or "").strip():
            errs["cost_reason"] = "必须填写修正原因（留痕追溯）"
        render.field_error("cost_price", errs.get("cost_price", ""), "如 12.50")
        render.field_error("cost_reason", errs.get("cost_reason", ""), "如 实盘核对修正")

        if not errs and cost_price > 0:
            lv = _risk_preview(cost_price, price)
            render.stat_cards([
                {"label": "修正后成本价", "value": f"{cost_price:,.2f}", "tone": "mute"},
                {"label": "C3 止损（自动重算）", "value": f"{lv['c3']:,.2f}",
                 "sub": "成本 × 0.92，不可手动修改", "tone": "err"},
                {"label": "+5% 减仓档", "value": f"{lv['tp5']:,.2f}", "tone": "mute"},
                {"label": "+10% 减仓档", "value": f"{lv['tp10']:,.2f}", "tone": "mute"},
                {"label": "移动止盈", "value": f"{lv['trail']:,.2f}" if lv["trail"] else "—",
                 "tone": "mute"},
            ])

        if st.button("确认修正成本（仅记录，不触发实盘交易）", key=f"{pfx}btncost_{hid}",
                     disabled=bool(errs) or cost_price <= 0):
            try:
                api.holding_cost(hid, {"cost_price": float(cost_price),
                                       "reason": cost_reason.strip()})
                st.toast("成本已修正，C3 止损与全部风控档位已自动重算")
                _clear_op_state(hid, pfx)
                st.rerun()
            except Exception as exc:
                render.msg_card("err", "成本修正失败", "请核对输入后重试。", detail=exc)

    st.caption("以上操作仅记录人工成交结果，系统不自动下单；操作后 C3 止损/移动止盈/+5%/+10% "
               "减仓档位按知识库规则自动重算并留痕（K223 可追溯）。")


try:
    view = api.holding_quotes()
    rows = view.get("rows") or []

    # 行情更新时间（刷新/监控按钮已上移 page_header）
    st.caption(f"行情最后更新时间：{view.get('quote_time') or '—'}"
               "（实时行情约 60 秒缓存，可点击右侧「手动刷新行情」）")

    tab_hold, tab_alert, tab_hist = st.tabs(["当前持仓", "告警记录", "历史持仓"])

    with tab_hold:
        if view.get("quote_error"):
            render.msg_card("warn", "行情源临时降级",
                            f"{view['quote_error']}；行情字段暂以「—」展示，请稍后手动刷新重试。"
                            "持仓记录本身不受影响。")
        if not rows:
            render.empty_state("暂无持仓。在页面底部录入已人工建仓的标的。",
                               icon="📭")
        else:
            groups = _dedupe_and_merge(rows)
            total_capital = view.get("total_capital") or 0.0
            total_market_value = sum(
                (grp["current"].get("current_price") or 0.0) * grp["total_shares"]
                for grp in groups)
            st.caption("同一代码多笔建仓自动合并展示（加权平均成本 + 总股数），数据库原始记录完整保留；"
                       "参考止损/止盈取值顺序：手动设置 → 关联建仓计划 → 默认风控比例"
                       "（仅展示参考，不触发任何判断）；目标仓位% = 当前市值 ÷ 基准本金。"
                       "识别或行情缺失的字段显示「—」。")

            def _group_detail(g: dict, _i: int) -> None:
                c = g["current"]
                label = render.stock_label(c["stock_code"], c["stock_name"])
                price = c.get("current_price")
                w = g["weighted_price"]
                pnl_amt = pnl_pct = None
                if price is not None and w:
                    pnl_amt = (float(price) - w) * g["total_shares"]
                    pnl_pct = (float(price) - w) / w * 100
                sub_parts = [f"建仓 {c['entry_date']}"]
                if len(g["keep"]) > 1:
                    sub_parts.append(f"{len(g['keep'])} 笔合并")
                sub_parts.append(f"共 {g['total_shares']:,} 股")
                if w:
                    sub_parts.append(f"加权成本 {w:,.2f}")
                pnl_html = "—"
                if pnl_amt is not None:
                    cls = _pnl_cls(pnl_amt)
                    pnl_html = (f'<span class="{cls}">{_fmt_signed(pnl_amt)}'
                                f'（{pnl_pct:+.2f}%）</span>')
                meta = (f"现价 {price if price is not None else '—'}　盈亏 {pnl_html}<br>"
                        f"止损 {c.get('stop_loss') or '—'} / 止盈 {c.get('take_profit') or '—'}"
                        f" / 目标仓位 {c.get('target_pct') or '—'}%")
                key = f"hold_{c['id']}"
                show_op, opened = render.list_item_toggle_actions(
                    key, label, subtitle="　·　".join(sub_parts), dot="info", meta=meta,
                    actions=("持仓操作", "查看详情"), scope="hold")
                if show_op:
                    with st.container(border=True):
                        render.section_title(f"持仓操作 {label}")
                        # 批次2：高频操作前置（从 _operation_card 内提前到面板首行）
                        hid = c["id"]
                        _op_act = render.quick_actions(f"hold_op_{key}", [
                            {"label": "⚡ 立即执行监控", "type": "primary"},
                            {"label": "🧠 生成卖出决策", "type": "secondary"},
                        ])
                        if _op_act == 0:
                            with st.spinner("LLM 研判中..."):
                                _mr = api.monitor_holding(hid)
                                st.session_state[f"mon_result_{hid}"] = _mr.get("signal") or {}
                                st.session_state[f"mon_time_{hid}"] = _now_min()
                        if _op_act == 1:
                            api.submit_task("sell_decision", {"holding_id": hid})
                            st.toast("卖出决策任务已提交后台，完成后顶部任务状态区会提示")
                        _mon_result = st.session_state.get(f"mon_result_{hid}")
                        if _mon_result:
                            render_monitor_signal(_mon_result)
                            _signal_time("信号生成时间", st.session_state.get(f"mon_time_{hid}"),
                                         _mon_result)
                            render.raw_json_expander(_mon_result, key=f"raw_mon_{hid}")
                        _operation_panel(g, total_capital, total_market_value, pfx="row")
                if opened:
                    with st.container(border=True):
                        # 批次2：详情三块垂直堆叠 → detail_tabs（3 分区 ≤6 → st.tabs，切换零请求）
                        def _tab_tp_plan():
                            render.section_title("止盈与仓位计划（与系统概览同源，自动留痕）")
                            try:
                                tp_plans = {p["holding_id"]: p
                                            for p in api.take_profit_plan().get("rows") or []}
                            except Exception:  # noqa: BLE001 计划接口失败降级提示
                                tp_plans = {}
                            _tp_shown = False
                            for r in g["records"]:
                                tp = tp_plans.get(r["id"])
                                if tp:
                                    _tp_shown = True
                                    render.position_plan_card(
                                        f"tp_{r['id']}",
                                        render.stock_label(c["stock_code"], c["stock_name"]),
                                        tp)
                            if not _tp_shown:
                                st.caption("止盈计划暂不可用（计算服务未就绪），"
                                           "可稍后重试或手动刷新行情。")

                        def _tab_ops():
                            _operation_card(g, total_capital, total_market_value)

                        def _tab_history():
                            render.section_title("历史明细（数据库原始记录）")
                            detail = pd.DataFrame([_detail_row(r) for r in g["records"]])
                            st.dataframe(detail, width="stretch", hide_index=True)
                            st.caption("明细为数据库原始记录（包含被自动忽略的重复录入），仅查看不删除；"
                                       "合并行的行情计算基于加权平均成本与总股数。")

                        render.detail_tabs([
                            ("止盈与仓位计划", _tab_tp_plan),
                            ("操作与流水", _tab_ops),
                            ("历史明细", _tab_history),
                        ], key=f"hold_tabs_{key}", default_index=0)

            hold_keys = [f"hold_{g['current']['id']}" for g in groups]
            render.batch_fold_bar("hold", hold_keys,
                                  label="点击行内「持仓操作/查看详情」展开对应面板。")
            render.record_list(groups, _group_detail, batch=20, key="_hold_list_vis",
                               empty_text="无当前持仓。")

    with tab_alert:
        # ===== 组合哨兵（组合级风控，与 MonitorAgent 零耦合；交易时段每 10 分钟自动巡检）=====
        with st.container(border=True):
            render.section_title("组合哨兵 · 组合级风控")
            c1, c2 = st.columns([3, 1])
            with c1:
                st.caption("板块退潮 / 时间止损 / 组合回撤 / 集中度 四项组合级信号（LIGHT 模型巡检，"
                           "告警标记 source='portfolio_sentinel'）；手动触发一次即时巡检。")
            with c2:
                if st.button("运行组合哨兵", key="run_portfolio_sentinel", use_container_width=True):
                    try:
                        tid = api.submit_task("portfolio_sentinel", {})
                        st.success(f"组合哨兵任务已提交：{tid.get('task_id')}，"
                                   f"可到「Agent 对话」页或任务状态区查看结果")
                        st.session_state.pop("_hold_alerts_ts", None)
                    except Exception as exc:  # noqa: BLE001 提交失败提示即可
                        render.error_card("组合哨兵任务提交失败", str(exc))
        # 按需加载：首次点击才拉取告警（进页面零请求）；加载后 30s 会话缓存 + 手动刷新
        alert_rows = _throttle_load("_hold_alerts", api.alerts)
        if alert_rows is None and "_hold_alerts_ts" not in st.session_state:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.caption("告警记录为按需加载（页面提速）：点击右侧按钮拉取最近告警。")
            with c2:
                if st.button("加载告警记录", key="load_hold_alerts", use_container_width=True):
                    _throttle_load("_hold_alerts", api.alerts, ttl=0)
                    st.rerun()
        else:
            alert_rows = alert_rows or []
            # 组合哨兵告警（source 标记过滤展示）
            sentinel_rows = [r for r in alert_rows if r.get("source") == "portfolio_sentinel"]
            if sentinel_rows:
                st.markdown("**组合哨兵告警**（组合级风控，板块/组合/时间维度）")
                render.alert_list(sentinel_rows, key="sentinel_alert_list",
                                  empty_text="暂无组合哨兵告警。", scope="sentinel_alert")
                st.caption("组合哨兵在交易时段每 10 分钟自动巡检，也可点击上方「运行组合哨兵」手动触发。")
            if alert_rows:
                alert_keys = [f"hold_alert_list_{r['id']}" for r in alert_rows]
                render.batch_fold_bar("hold_alert", alert_keys,
                                      label="点击行内「查看详情」展开完整告警内容。")
            render.alert_list(alert_rows, key="hold_alert_list",
                              empty_text="暂无告警记录。持仓监控在交易时段每 3 分钟自动运行。",
                              scope="hold_alert")
            if st.button("刷新告警", key="refresh_hold_alerts"):
                st.session_state.pop("_hold_alerts_ts", None)
                st.rerun()

    with tab_hist:
        # 按需加载：首次点击才拉取历史持仓（进页面零请求）；加载后 30s 会话缓存 + 手动刷新
        exited = _throttle_load("_hold_exited", lambda: api.holdings(status="exited"))
        if exited is None and "_hold_exited_ts" not in st.session_state:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.caption("历史持仓为按需加载（页面提速）：点击右侧按钮拉取已离场记录。")
            with c2:
                if st.button("加载历史持仓", key="load_hold_exited", use_container_width=True):
                    _throttle_load("_hold_exited", lambda: api.holdings(status="exited"), ttl=0)
                    st.rerun()
        else:
            exited = exited or []
        if not exited:
            render.empty_state("暂无已离场持仓。在「当前持仓」详情中录入人工卖出后自动归档到此。",
                               icon="📭")
        else:
            def _exit_detail(r: dict, _i: int) -> None:
                label = render.stock_label(r["stock_code"], r["stock_name"])
                sub = (f"建仓 {r['entry_date']} · {r.get('shares', '')} 股 · "
                       f"成本 {r.get('entry_price', '—')}"
                       + (f" · 备注：{r.get('note')}" if r.get("note") else ""))
                meta = f"离场时间 {str(r.get('created_at') or '')[:16]}"
                key = f"exit_{r['id']}"
                if render.list_item_toggle(key, label, subtitle=sub, dot="mute", meta=meta,
                                           scope="exit"):
                    with st.container(border=True):
                        render.trace_line("记录时间", r.get("created_at"))
                        with st.container(border=True):
                            render.section_title("离场记录")
                            st.markdown(f"- 建仓日期：{r['entry_date']}")
                            st.markdown(f"- 成本价：{r.get('entry_price')}　股数：{r.get('shares')}")
                            st.markdown(f"- 备注：{r.get('note') or '（无）'}")
                        with st.container(border=True):
                            render.section_title("操作记录（流水可追溯）")
                            _trades_block(r["id"])
                        st.caption("复盘结论见「交易复盘」页（录入卖出后自动生成）。")

            exit_keys = [f"exit_{r['id']}" for r in exited]
            render.batch_fold_bar("exit", exit_keys,
                                  label="点击行内「查看详情」展开离场记录与操作流水。")
            render.record_list(exited, _exit_detail, batch=20, key="_exit_list_vis",
                               empty_text="暂无历史持仓。")
except Exception as exc:
    render.dismissible_error("持仓数据加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                             detail=exc, retry_key="retry_holdings", dismiss_key="hold_main")

# ============ 快速录入（OCR 截图识别 / 手动录入 二选一）============
st.subheader("快速录入持仓（截图识别 / 手动录入）")
ocr_tab, manual_tab = st.tabs(["📷 截图识别", "✍️ 手动录入"])




def _ocr_row_to_dict(r: dict) -> dict:
    """识别行 → 可编辑表格行（缺核心字段的行标注「需补全」，红色高亮引导人工完善；
    清仓记录（股数 0 且代码/名称齐全）为正常记录，不标错误）"""
    missing = not (str(r.get("stock_code") or "").strip()
                   and str(r.get("stock_name") or "").strip()
                   and render.field_ok(r.get("shares"))
                   and render.field_ok(r.get("cost_price")))
    return {
        "股票代码": r.get("stock_code") or "",
        "股票名称": r.get("stock_name") or "",
        "持仓数量": r.get("shares"),
        "持仓成本价": r.get("cost_price"),
        "当前市价": r.get("current_price"),
        "持仓盈亏金额": r.get("pnl_amount"),
        "持仓盈亏比例": r.get("pnl_pct"),
        "状态": "需补全" if missing else "",
    }


def _mark_missing(row: pd.Series) -> list:
    """字段缺失行红色标注（配合「需补全」状态列，引导人工完善）"""
    if row["状态"]:
        return ["background-color: rgba(239, 68, 68, 0.12)"] * len(row)
    return [""] * len(row)


with ocr_tab:
    st.caption("上传券商持仓截图 → 多模态识别自动整理为结构化表格（代码/名称/股数/成本/市价/盈亏）"
               "→ 表格内直接核对修正 → 确认创建持仓。识别结果不会自动落库，请务必人工确认；"
               "市场研判仍由 LLM 完成，OCR 仅是快捷录入工具。")
    try:
        ocr_info = api.ocr_status()
    except Exception as exc:
        ocr_info = {"enabled": False, "available": False, "reason": f"状态查询失败: {exc}"}

    if not ocr_info.get("enabled"):
        render.msg_card("info", "OCR 识别未启用",
                        f"{ocr_info.get('reason')}；可继续使用下方手动录入。")
    elif not ocr_info.get("available"):
        render.msg_card("warn", "OCR 暂不可用",
                        f"{ocr_info.get('reason')}；可继续使用下方手动录入。")
    else:
        uploaded = st.file_uploader("上传券商持仓截图（png/jpg/jpeg/bmp/webp，尽量清晰、避开弹窗遮挡）",
                                    type=["png", "jpg", "jpeg", "bmp", "webp"], key="ocr_upload")
        if uploaded is not None:
            # 检测到新上传 → 清除旧识别结果，触发重新识别
            if st.session_state.get("ocr_file_id") != uploaded.file_id:
                st.session_state["ocr_file_id"] = uploaded.file_id
                st.session_state.pop("ocr_result", None)

            if "ocr_result" not in st.session_state:
                with st.spinner("OCR 识别中（MiniMax 云端识别，稍候）..."):
                    try:
                        st.session_state["ocr_result"] = api.ocr_holding(uploaded.getvalue(), uploaded.name)
                    except Exception as exc:
                        render.error_card("OCR 识别失败", "可重新上传截图重试，或使用下方手动录入。",
                                          detail=exc, retry_key="retry_ocr")
                        st.session_state["ocr_result"] = None

            result = st.session_state.get("ocr_result")
            if result is not None:
                rows = result.get("recognized") or []
                if not rows:
                    render.msg_card("warn", "未识别到有效的持仓字段",
                                    "可能截图不清晰或被遮挡，请下方手动补全。")
                    with st.expander("查看原始识别内容（排查用）"):
                        st.code(result.get("raw_text", ""), language=None)
                else:
                    st.markdown("**识别结果（已自动整理为结构化表格；点击单元格可直接修改修正识别偏差）**")
                    df = pd.DataFrame([_ocr_row_to_dict(r) for r in rows])
                    edited = st.data_editor(
                        df.style.apply(_mark_missing, axis=1),
                        column_config={
                            "股票代码": st.column_config.TextColumn("股票代码", width="small"),
                            "股票名称": st.column_config.TextColumn("股票名称", width="medium"),
                            "持仓数量": st.column_config.NumberColumn("持仓数量（股）", format="%d"),
                            "持仓成本价": st.column_config.NumberColumn("持仓成本价", format="%.2f"),
                            "当前市价": st.column_config.NumberColumn("当前市价", format="%.2f"),
                            "持仓盈亏金额": st.column_config.NumberColumn("持仓盈亏金额", format="%.2f"),
                            "持仓盈亏比例": st.column_config.NumberColumn("持仓盈亏比例（%）", format="%.2f"),
                            "状态": st.column_config.TextColumn("状态", width="small"),
                        },
                        hide_index=True, num_rows="fixed", width="stretch", key="ocr_editor")
                    st.caption("红色标注的行存在缺失字段（状态列显示「需补全」），请点击补全后再确认创建；"
                               "识别结果仅供参考，创建前请务必核对。")
                    with st.expander("查看原始识别内容（排查用）"):
                        st.code(result.get("raw_text", ""), language=None)

                    st.markdown("**录入参数（批次统一，可修改）**")
                    c1, c2 = st.columns(2)
                    with c1:
                        entry_date = st.text_input("建仓日期（YYYY-MM-DD）", key="ocr_batch_date")
                        stop_loss = st.number_input("止损参考价（可选）", min_value=0.0, step=0.01,
                                                    key="ocr_batch_sl")
                        take_profit = st.number_input("止盈参考价（可选）", min_value=0.0, step=0.01,
                                                      key="ocr_batch_tp")
                    with c2:
                        target_pct = st.number_input("目标仓位 %（可选）", min_value=0.0, max_value=100.0,
                                                     step=1.0, key="ocr_batch_tpct")
                        note = st.text_input("备注（可选）", key="ocr_batch_note")

                    confirmed = st.button("确认创建持仓（人工核对无误后批量入库，识别结果不会自动落库）")
                    if confirmed:
                        errors, valid = [], []
                        for i, r in edited.iterrows():
                            code = str(r["股票代码"] or "").strip()
                            name = str(r["股票名称"] or "").strip()
                            # 字段有效性统一判定：0（清仓）为合法值，不标为缺失
                            if not (code and name and render.field_ok(r["持仓数量"])
                                    and render.field_ok(r["持仓成本价"])):
                                errors.append(f"第 {i + 1} 行（{code or '未知代码'} {name or '未知名称'}）："
                                              f"代码/名称/股数/成本价 需补全")
                                continue
                            valid.append({
                                "stock_code": code, "stock_name": name,
                                "entry_date": entry_date or "2026-01-01",
                                "entry_price": float(r["持仓成本价"]), "shares": int(r["持仓数量"]),
                                "stop_loss": float(stop_loss), "take_profit": float(take_profit),
                                "target_pct": float(target_pct), "note": note or "OCR 截图识别批量录入"})
                        if errors:
                            render.msg_card("err", "以下条目需补全后重试（未写入任何持仓）",
                                            "；".join(errors))
                        else:
                            for v in valid:
                                api.add_holding(v)
                            st.success(f"已保存 {len(valid)} 条持仓（截图已自动清理，未长期存储）")
                            st.session_state.pop("ocr_result", None)
                            st.session_state.pop("ocr_file_id", None)
                            st.rerun()

                # ===== 账户汇总（OCR 提取截图顶部汇总栏，人工核对确认后才保存为账户基准） =====
                account = result.get("account")
                if account:
                    st.markdown("**截图识别：账户汇总**（识别结果仅供参考，请核对修正后保存；"
                                "保存后顶部状态栏的总资产/可用资金/整体仓位切换为券商真实值）")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        with st.container(key="fld_ocr_total"):
                            total_asset = st.number_input("总资产（元）*", min_value=0.0, step=1000.0,
                                                          value=float(account.get("total_asset") or 0.0),
                                                          key="ocr_acc_total")
                        render.field_error("ocr_total", render.get_field_error("ocr_total"),
                                           "请输入正确的资产数值")
                    with c2:
                        available_cash = st.number_input("可用资金（元）", min_value=0.0, step=1000.0,
                                                         value=float(account.get("available_cash") or 0.0),
                                                         key="ocr_acc_cash")
                    with c3:
                        position_pct = st.number_input("整体仓位比例（%）", min_value=0.0, max_value=100.0,
                                                       step=1.0,
                                                       value=float(account.get("position_pct") or 0.0),
                                                       key="ocr_acc_pct")
                    if st.button("保存账户基准（人工确认无误后落库）", key="ocr_save_baseline"):
                        if total_asset <= 0:
                            render.set_field_errors({"ocr_total": "总资产必须大于 0，请核对修正后再保存"})
                            st.rerun()
                        else:
                            render.set_field_errors({})
                            api.save_account_baseline({
                                "total_asset": total_asset, "available_cash": available_cash,
                                "position_pct": position_pct, "source": "ocr"})
                            st.success("账户基准已保存，顶部状态栏将自动切换为券商真实值（可点击「账户明细」查看）。")

with manual_tab:
    st.caption("系统不自动下单，交易必须人工执行")
    with st.form("add_holding"):
        c1, c2 = st.columns(2)
        with c1:
            with st.container(key="fld_hold_code"):
                code = st.text_input("股票代码 *")
            render.field_error("hold_code", render.get_field_error("hold_code"),
                               "请输入 6 位数字股票代码，如 603993")
            with st.container(key="fld_hold_name"):
                name = st.text_input("股票名称 *")
            render.field_error("hold_name", render.get_field_error("hold_name"),
                               "请输入股票名称")
            entry_date = st.text_input("建仓日期（YYYY-MM-DD）")
            with st.container(key="fld_hold_price"):
                entry_price = st.number_input("平均成本价 *", min_value=0.0, step=0.01)
            render.field_error("hold_price", render.get_field_error("hold_price"),
                               "平均成本价必须大于 0")
        with c2:
            with st.container(key="fld_hold_shares"):
                shares = st.number_input("股数 *", min_value=100, step=100)
            render.field_error("hold_shares", render.get_field_error("hold_shares"),
                               "股数必须大于 0")
            stop_loss = st.number_input("止损参考价", min_value=0.0, step=0.01)
            take_profit = st.number_input("止盈参考价", min_value=0.0, step=0.01)
            target_pct = st.number_input("目标仓位 %", min_value=0.0, max_value=100.0, step=1.0)
        note = st.text_input("备注（可引用建仓计划）")
        render.field_summary(label_map={"hold_code": "股票代码", "hold_name": "股票名称",
                                        "hold_price": "平均成本价", "hold_shares": "股数"})
        submitted = st.form_submit_button("保存持仓")
        if submitted:
            errs = {}
            if not code.strip():
                errs["hold_code"] = "股票代码不能为空"
            if not name.strip():
                errs["hold_name"] = "股票名称不能为空"
            if entry_price <= 0:
                errs["hold_price"] = "平均成本价必须大于 0"
            if shares <= 0:
                errs["hold_shares"] = "股数必须大于 0"
            if errs:
                render.set_field_errors(errs)
            else:
                render.set_field_errors({})
                result = api.add_holding({
                    "stock_code": code.strip(), "stock_name": name.strip(),
                    "entry_date": entry_date or "2026-01-01",
                    "entry_price": float(entry_price), "shares": int(shares),
                    "stop_loss": float(stop_loss), "take_profit": float(take_profit),
                    "target_pct": float(target_pct), "note": note})
                st.success(f"持仓已保存 ID={result['id']}")
