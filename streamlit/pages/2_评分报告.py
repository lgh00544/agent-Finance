"""评分报告：ScoreAgent 五维评分（A/B/C 分级 + 风险清单，自然语言分段展示）"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="评分报告", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("评分报告（ScoreAgent）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

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
                code_r, name_r = r["stock_code"], r["stock_name"]
                if st.button("生成建仓方案", key=f"scoreplan_{r['id']}"):
                    api.submit_task("position", {"stock_code": code_r, "stock_name": name_r})
                    st.toast("建仓方案生成任务已提交后台，可切换页面继续操作")

    manual = st.text_input("手动打分股票代码", "")
    if st.button("触发打分", disabled=not manual):
        api.submit_task("score", {"stock_code": manual.strip(), "stock_name": ""})
        st.toast("打分任务已提交后台，完成后顶部任务状态区会提示，可切换页面继续操作")
except Exception as exc:
    st.error(f"评分获取失败: {exc}")
