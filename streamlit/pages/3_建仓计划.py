"""建仓计划：PositionAgent 分批建仓方案（自然语言分段展示）"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="建仓计划", layout="wide")
st.title("建仓计划（PositionAgent）")

code = st.text_input("按股票代码筛选（留空显示全部）", "")

try:
    rows = api.plans(code=code or None)
    if not rows:
        st.info("暂无建仓方案。可在「每日候选池」「评分报告」页对标的生成，或输入代码手动生成。")
    else:
        for r in rows[:10]:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            status = {"proposed": "待评估", "accepted": "已采纳", "abandoned": "已放弃"}.get(
                r["status"], r["status"])
            with st.expander(f"{label}　{r['plan_date']} — 总仓位上限 {r['total_pct']}%（{status}）"):
                render.time_text("方案生成时间", r.get("created_at"))
                st.markdown(f"**市场强弱判断**：{r['rationale']}")
                st.markdown(f"**止损参考**：{r['stop_loss']}　|　**止盈参考**：{r['take_profit']}")
                if r["batches"]:
                    st.markdown("**分批建仓方案**")
                    batch_df = pd.DataFrame([
                        {"批次": b.get("tranche"), "价格区间": b.get("price_zone"),
                         "资金占比%": b.get("ratio_pct"), "触发条件": b.get("trigger_note")}
                        for b in r["batches"]
                    ])
                    st.dataframe(batch_df, width="stretch", hide_index=True)
                render.raw_json_expander(
                    {"status": r["status"], "batches": r["batches"]},
                    key=f"raw_plan_{r['id']}")

    manual = st.text_input("手动生成建仓方案代码", "")
    manual_name = st.text_input("股票名称（可选）", "")
    if st.button("生成建仓方案", disabled=not manual):
        with st.spinner("生成中..."):
            result = api.create_plan(manual, manual_name)
            label = render.stock_label(result.get("stock_code", manual), result.get("stock_name", ""))
            st.markdown(f"**{label} 建仓方案（{result.get('plan_date', '')}）**")
            if result.get("market_regime"):
                st.markdown(f"**市场强弱判断**：{result['market_regime']}")
            if result.get("batches"):
                st.markdown("**分批建仓方案**")
                batch_df = pd.DataFrame([
                    {"批次": b.get("tranche"), "价格区间": b.get("price_zone"),
                     "资金占比%": b.get("ratio_pct"), "触发条件": b.get("trigger_note")}
                    for b in result["batches"]
                ])
                st.dataframe(batch_df, width="stretch", hide_index=True)
            st.markdown(f"**止损参考**：{result.get('stop_loss', '—')}　|　"
                        f"**止盈参考**：{result.get('take_profit', '—')}")
            render.raw_json_expander(result, key="raw_manual_plan")
except Exception as exc:
    st.error(f"建仓计划获取失败: {exc}")
