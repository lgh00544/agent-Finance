"""前端渲染工具：LLM 结构化 JSON → 自然语言展示；原始 JSON 折叠查看

【刚性代码逻辑】仅做字段映射与格式化展示，不产生任何研判内容；
后端存储与 LLM 交互保持结构化 JSON 不变，仅在此层做渲染转换。
时间统一展示格式 YYYY-MM-DD HH:mm（北京时间），浅色小字标注数据生成/检测时间。
"""
import streamlit as st

# 时效标注配色：普通浅灰 / 紧急琥珀（深色主题下均清晰可读）
_TIME_COLOR = "#9CA3AF"
_TIME_HIGHLIGHT = "#F59E0B"


def stock_label(code: str, name: str) -> str:
    """统一股票标识：代码在前、名称紧随（如 600519 贵州茅台）"""
    name = (name or "").strip()
    code = str(code or "").strip()
    if name and name != code:
        return f"{code} {name}"
    return code


def render_dict(data: dict | None) -> None:
    """JSON 字典 → 带小标题的正文段落（列表分点、嵌套字典递归展开）"""
    if not data:
        st.markdown("（无）")
        return
    for key, value in data.items():
        if isinstance(value, dict):
            st.markdown(f"**{key}**")
            _render_nested(value, 1)
        elif isinstance(value, list):
            st.markdown(f"**{key}**")
            for i, item in enumerate(value, 1):
                if isinstance(item, dict):
                    flat = "；".join(f"{k}：{v}" for k, v in item.items()
                                     if not isinstance(v, (dict, list)))
                    st.markdown(f"{i}. {flat or item}")
                else:
                    st.markdown(f"{i}. {item}")
        else:
            st.markdown(f"- **{key}**：{value}")


def _render_nested(data: dict, level: int) -> None:
    pad = "　" * level
    for key, value in data.items():
        if isinstance(value, dict):
            st.markdown(f"{pad}**{key}**")
            _render_nested(value, level + 1)
        elif isinstance(value, list):
            st.markdown(f"{pad}**{key}**")
            for i, item in enumerate(value, 1):
                if isinstance(item, dict):
                    flat = "；".join(f"{k}：{v}" for k, v in item.items()
                                     if not isinstance(v, (dict, list)))
                    st.markdown(f"{pad}{i}. {flat or item}")
                else:
                    st.markdown(f"{pad}{i}. {item}")
        else:
            st.markdown(f"{pad}- **{key}**：{value}")


def raw_json_expander(data, label: str = "查看原始数据", key: str | None = None) -> None:
    """原始 JSON 折叠查看：默认收起，用户主动点击才展开"""
    with st.expander(label, expanded=False, key=key):
        st.json(data)


def submit_task(kind: str, params: dict | None = None, label: str = "后台任务") -> bool:
    """提交后台任务：重复触发（后端 409）与后端不可达时显示中文提示，返回是否成功"""
    import requests

    from api_client import submit_task as api_submit
    try:
        api_submit(kind, params)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 409:
            st.warning(f"{label}正在执行中，请等待其完成后再试")
        else:
            st.error(f"{label}提交失败，请确认后端服务正常运行（{type(exc).__name__}）")
        return False
    except Exception as exc:  # noqa: BLE001 后端不可达统一提示，不向页面抛原始报错
        st.error(f"{label}提交失败，请确认后端服务正常运行（{type(exc).__name__}）")
        return False
    st.toast(f"{label}已提交后台，可切换页面继续操作")
    return True


def time_text(label: str, time_str: str | None, highlight: bool = False) -> None:
    """时效标注：浅色小字（YYYY-MM-DD HH:mm）；紧急信号时间用琥珀色高亮"""
    if not time_str:
        return
    color = _TIME_HIGHLIGHT if highlight else _TIME_COLOR
    st.markdown(
        f'<span style="color:{color};font-size:0.85em">{label}：{str(time_str)[:16]}</span>',
        unsafe_allow_html=True)


@st.fragment(run_every="5s")
def task_status_area() -> None:
    """页面顶部统一后台任务状态区：每 5 秒轮询最近任务，任务全部结束自动消失

    - pending/running：琥珀色「后台任务执行中」明细 + 可切换页面继续操作提示；
    - failed：红色提示 + 一键重试（复用原任务ID重新入队）；
    - 任务完成/失败瞬间弹一次性 toast（session_state 标记，不重复弹）；
      任务完成时自动刷新整页（候选池等模块立即展示最新结果，无需手动刷新）；
    - 无未完成任务时本区域不渲染任何内容。
    """
    from api_client import recent_tasks, retry_task

    try:
        tasks = recent_tasks(limit=8) or []
    except Exception:  # noqa: BLE001 后端暂不可达时静默跳过，页面主体照常
        return
    active = [t for t in tasks if t["status"] in ("pending", "running")]
    failed = [t for t in tasks if t["status"] == "failed"]

    # 完成/失败一次性 toast（仅状态从进行中变为终态时弹一次）；
    # 完成瞬间自动刷新整页（scope=app），候选池/持仓等数据立即展示最新结果
    seen = st.session_state.setdefault("_task_seen", {})
    for t in tasks:
        prev = seen.get(t["task_id"])
        seen[t["task_id"]] = t["status"]
        if prev in ("pending", "running") and t["status"] == "done":
            st.toast(f"任务完成：{t['label']}")
            st.rerun(scope="app")
        elif prev in ("pending", "running") and t["status"] == "failed":
            st.toast(f"任务失败：{t['label']}，可点击重试", icon="⚠️")
    if len(seen) > 60:  # 只保留最近标记，防无限增长
        st.session_state["_task_seen"] = {k: v for k, v in list(seen.items())[-40:]}

    if not active and not failed:
        return
    if active:
        st.markdown(
            f'<span style="color:{_TIME_HIGHLIGHT}">⏳ 后台任务执行中（{len(active)} 个）</span>'
            f'<span style="color:{_TIME_COLOR};font-size:0.85em">　任务已提交后台，'
            f'可切换页面继续操作</span>',
            unsafe_allow_html=True)
        for t in active:
            st.markdown(f"- **{t['label']}**（提交于 {str(t['submitted_at'])[:16]}）")
    if failed:
        st.error(f"有 {len(failed)} 个后台任务执行失败：")
        for t in failed:
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{t['label']}**　`{t['task_id']}`\n\n{t['error']}")
            if c2.button("重试", key=f"retry_{t['task_id']}"):
                retry_task(t["task_id"])


# ================= 全局顶部常驻状态栏 =================
# 固定于原生顶部栏（stHeader，z-index 1000）之下、z-index 998，不随页面滚动消失；
# 布局规范：width 100% 撑满视口、左右内边距对称（无单侧大 padding）、
# align-items: center 全部内容统一垂直居中同一基线、line-height 1.5 紧凑行高；
# 信息按「账户资产」「大盘指数」两组展示（组间竖线分隔 + 组标签），
# 核心数据（总资产/总盈亏/上证指数）加粗加大；
# 主内容区与侧边栏同步预留 4.3rem 顶部内边距，保证首屏标题与核心操作区不被遮挡
_TOP_BAR_CSS = """
<style>
[data-testid="stMain"] { padding-top: 4.3rem; }
[data-testid="stSidebarContent"] { padding-top: 4.3rem; }
.top-status-bar {
  position: fixed; top: 2.95rem; left: 0; right: 0; z-index: 998;
  width: 100%; box-sizing: border-box;
  display: flex; align-items: center; flex-wrap: wrap;
  column-gap: 1rem; row-gap: 0.2rem;
  padding: 0.3rem 1rem; font-size: 0.92rem; line-height: 1.5;
  background: rgba(11, 13, 19, 0.98); border-bottom: 1px solid #2C2F36;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
}
.top-status-bar .bar-label { color: #B8BCC4; font-size: 0.82em; margin-right: 0.3rem; }
.top-status-bar .bar-group {
  display: inline-flex; align-items: center; flex-wrap: wrap;
  column-gap: 1.15rem; row-gap: 0.1rem;
  padding-left: 0.9rem; border-left: 1px solid #2C2F36;
}
.top-status-bar .bar-group-label {
  color: #7A8090; font-size: 0.76em; letter-spacing: 0.06em;
  margin-right: 0.15rem;
}
.top-status-bar b { font-weight: 700; color: #E5E7EB; }
.top-status-bar .bar-key { font-weight: 700; font-size: 1.08em; color: #FFFFFF; }
.top-status-bar .up { color: #FF6B6B; font-weight: 700; }
.top-status-bar .down { color: #34D399; font-weight: 700; }
.top-status-bar .flat { color: #B8BCC4; }
.top-status-bar .stale { color: #F59E0B; font-size: 0.8em; }
</style>
"""
_COLOR_UP = "up"
_COLOR_DOWN = "down"
_COLOR_FLAT = "flat"


def _bar_money(value) -> str:
    """金额千分位（None 显示 —）"""
    if value is None:
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _bar_pct(value) -> str:
    """百分比显示（None 显示 —）"""
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _bar_sign(value) -> str:
    """正红负绿（A 股习惯）：>0 → up，<0 → down，其余 flat"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _COLOR_FLAT
    return _COLOR_UP if v > 0 else (_COLOR_DOWN if v < 0 else _COLOR_FLAT)


def _bar_stale_fetch(state_key: str, fn):
    """接口失败时返回上次成功缓存值（标注「上次数据」）；无缓存返回 (None, 错误标记) 显示「数据加载中」"""
    try:
        data = fn()
        st.session_state[state_key] = data
        return data, ""
    except Exception as exc:  # noqa: BLE001 后端暂不可达时降级展示，不向页面抛原始报错
        return st.session_state.get(state_key), f"更新失败（{type(exc).__name__}）"


@st.fragment(run_every="60s")
def top_status_bar() -> None:
    """全局顶部常驻状态栏（所有页面固定显示，不随滚动消失）

    左=北京时间（每分钟自动刷新）；中=账户核心资产 5 项（双数据路径：有 OCR 账户基准
    用券商真实值，否则按总资金设定估算并标注「估算」；盈亏正红负绿）；
    右=三大指数（名称+点位+涨跌幅+更新时间）。
    「账户明细 / 指数详情」可点击展开查看详细数据；接口失败显示「数据加载中」或
    上次缓存值并标注，不向页面抛原始报错。
    """
    from datetime import datetime, timedelta, timezone

    import api_client as api

    st.markdown(_TOP_BAR_CSS, unsafe_allow_html=True)

    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    acc, acc_err = _bar_stale_fetch("_bar_account", api.account_summary)
    idx, idx_err = _bar_stale_fetch("_bar_indices", api.market_indices)

    parts = [f'<span class="bar-label">北京时间</span><b>{now}</b>']

    # ---------- 中：账户资产组（组标签 + 组内分隔，核心数据加粗加大） ----------
    acc_parts = ['<span class="bar-group-label">账户资产</span>']
    if acc:
        total = acc.get("total_asset")
        estimate_tag = ('<span class="stale">估算</span>'
                        if (acc.get("source") == "estimate" and total is not None) else "")
        acc_parts.append(f'<span class="bar-label">总资产</span>'
                         f'<b class="bar-key">{_bar_money(total)}{estimate_tag}</b>')
        acc_parts.append(f'<span class="bar-label">总持仓成本</span><b>{_bar_money(acc.get("total_cost"))}</b>')
        pnl = acc.get("pnl_amount")
        if pnl is not None:
            acc_parts.append(f'<span class="bar-label">总盈亏</span>'
                             f'<b class="{_bar_sign(pnl)}">{_bar_money(pnl)}（{_bar_pct(acc.get("pnl_pct"))}）</b>')
        else:
            acc_parts.append(f'<span class="bar-label">总盈亏</span><b>—</b>')
        acc_parts.append(f'<span class="bar-label">整体仓位</span><b>{_bar_pct(acc.get("position_pct"))}</b>')
        acc_parts.append(f'<span class="bar-label">可用资金</span><b>{_bar_money(acc.get("available_cash"))}</b>')
        if acc_err:
            acc_parts.append(f'<span class="stale">账户数据{acc_err}，显示上次数据</span>')
    else:
        hint = "数据加载中" if acc_err else "—"
        acc_parts.append(f'<span class="bar-label">总资产</span><b>{hint}</b>')
        acc_parts.append(f'<span class="bar-label">可用资金</span><b>{hint}</b>')
        acc_parts.append(f'<span class="bar-label">整体仓位</span><b>{hint}</b>')
    parts.append(f'<span class="bar-group">{"".join(acc_parts)}</span>')

    # ---------- 右：大盘指数组（组标签 + 上证指数加粗） ----------
    idx_parts = ['<span class="bar-group-label">大盘指数</span>']
    if idx:
        for it in idx.get("indices") or []:
            label = it.get("name") or it.get("code") or ""
            pct = it.get("change_pct")
            key_cls = " bar-key" if label in ("上证指数", "上证综指") else ""
            if pct is None:
                idx_parts.append(f'<span class="bar-label">{label}</span><b>—</b>')
            else:
                idx_parts.append(f'<span class="bar-label">{label}</span>'
                                 f'<b class="{_bar_sign(pct)}{key_cls}">'
                                 f'{_bar_money(it.get("price"))} {pct:+.2f}%</b>')
        if idx.get("updated_at"):
            idx_parts.append(f'<span class="bar-label">更新时间</span>'
                             f'<span class="stale">{idx["updated_at"]}</span>')
        if idx_err:
            idx_parts.append(f'<span class="stale">指数{idx_err}，显示上次数据</span>')
    else:
        idx_parts.append(f'<span class="bar-label">指数</span><b>{"数据加载中" if idx_err else "—"}</b>')
    parts.append(f'<span class="bar-group">{"".join(idx_parts)}</span>')

    st.markdown(f'<div class="top-status-bar">{"".join(parts)}</div>', unsafe_allow_html=True)

    # ---------- 展开详情（默认收起，点击展开查看详细数据） ----------
    show_acc = st.session_state.setdefault("_bar_show_acc", False)
    show_idx = st.session_state.setdefault("_bar_show_idx", False)
    c1, c2, c3 = st.columns([1.2, 1.2, 6])
    with c1:
        if st.button("账户明细 ▼" if not show_acc else "账户明细 ▲",
                     key="bar_toggle_acc", use_container_width=True):
            st.session_state["_bar_show_acc"] = not show_acc
            st.rerun()
    with c2:
        if st.button("指数详情 ▼" if not show_idx else "指数详情 ▲",
                     key="bar_toggle_idx", use_container_width=True):
            st.session_state["_bar_show_idx"] = not show_idx
            st.rerun()

    if show_acc and acc:
        st.markdown("**账户明细**")
        if acc.get("source") == "estimate":
            st.caption("暂无券商账户基准：总资产/可用资金/整体仓位按「总资金设定 + 持仓实时盈亏」估算。"
                       "上传持仓截图 OCR 识别并经人工确认保存账户基准后，自动切换为券商真实值。")
        else:
            b = acc.get("baseline") or {}
            st.caption(f"账户基准来自券商持仓截图（人工确认，{b.get('trade_date', '')} 保存）；"
                       f"总盈亏/总持仓成本随持仓与实时行情自动计算。")
        pnl_sign = _bar_sign(acc.get("pnl_amount"))
        for label, value, colored in [
            ("总资产", _bar_money(acc.get("total_asset")), False),
            ("总持仓成本", _bar_money(acc.get("total_cost")), False),
            ("持仓市值", _bar_money(acc.get("market_value")), False),
            ("总盈亏", _bar_money(acc.get("pnl_amount")), True),
            ("总盈亏比例", _bar_pct(acc.get("pnl_pct")), True),
            ("整体仓位占比", _bar_pct(acc.get("position_pct")), False),
            ("可用资金", _bar_money(acc.get("available_cash")), False),
        ]:
            if colored:
                st.markdown(f'- {label}：**<span class="{pnl_sign}">{value}</span>**',
                            unsafe_allow_html=True)
            else:
                st.markdown(f"- {label}：**{value}**")
        if acc.get("quote_error"):
            st.caption(f"⚠️ 行情刷新失败：{acc['quote_error']}（市价相关数值可能不准确）")

    if show_idx and idx:
        st.markdown("**指数详情**")
        for it in idx.get("indices") or []:
            pct = it.get("change_pct")
            cls = _bar_sign(pct)
            if pct is None:
                st.markdown(f"- **{it.get('name', it.get('code', ''))}**："
                            f"{_bar_money(it.get('price'))}（—）")
            elif pct > 0:
                mark = "涨"
            elif pct < 0:
                mark = "跌"
            else:
                mark = "平"
            if pct is not None:
                st.markdown(f"- **{it.get('name', it.get('code', ''))}**：{_bar_money(it.get('price'))} "
                            f"（<span class='{cls}'>{mark} {pct:+.2f}%</span>）", unsafe_allow_html=True)
        st.caption(f"指数数据更新时间：{idx.get('updated_at', '—')}")
        if idx_err:
            st.caption(f"⚠️ 指数行情更新失败：{idx_err}（显示上次缓存值）")
