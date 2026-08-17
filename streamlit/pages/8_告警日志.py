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

# ===== 批次3：页面头部收敛为 page_header 单行范式 =====
render.page_header(
    "告警日志（MonitorAgent）",
    caption="MonitorAgent 全部信号记录：含飞书推送状态，按级别/类型筛选。",
)

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

try:
    rows = api.alerts()
    if not rows:
        render.empty_state("暂无告警记录。持仓监控在交易时段每 3 分钟自动运行。")
    else:
        # 级别/类型筛选：数据全量在手，纯前端过滤零后端改动
        _LV = {"all": "全部级别", "critical": "严重", "warning": "警告", "info": "提示"}
        lv = st.selectbox("按级别筛选", list(_LV), format_func=lambda v: _LV[v], key="_al_lv")
        types = sorted({str(r.get("alert_type") or "未知") for r in rows})
        tp = st.selectbox("按类型筛选", ["全部类型"] + types, key="_al_tp")
        filtered = [r for r in rows
                    if (lv == "all" or str(r.get("severity") or "") == lv)
                    and (tp == "全部类型" or str(r.get("alert_type") or "") == tp)]
        render.time_text("告警统计时间范围",
                         f"{rows[0]['created_at'][:16]} ~ {rows[-1]['created_at'][:16]}")
        if not filtered:
            render.empty_state("当前筛选条件下无匹配告警。", icon="🔍")
        else:
            alert_keys = [f"alert_page_{r['id']}" for r in filtered]
            render.batch_fold_bar("alert", alert_keys,
                                  label="点击行内「查看详情」展开完整告警原因与处置建议。")
            render.alert_list(filtered, key="alert_page", empty_text="无匹配的告警记录。",
                              scope="alert")
except Exception as exc:
    render.dismissible_error("告警日志加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                             detail=exc, retry_key="retry_alerts", dismiss_key="alert_page")
