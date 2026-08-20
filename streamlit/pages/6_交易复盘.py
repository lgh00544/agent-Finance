"""交易复盘：ReviewAgent 输出 + 黑盒总览 + 交易偏好优化建议（一键采纳/驳回，人工审核后生效）

黑盒展示规范（2026-08-10）：
- 主界面（本期复盘总览）只暴露结果与可执行建议：综合评级 / 一句话总结 / 四张核心指标卡 /
  可执行优化建议清单（去审核）/ 历史走势折线图；
- 算法逻辑、规则推导、根因细节（止盈比对、维度归因、原始 JSON、迭代历史）收敛到
  「详情与历史记录」深层折叠（默认收起），且仅「专业视图」开关开启后可见；
- 企业级列表行范式：左=盈亏色圆点+代码名称(加粗)+离场日·持仓天数·建议状态(副标题)，
  右=盈亏%+生成时间+「查看详情」；详情分区卡片化（计划兑现度/止盈比对/经验教训/偏好微调/优化建议），
  原始 JSON 永久折叠在最底部。
"""
import html
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

import api_client as api
import render

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _HAS_PLOTLY = True
except Exception:  # noqa: BLE001 依赖缺失时图表降级为 st.line_chart 兜底，不阻断页面
    _HAS_PLOTLY = False

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次3：页面头部收敛为 page_header（黑盒展示规范保持）=====
render.page_header(
    "交易复盘（ReviewAgent）",
    caption="黑盒总览：主界面只暴露结果与可执行建议（综合评级/一句话总结/指标卡/建议清单/走势图）；"
            "算法与根因细节在「详情与历史记录」深层折叠 + 专业视图开关。建议一键采纳/驳回，人工审核后生效。",
)

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# ================= 展示层常量区（人工核定，仅作本页展示标签，不参与任何交易决策） =================
# 综合评级阈值：仅用于「本期复盘总览」的 达标/待优化/异常 标签判定；
# 展示层判定·人工核定——如需调整阈值请修改本常量块（本页代码不散落任何其他判定阈值）。
_GRADE_CFG = {"min_samples": 3, "win_rate_ok": 60.0, "win_rate_warn": 50.0,
              "avg_pnl_ok": 0.0, "max_dd_warn": 10.0}
_WINDOW_DAYS = {"近7天": 7, "近30天": 30}
_WINDOW_ALL = "全部"
_ACTION_MAX = 5
_TP_KIND_EFFECT = {"profile": "写入个人交易偏好档案（版本+1，全部 Agent 立即生效）",
                   "prompt": "规则类建议：一键采纳自动注入全部 Agent 生效（可回滚）"}
_CN_TZ = timezone(timedelta(hours=8))


def _api_error_detail(exc: requests.HTTPError) -> str:
    """从 HTTPError 提取后端 detail（采纳/驳回的校验拦截原因直接展示给用户）"""
    try:
        resp = exc.response
        if resp is not None:
            body = resp.json()
            if isinstance(body, dict) and body.get("detail"):
                return str(body["detail"])
    except Exception:  # noqa: BLE001 响应体非 JSON 时回落原始异常
        pass
    return str(exc)


# ================= 纯函数：窗口过滤 / 事实统计 / 评级标签 / 总结 / 走势（零后端依赖，可单测） =================
def _pnl(r: dict) -> float | None:
    try:
        return float(r.get("pnl_pct"))
    except (TypeError, ValueError):
        return None


def _window_rows(rows: list, window: str) -> list:
    """按离场日过滤统计窗口（exit_date YYYY-MM-DD 字符串比较；无日期行仅计入「全部」）"""
    days = _WINDOW_DAYS.get(window)
    if days is None:
        return rows
    cutoff = (datetime.now(_CN_TZ) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [r for r in rows if (r.get("exit_date") or "") >= cutoff]


def _calc_stats(rows: list) -> dict:
    """纯事实统计（零判断阈值）：胜率/平均涨幅/盈亏比/最大回撤 + 样本计数"""
    pnls = [p for p in (_pnl(r) for r in rows) if p is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls)
    stats = {"n": n, "wins": len(wins), "losses": len(losses),
             "win_rate": len(wins) / n if n else None,
             "avg_pnl": sum(pnls) / n if n else None,
             "pl_ratio": sum(wins) / abs(sum(losses)) if losses else None,
             "max_dd": None}
    if losses:
        # 最大回撤：按离场日排序的累计盈亏曲线 峰值→谷值最大跌幅
        cum = peak = dd = 0.0
        for r in sorted(rows, key=lambda x: (str(x.get("exit_date") or ""), x.get("id") or 0)):
            p = _pnl(r)
            if p is None:
                continue
            cum += p
            peak = max(peak, cum)
            dd = max(dd, peak - cum)
        stats["max_dd"] = dd if dd > 0 else None
    return stats


def _grade_of(stats: dict) -> tuple[str, str]:
    """综合评级（阈值见 _GRADE_CFG 人工核定，仅展示标签）"""
    if stats["n"] < _GRADE_CFG["min_samples"]:
        return "样本不足", "mute"
    win_rate = (stats["win_rate"] or 0) * 100
    avg = stats["avg_pnl"] or 0
    dd = stats["max_dd"] or 0
    ok = (win_rate >= _GRADE_CFG["win_rate_ok"] and avg >= _GRADE_CFG["avg_pnl_ok"]
          and dd < _GRADE_CFG["max_dd_warn"])
    bad = (win_rate < _GRADE_CFG["win_rate_warn"] or avg < _GRADE_CFG["avg_pnl_ok"]
           or dd >= _GRADE_CFG["max_dd_warn"])
    if ok:
        return "达标", "ok"
    if bad:
        return "异常", "err"
    return "待优化", "warn"


def _summary_text(stats: dict) -> str:
    """一句话总结：纯事实插值模板，无判断分支"""
    if not stats["n"]:
        return "该窗口暂无复盘记录，平仓并复盘后自动生成统计。"
    parts = [f"本窗口共复盘 {stats['n']} 笔：胜率 {stats['win_rate'] * 100:.0f}%、"
             f"平均涨幅 {stats['avg_pnl']:+.2f}%、盈利 {stats['wins']} 笔、"
             f"亏损 {stats['losses']} 笔"]
    if stats["pl_ratio"] is not None:
        parts.append(f"，盈亏比 {stats['pl_ratio']:.2f}、最大回撤 {stats['max_dd']:.1f}%")
    else:
        parts.append("；当前暂无亏损样本")
    return "".join(parts)


def _trend_df(rows: list) -> pd.DataFrame | None:
    """历史走势（累计口径）：按离场日累计胜率/盈亏比。
    样本较少时逐日胜率是 0/1 毛刺，累计口径才有意义；无亏损的日子盈亏比缺列（NaN 断线）。"""
    by_date: dict[str, list[float]] = {}
    for r in rows:
        p = _pnl(r)
        if p is None:
            continue
        by_date.setdefault(str(r.get("exit_date") or "未知日期"), []).append(p)
    if not by_date:
        return None
    cum_w = cum_l = n = 0
    recs = []
    for d in sorted(by_date):
        for p in by_date[d]:
            n += 1
            if p > 0:
                cum_w += 1
            elif p < 0:
                cum_l += 1
        rec = {"exit_date": d, "累计胜率%": round(cum_w / n * 100, 1)}
        if cum_l:
            rec["累计盈亏比"] = round(cum_w / cum_l, 2)
        recs.append(rec)
    return pd.DataFrame(recs).set_index("exit_date")


# ================= 走势图与归因：纯数据函数（真实数据计算，估算项一律标注） =================
def _trend_points(rows: list) -> list[dict]:
    """按离场日分组的逐日走势点（每个点 = 真实复盘日期，无占位日期、无缺口连线）"""
    by_date: dict[str, list[float]] = {}
    for r in rows:
        p = _pnl(r)
        if p is None:
            continue
        by_date.setdefault(str(r.get("exit_date") or "未知日期"), []).append(p)
    cum_w = cum_l = n = 0
    pts = []
    for d in sorted(by_date):
        ws = ls = 0
        for p in by_date[d]:
            n += 1
            if p > 0:
                cum_w += 1
                ws += 1
            elif p < 0:
                cum_l += 1
                ls += 1
        pts.append({"date": d, "n": len(by_date[d]), "wins": ws, "losses": ls,
                    "cum_n": n, "cum_win_rate": round(cum_w / n * 100, 1),
                    "cum_pl_ratio": round(cum_w / cum_l, 2) if cum_l else None})
    return pts


def _abs_pnl_of(r: dict, total_asset: float) -> tuple[float | None, bool]:
    """单笔绝对盈亏（交易流水反算：pnl_pct × 累计买入金额；无持仓ID/无流水降级按总资产估算并标注）"""
    p = _pnl(r)
    if p is None:
        return None, False
    buy_amt = 0.0
    if r.get("holding_id"):
        try:
            for t in (api.holding_trades(r.get("holding_id")) or []):
                if t.get("side") == "buy":
                    try:
                        buy_amt += float(t.get("amount") or 0)
                    except (TypeError, ValueError):
                        pass
        except Exception:  # noqa: BLE001 流水拉取失败降级估算
            buy_amt = 0.0
    if buy_amt > 0:
        return p / 100 * buy_amt, False
    return p / 100 * total_asset, True


def _big_pnl_rows(win_rows: list, total_asset: float) -> list[tuple[dict, float, bool]]:
    """窗口内大额盈亏笔（单笔绝对盈亏超总资产 2%）→ [(row, abs_pnl, est_flag)]"""
    out = []
    for r in win_rows:
        ap, est = _abs_pnl_of(r, total_asset)
        if ap is not None and abs(ap) >= total_asset * 0.02:
            out.append((r, ap, est))
    return out


def _attr_decompose(win_rows: list, all_rows: list, rule_rows: list,
                    index_items: list, total_asset: float) -> dict:
    """四因素分层归因（估算口径，全部由真实数据计算）：
    Δ = 全量基准胜率 − 窗口胜率（>0 才拆解）；规则变动 = 窗口内最早规则变更日前后段胜率差；
    偶发 = 剔除大额亏损笔（单笔超总资产 2%）后胜率回升；市场 = 复盘日大盘波动占比相对全量的超额；
    标的结构 = 余量。占比按贡献归一化到 100%，全部标注「估算」。"""
    base = _calc_stats(all_rows)
    win = _calc_stats(win_rows)
    out = {"flat": True, "reason": "", "gap": 0.0, "win": win, "base": base,
           "shares": {"struct": 0, "market": 0, "rule": 0, "rand": 0},
           "notes": {}, "counterfactual": "", "top": "", "top_share": 0.0,
           "rc0": None, "n_outlier": 0}
    if not base["n"] or not win["n"] or not win["win_rate"]:
        out["reason"] = "样本不足"
        return out
    gap = (base["win_rate"] - win["win_rate"]) * 100  # 百分点，>0 = 窗口落后基准
    if gap <= 0:
        out["reason"] = "本窗口胜率不低于全量历史基准，暂无需归因"
        return out
    out["flat"] = False
    out["gap"] = gap
    dates = sorted({str(r.get("exit_date") or "") for r in win_rows})
    d0, d1 = dates[0], dates[-1]

    # ① 规则变动因素：窗口内最早规则变更日为分界，前后段胜率差（段内样本 <2 无法量化 → 0）
    c_rule, rc0, note_rule = 0.0, None, "窗口内无规则变更记录"
    rc_dates = sorted({(str(rc.get("created_at") or ""))[:10] for rc in (rule_rows or [])
                       if d0 <= (str(rc.get("created_at") or ""))[:10] <= d1})
    if rc_dates:
        rc0 = rc_dates[0]
        pre = [r for r in win_rows if (str(r.get("exit_date") or "")) < rc0]
        post = [r for r in win_rows if (str(r.get("exit_date") or "")) >= rc0]
        pst, qst = _calc_stats(pre), _calc_stats(post)
        if (pst["n"] >= 2 and qst["n"] >= 2
                and pst["win_rate"] is not None and qst["win_rate"] is not None):
            c_rule = max(0.0, (pst["win_rate"] - qst["win_rate"]) * 100)
            note_rule = (f"{rc0} 起规则调整前后段胜率 "
                         f"{pst['win_rate'] * 100:.0f}% → {qst['win_rate'] * 100:.0f}%")
        else:
            note_rule = f"{rc0} 规则变更前后段样本不足（<2 笔/段），无法量化（估算 0）"
    out["rc0"] = rc0

    # ② 偶发不可控因素：剔除大额亏损笔后胜率回升（反事实口径，真实数据重算）
    c_rand, note_rand = 0.0, "窗口内无大额亏损笔（单笔超总资产 2%）"
    outliers = [(r, ap, _est) for r, ap, _est in _big_pnl_rows(win_rows, total_asset) if ap < 0]
    if outliers:
        excl_ids = {r.get("id") for r, _a, _e in outliers}
        ewr = _calc_stats([r for r in win_rows if r.get("id") not in excl_ids])["win_rate"]
        if ewr is not None:
            c_rand = max(0.0, (ewr - win["win_rate"]) * 100)
            note_rand = (f"剔除 {len(outliers)} 笔大额亏损后胜率 "
                         f"{win['win_rate'] * 100:.0f}% → {ewr * 100:.0f}%")
            out["counterfactual"] = (f"若剔除该因素相关亏损 {len(outliers)} 笔，"
                                     f"窗口胜率 {win['win_rate'] * 100:.0f}% "
                                     f"→ {ewr * 100:.0f}%（估算）")
    out["n_outlier"] = len(outliers)

    # ③ 市场环境因素：复盘日大盘波动占比（|涨跌幅|≥1%）窗口 vs 全量 的超额
    c_mkt, note_mkt = 0.0, "暂无大盘数据"
    sh_by = {it.get("date"): it.get("change_pct")
             for it in (index_items or []) if it.get("code") == "sh000001"}
    win_dates = {str(r.get("exit_date") or "") for r in win_rows if r.get("exit_date")}
    base_dates = {str(r.get("exit_date") or "") for r in all_rows if r.get("exit_date")}

    def _vol_ratio(dates: set) -> float | None:
        vals = [sh_by[d] for d in dates if d in sh_by and sh_by[d] is not None]
        if not vals:
            return None
        return sum(1 for v in vals if abs(v) >= 1.0) / len(vals)

    r_win, r_base = _vol_ratio(win_dates), _vol_ratio(base_dates)
    if r_win is None or r_base is None:
        note_mkt = "复盘日无对应大盘数据，无法量化（估算 0）"
    else:
        note_mkt = (f"复盘日大盘波动占比：窗口 {r_win * 100:.0f}% vs 全量 {r_base * 100:.0f}%"
                    "（|涨跌幅|≥1%）")
        if r_win > r_base and r_base > 0:
            c_mkt = gap * min((r_win - r_base) / r_base, 1.0)

    # ④ 标的结构因素：余量（Δ 未被其余因素解释的部分）
    c_struct = max(0.0, gap - c_rule - c_rand - c_mkt)

    raw = {"struct": c_struct, "market": c_mkt, "rule": c_rule, "rand": c_rand}
    total = sum(raw.values())
    if total <= 0:
        out["shares"] = {"struct": 100, "market": 0, "rule": 0, "rand": 0}
        out["notes"] = {"struct": "窗口内暂无可归因的明确因素，波动归于标的本身",
                        "market": note_mkt, "rule": note_rule, "rand": note_rand}
        out["top"], out["top_share"] = "标的结构因素", 100.0
        return out
    shares = {k: round(v / total * 100) for k, v in raw.items()}
    shares[max(raw, key=raw.get)] += 100 - sum(shares.values())  # 尾差修正合计 100
    out["shares"] = shares
    out["notes"] = {"struct": (f"标的结构余量（Δ − 其余因素）≈ {c_struct:.1f}pp"
                               if c_struct > 0 else "规则/偶发/市场因素已覆盖本窗口波动"),
                    "market": note_mkt, "rule": note_rule, "rand": note_rand}
    _F = {"struct": "标的结构因素", "market": "市场环境因素", "rule": "规则变动因素", "rand": "偶发不可控因素"}
    top = max(shares, key=shares.get)
    out["top"], out["top_share"] = _F[top], float(shares[top])
    if not out["counterfactual"] and c_rule > 0 and rc0:
        out["counterfactual"] = (f"规则变更前后段胜率差 {c_rule:.1f}pp（{rc0} 起），"
                                 "回滚或修订该规则可期改善（估算）")
    if not out["counterfactual"] and c_struct > 0:
        out["counterfactual"] = (f"标的结构因素贡献约 {c_struct:.1f}pp，"
                                 "优化对应选股方向可期改善（估算）")
    return out


def _y_at(ymap: dict, d: str) -> float | None:
    """节点标记置于 ≤该日期的最近累计值上（避免悬挂在无复盘日）"""
    best = None
    for dt in sorted(ymap):
        if dt <= d:
            best = ymap[dt]
        else:
            break
    return best


def _build_markers(pts: list[dict], win_rows: list, rule_rows: list,
                   index_items: list, total_asset: float) -> dict[str, go.Scatter]:
    """三类关键事件节点（真实数据）：规则变更（star/x）/ 大额盈亏（△ 红涨 ▽ 绿跌）/ 市场异动（□）"""
    out: dict[str, go.Scatter] = {}
    if not pts:
        return out
    d0, d1 = pts[0]["date"], pts[-1]["date"]
    ymap = {p["date"]: p["cum_win_rate"] for p in pts}

    rcs = []
    for rc in (rule_rows or []):
        d = (str(rc.get("created_at") or ""))[:10]
        if d0 <= d <= d1:
            rcs.append((d, rc, bool(rc.get("rollback_time"))))
    if rcs:
        xs, ys, cds, syms, cols = [], [], [], [], []
        for d, rc, rolled in rcs:
            y = _y_at(ymap, d)
            if y is None:
                continue
            xs.append(d)
            ys.append(y)
            cds.append(["rule", rc.get("id"), rc.get("rule_name") or "—",
                        "已回滚" if rolled else "已采纳", (str(rc.get("created_at") or ""))[:16]])
            syms.append("x" if rolled else "star")
            cols.append("rgba(117,117,117,0.9)" if rolled else "rgba(245,166,35,0.9)")
        if xs:
            out["rule"] = go.Scatter(
                x=xs, y=ys, mode="markers", name="规则变更",
                marker=dict(symbol=syms, size=11, color=cols, line=dict(width=1, color="black")),
                customdata=cds,
                hovertemplate="<b>规则变更</b><br>日期：%{x}<br>规则：%{customdata[2]}"
                              "<br>状态：%{customdata[3]}<extra>规则变更</extra>")

    bp = [(r, ap, est) for r, ap, est in _big_pnl_rows(win_rows, total_asset)]
    if bp:
        xs, ys, cds, syms, cols = [], [], [], [], []
        for r, ap, est in bp:
            y = _y_at(ymap, str(r.get("exit_date") or ""))
            if y is None:
                continue
            xs.append(str(r.get("exit_date")))
            ys.append(y)
            cds.append(["bigpnl", r.get("id"), r.get("stock_code"), round(ap, 0),
                        "估算" if est else "流水反算"])
            syms.append("triangle-up" if ap > 0 else "triangle-down")
            cols.append("rgba(229,57,53,0.85)" if ap > 0 else "rgba(46,160,67,0.85)")
        if xs:
            out["bigpnl"] = go.Scatter(
                x=xs, y=ys, mode="markers", name="大额盈亏",
                marker=dict(symbol=syms, size=11, color=cols, line=dict(width=1, color="black")),
                customdata=cds,
                hovertemplate="<b>大额盈亏</b><br>日期：%{x}<br>股票：%{customdata[2]}"
                              "<br>绝对盈亏：%{customdata[3]:+,.0f} 元<br>口径：%{customdata[4]}"
                              "<extra>大额盈亏</extra>")

    mks = [(it["date"], it.get("change_pct")) for it in (index_items or [])
           if it.get("code") == "sh000001" and it.get("change_pct") is not None
           and abs(it["change_pct"]) >= 2 and d0 <= str(it.get("date") or "") <= d1]
    if mks:
        xs, ys, cds = [], [], []
        for d, chg in mks:
            y = _y_at(ymap, d)
            if y is None:
                continue
            xs.append(d)
            ys.append(y)
            cds.append(["market", d, chg])
        if xs:
            out["market"] = go.Scatter(
                x=xs, y=ys, mode="markers", name="市场异动",
                marker=dict(symbol="square", size=9, color="rgba(158,158,158,0.9)",
                            line=dict(width=1, color="black")),
                customdata=cds,
                hovertemplate="<b>市场异动</b><br>日期：%{x}<br>上证指数涨跌幅："
                              "%{customdata[2]:+.2f}%<extra>市场异动</extra>")
    return out


def _build_trend_figure(pts: list[dict], markers: dict[str, go.Scatter]) -> go.Figure:
    """双轨走势图（累计胜率/累计盈亏比，shared_xaxes 严格对齐并联动缩放）；
    边界锁定：minallowed/maxallowed 原生钳制平移与缩放（plotly ≥5.14）；hover 含逐日明细"""
    dates = [p["date"] for p in pts]
    cd = [[p["date"], p["n"], p["wins"], p["losses"], p["cum_win_rate"],
           p["cum_pl_ratio"] if p["cum_pl_ratio"] is not None else "—"] for p in pts]
    hov = ("统计日期：%{customdata[0]}<br>当期复盘笔数：%{customdata[1]}<br>"
           "新增盈利 / 亏损：%{customdata[2]} / %{customdata[3]} 笔<br>"
           "累计胜率：%{customdata[4]}%<br>累计盈亏比：%{customdata[5]}")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("累计胜率（%）", "累计盈亏比"))
    fig.add_trace(go.Scatter(x=dates, y=[p["cum_win_rate"] for p in pts],
                             mode="lines+markers", name="累计胜率",
                             line=dict(width=2), customdata=cd,
                             hovertemplate=hov + "<extra>累计胜率</extra>"),
                  row=1, col=1)
    if any(p["cum_pl_ratio"] is not None for p in pts):
        fig.add_trace(go.Scatter(x=dates, y=[p["cum_pl_ratio"] for p in pts],
                                 mode="lines+markers", name="累计盈亏比",
                                 line=dict(width=2), customdata=cd,
                                 hovertemplate=hov + "<extra>累计盈亏比</extra>"),
                      row=2, col=1)
    else:
        fig.add_annotation(text="暂无亏损样本，盈亏比曲线待积累", xref="paper", yref="paper",
                           x=0.5, y=0.28, showarrow=False,
                           font=dict(color="rgba(128,128,128,0.9)", size=12))
    for tr in markers.values():
        fig.add_trace(tr)
    fig.update_layout(height=520, dragmode="select", hovermode="x unified",
                      showlegend=True, margin=dict(t=36, b=24, l=8, r=8))
    fig.update_xaxes(minallowed=dates[0], maxallowed=dates[-1],
                     range=[dates[0], dates[-1]], row=1, col=1)
    fig.update_xaxes(minallowed=dates[0], maxallowed=dates[-1],
                     range=[dates[0], dates[-1]], row=2, col=1)
    return fig


def _node_detail_from(sel: dict) -> dict:
    """节点点击 → 详情卡（仅展示已存数据，无额外请求）"""
    cd = sel.get("customdata") or []
    kind = cd[0] if cd else ""
    if kind == "rule":
        return {"title": f"规则变更节点 · {cd[3] if len(cd) > 3 else '—'}",
                "body": f"规则：{cd[2] if len(cd) > 2 else '—'} · 时间：{cd[4] if len(cd) > 4 else '—'}。"
                        "完整规则文本见「策略闭环」或「规则变更记录」页。"}
    if kind == "bigpnl":
        return {"title": f"大额盈亏节点 · {cd[2] if len(cd) > 2 else '—'}",
                "body": f"单笔绝对盈亏 {cd[3]:,.0f} 元（口径：{cd[4] if len(cd) > 4 else '—'}，"
                        "阈值 = 账户总资产 × 2%）。"}
    if kind == "market":
        return {"title": f"市场异动节点 · {cd[1] if len(cd) > 1 else '—'}",
                "body": f"上证指数当日涨跌幅 {cd[2]:+.2f}%（|涨跌幅| ≥ 2% 视为市场异动）。"}
    return {}


def _handle_chart_event(evt, pts: list[dict]) -> None:
    """图表事件：框选区间 → 归因模块锁定区间（同次运行下方折叠区即联动）；单节点点击 → 详情卡"""
    if evt is None or not getattr(evt, "selection", None):
        return
    points = (evt.selection or {}).get("points") or []
    if not points:
        return
    marker_sel = [p for p in points
                  if (p.get("customdata") or [None])[0] in ("rule", "bigpnl", "market")]
    if marker_sel and len(marker_sel) == len(points) == 1:
        st.session_state["_node_detail"] = _node_detail_from(marker_sel[0])
        return
    xs = [p.get("x") for p in points if p.get("x") is not None]
    if not xs:
        return
    start, end = min(xs), max(xs)
    in_range = [p for p in pts if start <= p["date"] <= end]
    st.session_state["_attr_range"] = {"start": start, "end": end, "n": len(in_range)}


def _jump_sug(sid, pending_only: bool) -> None:
    """直达策略闭环对应建议（查看详情可选不改筛选；去审核自动切「待审核」筛选）"""
    if pending_only:
        st.session_state["_sug_filter"] = "pending"
    st.session_state["mod_strategy_loop"] = True
    st.session_state[f"open_sug_{sid}"] = True
    st.rerun()


def _match_attr_sugs(sugs: list, win_rows: list, dec: dict) -> list:
    """归因 → 对应建议匹配：标的结构→窗口内复盘相关建议；规则变动→变更日后的建议；其余取待审核前列"""
    if not sugs:
        return []
    if dec.get("flat"):
        return sugs[:_ACTION_MAX]
    win_ids = {r.get("id") for r in win_rows}
    matched = [s for s in sugs if s.get("review_id") in win_ids]
    if not matched and dec.get("rc0"):
        matched = [s for s in sugs
                   if (str(s.get("created_at") or ""))[:10] >= dec["rc0"]]
    return (matched or sugs)[:_ACTION_MAX]


STATUS_MAP = {"pending": "待审核", "adopted": "已采纳", "rejected": "已驳回"}
_SUG_STATUS = {"pending": "待审核", "approved": "已采纳", "rejected": "已驳回"}
_SUG_TONE = {"pending": "warn", "approved": "ok", "rejected": "err"}

# 专业视图开关（黑盒默认关：隐藏算法/规则/根因细节；本地单用户以页内开关等效权限控制）
pro_view = st.toggle("专业视图（显示止盈比对 / 维度归因 / 原始留痕等内部细节）",
                     key="pro_view",
                     help="默认黑盒展示：仅显示结果、核心指标与可执行建议；"
                          "开启后显示算法规则、根因推导等完整细节。")

# ================= 数据获取（单次全量拉取，前端聚合，保证核心区秒级加载） =================
# 审核区建议流（状态随筛选变化）
sug_filter = st.session_state.get("_sug_filter", "pending")  # all/pending/approved/rejected
try:
    sug_status = None if sug_filter == "all" else sug_filter
    suggestions = api.agent_suggestions(status=sug_status)
except Exception:  # noqa: BLE001 后端未起时降级为空态，不阻断页面
    suggestions = []

# 复盘行（总览聚合 + 详情列表共用，一次请求）
try:
    rows = api.reviews() or []
    rows_err = None
except Exception as exc:  # noqa: BLE001 后端未起/接口异常：总览区展示可重试错误卡
    rows, rows_err = [], exc

# 待审核建议（总览「可执行优化建议」+「走势变动分析」对应改善建议共用，一次请求）
try:
    pending_sugs = api.agent_suggestions(status="pending")
except Exception:  # noqa: BLE001 建议流失败降级为空态，不阻断页面
    pending_sugs = []

# ================= 走势归因数据源（只读，失败降级为空态，不阻断页面） =================
try:
    rule_rows = api.rule_changes() or []
except Exception:  # noqa: BLE001
    rule_rows = []
# 账户总资产（大额盈亏阈值口径；全市场快照拉取耗时 ~1 分钟，仅每会话取一次，之后复用）
try:
    if "_total_asset" not in st.session_state:
        st.session_state["_total_asset"] = float(
            (api.account_summary() or {}).get("total_asset") or 100000.0)
    total_asset = st.session_state["_total_asset"]
except Exception:  # noqa: BLE001 拉取失败按默认总资金估算
    total_asset = 100000.0
try:
    index_items = (api.index_history(90) or {}).get("items") or []
except Exception:  # noqa: BLE001
    index_items = []

# ================= 选股效果验证（候选池 T+N 自动追踪·选股质量闭环） =================
_PERIOD_LABELS = {"t3": "T+3", "t5": "T+5", "t10": "T+10"}

# 评级→排序权重（A 最前，B 次之，C 与"未评级"靠后）——只在展示层用，不改判定
_TV_SORT_RATING = {"A": 0, "B": 1, "C": 2}

# 可建仓徽章 CSS class —— 与 1_每日候选池.py 同款样式，视觉一致
_TV_BADGE_CLS = {"可建仓": "badge-ok", "建议关注": "badge-info", "观察": "badge-mute"}


def _tv_pct(row: dict, period: str) -> float | None:
    v = row.get(f"{period}_pct")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


with render.fold_module("track_verify", "选股效果验证（T+N 自动追踪）",
                        meta="候选池标的自选中日起追踪 T+3/T+5/T+10 涨跌幅与最大回撤 · "
                             "每日 16:00 自动验证 · 建议需人工审核后生效",
                        default_open=True) as tv_opened:
    if tv_opened:
        c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.3], vertical_alignment="bottom")
        with c1:
            period = st.selectbox("统计周期", list(_PERIOD_LABELS), index=1,
                                  key="_tv_period",
                                  format_func=lambda p: _PERIOD_LABELS[p])
        with c2:
            if st.button("手动验证", use_container_width=True, key="_tv_run",
                         help="立即执行一次 T+N 验证（与每日 16:00 自动任务同链路，幂等）"):
                try:
                    api.run_track_verify(False)
                    st.toast("候选 T+N 验证已提交后台，完成后数据自动落库，可刷新查看")
                except Exception as exc:  # noqa: BLE001 提交失败提示，不阻断页面
                    st.toast(f"提交失败：{_api_error_detail(exc)}")
        with c3:
            if st.button("历史回填", use_container_width=True, key="_tv_backfill",
                         help="初始化并验证全部历史候选（幂等，重复执行安全）"):
                try:
                    api.run_track_verify(True)
                    st.toast("历史回填已提交后台（幂等，重复执行安全）")
                except Exception as exc:  # noqa: BLE001
                    st.toast(f"提交失败：{_api_error_detail(exc)}")
        with c4:
            if st.button("生成建议", use_container_width=True, key="_tv_suggest",
                         help="基于验证统计生成选股规则优化建议（LLM 为主、异常模板兜底，来源已标记）"):
                try:
                    api.run_track_suggest()
                    st.toast("建议生成已提交后台，完成后在下方建议列表可见（LLM/模板来源已标记）")
                except Exception as exc:  # noqa: BLE001
                    st.toast(f"提交失败：{_api_error_detail(exc)}")
        st.caption("口径：T+N 涨跌幅 = 选中日后第 N 个交易日收盘 / 选中日收盘 − 1；"
                   "最大回撤 = 相对选中日收盘的区间最低收盘回撤；T+10 数据齐全即到期收尾。")

        try:
            tv_rows = api.track_verify_list() or []
        except Exception:  # noqa: BLE001 后端未起降级为空态，不阻断页面
            tv_rows = []

        # —— 可建仓徽章数据：按 track 行的 select_date 跨查 candidate_tradeable（只读已落库判定）
        # 与候选池页的 _badge_html 同源视觉，不调判定、不补算、不缓存跨进程态。
        tv_badges: dict[str, dict] = {}  # key = f"{select_date}_{stock_code}" → 带 label 的 item
        if tv_rows:
            # 批量按 select_date 分组调一次 api.candidate_tradeable(date=...)，
            # 每个日期只调一次（通常 1-3 个日期），避免逐行 N+1
            _select_dates = sorted({r.get("select_date", "") for r in tv_rows if r.get("select_date")})
            for _sd in _select_dates:
                try:
                    _tview = api.candidate_tradeable(date=_sd, limit=200)
                    for _it in (_tview.get("items") or []):
                        _key = f"{_sd}_{_it.get('stock_code', '')}"
                        tv_badges[_key] = _it
                except Exception:  # noqa: BLE001 跨查失败仅降级无徽章，不阻塞追踪列表渲染
                    pass  # 该日期判定未落库 → 该批次无徽章

        try:
            tv_stats = api.track_verify_stats(period)
        except Exception:  # noqa: BLE001
            tv_stats = None

        if not tv_rows:
            render.empty_state("暂无追踪标的。候选池有新候选后每日 16:00 自动初始化并验证；"
                               "也可点击上方「历史回填」立即初始化全部历史候选。", icon="📡")
        else:
            sts = tv_stats or {}
            s_n = sts.get("n") or 0
            s_wr = sts.get("win_rate")
            s_avg = sts.get("avg_pct")
            s_pl = sts.get("pl_ratio")
            s_dd = sts.get("avg_max_dd")
            render.stat_cards([
                {"label": "胜率", "value": f"{s_wr:.1f}%" if s_wr is not None else "—",
                 "sub": f"盈利 {sts.get('wins', 0)} 笔 / 共 {s_n} 笔",
                 "tone": ("ok" if s_wr is not None and s_wr >= 50 else
                          "err" if s_wr is not None else "mute")},
                {"label": "平均涨幅", "value": f"{s_avg:+.2f}%" if s_avg is not None else "—",
                 "sub": f"{_PERIOD_LABELS[period]} 周期",
                 "tone": "up" if s_avg is not None and s_avg > 0
                         else "down" if s_avg is not None else "mute"},
                {"label": "盈亏比", "value": f"{s_pl:.2f}" if s_pl is not None else "—",
                 "sub": "盈利合计 / 亏损合计", "tone": "mute"},
                {"label": "平均最大回撤", "value": f"-{s_dd:.2f}%" if s_dd is not None else "—",
                 "sub": "相对选中日收盘", "tone": "warn"},
            ])
            anomalies = (sts or {}).get("anomalies") or []
            for a in anomalies:
                data = a.get("data") or {}
                desc = "；".join(f"{k} {v}" for k, v in data.items())
                render.msg_card("warn", a.get("desc", "异常提示"), desc)

            # ---- 筛选（客户端过滤，数据量小不额外请求） ----
            ratings = sorted({(r.get("select_rating") or "").strip() or "未评级"
                              for r in tv_rows})
            try:
                tv_dates = api.track_verify_dates() or []
            except Exception:  # noqa: BLE001
                tv_dates = []
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                f_rating = st.selectbox("评级", ["全部"] + ratings, key="_tv_f_rating")
            with f2:
                f_status = st.selectbox("状态", ["全部", "追踪中", "已到期"], key="_tv_f_status")
            with f3:
                f_date = st.selectbox("选中日", ["全部"] + list(tv_dates), key="_tv_f_date")
            with f4:
                f_sort = st.selectbox(
                    "排序",
                    ["评级 + 选中日（默认）", "选中日 + 评级", "T+N 涨跌幅 高→低", "最大回撤 高→低"],
                    key="_tv_f_sort",
                )

            def _tv_filter(row: dict) -> bool:
                if f_rating != "全部":
                    r = (row.get("select_rating") or "").strip() or "未评级"
                    if r != f_rating:
                        return False
                if f_status == "追踪中" and row.get("is_finished"):
                    return False
                if f_status == "已到期" and not row.get("is_finished"):
                    return False
                if f_date != "全部" and row.get("select_date") != f_date:
                    return False
                return True

            shown = [r for r in tv_rows if _tv_filter(r)]

            # —— 排序：仅在前端展示层做 stable sort，不动后端默认顺序
            if shown:
                if f_sort == "评级 + 选中日（默认）":
                    shown.sort(
                        key=lambda r: (_TV_SORT_RATING.get((r.get("select_rating") or "").strip(), 3),
                                       r.get("select_date") or "")
                    )
                elif f_sort == "选中日 + 评级":
                    shown.sort(
                        key=lambda r: (r.get("select_date") or "",
                                       _TV_SORT_RATING.get((r.get("select_rating") or "").strip(), 3)),
                        reverse=True  # 选中日降序，让最新选入的排前
                    )
                elif f_sort.startswith("T+N 涨跌幅"):
                    shown.sort(
                        key=lambda r: (_tv_pct(r, period) if _tv_pct(r, period) is not None else -999),
                        reverse=True
                    )
                elif f_sort.startswith("最大回撤"):
                    shown.sort(
                        key=lambda r: (r.get("max_drawdown") if r.get("max_drawdown") is not None else 999),
                        reverse=True
                    )

            if not shown:
                render.empty_state("当前筛选条件下无追踪标的。", icon="🔍")
            else:
                # 历史胜率趋势（by_date 分组，数据源=后端统计）
                by_date = (sts or {}).get("by_date") or {}
                trend = {d: g["win_rate"] for d, g in sorted(by_date.items())
                         if g.get("win_rate") is not None}
                if len(trend) >= 2:
                    render.section_title(f"历史胜率趋势（{_PERIOD_LABELS[period]}，按选中日）")
                    st.line_chart(pd.DataFrame({"胜率%": trend}))
                elif trend:
                    render.section_title(f"历史胜率趋势（{_PERIOD_LABELS[period]}，按选中日）")
                    st.caption(" · ".join(f"{d} {v}%" for d, v in trend.items())
                               + "（仅一个统计日，暂不成线）")

                render.batch_fold_bar("tv", [f"tv_{r['id']}" for r in shown],
                                      label=f"共 {len(shown)} 个标的")
                for r in shown:
                    pct = _tv_pct(r, period)
                    rating = (r.get("select_rating") or "").strip() or "未评级"
                    # 徽章：按 (select_date, stock_code) 跨查 candidate_tradeable 历史判定
                    _tb_item = tv_badges.get(f"{r.get('select_date')}_{r.get('stock_code')}") or {}
                    _tb_label = _tb_item.get("label") or ""
                    _tb_cls = _TV_BADGE_CLS.get(_tb_label, "badge-mute")
                    _badge_html = (
                        f'<span class="badge {_tb_cls}">{_tb_label or "未判定"}</span>'
                        if _tb_label else  # 未判定时不渲染徽章（避免历史回填日期无 tradeable 数据时全屏徽章噪音）
                        ''
                    )
                    title = f"{render.stock_label(r['stock_code'], r['stock_name'])} · {rating}" + (
                        f"　{_badge_html}" if _badge_html else ""
                    )
                    subtitle = (f"{r.get('select_date')} · {_PERIOD_LABELS[period]} "
                                f"{pct:+.2f}%" if pct is not None
                                else f"{r.get('select_date')} · {_PERIOD_LABELS[period]} 未到周期")
                    dd = r.get("max_drawdown")
                    subtitle += f" · 回撤 {dd:.2f}%" if dd is not None else " · 回撤 —"
                    dot = ("up" if pct is not None and pct > 0
                           else "down" if pct is not None else "mute")
                    meta = (f"{'已到期' if r.get('is_finished') else '追踪中'} · "
                            f"更新 {r.get('update_time') or '—'}")
                    if render.list_item_toggle(key=f"tv_{r['id']}", scope="tv",
                                               title=title, subtitle=subtitle,
                                               dot=dot, meta=meta):
                        with st.container(border=True, key=f"tvdetail_{r['id']}"):
                            vres = r.get("verify_result") or {}
                            periods = vres.get("periods") or {}
                            rows_tbl = []
                            for pk, pl in _PERIOD_LABELS.items():
                                cell = periods.get(pk)
                                rows_tbl.append({
                                    "周期": pl,
                                    "涨跌幅%": (f"{r.get(pk + '_pct'):+.2f}" if r.get(pk + "_pct") is not None else "未到周期"),
                                    "胜负": ("盈利" if cell and cell.get("win")
                                             else "亏损" if cell and cell.get("countable")
                                             else "—"),
                                })
                            st.table(rows_tbl)
                            st.caption(
                                f"基准收盘 {vres.get('base_close', '—')} ｜ "
                                f"最新收盘 {vres.get('latest_close', '—')}"
                                f"（{vres.get('latest_date') or '—'}）｜ "
                                f"最低收盘回撤 {vres.get('drawdown', {}).get('max_pct', '—')}%"
                                f"（{vres.get('drawdown', {}).get('min_close_date') or '—'}）")
                            for note in (vres.get("notes") or []):
                                st.caption(f"· {note}")

# ================= 本期复盘总览（黑盒主界面：只给结果与可执行建议，不给推导） =================
with render.fold_module("overview", "本期复盘总览",
                        meta=f"共 {len(rows)} 笔复盘 · 展示层统计，不含内部推导",
                        default_open=True) as ov_opened:
    if ov_opened:
        if rows_err is not None:
            render.dismissible_error("交易复盘加载失败", "请确认后端服务运行正常后点击「重试」刷新。",
                                     detail=rows_err, retry_key="retry_reviews",
                                     dismiss_key="rev_list")
        else:
            win_sel = st.selectbox("统计窗口", ["近7天", "近30天", _WINDOW_ALL],
                                   key="_ov_window", index=0)
            window_rows = _window_rows(rows, win_sel)
            stats = _calc_stats(window_rows)
            grade, tone = _grade_of(stats)
            with st.container(border=True):
                render.badge(grade, tone)
                st.markdown(f"**一句话总结**：{_summary_text(stats)}")
            avg = stats["avg_pnl"]
            avg_tone = "up" if (avg or 0) > 0 else ("down" if (avg or 0) < 0 else "mute")
            render.stat_cards([
                {"label": "选股胜率", "value": "—" if stats["win_rate"] is None
                 else f"{stats['win_rate'] * 100:.1f}%",
                 "sub": f"盈利 {stats['wins']} / 共 {stats['n']} 笔"},
                {"label": "平均涨幅", "value": "—" if avg is None else f"{avg:+.2f}%",
                 "tone": avg_tone, "sub": f"盈利 {stats['wins']} 笔 · 亏损 {stats['losses']} 笔"},
                {"label": "盈亏比", "value": "—" if stats["pl_ratio"] is None
                 else f"{stats['pl_ratio']:.2f}",
                 "sub": "暂无亏损样本" if stats["pl_ratio"] is None else "平均盈利 / 平均亏损"},
                {"label": "最大回撤", "value": "—" if stats["max_dd"] is None
                 else f"-{stats['max_dd']:.1f}%",
                 "sub": "暂无亏损样本" if stats["max_dd"] is None else "累计盈亏曲线峰值回撤"},
            ])

            # 可执行优化建议（只给「操作项 + 预期效果」，内部推导 reason/evidence 收敛不展示）
            render.section_title("可执行优化建议（人工审核后生效）")
            act_sugs = pending_sugs[:_ACTION_MAX]
            if not act_sugs:
                render.empty_state("暂无待审核优化建议。平仓并复盘后，复盘进化Agent 会自动提出建议。")
            else:
                for s in act_sugs:
                    effect = _TP_KIND_EFFECT.get(s.get("target_kind"), "需人工修改对应规则后生效")
                    clicked = render.list_item(
                        f"ov_act_{s['id']}",
                        f"[{s.get('target_agent')}] {s.get('rule_name')}",
                        subtitle=f"操作项：当前 {s.get('current_value') or '（空）'} → "
                                 f"建议 {s.get('suggested_value')} · 预期效果：{effect}",
                        dot="warn", meta=f'生成 {str(s.get("created_at") or "")[:16]}',
                        actions=("去审核",))
                    if clicked == 0:  # 去审核：展开下方审核区并直达该条建议
                        _jump_sug(s["id"], pending_only=True)

            # 历史走势（真实复盘日期 · 双轨联动 · 框选区间联动下方归因模块）
            render.section_title("历史走势（累计口径）")
            pts = _trend_points(window_rows)
            if sum(p["n"] for p in pts) < _GRADE_CFG["min_samples"]:
                render.empty_state("样本量不足（<3 笔），历史走势待数据积累后呈现。", icon="📊")
            elif _HAS_PLOTLY:
                markers = _build_markers(pts, window_rows, rule_rows, index_items, total_asset)
                fig = _build_trend_figure(pts, markers)
                evt = st.plotly_chart(fig, key="_trend_chart", on_select="rerun",
                                      selection_mode=("box",), height=520,
                                      config={"scrollZoom": True, "displaylogo": False})
                _handle_chart_event(evt, pts)
                st.caption("交互：拖拽框选任意日期区间可联动下方「走势变动分析」；点击节点查看详情；"
                           "平移/缩放被钳制在首尾数据点内（工具栏可切换框选/平移/缩放）。")
                node = st.session_state.get("_node_detail")
                if node:
                    with st.container(border=True):
                        render.msg_card("info", node["title"], node["body"])
                        if st.button("关闭节点详情", key="_node_close"):
                            st.session_state.pop("_node_detail", None)
                            st.rerun()
            else:
                trend = _trend_df(window_rows)
                if trend is None:
                    render.empty_state("该窗口暂无复盘数据，历史走势待数据积累后呈现。", icon="📈")
                else:
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        st.markdown("**胜率走势（累计）**")
                        st.line_chart(trend[["累计胜率%"]], height=240)
                    with tc2:
                        st.markdown("**盈亏比走势（累计）**")
                        if "累计盈亏比" in trend.columns:
                            st.line_chart(trend[["累计盈亏比"]], height=240)
                        else:
                            # 保留 caption：半宽列内子图占位（左侧胜率图已渲染），
                            # empty_state 虚线框在此 2 列布局下视觉过重
                            st.caption("暂无亏损样本，盈亏比曲线待积累。")

# ================= 走势变动分析（黑盒结果区：一句话结论 + 分层归因 + 对应改善建议） =================
with render.fold_module("attribution", "走势变动分析",
                        meta="基于真实复盘数据的分层归因 · 估算项已标注 · 框选图表区间可联动",
                        default_open=True) as at_opened:
    if at_opened:
        if rows_err is not None:
            st.caption("复盘数据不可用，走势归因待数据加载后呈现。")
        else:
            attr_range = st.session_state.get("_attr_range")
            if attr_range:
                win_rows_attr = [r for r in rows
                                 if (str(r.get("exit_date") or "")) >= str(attr_range["start"])
                                 and (str(r.get("exit_date") or "")) <= str(attr_range["end"])]
                h1, h2 = st.columns([4, 1])
                with h1:
                    st.caption(f"已锁定区间 {attr_range['start']} ~ {attr_range['end']}"
                               f"（{attr_range['n']} 笔）· 在图表中拖拽框选可切换区间")
                with h2:
                    if st.button("重置区间", key="_attr_reset", use_container_width=True):
                        st.session_state.pop("_attr_range", None)
                        st.rerun()
            else:
                win_rows_attr = _window_rows(rows, st.session_state.get("_ov_window", "近7天"))
            if len(win_rows_attr) < _GRADE_CFG["min_samples"]:
                render.empty_state("样本量不足（<3 笔），待数据积累后呈现。", icon="📊")
            else:
                dec = _attr_decompose(win_rows_attr, rows, rule_rows, index_items, total_asset)
                stats_attr = _calc_stats(win_rows_attr)
                if dec["flat"]:
                    render.msg_card("info", "本窗口胜率不低于全量历史基准，暂无需归因",
                                    dec["reason"])
                    st.markdown(f"**一句话核心结论**：{_summary_text(stats_attr)}")
                else:
                    label = (f"区间 {attr_range['start']} ~ {attr_range['end']}" if attr_range
                             else f"{st.session_state.get('_ov_window', '近7天')}窗口")
                    concl = (f"{label}共复盘 {dec['win']['n']} 笔："
                             f"胜率 {dec['win']['win_rate'] * 100:.1f}%"
                             f"（全量基准 {dec['base']['win_rate'] * 100:.1f}%），"
                             f"较基准 {dec['gap']:+.1f}pp")
                    if dec["top"]:
                        concl += f"；主要负向因素为「{dec['top']}」（占比 {dec['top_share']:.0f}%）。"
                    st.markdown(f"**一句话核心结论**：{concl}")
                    render.section_title("波动原因分层拆解（估算口径）")
                    sh, notes = dec["shares"], dec["notes"]
                    render.stat_cards([
                        {"label": "标的结构因素", "value": f"{sh['struct']}%",
                         "sub": notes["struct"], "tone": "warn"},
                        {"label": "市场环境因素", "value": f"{sh['market']}%",
                         "sub": notes["market"], "tone": "mute"},
                        {"label": "规则变动因素", "value": f"{sh['rule']}%",
                         "sub": notes["rule"], "tone": "mute"},
                        {"label": "偶发不可控因素", "value": f"{sh['rand']}%",
                         "sub": notes["rand"], "tone": "mute"},
                    ])
                    st.caption("归因口径：Δ = 全量基准胜率 − 窗口胜率（>0 才拆解）；"
                               "规则变动 = 窗口内最早规则变更日前后段胜率差；"
                               "偶发 = 剔除大额亏损笔（单笔超总资产 2%）后胜率回升；"
                               "市场 = 复盘日大盘波动占比（|涨跌幅|≥1%）相对全量的超额；"
                               "标的结构 = 余量。占比为估算值，仅供人工参考，不构成任何交易决策。")
                # 对应改善建议（闭环：看图 → 找因 → 改规则，人工审核后生效）
                render.section_title("对应改善建议（人工审核后生效）")
                act_attr = _match_attr_sugs(pending_sugs, win_rows_attr, dec)
                if not act_attr:
                    render.empty_state("暂无待审核优化建议。平仓并复盘后，复盘进化Agent 会自动提出建议。")
                else:
                    for s in act_attr:
                        effect = (dec.get("counterfactual")
                                  or _TP_KIND_EFFECT.get(s.get("target_kind"),
                                                         "需人工修改对应规则后生效"))
                        clicked = render.list_item(
                            f"attr_act_{s['id']}",
                            f"[{s.get('target_agent')}] {s.get('rule_name')}",
                            subtitle=f"调整方向：{_TP_KIND_EFFECT.get(s.get('target_kind'), '需人工修改对应规则后生效')}"
                                     f" · 预期改善：{effect}",
                            dot="warn", meta=f'生成 {str(s.get("created_at") or "")[:16]}',
                            actions=("查看详情", "去审核"))
                        if clicked == 0:  # 查看详情：直达策略闭环该条建议（不改筛选）
                            _jump_sug(s["id"], pending_only=False)
                        elif clicked == 1:  # 去审核：直达并切「待审核」筛选
                            _jump_sug(s["id"], pending_only=True)

# ================= 策略闭环 · Agent 优化建议（人工审核后生效） =================
with render.fold_module("strategy_loop", "策略闭环 · Agent 优化建议",
                        meta=f"当前 {len(suggestions)} 条 · 人工审核后生效",
                        default_open=False) as sl_opened:
    if sl_opened:
        st.caption("复盘进化Agent 持续跟踪全链路各 Agent 方案落地表现后提出以下建议。"
                   "⚠️ 所有建议必须经你人工审核确认后才生效，系统严格禁止自动、无监督修改任何策略参数。")
        # 状态筛选下拉（API 已支持 status 过滤，零后端改动）
        _FILT_LABEL = {"all": "全部", "pending": "待审核", "approved": "已采纳", "rejected": "已驳回"}
        sel = st.selectbox("状态筛选", list(_FILT_LABEL), index=list(_FILT_LABEL).index(sug_filter),
                           format_func=lambda v: _FILT_LABEL[v], key="_sug_filter_sel")
        if sel != sug_filter:
            st.session_state["_sug_filter"] = sel
            st.rerun()
        if not suggestions:
            st.info("当前筛选条件下暂无策略优化建议。平仓并复盘后，复盘进化Agent 会自动提出建议。")
        else:
            render.batch_fold_bar("sug", [f"sug_{s['id']}" for s in suggestions],
                                  label="点击行内「展开详情」查看完整建议；"
                                        "采纳/驳回仅对待审核建议生效。")
            for s in suggestions:
                key = f"sug_{s['id']}"
                opened = st.session_state.get(f"open_{key}", False)
                status = s.get("status") or "pending"
                rule_type = s.get("rule_type") or "soft"
                is_prompt = s.get("target_kind") == "prompt"
                has_rule_text = bool((s.get("rule_text") or "").strip())
                # 折叠态：标题=归属Agent+规则名；副标题=优化规则摘要（旧版建议回落 当前→建议）；
                # 元信息=类型/优先级徽章 + 状态 + 提交时间（去黑盒：类型与优先级一屏可见）
                summary = (s.get("rule_text") or "").strip()
                if len(summary) > 80:
                    summary = summary[:80] + "…"
                subtitle = (f"优化规则：{summary}" if summary else
                            f"当前 {s['current_value'] or '（空）'} → 建议 {s['suggested_value']}")
                badge_type = "info" if rule_type == "soft" else "err"
                meta = (f'<span class="badge badge-{badge_type}">{html.escape(render.rule_type_label(rule_type))}</span>'
                        f'<span class="badge badge-info">{html.escape(render.rule_priority_label(s.get("priority") or "medium"))}</span>'
                        f' {_SUG_STATUS.get(status, status)} · {str(s.get("created_at") or "")[:16]}')
                clicked = render.list_item(
                    key, f"[{html.escape(s['target_agent'])}] {html.escape(s['rule_name'])}",
                    subtitle=subtitle, dot=_SUG_TONE.get(status, "mute"), meta=meta,
                    actions=("收起详情" if opened else "展开详情", "采纳", "驳回"))
                if clicked == 0:  # 展开/收起详情
                    opened = not opened
                    st.session_state[f"open_{key}"] = opened
                    st.rerun()
                elif clicked == 1 and status == "pending":  # 采纳
                    if not is_prompt:
                        api.approve_suggestion(s["id"])
                        st.success("已采纳，偏好档案已更新。")
                        st.rerun()
                    elif has_rule_text:
                        st.session_state[f"show_adopt_sug_{s['id']}"] = True
                        st.rerun()
                    else:
                        st.info("该建议为旧版规则建议（无落地规则正文），不支持一键采纳；"
                                "可驳回后由 AI 重新生成新版建议。")
                elif clicked == 2 and status == "pending":
                    st.session_state[f"show_reject_sug_{s['id']}"] = True
                    st.rerun()
                if opened or st.session_state.get(f"show_reject_sug_{s['id']}") \
                        or st.session_state.get(f"show_adopt_sug_{s['id']}"):
                    with st.container(border=True):
                        render.trace_line("建议提交时间", s.get("created_at"))
                        # 分区一：问题背景（当前规则缺陷 + 触发案例；根因推导仅专业视图可见）
                        with st.container(border=True):
                            render.section_title("问题背景（当前规则缺陷 + 触发案例）")
                            st.markdown(s.get("problem_desc") or s.get("reason") or "（无）")
                            if pro_view and s.get("evidence"):
                                st.markdown(f"**事实依据**：{s['evidence']}")
                        # 分区二：优化规则全文 + 落地说明 + 预期效果与风险（v2 一键采纳落地信息）
                        if has_rule_text:
                            with st.container(border=True):
                                render.section_title("优化规则（完整条文，采纳后自动注入生效）")
                                st.markdown(f"> {s['rule_text']}")
                            with st.container(border=True):
                                render.section_title("落地说明（全透明）")
                                st.markdown(f"- 规则类型：{render.rule_type_label(rule_type)}（"
                                            f"{'全局底线，全部 Agent 无条件遵守' if rule_type == 'hard' else '参考权重，非死条件'}）")
                                st.markdown(f"- 归属模块：{s['target_agent']} · "
                                            f"优先级：{render.rule_priority_label(s.get('priority') or 'medium')}")
                                if s.get("file_path"):
                                    st.markdown(f"- 文件路径（仅展示元数据）：{s['file_path']}")
                                if s.get("insert_position"):
                                    st.markdown(f"- 建议插入位置：{s['insert_position']}")
                                st.caption("落地方式：系统自动注入（规则存库，全部 Agent 下次任务自动携带，"
                                           "LLM 缓存自动失效），绝不写入源码文件。")
                            with st.container(border=True):
                                render.section_title("预期效果与风险")
                                st.markdown(f"- 预期效果：{s.get('expected_effect') or '（未量化）'}")
                                st.markdown(f"- 风险提示：{s.get('risk_note') or '（无）'}")
                        else:
                            # 旧版建议（无落地信息）：原内容展示 + 不支持一键采纳提示
                            with st.container(border=True):
                                render.section_title("建议内容")
                                st.markdown(f"- 当前值：{s['current_value'] or '（空）'}")
                                st.markdown(f"- 建议值：{s['suggested_value']}")
                                if pro_view:  # 根因推导仅专业视图可见（黑盒收敛）
                                    st.markdown(f"- 问题背景与根因分析：{s['reason']}")
                                    st.markdown(f"- 事实数据依据：{s['evidence']}")
                            st.caption("该建议为旧版规则建议（无落地规则正文），暂不支持一键采纳；"
                                       "可驳回后由 AI 重新生成新版建议。")
                        if status == "approved" and is_prompt:
                            # 采纳后：变更对比 + 回滚入口（查该建议的生效记录）
                            rc_rows = []
                            try:
                                rc_rows = [c for c in (api.rule_changes(suggestion_id=s["id"]) or [])
                                           if c.get("source_suggestion_id") == s["id"]]
                            except Exception:  # noqa: BLE001 记录接口失败降级为成功提示
                                rc_rows = []
                            if rc_rows:
                                render.rule_change_card(rc_rows[0], key=f"rc_{s['id']}")
                            else:
                                st.success("已采纳并自动生效：规则已写入生效表，全部 Agent 下次任务自动携带"
                                           "（LLM 缓存已失效）。可在「规则变更记录」页查看对比与回滚。")
                        if status == "rejected" and s.get("reject_reason"):
                            st.caption(f"已驳回 · 驳回原因：{s['reject_reason']}")
                        # 采纳操作面板（规则类：硬规则需勾选二次确认；软规则直接确认）
                        if status == "pending" and is_prompt and has_rule_text \
                                and st.session_state.get(f"show_adopt_sug_{s['id']}"):
                            with st.container(border=True):
                                render.section_title("一键采纳自动落地（人工确认）")
                                if s.get("conflict_note") or s.get("dedup_note"):
                                    render.msg_card("warn", "采纳校验未通过（可重新尝试）",
                                                    message=s.get("conflict_note") or s.get("dedup_note"))
                                with st.form(key=f"adopt_sug_form_{s['id']}"):
                                    confirm = st.checkbox(
                                        ("我已知晓：该规则为硬性规则（全局底线，全部 Agent 无条件遵守），"
                                         "采纳后立即全局生效；系统会自动执行重复/红线冲突二次校验。"
                                         if rule_type == "hard" else
                                         "确认采纳：该规则将作为参考权重注入全部 Agent 研判上下文，立即生效。"),
                                        key=f"adopt_confirm_{s['id']}")
                                    if st.form_submit_button("确认采纳并自动生效", type="primary"):
                                        if not confirm:
                                            render.msg_card("warn", "请先勾选确认后再提交。")
                                        else:
                                            try:
                                                result = api.adopt_suggestion(s["id"], confirm=bool(confirm))
                                                st.success(f"已采纳并自动生效：{result.get('rule_name', '')}")
                                                st.session_state.pop(f"show_adopt_sug_{s['id']}", None)
                                                st.rerun()
                                            except requests.HTTPError as exc:
                                                render.msg_card("warn", "采纳被拦截（校验未通过）",
                                                                message=_api_error_detail(exc))
                                            except Exception as exc:  # noqa: BLE001 后端不可达统一提示
                                                render.msg_card("err", "采纳失败",
                                                                "请确认后端服务正常运行后重试。", detail=exc)
                        # 驳回强制原因输入（审核留痕，落库可追溯）
                        if status == "pending" and st.session_state.get(f"show_reject_sug_{s['id']}"):
                            with st.form(key=f"reject_sug_form_{s['id']}"):
                                reason = st.text_area(
                                    "驳回原因（必填，多行）",
                                    placeholder="例如：不认可该结论 / 不符合我的交易风格 / 规则过于严格",
                                    key=f"reject_sug_reason_{s['id']}")
                                render.field_error(f"reject_sug_{s['id']}",
                                                    render.get_field_error(f"reject_sug_{s['id']}"),
                                                    "驳回原因必填，请说明不认可的具体理由")
                                if st.form_submit_button("提交驳回（驳回原因留痕）", type="primary"):
                                    if not reason.strip():
                                        render.set_field_errors({f"reject_sug_{s['id']}": "驳回原因不能为空"})
                                    else:
                                        render.set_field_errors({})
                                        api.reject_suggestion(s["id"], reason.strip())
                                        st.success("已驳回，原因已留痕；不修改任何配置。")
                                        st.session_state.pop(f"show_reject_sug_{s['id']}", None)
                                        st.rerun()

# ================= 详情与历史记录（深层折叠：默认完全收起） =================
with render.fold_module("detail_hist", "详情与历史记录",
                        meta=f"共 {len(rows)} 笔复盘 · 默认收起",
                        default_open=False) as dh_opened:
    if dh_opened:
        if rows_err is not None:
            st.caption("复盘数据加载失败，请在上方「本期复盘总览」点击「重试」。")
        else:
            # 筛选防抖：输入后点「查询」才过滤（避免每敲一个字符全页 rerun + 全量请求）
            f_code = st.text_input("按股票代码筛选（留空显示全部，输入后点查询）",
                                   value=st.session_state.get("_rev_filter", ""),
                                   key="_rev_filter_input")
            c1, c2 = st.columns([1, 5])
            with c1:
                if st.button("查询", use_container_width=True):
                    st.session_state["_rev_filter"] = f_code.strip()
                    st.session_state.pop("_rev_list_vis", None)
                    st.rerun()
            with c2:
                if st.session_state.get("_rev_filter"):
                    if st.button("清除筛选"):
                        st.session_state["_rev_filter"] = ""
                        st.session_state.pop("_rev_list_vis", None)
                        st.rerun()
            code = st.session_state.get("_rev_filter", "")
            # 客户端子串过滤（总览聚合用全量，列表按代码过滤）
            list_rows = [r for r in rows
                         if not code or code in str(r.get("stock_code") or "")]

            def _review_detail(r: dict, _i: int) -> None:
                label = render.stock_label(r["stock_code"], r["stock_name"])
                pnl = float(r.get("pnl_pct") or 0)
                # A股配色：盈利红（tier-a）、亏损绿（ok），与全站涨跌色一致
                dot = "tier-a" if pnl >= 0 else "ok"
                suggest = STATUS_MAP.get(r.get("suggest_status") or "pending", "待审核")
                meta = (f'<span class="{"up" if pnl >= 0 else "down"}">'
                        f'{"+" if pnl >= 0 else ""}{r["pnl_pct"]}%</span>　'
                        f'生成 {str(r.get("created_at") or "")[:16]}')
                key = f"review_{r['id']}"
                if render.list_item_toggle(key, label,
                                           subtitle=f"离场 {r['exit_date']} · 持仓 {r['hold_days']} 天"
                                                    f" · 偏好建议 {suggest}",
                                           dot=dot, meta=meta, scope="rev"):
                    with st.container(border=True):
                        render.trace_line("复盘生成时间", r.get("created_at"), source="LLM 生成")
                        # 批次3：详情分区 Tab 化（仍收在「详情与历史记录」折叠内；黑盒规范不变：
                        # 止盈比对/离场归因等算法细节仍仅专业视图可见；采纳/驳回逻辑零改动）
                        suggestion = (r["feedback"] or {}).get("profile_suggestion")
                        adopted = r.get("suggest_status") == "adopted"

                        def _tab_pva():
                            # 计划兑现度（入场逻辑 vs 实际走势，黑盒可见的结论区）
                            render.section_title("计划兑现度")
                            render.render_dict(r["plan_vs_actual"])
                            if pro_view:  # 完整留痕仅专业视图可见
                                render.raw_json_expander(r["plan_vs_actual"], key=f"raw_pva_{r['id']}")

                        def _tab_tp():
                            # 止盈计划兑现比对（预判止盈位 vs 实际卖出价，留痕追溯；仅专业视图可见）
                            render.section_title("止盈计划兑现比对（留痕追溯）")
                            tp_trace = None
                            try:
                                for t in api.traces(code=r["stock_code"], date=r["exit_date"],
                                                    limit=5) or []:
                                    if t.get("source_module") == "position_monitor":
                                        tp_trace = t
                                        break
                            except Exception:  # noqa: BLE001 留痕接口失败降级提示
                                tp_trace = None
                            if tp_trace:
                                try:
                                    concl = json.loads(tp_trace.get("final_conclusion") or "{}")
                                except (json.JSONDecodeError, TypeError):
                                    concl = {}
                                tp1, tp2 = concl.get("tp1"), concl.get("tp2")
                                st.markdown(f"- 预判第一止盈位：**{render.num(tp1 or '—')} 元**；"
                                            f"第二止盈位：**{render.num(tp2 or '—')} 元**"
                                            f"（留痕 {str(tp_trace.get('create_time') or '')[:16]}，"
                                            "source_module=position_monitor）",
                                            unsafe_allow_html=True)
                                exit_prices = []
                                try:
                                    for tr in api.holding_trades(r.get("holding_id") or 0) or []:
                                        if tr.get("side") == "sell" and tr.get("price"):
                                            exit_prices.append(float(tr["price"]))
                                except Exception:  # noqa: BLE001 流水失败降级提示
                                    pass
                                if exit_prices:
                                    avg = sum(exit_prices) / len(exit_prices)
                                    if tp1 and tp2 and avg >= tp2:
                                        verdict = (f"实际卖出均价 {render.num(f'{avg:,.2f}')} ≥ "
                                                   f"第二止盈位 {render.num(tp2)}："
                                                   "到达波段目标，超预期兑现")
                                    elif tp1 and avg >= tp1:
                                        verdict = (f"实际卖出均价 {render.num(f'{avg:,.2f}')} ≥ "
                                                   f"第一止盈位 {render.num(tp1)}："
                                                   "分档锁利生效")
                                    else:
                                        verdict = (f"实际卖出均价 {render.num(f'{avg:,.2f}')} "
                                                   f"低于第一止盈位 {render.num(tp1 or '—')}："
                                                   "未触发止盈分档")
                                    st.markdown(f"- 实际卖出：{render.num(len(exit_prices))} 笔，"
                                                f"均价 {render.num(f'{avg:,.2f}')} 元",
                                                unsafe_allow_html=True)
                                    st.markdown(f"- **比对结论**：{verdict}", unsafe_allow_html=True)
                                else:
                                    st.caption("无卖出流水记录，无法比对实际卖出价。")
                            else:
                                st.caption("离场日无 position_monitor 留痕（止盈计划功能上线前的"
                                           "历史离场，无法回溯预判止盈位；留痕数据可供复盘进化"
                                           "Agent 后续做止盈准确率统计）。")

                        def _tab_sell():
                            # 离场决策维度归因（白盒；回溯 SellAgent 离场决策维度依据；仅专业视图可见）
                            render.section_title("离场决策维度归因（白盒追溯）")
                            sell_hist = []
                            try:
                                sell_hist = api.sell_decisions(r.get("holding_id") or 0) or []
                            except Exception:  # noqa: BLE001 决策接口失败降级提示，不阻塞复盘
                                sell_hist = []
                            sell_d = (sell_hist[0].get("decision") or {}) if sell_hist else {}
                            if sell_d:
                                render.dimension_bars(sell_d.get("dimensions"),
                                                      final_advice=sell_d.get("final_advice"))
                                if sell_d.get("reasons"):
                                    st.markdown("**决策依据**")
                                    for i, rr in enumerate(sell_d["reasons"], 1):
                                        st.markdown(f"{i}. {rr}")
                                render.time_text("决策时间", sell_hist[0].get("created_at"))
                            else:
                                st.caption("无离场卖出决策记录（手动卖出或历史数据），"
                                           "维度归因留痕在「持仓监控」页生成卖出决策后自动记录。")

                        def _tab_lesson():
                            # 经验教训
                            render.section_title("经验教训")
                            st.markdown(r["lesson"] or "（无）")

                        def _tab_feedback():
                            # 筛选偏好微调建议
                            render.section_title("筛选偏好微调建议")
                            render.render_dict(r["feedback"])
                            if pro_view:  # 完整留痕仅专业视图可见
                                render.raw_json_expander(r["feedback"], key=f"raw_fb_{r['id']}")

                        def _tab_sugg():
                            # 交易偏好优化建议（版本迭代 + 采纳/驳回，人工审核后生效）
                            render.section_title("交易偏好优化建议（人工审核后生效）")
                            st.markdown(f"第 {r.get('suggest_iteration', 1)} 版 · "
                                        f"状态：{suggest}：修改 `{suggestion['field']}` → "
                                        f"{suggestion['value']}")
                            if pro_view:  # 推导理由仅专业视图可见
                                st.caption(f"理由：{suggestion['reason']}")

                            if pro_view:  # 迭代历史深层收敛
                                history = r.get("suggest_history") or []
                                if history:
                                    with st.expander(f"查看迭代历史（共 {len(history)} 轮，默认收起）"):
                                        for h in reversed(history):
                                            it = h.get("suggestion") or {}
                                            if it:
                                                st.markdown(f"**第 {h.get('iteration')} 版**：修改 "
                                                            f"`{it.get('field')}` → {it.get('value')}")
                                                st.caption(f"建议理由：{it.get('reason')}")
                                            else:
                                                st.markdown(f"**第 {h.get('iteration')} 版**：无字段建议")
                                            st.warning(f"驳回原因：{h.get('reject_reason')}")
                                            st.divider()

                            if adopted:
                                st.success("该建议已采纳并写入偏好档案，全部 Agent 立即生效。")
                            else:
                                c1, c2 = st.columns(2)
                                with c1:
                                    if st.button("采纳建议并更新偏好档案", key=f"adopt_{r['id']}"):
                                        result = api.adopt_review(r["id"])
                                        st.success(f"已采纳：{result['field']}，"
                                                   f"偏好档案版本 v{result['version']}，立即生效")
                                        st.rerun()
                                with c2:
                                    if st.button("驳回", key=f"reject_btn_{r['id']}"):
                                        st.session_state[f"show_reject_{r['id']}"] = True
                                        st.rerun()
                                if st.session_state.get(f"show_reject_{r['id']}"):
                                    with st.form(key=f"reject_form_{r['id']}"):
                                        reason = st.text_area(
                                            "驳回原因（必填，多行）",
                                            placeholder="例如：不认可该结论 / 不符合我的交易风格"
                                                        " / 规则过于严格",
                                            key=f"reject_reason_{r['id']}")
                                        # 驳回原因必填：原位标红 + 填写指引，不整段报错
                                        render.field_error(
                                            f"reject_{r['id']}",
                                            render.get_field_error(f"reject_{r['id']}"),
                                            "驳回原因必填，请说明不认可的具体理由")
                                        if st.form_submit_button("提交驳回，让 AI 重新思考",
                                                                 type="primary"):
                                            if not reason.strip():
                                                render.set_field_errors(
                                                    {f"reject_{r['id']}": "驳回原因不能为空"})
                                            else:
                                                render.set_field_errors({})
                                                res = api.reject_review(r["id"], reason.strip())
                                                st.success("已驳回，AI 重思考任务已提交后台"
                                                           f"（{res.get('task_id')}），"
                                                           "完成后顶部任务状态区会提示。")
                                                st.session_state.pop(f"show_reject_{r['id']}", None)
                                                st.rerun()

                        _sections = [("计划兑现度", _tab_pva)]
                        if pro_view:
                            _sections.append(("止盈比对", _tab_tp))
                            _sections.append(("离场维度归因", _tab_sell))
                        _sections.append(("经验教训", _tab_lesson))
                        _sections.append(("偏好微调", _tab_feedback))
                        if suggestion:
                            _sections.append(("优化建议", _tab_sugg))
                        render.detail_tabs(_sections, key=f"review_tabs_{r['id']}", default_index=0)
            t1, t2, t3 = st.tabs(["每日复盘报告", "失效标的明细", "分评级分组统计"])
            with t1:
                if not list_rows:
                    render.empty_state("暂无复盘记录。在「持仓监控」页录入人工卖出（全部卖出）后自动触发复盘。")
                else:
                    rev_keys = [f"review_{r['id']}" for r in list_rows]
                    render.batch_fold_bar("rev", rev_keys,
                                          label="点击行内「查看详情」展开完整复盘分区内容。")
                    render.record_list(list_rows, _review_detail, batch=20, key="_rev_list_vis",
                                       empty_text="无匹配的复盘记录。")
            with t2:
                losers = [r for r in list_rows if (_pnl(r) or 0) < 0]
                if not losers:
                    render.empty_state("暂无亏损/失效标的。失效标的明细将随亏损复盘积累自动呈现。")
                else:
                    render.batch_fold_bar("rev", [f"review_{r['id']}" for r in losers],
                                          label="点击「查看详情」展开该失效标的完整复盘。")
                    render.record_list(losers, _review_detail, batch=20, key="_rev_losers_vis",
                                       empty_text="无匹配的失效标的。")
            with t3:
                groups = {"盈利": [], "亏损": [], "持平": []}
                for r in list_rows:
                    p = _pnl(r)
                    if p is None:
                        continue
                    groups["盈利" if p > 0 else "亏损" if p < 0 else "持平"].append(p)
                if not any(groups.values()):
                    render.empty_state("暂无分组统计数据。")
                else:
                    render.stat_cards([
                        {"label": "盈利笔数", "value": len(groups["盈利"]), "tone": "ok",
                         "sub": "—" if not groups["盈利"] else
                         f"平均 {sum(groups['盈利']) / len(groups['盈利']):+.2f}%"},
                        {"label": "亏损笔数", "value": len(groups["亏损"]), "tone": "err",
                         "sub": "—" if not groups["亏损"] else
                         f"平均 {sum(groups['亏损']) / len(groups['亏损']):+.2f}%"},
                        {"label": "持平笔数", "value": len(groups["持平"]), "tone": "mute",
                         "sub": "盈亏 0.00%"},
                    ])
