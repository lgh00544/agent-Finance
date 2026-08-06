"""告警日志：MonitorAgent 全部信号记录（含飞书推送状态，自然语言分段展示）

复用全局告警行范式（render.alert_list）：左=严重度色圆点+代码名称+告警类型(加粗)，
副标题=消息摘要，右=触发时间+飞书推送状态+「查看详情」；详情分区展示完整消息、
建议动作与 LLM 研判结论，原始 JSON 永久折叠在最底部。
"""
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("告警日志（MonitorAgent）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

try:
    rows = api.alerts()
    if not rows:
        render.empty_state("暂无告警记录。持仓监控在交易时段每 3 分钟自动运行。")
    else:
        render.time_text("告警统计时间范围",
                         f"{rows[0]['created_at'][:16]} ~ {rows[-1]['created_at'][:16]}")
        render.alert_list(rows, key="alert_page", empty_text="无匹配的告警记录。")
except Exception as exc:
    render.error_card("告警日志加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key="retry_alerts")
