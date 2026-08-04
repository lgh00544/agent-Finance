"""每日候选池：DiscoverAgent 输出（候选理由 + 风险初判，自然语言分段展示）"""
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="每日候选池", layout="wide")
st.title("每日候选池（DiscoverAgent）")

dates = st.selectbox("选择日期", ["最新"] + [])
st.caption("筛选标准由 LLM 综合量能/趋势/行业热度/基本面研判，每日 16:10 自动生成，也可手动触发。")

try:
    rows = api.candidates()
    if not rows:
        st.info("暂无候选数据。可回到首页点击「手动触发每日挖掘」，或等待每日定时任务。")
    else:
        for r in rows:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            with st.expander(f"#{r['rank']} {label}　{r['trade_date']}"):
                render.time_text("本轮挖掘执行时间", r.get("created_at"))
                st.markdown("**候选理由**")
                for i, reason in enumerate(r["reasons"] or [], 1):
                    st.markdown(f"{i}. {reason}")
                st.markdown("**风险初判**")
                risks = r["risk_notice"] or []
                if risks:
                    for risk in risks:
                        st.markdown(f"- {risk}")
                else:
                    st.markdown("（无）")
                render.raw_json_expander(
                    {"reasons": r["reasons"], "risk_notice": r["risk_notice"]},
                    key=f"raw_cand_{r['stock_code']}_{r['trade_date']}")
                st.button("生成建仓方案", key=f"plan_{r['stock_code']}",
                          on_click=lambda c=r["stock_code"], n=r["stock_name"]: api.create_plan(c, n))
except Exception as exc:
    st.error(f"候选池获取失败: {exc}")
