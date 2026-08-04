"""持仓监控：当前持仓 + 最新 LLM 监控信号 + 人工录入买卖（系统不下单）"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="持仓监控", layout="wide")
st.title("持仓监控（MonitorAgent）")

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


try:
    rows = api.holdings(status="holding")
    if rows:
        df = pd.DataFrame([{
            "ID": r["id"], "股票": render.stock_label(r["stock_code"], r["stock_name"]),
            "建仓日": r["entry_date"], "成本价": r["entry_price"], "股数": r["shares"],
            "参考止损": r["stop_loss"], "参考止盈": r["take_profit"],
            "目标仓位%": r["target_pct"],
        } for r in rows])
        st.dataframe(df, width="stretch", hide_index=True)

        for r in rows:
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
                        with st.spinner("SellAgent 研判中..."):
                            st.session_state[f"sell_result_{r['id']}"] = api.sell_decision(r["id"]).get("decision") or {}
                            st.session_state[f"sell_time_{r['id']}"] = _now_min()
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
                    st.caption("盘中监控每 5 分钟自动运行，触发信号自动推送飞书并记录告警日志。"
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
                        st.success(f"已记录卖出，剩余 {result['remain_shares']} 股，"
                                   f"复盘触发: {result['review_triggered']}")
    else:
        st.info("暂无持仓。在下方录入已人工建仓的标的。")
except Exception as exc:
    st.error(f"持仓获取失败: {exc}")

# ============ 截图识别快速录入（OCR 仅文字识别回填，必须人工核对后入库）============
st.subheader("截图识别快速录入")
st.caption("上传券商持仓截图 → OCR 自动识别 代码/名称/股数/成本/市价 → 人工核对修正 → 确认创建持仓。"
           "识别结果不会直接入库，请务必核对；市场研判仍由 LLM 完成，OCR 仅是快捷录入工具。")
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
            with st.spinner("OCR 识别中（首次使用需下载识别模型，可能较慢）..."):
                try:
                    st.session_state["ocr_result"] = api.ocr_holding(uploaded.getvalue(), uploaded.name)
                except Exception as exc:
                    st.error(f"识别失败：{exc}，请手动录入或重试。")
                    st.session_state["ocr_result"] = None

        result = st.session_state.get("ocr_result")
        if result is not None:
            rows = result.get("recognized") or []
            if not rows:
                st.warning("未识别到有效的持仓字段（可能截图不清晰或被遮挡），请下方手动补全。识别原文：")
                st.code(result.get("raw_text", ""), language=None)
            else:
                labels = [f"{r.get('stock_code') or '未知代码'} {r.get('stock_name') or '未知名称'} | "
                          f"股数 {r.get('shares') or '?'} | 成本 {r.get('cost_price') or '?'} | "
                          f"市价 {r.get('current_price') or '?'}" for r in rows]
                sel = st.selectbox("识别结果列表（选择要录入的一只）", range(len(rows)),
                                   format_func=lambda i: labels[i])
                row = rows[sel]
                st.caption("以下字段已由 OCR 自动填充，请人工核对修正（识别可能有误，缺失字段需手动补全）。")
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                with st.expander("识别原文（排查用）"):
                    st.code(result.get("raw_text", ""), language=None)

                with st.form("ocr_add_holding"):
                    c1, c2 = st.columns(2)
                    with c1:
                        code = st.text_input("股票代码 *（OCR 识别，可修改）",
                                             value=row.get("stock_code") or "", key=f"ocr_code_{sel}")
                        name = st.text_input("股票名称 *（OCR 识别，可修改）",
                                             value=row.get("stock_name") or "", key=f"ocr_name_{sel}")
                        entry_date = st.text_input("建仓日期（YYYY-MM-DD）", key=f"ocr_date_{sel}")
                        entry_price = st.number_input("平均成本价 *（OCR 识别，可修改）",
                                                      value=float(row.get("cost_price") or 0.0),
                                                      min_value=0.0, step=0.01, key=f"ocr_price_{sel}")
                    with c2:
                        shares = st.number_input("股数 *（OCR 识别，可修改）",
                                                 value=float(row.get("shares") or 100.0),
                                                 min_value=100.0, step=100.0, key=f"ocr_shares_{sel}")
                        stop_loss = st.number_input("止损参考价", min_value=0.0, step=0.01, key=f"ocr_sl_{sel}")
                        take_profit = st.number_input("止盈参考价", min_value=0.0, step=0.01, key=f"ocr_tp_{sel}")
                        target_pct = st.number_input("目标仓位 %", min_value=0.0, max_value=100.0,
                                                     step=1.0, key=f"ocr_tpct_{sel}")
                    current_price = row.get("current_price")
                    note = st.text_input("备注", value=(
                        f"OCR 截图识别录入（识别市价 {current_price} 仅参考）" if current_price else ""),
                        key=f"ocr_note_{sel}")
                    submitted = st.form_submit_button("确认创建持仓（人工核对无误后）")
                    if submitted:
                        if not code or not name or entry_price <= 0 or shares <= 0:
                            st.error("请核对并补全必填项（代码/名称/成本价/股数）")
                        else:
                            result_api = api.add_holding({
                                "stock_code": code.strip(), "stock_name": name.strip(),
                                "entry_date": entry_date or "2026-01-01",
                                "entry_price": float(entry_price), "shares": int(shares),
                                "stop_loss": float(stop_loss), "take_profit": float(take_profit),
                                "target_pct": float(target_pct), "note": note})
                            st.success(f"持仓已保存 ID={result_api['id']}（截图已自动清理，未长期存储）")
                            st.session_state.pop("ocr_result", None)
                            st.session_state.pop("ocr_file_id", None)
                            st.rerun()

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
