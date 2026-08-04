"""持仓监控：当前持仓 + 最新 LLM 监控信号 + 人工录入买卖（系统不下单）"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="持仓监控", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("持仓监控（MonitorAgent）")

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


def _signal_time(label: str, time_str: str | None, signal: dict) -> None:
    """信号生成时间标注：紧急信号（减仓/清仓建议或高严重度）时间琥珀色高亮"""
    urgent = bool(signal) and (signal.get("action") != "hold"
                               or signal.get("severity") in ("warning", "critical"))
    render.time_text(label, time_str, highlight=urgent)


def render_sell_decision(d: dict) -> None:
    """卖出决策 → 自然语言分段"""
    action = ACTION_MAP.get(d.get("action"), d.get("action"))
    conf = CONF_MAP.get(d.get("confidence"), d.get("confidence"))
    st.markdown(f"**卖出决策：{action}**（置信度 {conf}）")
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


def _pnl_color(value):
    """盈亏颜色：正收益红、负收益绿（A 股习惯，适配深色主题的浅色文字）"""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if value > 0:
        return "color: #F87171; font-weight: 600;"
    if value < 0:
        return "color: #4ADE80; font-weight: 600;"
    return ""


def _fmt_signed(value) -> str:
    """带符号金额（如 +3,030.00 / -1,234.50）"""
    if value is None or (isinstance(value, float) and value != value):
        return "—"
    return f"{value:+,.2f}"


def _group_row(g: dict, total_capital: float) -> dict:
    """合并行：行情字段按合并总股数与加权成本重算（后端字段为单条口径）"""
    c = g["current"]
    price = c.get("current_price")
    mv = pnl_amt = pnl_pct = None
    w = g["weighted_price"]
    if price is not None:
        mv = price * g["total_shares"]
        if w:
            pnl_amt = (price - w) * g["total_shares"]
            pnl_pct = (price - w) / w * 100
    target = mv / total_capital * 100 if (mv is not None and total_capital > 0) else None
    multi = len(g["keep"]) > 1
    return {
        "股票": render.stock_label(c["stock_code"], c["stock_name"]),
        "建仓日": f"{c['entry_date']}（{len(g['keep'])}笔）" if multi else c["entry_date"],
        "总股数": g["total_shares"],
        "加权成本": round(w, 2) if w else None,
        "当前市价": price,
        "当前市值": round(mv, 2) if mv is not None else None,
        "盈亏金额": round(pnl_amt, 2) if pnl_amt is not None else None,
        "盈亏比例": round(pnl_pct, 2) if pnl_pct is not None else None,
        "参考止损": c.get("stop_loss"),
        "参考止盈": c.get("take_profit"),
        "目标仓位%": round(target, 1) if target is not None else None,
    }


def _detail_row(r: dict) -> dict:
    """历史明细行：每笔原始记录（含被去重的重复录入），标注状态"""
    return {"ID": r["id"], "股票": render.stock_label(r["stock_code"], r["stock_name"]),
            "建仓日": r["entry_date"], "成本价": r["entry_price"], "股数": r["shares"],
            "状态": r.get("_dedupe_status", "")}


def _style_view_df(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    return (df.style.map(_pnl_color, subset=["盈亏金额", "盈亏比例"]).format({
        "总股数": "{:,.0f}", "加权成本": "{:,.2f}", "当前市价": "{:,.2f}", "当前市值": "{:,.2f}",
        "盈亏金额": _fmt_signed, "盈亏比例": "{:+.2f}%", "参考止损": "{:,.2f}",
        "参考止盈": "{:,.2f}", "目标仓位%": "{:,.1f}",
    }, na_rep="—"))


try:
    view = api.holding_quotes()
    rows = view.get("rows") or []
    if rows:
        groups = _dedupe_and_merge(rows)
        total_capital = view.get("total_capital") or 0.0
        c1, c2 = st.columns([4, 1])
        with c1:
            st.caption(f"行情最后更新时间：{view.get('quote_time') or '—'}"
                       "（实时行情约 60 秒缓存，可点击右侧手动刷新）")
        with c2:
            if st.button("手动刷新行情"):
                st.rerun()
        if st.button("立即刷新监控（全量持仓实时检测）", type="primary"):
            api.submit_task("monitor_all")
            st.toast("全量持仓监控已提交后台，完成后顶部任务状态区会提示；"
                     "新信号会自动落库并在告警日志页展示")
        if view.get("quote_error"):
            st.warning(f"{view['quote_error']}；行情字段暂以「—」展示，请稍后手动刷新重试。"
                       "持仓记录本身不受影响。")
        df = pd.DataFrame([_group_row(g, total_capital) for g in groups])
        st.dataframe(_style_view_df(df), width="stretch", hide_index=True)
        st.caption("同一代码多笔建仓自动合并展示（加权平均成本 + 总股数），数据库原始记录完整保留；"
                   "参考止损/止盈取值顺序：手动设置 → 关联建仓计划 → 默认风控比例（仅展示参考，不触发任何判断）；"
                   "目标仓位% = 当前市值 ÷ 基准本金。识别或行情缺失的字段显示「—」。")

        for g in groups:
            label = render.stock_label(g["current"]["stock_code"], g["current"]["stock_name"])
            with st.expander(f"查看历史持仓明细：{label}"):
                detail = pd.DataFrame([_detail_row(r) for r in g["records"]])
                st.dataframe(detail, width="stretch", hide_index=True)
                st.caption("明细为数据库原始记录（包含被自动忽略的重复录入），仅查看不删除；"
                           "合并行的行情计算基于加权平均成本与总股数。")

        for g in groups:
            r = g["current"]
            label = render.stock_label(r["stock_code"], r["stock_name"])
            with st.expander(f"操作 {label}"):
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("立即执行监控", key=f"mon_{r['id']}"):
                        with st.spinner("LLM 研判中..."):
                            result = api.monitor_holding(r["id"])
                            st.session_state[f"mon_result_{r['id']}"] = result.get("signal") or {}
                            st.session_state[f"mon_time_{r['id']}"] = _now_min()
                    mon_result = st.session_state.get(f"mon_result_{r['id']}")
                    if mon_result:
                        render_monitor_signal(mon_result)
                        _signal_time("信号生成时间", st.session_state.get(f"mon_time_{r['id']}"),
                                     mon_result)
                        render.raw_json_expander(mon_result, key=f"raw_mon_{r['id']}")
                    if st.button("生成卖出决策", key=f"sell_{r['id']}"):
                        api.submit_task("sell_decision", {"holding_id": r["id"]})
                        st.toast("卖出决策任务已提交后台，完成后顶部任务状态区会提示")
                    sell_result = st.session_state.get(f"sell_result_{r['id']}")
                    if sell_result:
                        st.markdown("决策仅供参考，卖出必须由你人工执行。")
                        render_sell_decision(sell_result)
                        _signal_time("信号生成时间", st.session_state.get(f"sell_time_{r['id']}"),
                                     sell_result)
                        render.raw_json_expander(sell_result, key=f"raw_sell_{r['id']}")
                    sell_hist = api.sell_decisions(r["id"])
                    if sell_hist:
                        with st.expander(f"卖出决策历史（{len(sell_hist)} 条，仅供参考）"):
                            for h in sell_hist:
                                d = h.get("decision") or {}
                                action = ACTION_MAP.get(d.get("action"), d.get("action"))
                                conf = CONF_MAP.get(d.get("confidence"), d.get("confidence"))
                                st.markdown(f"- **{action}**（置信度 {conf}）："
                                            f"{d.get('exit_price_zone') or d.get('risk_warning') or ''}")
                                render.time_text("信号生成时间", h["created_at"],
                                                 highlight=d.get("action") != "hold"
                                                 or d.get("severity") in ("warning", "critical"))
                                render.raw_json_expander(d, label="原始数据",
                                                         key=f"raw_sellhist_{h['id']}")
                with c2:
                    st.caption("交易时段监控每 3 分钟自动运行（实时行情 60 秒内缓存），"
                               "触发信号自动推送飞书并记录告警日志；收盘后 15:00-15:30 做收盘数据校验。"
                               "卖出决策由 SellAgent 独立研判，人工按需触发。")
                st.markdown("**录入人工卖出（执行后自动触发复盘）**")
                with st.form(f"exit_{r['id']}"):
                    price = st.number_input("卖出价格", min_value=0.0, step=0.01, key=f"p_{r['id']}")
                    shares = st.number_input("卖出股数", min_value=1, max_value=r["shares"],
                                             step=100, key=f"s_{r['id']}")
                    date = st.text_input("成交日期（YYYY-MM-DD）", key=f"d_{r['id']}")
                    note = st.text_input("备注", key=f"n_{r['id']}")
                    submitted = st.form_submit_button("确认卖出（人工已成交后录入）")
                    if submitted:
                        result = api.exit_holding(r["id"], {
                            "price": float(price), "shares": int(shares),
                            "trade_date": date or r["entry_date"], "note": note})
                        msg = (f"已记录卖出，剩余 {result['remain_shares']} 股"
                               + (f"，复盘任务已提交后台（{result['review_task_id']}）"
                                  if result.get("review_task_id") else "。"))
                        st.success(msg)
    else:
        st.info("暂无持仓。在下方录入已人工建仓的标的。")
except Exception as exc:
    st.error(f"持仓获取失败: {exc}")

# ============ 截图识别快速录入（OCR 仅文字识别回填，必须人工核对后入库）============
st.subheader("截图识别快速录入")
st.caption("上传券商持仓截图 → 多模态识别自动整理为结构化表格（代码/名称/股数/成本/市价/盈亏）"
           "→ 表格内直接核对修正 → 确认创建持仓。识别结果不会自动落库，请务必人工确认；"
           "市场研判仍由 LLM 完成，OCR 仅是快捷录入工具。")


def _ocr_row_to_dict(r: dict) -> dict:
    """识别行 → 可编辑表格行（缺核心字段的行标注「需补全」，红色高亮引导人工完善）"""
    missing = not (r.get("stock_code") and r.get("stock_name")
                   and r.get("shares") and r.get("cost_price"))
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
        return ["background-color: #ffe0e0"] * len(row)
    return [""] * len(row)


def _field_ok(value) -> bool:
    """字段有效性判断（None/NaN/空/非正数均为需补全）"""
    if value is None:
        return False
    try:
        if isinstance(value, float) and value != value:  # NaN
            return False
        return float(value) > 0
    except (TypeError, ValueError):
        return str(value).strip() != ""
try:
    ocr_info = api.ocr_status()
except Exception as exc:
    ocr_info = {"enabled": False, "available": False, "reason": f"状态查询失败: {exc}"}

if not ocr_info.get("enabled"):
    st.info(f"OCR 识别未启用（{ocr_info.get('reason')}），可继续使用下方手动录入。")
elif not ocr_info.get("available"):
    st.warning(f"OCR 暂不可用（{ocr_info.get('reason')}），可继续使用下方手动录入。")
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
                    st.error(f"识别失败：{exc}，请手动录入或重试。")
                    st.session_state["ocr_result"] = None

        result = st.session_state.get("ocr_result")
        if result is not None:
            rows = result.get("recognized") or []
            if not rows:
                st.warning("未识别到有效的持仓字段（可能截图不清晰或被遮挡），请下方手动补全。")
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
                        if not (code and name and _field_ok(r["持仓数量"]) and _field_ok(r["持仓成本价"])):
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
                        st.error("以下条目需补全后重试（未写入任何持仓）：\n" + "\n".join(errors))
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
                    total_asset = st.number_input("总资产（元）*", min_value=0.0, step=1000.0,
                                                  value=float(account.get("total_asset") or 0.0),
                                                  key="ocr_acc_total")
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
                        st.error("总资产必须大于 0，请核对修正后再保存。")
                    else:
                        api.save_account_baseline({
                            "total_asset": total_asset, "available_cash": available_cash,
                            "position_pct": position_pct, "source": "ocr"})
                        st.success("账户基准已保存，顶部状态栏将自动切换为券商真实值（可点击「账户明细」查看）。")

st.divider()
st.subheader("录入人工建仓（系统不自动下单，交易必须人工执行）")
with st.form("add_holding"):
    c1, c2 = st.columns(2)
    with c1:
        code = st.text_input("股票代码 *")
        name = st.text_input("股票名称 *")
        entry_date = st.text_input("建仓日期（YYYY-MM-DD）")
        entry_price = st.number_input("平均成本价 *", min_value=0.0, step=0.01)
    with c2:
        shares = st.number_input("股数 *", min_value=100, step=100)
        stop_loss = st.number_input("止损参考价", min_value=0.0, step=0.01)
        take_profit = st.number_input("止盈参考价", min_value=0.0, step=0.01)
        target_pct = st.number_input("目标仓位 %", min_value=0.0, max_value=100.0, step=1.0)
    note = st.text_input("备注（可引用建仓计划）")
    submitted = st.form_submit_button("保存持仓")
    if submitted:
        if not code or not name or entry_price <= 0 or shares <= 0:
            st.error("请填写必填项（代码/名称/成本价/股数）")
        else:
            result = api.add_holding({
                "stock_code": code.strip(), "stock_name": name.strip(),
                "entry_date": entry_date or "2026-01-01",
                "entry_price": float(entry_price), "shares": int(shares),
                "stop_loss": float(stop_loss), "take_profit": float(take_profit),
                "target_pct": float(target_pct), "note": note})
            st.success(f"持仓已保存 ID={result['id']}")
