"""规则变更记录：复盘建议一键采纳的完整留痕（生效中/已回滚，全透明可追溯）

每行=一次规则变更（来源复盘建议、归属 Agent、类型、变更前后对比）；
展开详情=变更对比 + 落地元数据 + 理由与依据 + 预期效果与风险；
生效中的规则可一键回滚（原因必填留痕），回滚后全部 Agent 立即停止携带该规则。
所有落地均为「系统自动注入」：规则存库由 agent_call 管道动态拼入，绝不写入源码文件。
"""
import html

import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次3：页面头部收敛为 page_header 单行范式 =====
render.page_header(
    "规则变更记录（全透明·可回滚）",
    caption="复盘页一键采纳的每一条规则都在这份台账中留痕：变更前后对比、来源复盘、"
            "落地元数据一目了然；生效中的规则可随时回滚（原因必填）。"
            "落地方式为系统自动注入（规则存库，全部 Agent 下次任务自动携带），绝不写源码文件。",
)

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

try:
    changes = api.rule_changes() or []
    changes_err = None
except Exception as exc:  # noqa: BLE001 后端未起/接口异常：展示可重试错误卡
    changes, changes_err = [], exc

# 生效状态中文标签与徽章色
_STATUS_LABEL = {"active": "生效中", "rolled_back": "已回滚"}
_STATUS_TONE = {"active": "ok", "rolled_back": "err"}

if changes_err is not None:
    render.dismissible_error("规则变更记录加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                             detail=changes_err, retry_key="retry_rc", dismiss_key="rc_list")
else:
    if not changes:
        render.empty_state("暂无规则变更记录。在「交易复盘」页对规则类建议执行「一键采纳」后，"
                           "变更将在此全量留痕。")
    else:
        # 筛选（客户端过滤：规则变更属低频数据，一次拉取本地过滤即可）
        status_sel = st.selectbox("状态筛选", ["all", "active", "rolled_back"],
                                  format_func=lambda v: {"all": "全部",
                                                         "active": "生效中",
                                                         "rolled_back": "已回滚"}[v],
                                  key="rc_status_sel")
        agents = sorted({c.get("target_agent") for c in changes if c.get("target_agent")})
        agent_sel = st.selectbox("归属 Agent", ["all"] + agents, key="rc_agent_sel")
        rows = [c for c in changes
                if (status_sel == "all" or c.get("status") == status_sel)
                and (agent_sel == "all" or c.get("target_agent") == agent_sel)]
        if not rows:
            render.empty_state("当前筛选条件下暂无记录。")
        else:
            st.caption(f"共 {len(rows)} 条记录（时间倒序）· 点击行内「查看详情」展开变更对比与回滚入口")
            render.batch_fold_bar("rc", [f"rc_{r['id']}" for r in rows],
                                  label="点击「查看详情」展开变更对比与回滚；新加载项自动跟随批量状态。")

            def _row(rc: dict, index: int) -> None:
                rid = rc.get("id")
                key = f"rc_{rid}"
                status = rc.get("status") or "active"
                summary = (rc.get("after_text") or "").strip()
                if len(summary) > 60:
                    summary = summary[:60] + "…"
                meta = (f'<span class="badge badge-{"ok" if status == "active" else "err"}">'
                        f'{html.escape(_STATUS_LABEL.get(status, status))}</span>'
                        f'<span class="badge badge-info">{html.escape(render.rule_type_label(rc.get("rule_type") or "soft"))}</span>'
                        f' {str(rc.get("created_at") or "")[:16]}')
                _, opened = render.list_item_toggle_actions(
                    key, f"[{html.escape(rc.get('target_agent') or '—')}] {html.escape(rc.get('rule_name') or '（未命名规则）')}",
                    subtitle=(f"规则内容：{html.escape(summary)}" if summary else
                              f"标的 {rc.get('stock_name') or rc.get('stock_code') or '—'} · "
                              f"来源复盘 {rc.get('review_id') or '—'}"),
                    dot=_STATUS_TONE.get(status, "mute"), meta=meta,
                    actions=("查看详情",))
                if opened:
                    render.rule_change_card(rc, key=f"rc_card_{rid}")

            render.record_list(rows, _row, batch=20, key="rc_rl")
