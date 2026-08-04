"""评分报告：ScoreAgent 五维评分（A/B/C 分级 + 风险清单，自然语言分段展示）"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="评分报告", layout="wide")
st.title("评分报告（ScoreAgent）")

code = st.text_input("按股票代码筛选（留空显示全部）", "")

try:
    rows = api.scores(code=code or None)
    if not rows:
        st.info("暂无评分数据。可在「每日候选池」或首页挖掘后生成，也可输入代码手动触发。")
    else:
        overview = pd.DataFrame([
            {"股票": render.stock_label(r["stock_code"], r["stock_name"]),
             "日期": r["trade_date"], "综合分": r["score"], "评级": r["grade"]} for r in rows
        ])
        st.dataframe(overview, width="stretch", hide_index=True)

        for r in rows[:10]:
            label = render.stock_label(r["stock_code"], r["stock_name"])
            with st.expander(f"{label}　{r['trade_date']} — {r['score']}分 {r['grade']}级"):
                render.time_text("评分生成时间", r.get("created_at"))
                dims = r["detail"]
                if dims:
                    st.markdown("**五维评分明细**")
                    dim_df = pd.DataFrame([
                        {"维度": name, "得分": v.get("score", ""), "依据": v.get("comment", "")}
                        for name, v in dims.items()
                    ])
                    st.dataframe(dim_df, width="stretch", hide_index=True)
                st.markdown("**风险清单**")
                risks = r["risk_list"] or []
                if risks:
                    for risk in risks:
                        st.markdown(f"- {risk}")
                else:
                    st.markdown("（无）")
                render.raw_json_expander(
                    {"detail": r["detail"], "risk_list": r["risk_list"]},
                    key=f"raw_score_{r['id']}")
                st.button("生成建仓方案", key=f"scoreplan_{r['id']}",
                          on_click=lambda c=r["stock_code"], n=r["stock_name"]: api.create_plan(c, n))

    manual = st.text_input("手动打分股票代码", "")
    if st.button("触发打分", disabled=not manual):
        with st.spinner("打分中..."):
            result = api.trigger_score(manual)
            res = result["score_result"] or {}
            label = render.stock_label(res.get("stock_code", manual), res.get("stock_name", ""))
            st.markdown(f"**{label} — {res.get('score', '?')}分 {res.get('grade', '?')}级**")
            if res.get("summary"):
                st.markdown(res["summary"])
            if res.get("dimensions"):
                st.markdown("**五维评分明细**")
                dim_df = pd.DataFrame([
                    {"维度": d.get("name", ""), "得分": d.get("score", ""),
                     "依据": d.get("comment", "")} for d in res["dimensions"]
                ])
                st.dataframe(dim_df, width="stretch", hide_index=True)
            st.markdown("**风险清单**")
            for risk in (res.get("risk_list") or []):
                st.markdown(f"- {risk}")
            render.raw_json_expander(res, key="raw_manual_score")
except Exception as exc:
    st.error(f"评分获取失败: {exc}")
