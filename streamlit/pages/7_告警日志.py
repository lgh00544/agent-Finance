"""告警日志：MonitorAgent 全部信号记录（含飞书推送状态，自然语言分段展示）"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="告警日志", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("告警日志（MonitorAgent）")

SEVERITY_MAP = {"info": "一般", "warning": "警告", "critical": "严重"}
ACTION_MAP = {"hold": "持有", "reduce": "减仓", "exit": "清仓"}

try:
    rows = api.alerts()
    if not rows:
        st.info("暂无告警记录。持仓监控在交易时段每 3 分钟自动运行。")
    else:
        render.time_text("告警统计时间范围",
                         f"{rows[0]['created_at'][:16]} ~ {rows[-1]['created_at'][:16]}")
        df = pd.DataFrame([{
            "时间": a["created_at"][:16],
            "股票": render.stock_label(a["stock_code"], a["stock_name"]),
            "类型": a["alert_type"],
            "严重度": SEVERITY_MAP.get(a["severity"], a["severity"]),
            "建议": ACTION_MAP.get(a["action"], a["action"]),
            "飞书推送": "✅" if a["pushed"] else "—",
        } for a in rows])
        st.dataframe(df, width="stretch", hide_index=True)

        for a in rows[:20]:
            label = render.stock_label(a["stock_code"], a["stock_name"])
            with st.expander(f"{a['created_at'][:16]} {label} — {a['alert_type']}（"
                             f"{SEVERITY_MAP.get(a['severity'], a['severity'])} / "
                             f"{ACTION_MAP.get(a['action'], a['action'])}）"):
                render.time_text("告警触发时间", a["created_at"],
                                 highlight=a["severity"] in ("warning", "critical")
                                 or a["action"] != "hold")
                st.markdown(a["message"])
                st.markdown("**LLM 研判结论**")
                render.render_dict(a["signal"])
                render.raw_json_expander(a["signal"], key=f"raw_alert_{a['id']}")
except Exception as exc:
    st.error(f"告警日志获取失败: {exc}")
