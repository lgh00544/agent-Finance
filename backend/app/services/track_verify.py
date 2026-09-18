"""候选池标的 T+N 自动追踪验证（选股效果闭环·代码侧客观统计）

职责边界（【刚性代码逻辑】）：只做客观统计与建议生成，不做市场判断；
所有"候选池选股质量如何改进"的定性建议在提示词层（track_verify_prompt）。

口径（定稿）：
- T+N 涨跌幅 = (选中日后第 N 个交易日收盘 / base_close_price − 1) × 100；
  第 N 周期成立条件 t0 + N < len(dates)（选中日收盘为 t0，日 K 仅含交易日）；
  不足 → 对应列存 null、不参与统计、不标记完成。
- max_drawdown = 相对 base_close_price 的区间最低收盘回撤
  max(0, (base_close − min(closes[t0:])) / base_close × 100)，记录最低收盘日期。
  用收盘价、与涨跌幅同一基准可比（先涨后回落不双计为高涨幅+大回撤）。
- daily_path = 从选中日 t0 起逐交易日记录已确认收盘路径，供后续 Agent 做观察与归因；
  不足 T+N 也会保留已发生事实，禁止使用未确认当天日K。

【系统监管红线】
- 建议全部落 agent_suggestion（status=pending），任何规则调整必须经人工审核
  确认后才生效（既有 adopt/reject/rollback 审核闭环）；
- 建议生成 LLM 为主、确定性模板兜底，来源强制标记（llm/template）；
- 主链路幂等：初始化天然去重 + 唯一约束，重复执行安全。
"""
import hashlib
import json
import logging
import time
from datetime import datetime

from app.agents.schemas import TrackVerifyOutput
from app.cache import cache
from app.db import repo
from app.llm.structured import ModelLevel

logger = logging.getLogger(__name__)

TRACK_PERIODS = (3, 5, 10)   # T+N 验证周期（交易日）
_WIN_LOW = 40.0              # 总体胜率 < 40% → 胜率过低异常
_MIN_SAMPLE = 3              # 分组样本下限（低于不参与异常判定/模板建议，防小样本误判）
_LOCK_TTL = 7200             # 主链路锁（2 小时，覆盖一次完整验证）
_MAX_ERRORS = 20             # 单次链路错误记录上限（防日志与响应膨胀）
_PERF_SUMMARY_TTL = 1800     # 选股表现摘要缓存（30 分钟，与组合哨兵同节奏）
_PERF_SUMMARY_SAMPLE = 20    # 选股表现回顾样本数（近 20 只有到期数据的候选）
_PERIOD_LABELS = {"t3": "T+3", "t5": "T+5", "t10": "T+10"}
_CLOSE_CONFIRM_HOUR = 16     # 16:00 后才把当天日K视为收盘确认数据

# ==================== 因子回测校准闭环（评级重做-C） ====================
_FACTOR_NAMES = ("动量", "催化", "估值", "主线契合", "资金面", "基本面质量")
_FACTOR_HIGH = 7        # 高分阈值（≥7 为高分组）
_FACTOR_LOW = 3         # 低分阈值（≤3 为低分组）
_FACTOR_MIN_GROUP = 3   # 每组最少样本（沿用 _MIN_SAMPLE，防小样本误判）
_CALIBRATION_THRESHOLD = 5.0   # avg_pct 差值超过此值才生成校准建议
_CALIBRATION_TTL = 3600        # 因子校准摘要缓存（1 小时）
_FACTOR_DEFAULT_WEIGHTS = {
    "动量": "20%", "催化": "20%", "估值": "15%",
    "主线契合": "15%", "资金面": "15%", "基本面质量": "15%",
}


# ==================== T+N 计算（纯函数，可单测） ====================

def _norm_kline(kline_df):
    """日K规整：抽取 (date, close) 两列，脏值/NaN 丢弃；空返回 None。
    对齐 hot_money_review._forward_5d_returns 的规整模式。"""
    if kline_df is None or getattr(kline_df, "empty", True):
        return None
    try:
        dates, closes = [], []
        for _, row in kline_df.iterrows():
            d = str(row["date"]).strip()
            c = row["close"]
            try:
                c = float(c)
            except (TypeError, ValueError):
                continue
            if d and c == c:  # NaN 自比较不等
                dates.append(d)
                closes.append(c)
    except (KeyError, TypeError):
        return None
    return (dates, closes) if dates else None


def compute_tn_metrics(dates: list[str], closes: list[float],
                       base_close: float, select_date: str) -> dict:
    """核心纯函数：计算 T+3/T+5/T+10 涨跌幅与最大回撤。

    返回 {t3/t5/t10: {"pct": float|None}, "max_drawdown": float|None,
          "min_close_date": str|None, "due": bool, "notes": [...]}
    select_date 不在 dates 中 → 抛 ValueError（调用方降级跳过）。"""
    if select_date not in dates:
        raise ValueError(f"选中日 {select_date} 不在日K数据中")
    t0 = dates.index(select_date)
    base = base_close if base_close and base_close > 0 else closes[t0]

    periods: dict[str, dict] = {}
    notes: list[str] = []
    for n in TRACK_PERIODS:
        key = f"t{n}"
        if t0 + n < len(dates):
            pct = round((closes[t0 + n] / base - 1) * 100, 2)
            periods[key] = {"pct": pct}
        else:
            periods[key] = {"pct": None}
            notes.append(f"T+{n} 数据不足（需 {n} 个交易日），暂不统计")

    window = closes[t0:]
    min_close = min(window)
    max_drawdown = round(max(0.0, (base - min_close) / base * 100), 2)
    min_close_date = dates[t0 + window.index(min_close)] if max_drawdown > 0 else None

    due = periods["t10"]["pct"] is not None
    return {"t3": periods["t3"], "t5": periods["t5"], "t10": periods["t10"],
            "max_drawdown": max_drawdown, "min_close_date": min_close_date,
            "due": due, "notes": notes}


def confirmed_kline_points(dates: list[str], closes: list[float],
                           now: datetime | None = None) -> tuple[list[str], list[float]]:
    """过滤未确认日K：盘中数据源可能返回当天正在形成的日K，16:00 前不得用于 T+N。"""
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    include_today = now.hour >= _CLOSE_CONFIRM_HOUR
    pairs = [
        (d, c) for d, c in zip(dates, closes)
        if d < today or (d == today and include_today)
    ]
    return [d for d, _ in pairs], [c for _, c in pairs]


def build_daily_path(dates: list[str], closes: list[float],
                     base_close: float, select_date: str,
                     max_days: int = 10) -> list[dict]:
    """选中日起逐交易日事实路径；调用方需先过滤未确认日K。

    day_n=0 为选中日收盘基准；后续仅记录已经发生的交易日，最多到 T+10。
    attention_flags 只是客观触发项，供归因 Agent 消费，不直接改变策略规则。"""
    if select_date not in dates:
        raise ValueError(f"选中日 {select_date} 不在日K数据中")
    t0 = dates.index(select_date)
    base = base_close if base_close and base_close > 0 else closes[t0]
    end = min(len(dates), t0 + max_days + 1)
    path: list[dict] = []
    min_close = base
    for i in range(t0, end):
        day_n = i - t0
        close = closes[i]
        pct_from_base = round((close / base - 1) * 100, 2)
        daily_pct = None if i == t0 else round((close / closes[i - 1] - 1) * 100, 2)
        min_close = min(min_close, close)
        drawdown_from_base = round(max(0.0, (base - min_close) / base * 100), 2)
        flags: list[str] = []
        if pct_from_base <= -3:
            flags.append("累计跌幅>=3%")
        if daily_pct is not None and daily_pct <= -3:
            flags.append("单日跌幅>=3%")
        if drawdown_from_base >= 5:
            flags.append("最大回撤>=5%")
        path.append({
            "date": dates[i],
            "day_n": day_n,
            "close": round(close, 4),
            "pct_from_base": pct_from_base,
            "daily_pct": daily_pct,
            "drawdown_from_base": drawdown_from_base,
            "attention_flags": flags,
        })
    return path


# ==================== 统计（纯函数，可单测） ====================

def _group_stats(items: list[dict]) -> dict:
    """单组统计（countable=周期列非 null 才参与）"""
    pcts = [i["pct"] for i in items if i["pct"] is not None]
    n = len(pcts)
    if n == 0:
        return {"n": 0, "wins": 0, "win_rate": None, "avg_pct": None,
                "pl_ratio": None, "avg_max_dd": None}
    wins = sum(1 for p in pcts if p > 0)
    avg_pct = round(sum(pcts) / n, 2)
    gains = sum(p for p in pcts if p > 0)
    losses = sum(p for p in pcts if p < 0)
    pl_ratio = round(gains / abs(losses), 2) if losses < 0 else None
    dds = [i.get("max_drawdown") for i in items if i.get("max_drawdown") is not None]
    return {"n": n, "wins": wins, "win_rate": round(wins / n * 100, 1),
            "avg_pct": avg_pct, "pl_ratio": pl_ratio,
            "avg_max_dd": round(sum(dds) / len(dds), 2) if dds else None}


def compute_stats(rows: list[dict], period: str = "t5") -> dict:
    """从追踪验证行计算周期统计（代码侧事实，前端展示与建议生成共用）。

    返回 {period, n, wins, win_rate, avg_pct, pl_ratio, avg_max_dd,
          by_rating: {评级: 组统计}, by_date: {日期: 组统计}}"""
    col = f"{period}_pct"
    items = [{"pct": r.get(col), "max_drawdown": r.get("max_drawdown"),
              "select_rating": (r.get("select_rating") or "").strip() or "未知",
              "select_date": r.get("select_date")} for r in rows]
    stats = {"period": period, **_group_stats(items), "by_rating": {}, "by_date": {}}

    by_rating: dict[str, list[dict]] = {}
    by_date: dict[str, list[dict]] = {}
    for i in items:
        by_rating.setdefault(i["select_rating"], []).append(i)
        by_date.setdefault(i["select_date"], []).append(i)
    for key in sorted(by_rating):
        stats["by_rating"][key] = _group_stats(by_rating[key])
    for key in sorted(by_date):
        stats["by_date"][key] = _group_stats(by_date[key])
    return stats


def detect_anomalies(stats: dict) -> list[dict]:
    """确定性异常检测（供建议生成注入；全部要求样本≥3 防小样本误判）：
    - consecutive_decline: 按日期时间序胜率连续 3 期下降（每期样本≥3）
    - rating_inversion:    评级 A/B/C 两两对比，高评级档 avg_pct < 低评级档 avg_pct
                           （评级越高反而涨得越差 → 倒挂）。pair 语义统一为"高<低"（如 "A<C"=A 档低于 C 档）
    - win_rate_low:        总体胜率 < 40% 且 n≥3
    返回 [{type, desc, data}]（data 为事实数值，模板建议引用）"""
    anomalies: list[dict] = []

    by_date = stats.get("by_date", {})
    dates = sorted(by_date)
    usable = [d for d in dates if by_date[d]["n"] >= _MIN_SAMPLE]
    if len(usable) >= 3:
        rates = [by_date[d]["win_rate"] for d in usable[-3:]]
        if all(r is not None for r in rates) and rates == sorted(rates, reverse=True) \
                and len(set(rates)) == 3:
            anomalies.append({"type": "consecutive_decline",
                              "desc": "候选池胜率连续 3 期下降",
                              "data": {d: by_date[d]["win_rate"] for d in usable[-3:]}})

    by_rating = stats.get("by_rating", {})
    # 全档位两两对比（只保留"高评级在前、低评级在后"），倒挂判定统一为 high_avg < low_avg
    for high, low in (("A", "B"), ("A", "C"), ("B", "C")):
        hi, lo = by_rating.get(high), by_rating.get(low)
        if not (hi and lo and hi["n"] >= _MIN_SAMPLE and lo["n"] >= _MIN_SAMPLE
                and hi["avg_pct"] is not None and lo["avg_pct"] is not None):
            continue
        if lo["avg_pct"] > hi["avg_pct"]:
            anomalies.append({"type": "rating_inversion",
                              "desc": f"{low} 档平均涨幅高于 {high} 档（评级正相关性倒挂）",
                              "data": {"pair": f"{high}<{low}",
                                       high: {"n": hi["n"], "avg_pct": hi["avg_pct"]},
                                       low: {"n": lo["n"], "avg_pct": lo["avg_pct"]}}})

    if stats["n"] >= _MIN_SAMPLE and stats["win_rate"] is not None \
            and stats["win_rate"] < _WIN_LOW:
        anomalies.append({"type": "win_rate_low",
                          "desc": f"候选池{stats['period']}周期胜率低于 {_WIN_LOW:.0f}%",
                          "data": {"n": stats["n"], "wins": stats.get("wins", 0),
                                   "win_rate": stats["win_rate"],
                                   "avg_pct": stats["avg_pct"]}})
    return anomalies


def build_stats_json(stats: dict, anomalies: list[dict]) -> str:
    """stats + anomalies → 紧凑 JSON 字符串（LLM user prompt 与缓存键共用）"""
    dates = sorted(stats.get("by_date", {}))
    return json.dumps({"stats": stats, "anomalies": anomalies,
                       "evidence_scope": {
                           "kind": "descriptive_candidate_returns",
                           "period": stats.get("period"),
                           "select_date_start": dates[0] if dates else None,
                           "select_date_end": dates[-1] if dates else None,
                           "selection_dates": len(dates),
                           "window_note": "输入包含的候选样本，不能改称近20个交易日；各周期到期样本可能不同",
                           "return_basis": "入选基准价到T+N收盘的候选收益，未验证实际入场成交和费用",
                           "pl_ratio_definition": "盈利总额/亏损绝对值总额（利润因子），不是单笔计划盈亏比",
                           "rating_provenance_verified": False,
                           "rule_effect_validated": False,
                           "limitations": [
                               "评级可能混用Score与Discover，未按来源和规则版本统一",
                               "没有候选通过与被拦截组的同口径对照、特征覆盖率或样本外验证",
                               "同日和重复股票并非独立样本，收益与市场暴露可能相关",
                               "最大回撤为入选后的结果，不能直接当作入选前过滤特征",
                           ],
                       }},
                      ensure_ascii=False, default=str)


def get_selection_performance_summary(period: str = "t5") -> str:
    """选股表现回顾（紧凑文本，供 DiscoverAgent 注入；单向只读本模块统计，不改任何逻辑）。
    读 repo.list_track_verify() → 过滤 {period}_pct IS NOT NULL → select_date DESC 取前 20
    → compute_stats → detect_anomalies → 格式化紧凑文本；结果缓存 _PERF_SUMMARY_TTL 秒。
    口径：近 20 只有到期数据的候选（近期感知），与前端/API 全量口径有意不同，禁止统一。
    无数据/读取失败 → 返回空字符串（调用方不注入、不报错、不阻塞）。"""
    key = f"selection:perf_summary:{period}"
    try:
        cached = cache.get(key)
        if cached:
            return cached
        rows = repo.list_track_verify()
    except Exception as exc:  # noqa: BLE001 读失败不阻塞注入
        logger.warning("选股表现摘要读取失败（跳过注入）: %s", exc)
        return ""
    items = [r for r in rows if r.get(f"{period}_pct") is not None]
    if not items:
        return ""
    # list_track_verify 已按 select_date DESC 排序，过滤后前 20 即最近 20 只有到期数据的候选
    stats = compute_stats(items[:_PERF_SUMMARY_SAMPLE], period=period)
    text = _format_perf_summary(stats, detect_anomalies(stats),
                                _PERIOD_LABELS.get(period, "T+N"))
    if text:
        try:
            cache.set(key, text, _PERF_SUMMARY_TTL)
        except Exception as exc:  # noqa: BLE001 缓存失败不影响注入
            logger.warning("选股表现摘要缓存写入失败: %s", exc)
    return text


# ==================== 前瞻兑现对照事实（Discover 第 5 子 Agent 输入切片） ====================
# 纯统计、零 LLM。为 shortlist 每只拼一段【前瞻对照事实】，供 Discover 终选做 延续/回归/回吐 判断。
# 数据来源仅：初选威科夫列 + enrich 资金列 + candidate_track_verify（复用现有统计）。
# 铁律：缺列/失败写「数据不足」，禁止编造、禁止 LLM 算这些数、禁止「延续概率 70%」这类模型分。
#
# 【D1 决策】同类 T+5 分组维度 = select_rating（A/B/C 信心档），非 pos_52w 位置桶。
#   实测历史 candidate_track_verify 57 条仅 8 条 snapshot 含 pos_52w（其余早于威科夫列加入，
#   stock_type 历史也从未落库）。按位置桶近期必然样本不足；select_rating 100% 落库且直接对应
#   同类信念强度，故同类桶退回 confidence-tier 档。单测须锁死此边界。
_HORIZON_MIN_SAMPLE = 5      # 同类桶样本下限（写入注入事实的阈值；以下写「样本不足」）
_HORIZON_SELF_MAX = 2        # 自身历史入选最多展示次数


def _fmt_float(v, suffix="%"):
    """数值格式化：None/非数值 → '数据不足'；否则保留 1 位小数 + 后缀"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "数据不足"
    if f != f:  # NaN
        return "数据不足"
    return f"{f:.1f}{suffix}"


def build_horizon_context(shortlist: list[dict], data_enrichment: dict,
                          trade_date: str | None = None) -> str:
    """逐 shortlist 候选组装【前瞻对照事实】文本段（供 Discover 终选注入）。
    shortlist: LLM 初选输出（含威科夫列 pos_52w/pct_change_5d/dist_52w_high_pct/
               ma20_pos_pct/ma60_pos_pct/vol_5_20 与 confidence_tier/horizon_bias/horizon_clarity）；
    data_enrichment: {code: enrich}，enrich 含 main_net_3d/5d/10d（有则给，无则标注不可用）；
    trade_date: 选入日（缺省取当日；仅用于前瞻快照落库，discover 顺带调用不传则用 today）。
    返回多行文本；任何一只数据不足只影响该只，整段异常返回空串（调用方省略，终选退回今日行为）。
    副作用：逐候选同步落库前瞻三态快照（预测性选股 2.5 衔接点，save_forward_view 内部 skip missing）。"""
    if not shortlist:
        return ""
    try:
        track_rows = repo.list_track_verify(limit=500)
    except Exception as exc:  # noqa: BLE001 读失败整段省略，不阻塞终选
        logger.warning("前瞻对照统计读取失败（省略前瞻段）: %s", exc)
        return ""

    # 同类 T+5 分组：按 select_rating（A/B/C 信心档）→ _group_stats（样本含 t5_pct 才计入）
    t5_by_rating: dict[str, list[dict]] = {}
    self_history: dict[str, list[dict]] = {}
    for r in track_rows:
        code, date = r.get("stock_code"), r.get("select_date")
        if r.get("t5_pct") is not None:
            rating = (r.get("select_rating") or "").strip() or "未知"
            t5_by_rating.setdefault(rating, []).append({"pct": r.get("t5_pct")})
        if code and date:
            self_history.setdefault(code, []).append(
                {"select_date": date, "t3": r.get("t3_pct"), "t5": r.get("t5_pct")})
    rating_stats = {k: _group_stats(v) for k, v in t5_by_rating.items()}
    # 自身历史按 select_date 降序（list_track_verify 已按 select_date DESC）
    for code in self_history:
        self_history[code] = self_history[code][:_HORIZON_SELF_MAX]

    blocks = []
    for cand in shortlist:
        code = cand.get("stock_code") or cand.get("code") or ""
        name = cand.get("stock_name") or cand.get("name") or ""
        enrich = data_enrichment.get(code) or {}

        # —— 位置/量能行 ——
        pos_line = (f"位置：5日斜率 {_fmt_float(cand.get('pct_change_5d'))}；"
                    f"距52周高点 {_fmt_float(cand.get('dist_52w_high_pct'))}；"
                    f"区间位置 {_fmt_float(cand.get('pos_52w'))}；"
                    f"MA20 {_fmt_float(cand.get('ma20_pos_pct'))} / MA60 {_fmt_float(cand.get('ma60_pos_pct'))}；"
                    f"量能5/20 {_fmt_float(cand.get('vol_5_20'))}")

        # —— 资金行（3/5/10 日主力净额，enrich 无则标注不可用）——
        m3, m5, m10 = (enrich.get("main_net_3d"), enrich.get("main_net_5d"),
                       enrich.get("main_net_10d"))
        money_val = lambda v: f"{float(v) / 100000000:.2f}亿" if v not in (None, "") else "无"  # noqa: E731
        money_line = (f"资金：3/5/10日主力 {money_val(m3)}/{money_val(m5)}/{money_val(m10)}"
                      + ("（当日主力资金可用）" if any(v not in (None, "") for v in (m3, m5, m10))
                         else "（当日资金不可用）"))

        # —— 同类 T+5（confidence-tier 桶）——
        cand_rating = (cand.get("confidence_tier") or "").strip()
        g = rating_stats.get(cand_rating) if cand_rating else None
        if cand_rating and g and g.get("n", 0) >= _HORIZON_MIN_SAMPLE:
            wr = f"{g['win_rate']:.1f}%" if g["win_rate"] is not None else "数据不足"
            avg = f"{g['avg_pct']:+.2f}%" if g["avg_pct"] is not None else "数据不足"
            peer_line = (f"同类T+5：桶={cand_rating} 档 样本={g['n']} 胜率={wr} 均收益={avg}"
                         f"（{_HORIZON_MIN_SAMPLE} 个以上可用样本，可作为对照）")
        else:
            n_txt = f"（现有 {g['n']} 个）" if g and g.get("n") else ""
            peer_line = f"同类T+5：桶={cand_rating or '未知'} 档 样本不足{n_txt}，禁止当作结论（需≥{_HORIZON_MIN_SAMPLE}）"

        # —— 自身历史入选 ——
        hist = self_history.get(code) or []
        if hist:
            parts = []
            for h in hist:
                t3 = f"{h['t3']:+.2f}%" if h.get("t3") is not None else "—"
                t5 = f"{h['t5']:+.2f}%" if h.get("t5") is not None else "—"
                parts.append(f"{h['select_date']} T3={t3} T5={t5}")
            hist_line = "自身历史入选：" + "；".join(parts)
        else:
            hist_line = "自身历史入选：无"

        blocks.append(f"【前瞻对照】{code} {name}\n{pos_line}\n{money_line}\n{peer_line}\n{hist_line}")

        # 预测性选股 2.5 衔接点：同步落库前瞻三态快照（discover 计算时顺带存；
        # horizon_clarity=低 → missing_data 跳过；trade_date+stock_code 唯一，重复更新）
        if code:
            try:
                from datetime import date
                from app.services.forward_view_history import save_forward_view
                save_forward_view(
                    stock_code=code,
                    trade_date=trade_date or date.today().isoformat(),
                    horizon_bias=cand.get("horizon_bias") or "",
                    horizon_clarity=cand.get("horizon_clarity") or "",
                    signals={"position": pos_line, "money": money_line,
                             "peer": peer_line, "history": hist_line,
                             "note": cand.get("horizon_note") or ""},
                )
            except Exception as exc:  # noqa: BLE001 快照落库失败不影响前瞻段
                logger.warning("前瞻快照落库失败（不影响前瞻段）: %s", exc)

    return "\n\n".join(blocks)


def _format_perf_summary(stats: dict, anomalies: list[dict], period_label: str = "T+5") -> str:
    """统计 + 异常 → 紧凑文本（客观事实；win_rate/avg_pct/pl_ratio 为 None 时降级不报错；
    分评级仅展示样本≥3 的档位；异常只列事实 desc+data，不给结论）。"""
    n = stats.get("n") or 0
    if n == 0:
        return ""
    wr, avg, pl = stats.get("win_rate"), stats.get("avg_pct"), stats.get("pl_ratio")
    wr_txt = f"{wr:.1f}%" if wr is not None else "（无数据）"
    avg_txt = f"{avg:+.2f}%" if avg is not None else "（无数据）"
    pl_txt = f"{pl:.2f}" if pl is not None else "无亏损样本"
    lines = [f"近 {n} 只候选：{period_label}胜率 {wr_txt} / 平均涨幅 {avg_txt} / 盈亏比 {pl_txt}"]
    ratings = []
    for r in ("A", "B", "C"):  # 只取 A/B/C 档，过滤「未知」等其他键
        g = stats.get("by_rating", {}).get(r)
        if g and g.get("n", 0) >= _MIN_SAMPLE:
            rw, ra = g.get("win_rate"), g.get("avg_pct")
            ratings.append(
                f"{r} 档：胜率 {f'{rw:.1f}%' if rw is not None else '（无数据）'}"
                f"（n={g['n']}）平均涨幅 {f'{ra:+.2f}%' if ra is not None else '（无数据）'}")
    if ratings:
        lines.append("分评级（各档样本≥3）：" + " ｜ ".join(ratings))
    if anomalies:
        lines.append("异常提示（仅列事实，不做结论）：")
        for a in anomalies:
            data = a.get("data") or {}
            facts = "；".join(f"{k} {v}" for k, v in data.items())
            lines.append(f"- {a.get('desc', '')}：{facts}")
    lines.append("以上为你的近期选股表现回顾，请结合表现适当调整筛选严格度"
                 "（表现差时提高标准，表现好时保持）。此为参考信息，不改变已有规则。")
    return "\n".join(lines)


# ==================== 因子回测校准闭环（评级重做-C） ====================

def _group_stats_simple(pcts: list[float]) -> dict:
    """简化的组统计（只算 n/wins/win_rate/avg_pct）"""
    n = len(pcts)
    if n == 0:
        return {"n": 0, "wins": 0, "win_rate": None, "avg_pct": None}
    wins = sum(1 for p in pcts if p > 0)
    return {
        "n": n,
        "wins": wins,
        "win_rate": round(wins / n * 100, 1),
        "avg_pct": round(sum(pcts) / n, 2),
    }


def compute_factor_correlation(rows: list[dict], period: str = "t5") -> dict:
    """因子相关性分析（纯函数，可单测）。

    输入：track_verify 行列表（需含 factor_scores 和 {period}_pct）
    输出：{
        "period": "t5",
        "n_total": 40,           # 总行数
        "n_with_factors": 25,    # 有因子分的行数
        "factors": {
            "动量": {
                "high": {"n": 8, "win_rate": 62.5, "avg_pct": 2.1},
                "low":  {"n": 5, "win_rate": 40.0, "avg_pct": -1.2},
                "status": "effective",   # effective/ineffective/neutral/insufficient_sample
                "win_rate_diff": 22.5,
                "avg_pct_diff": 3.3
            },
            ...
        },
        "calibration_notes": [...]
    }

    口径：
    - 高分组 = 该因子分值 ≥ 7 的候选；低分组 = 该因子分值 ≤ 3 的候选
    - 每组样本 < 3 → status="insufficient_sample"，不参与比较
    - win_rate_diff = high.win_rate - low.win_rate（>10pp = effective, <-10pp = ineffective）
    - avg_pct_diff = high.avg_pct - low.avg_pct
    """
    col = f"{period}_pct"
    # 只取有因子分且有 T+N 数据的行
    usable = []
    for r in rows:
        fs = r.get("factor_scores")
        pct = r.get(col)
        if not isinstance(fs, list) or not fs or pct is None:
            continue
        # 转为 {因子名: 分值} 字典
        factor_map = {}
        for f in fs:
            if isinstance(f, dict) and f.get("factor"):
                try:
                    factor_map[f["factor"]] = int(f.get("score", 0))
                except (TypeError, ValueError):
                    pass
        if factor_map:
            usable.append({"pct": float(pct), "factors": factor_map})

    result = {
        "period": period,
        "n_total": len(rows),
        "n_with_factors": len(usable),
        "factors": {},
        "calibration_notes": [],
    }

    for fname in _FACTOR_NAMES:
        high_group = [u for u in usable if u["factors"].get(fname, -1) >= _FACTOR_HIGH]
        low_group = [u for u in usable
                     if 0 <= u["factors"].get(fname, -1) <= _FACTOR_LOW]

        high_stats = _group_stats_simple([u["pct"] for u in high_group])
        low_stats = _group_stats_simple([u["pct"] for u in low_group])

        entry = {
            "high": high_stats,
            "low": low_stats,
            "status": "insufficient_sample",
            "win_rate_diff": None,
            "avg_pct_diff": None,
        }

        if high_stats["n"] >= _FACTOR_MIN_GROUP and low_stats["n"] >= _FACTOR_MIN_GROUP:
            wr_diff = (high_stats["win_rate"] or 0) - (low_stats["win_rate"] or 0)
            ap_diff = (high_stats["avg_pct"] or 0) - (low_stats["avg_pct"] or 0)
            entry["win_rate_diff"] = round(wr_diff, 1)
            entry["avg_pct_diff"] = round(ap_diff, 2)
            if wr_diff > 10:
                entry["status"] = "effective"
            elif wr_diff < -10:
                entry["status"] = "ineffective"
            else:
                entry["status"] = "neutral"

        result["factors"][fname] = entry

        # 生成校准备注（仅对差 avg_pct_diff 超阈值且状态明确的有效/失效因子）
        if entry["status"] in ("ineffective", "effective") \
                and abs(entry["avg_pct_diff"] or 0) >= _CALIBRATION_THRESHOLD:
            verb = "低于" if entry["status"] == "ineffective" else "高于"
            result["calibration_notes"].append(
                f"{fname}因子高分组的{_PERIOD_LABELS.get(period, 'T+N')}"
                f"胜率 {high_stats['win_rate']}% {verb}低分组 {low_stats['win_rate']}%"
                f"（差 {entry['win_rate_diff']}pp），平均涨幅差 {entry['avg_pct_diff']}pp，"
                + ("因子预测力失效，建议人工复核权重"
                   if entry["status"] == "ineffective" else "因子预测力有效")
            )

    return result


def _template_calibration_suggestions(correlation: dict) -> list[dict]:
    """因子校准建议模板（确定性，全部 suggestion_source=template）。
    仅对 status=ineffective 且 avg_pct_diff 超阈值的因子生成建议。"""
    out = []
    period = correlation.get("period", "t5")
    period_label = _PERIOD_LABELS.get(period, "T+N")
    factors = correlation.get("factors", {})

    ineffective = []
    for fname, data in factors.items():
        if data.get("status") == "ineffective" and abs(data.get("avg_pct_diff") or 0) >= _CALIBRATION_THRESHOLD:
            ineffective.append(fname)
            high = data["high"]
            low = data["low"]
            out.append({
                "target_agent": "score", "target_kind": "prompt", "rule_type": "soft",
                "priority": "high",
                "rule_name": f"因子权重校准建议（{fname} 预测力失效）",
                "current_value": f"{fname}因子参考权重约 {_FACTOR_DEFAULT_WEIGHTS.get(fname, '15%')}，"
                                 f"高分组合格率 {high['win_rate']}%，低分组 {low['win_rate']}%",
                "suggested_value": (f"{fname}因子高分组的{period_label}胜率 {high['win_rate']}% "
                                    f"低于低分组 {low['win_rate']}%（差 {data['win_rate_diff']}pp），"
                                    f"建议人工复核降低该因子权重"),
                "reason": (f"统计显示 {fname} 因子高分组（≥7分）表现反而差于低分组（≤3分），"
                           f"该因子对后续涨幅的预测力失效，可能误导评分"),
                "evidence": (f"高分组 n={high['n']} 胜率 {high['win_rate']}% 平均 {high['avg_pct']}%，"
                             f"低分组 n={low['n']} 胜率 {low['win_rate']}% 平均 {low['avg_pct']}%"),
                "rule_text": (f"当 {fname} 因子高分组胜率持续低于低分组（差值>10pp 且 avg_pct 差>"
                              f"{_CALIBRATION_THRESHOLD}pp）时，应在评分提示词中降低该因子权重，"
                              f"直至因子预测力恢复后人工复核恢复"),
                "problem_desc": f"{fname}因子与后续表现相关性倒挂，可能误导评级与仓位分配",
                "expected_effect": "恢复因子与表现的正常相关性，失效期降低该因子对评分的影响",
                "risk_note": "小样本可能为噪声，需连续 2 个统计期确认后才调整权重",
                "file_path": "agent_prompts/score_prompt.py",
                "insert_position": "六因子定义与参考权重段",
            })

    # 多因子同时失效 → 整体复核建议
    if len(ineffective) >= 3:
        out.append({
            "target_agent": "score", "target_kind": "prompt", "rule_type": "soft",
            "priority": "high",
            "rule_name": f"评分体系整体复核建议（{len(ineffective)}个因子同时失效）",
            "current_value": f"六因子中 {', '.join(ineffective)} 预测力失效",
            "suggested_value": "建议人工全面复核评分体系，考虑调整因子结构或引入新因子",
            "reason": "多个因子同时失效说明当前评分体系可能不适应近期市场环境",
            "evidence": f"失效因子：{', '.join(ineffective)}",
            "rule_text": "当六因子中≥3个因子预测力同时失效时，应触发评分体系整体复核",
            "problem_desc": "评分体系整体预测力下降，多因子同时与后续表现脱钩",
            "expected_effect": "及时识别评分体系系统性失效，避免持续误导",
            "risk_note": "整体复核须人工执行，禁止系统自动改变因子结构",
            "file_path": "agent_prompts/score_prompt.py",
            "insert_position": "六因子定义段",
        })

    return out


def get_factor_calibration(period: str = "t5") -> str:
    """因子校准相关性摘要（紧凑文本，供 ScoreAgent build_user_prompt 注入）。
    只读本模块统计，不改任何逻辑。无数据/读取失败 → 返回空字符串。"""
    key = f"factor:calibration:{period}"
    try:
        cached = cache.get(key)
        if cached:
            return cached
        rows = repo.list_track_verify(limit=500)
    except Exception as exc:  # noqa: BLE001 读失败不阻塞注入
        logger.warning("因子校准摘要读取失败（跳过注入）: %s", exc)
        return ""

    correlation = compute_factor_correlation(rows, period=period)
    text = _format_calibration_text(correlation)
    if text:
        try:
            cache.set(key, text, _CALIBRATION_TTL)
        except Exception as exc:  # noqa: BLE001 缓存失败不影响注入
            logger.warning("因子校准摘要缓存写入失败: %s", exc)
    return text


def _format_calibration_text(correlation: dict) -> str:
    """因子相关性 → 紧凑文本（客观事实，不给结论性建议）。"""
    n = correlation.get("n_with_factors", 0)
    if n < _FACTOR_MIN_GROUP:
        return ""
    period_label = _PERIOD_LABELS.get(correlation.get("period", ""), "T+N")
    lines = [f"因子校准相关性（{n} 个有因子分的样本，{period_label}周期）："]
    for fname in _FACTOR_NAMES:
        f = correlation.get("factors", {}).get(fname)
        if not f or f.get("status") == "insufficient_sample":
            continue
        high, low = f["high"], f["low"]
        status_map = {"effective": "有效", "ineffective": "失效", "neutral": "无显著差异"}
        lines.append(
            f"- {fname}：高分组({high['n']}只)胜率{high['win_rate']}%/均涨{high['avg_pct']}% "
            f"vs 低分组({low['n']}只)胜率{low['win_rate']}%/均涨{low['avg_pct']}% → {status_map.get(f['status'], '未知')}"
        )
    if len(lines) <= 1:
        return ""
    lines.append("以上为因子预测力的历史统计事实，供你评分时参考。表现差的因子可适当降低权重，"
                 "但不得增减因子数量。此为参考信息，不改变已有规则。")
    return "\n".join(lines)


# ==================== 建议生成（LLM 为主 + 确定性模板兜底 + 来源标记） ====================

def _template_suggestions(stats: dict, anomalies: list[dict]) -> list[dict]:
    """确定性模板兜底（仅异常时产出，全部 suggestion_source=template）。
    分组样本 <3 的异常不产建议（detect_anomalies 已前置门槛）。"""
    out: list[dict] = []
    period_label = {"t3": "T+3", "t5": "T+5", "t10": "T+10"}.get(stats.get("period"), "T+N")
    for anom in anomalies:
        if anom["type"] == "rating_inversion":
            d = anom["data"]
            pair = str(d.get("pair") or "")
            # pair 语义：高<低，如 "A<C" → A 档低于 C 档（倒挂成立）。高评级在前、低评级在后
            high, low = pair.split("<") if "<" in pair else ("高评级", "低评级")
            hi, lo = d.get(high, {}), d.get(low, {})
            hi_avg = hi.get("avg_pct")
            lo_avg = lo.get("avg_pct")
            out.append({
                "target_agent": "discover", "target_kind": "prompt", "rule_type": "soft",
                "priority": "high",
                "rule_name": f"候选池评级正相关性校验（{pair} 倒挂）",
                "current_value": "评级 A/B/C 默认代表选股质量优劣，未单独校验与后续涨幅的相关性",
                "suggested_value": (f"{low} 档平均{period_label}涨幅 {lo_avg}% 高于 {high} 档 "
                                    f"{hi_avg}%，需人工复核评级维度权重"),
                "reason": (f"统计显示 {low} 档平均涨幅高于 {high} 档，评级与后续表现相关性倒挂，"
                           f"需要先排查评级来源与样本口径"),
                "evidence": (f"{low} 档 {lo.get('n')} 笔平均 {lo_avg}%，"
                             f"{high} 档 {hi.get('n')} 笔平均 {hi_avg}%"),
                "rule_text": (f"出现{period_label}评级分组收益倒挂时，在分析结论中列明样本期、数量、"
                              "评级来源、评分版本和市场环境；来源或时点不一致时标记口径待核实。"
                              "仅作为研究复核提示，不据此调整评级、排序、仓位或入池条件；"
                              "需有同口径对照及样本外验证后，再单独提交规则变更。"),
                "problem_desc": "混合评级的收益差异可能来自口径或市场暴露，尚不能归因为评分失效",
                "expected_effect": "提高评级验证的可追溯性，减少由混合口径引起的错误调参",
                "risk_note": "描述性分组差异不证明因果或盈利能力；本建议只约束研究说明，不改变交易条件",
                "file_path": "agent_prompts/score_prompt.py", "insert_position": "评级维度权重段",
            })
        elif anom["type"] == "consecutive_decline":
            d = anom["data"]
            seq = " → ".join(f"{k} {v}%" for k, v in d.items())
            out.append({
                "target_agent": "discover", "target_kind": "prompt", "rule_type": "soft",
                "priority": "high",
                "rule_name": "候选池胜率连续下降预警阈值",
                "current_value": "候选池胜率未设连续下滑预警机制",
                "suggested_value": f"最近 3 期胜率连续下降（{seq}），核对样本、数据和市场变化",
                "reason": "连续下降是研究线索，尚不能证明过滤条件需要收紧",
                "evidence": seq,
                "rule_text": (f"候选池{period_label}按日胜率连续下降时，说明到期样本数、同日市场暴露、"
                              "数据缺失及策略版本是否变化；对待验证原因和反例分别列证据。"
                              "此提示不改变候选数量、评分权重或入池条件；提出收紧或放宽方案时，"
                              "需同时给出通过组与拦截组对照、候选覆盖影响和退出条件。"),
                "problem_desc": "胜率下降可能被错误解释为需要继续追加过滤条件",
                "expected_effect": "区分数据、市场与策略原因，提高调优依据的质量",
                "risk_note": "少量同日样本可能共享同一风险；未验证时只做原因核查，不执行参数调整",
                "file_path": "agent_prompts/discover_prompt.py", "insert_position": "候选池规模段",
            })
        elif anom["type"] == "win_rate_low":
            d = anom["data"]
            out.append({
                "target_agent": "discover", "target_kind": "prompt", "rule_type": "soft",
                "priority": "high",
                "rule_name": "候选池选股胜率下限复核",
                "current_value": f"候选池{period_label}胜率 {d['win_rate']}%"
                                 f"（{d.get('wins', 0)}/{d['n']}）低于 {_WIN_LOW:.0f}%",
                "suggested_value": f"胜率 {d['win_rate']}% 低于 {_WIN_LOW:.0f}%，建议人工复核选股标准",
                "reason": "低胜率可能来自数据、市场、择时或筛选条件，汇总结果不能确定原因",
                "evidence": (f"n={d['n']} 胜率 {d['win_rate']}% 平均涨幅 {d['avg_pct']}% "
                             f"（{period_label}周期）"),
                "rule_text": (f"候选池{period_label}正收益胜率偏低时，在研究说明中核对事实数据完整性、"
                              "评级来源、市场环境和入场时点，列出证据支持及不支持的原因。"
                              "低胜率本身不改变候选池规模、风险权重或入池阈值；"
                              "具体调整需另行提供同口径对照、覆盖率、适用范围、有效期和退出条件。"),
                "problem_desc": "汇总收益异常尚不能证明入池条件过松，直接加码可能使研究范围持续缩小",
                "expected_effect": "识别可验证的改进方向，避免仅凭低胜率反复增加过滤条件",
                "risk_note": "保持既有交易风控；此建议只要求解释证据，不产生收紧或放宽操作",
                "file_path": "agent_prompts/discover_prompt.py", "insert_position": "筛选条件段",
            })
    return out


_UNVALIDATED_RESTRICTION_TERMS = (
    "否则不纳入", "否则排除", "一律不纳入", "直接排除", "减少候选",
    "候选池收缩", "候选数量", "提高门槛", "收紧条件", "强制叠加",
    "量比>", "净流入", "板块内", "板块共振", "降低候选", "限制推荐",
)


def _allow_llm_proposal(item, stats: dict) -> bool:
    """Aggregate returns alone cannot authorize a new discovery filter.

    This deterministic guard is intentionally conservative.  It prevents a
    model or a stale prompt from turning a descriptive anomaly into a new
    exclusion rule before the caller has supplied validated counterfactual
    evidence.  Diagnostic/observation proposals remain allowed.
    """
    if not item or getattr(item, "target_agent", "") != "discover":
        return True
    rule_text = str(getattr(item, "rule_text", "") or "")
    if not rule_text:
        return True
    return not any(term in rule_text for term in _UNVALIDATED_RESTRICTION_TERMS)


def generate_suggestions(stats: dict, anomalies: list[dict],
                         llm_call=None) -> dict:
    """选股验证规则建议生成（LLM 为主 + 确定性模板兜底，来源强制标记）。

    llm_call 签名 (stats_json, anomalies_json) -> TrackVerifyOutput，可注入测试替身；
    默认走真实 agent_call（agent="track_verify"，缓存键含统计指纹）。
    返回 {"suggestions": [{"id", "rule_name", "suggestion_source"}],
          "fallbacks": [{"rule_name", "suggestion_source"}], "deduped": int,
          "summary_note": str}"""
    stats_json = build_stats_json(stats, anomalies)
    llm_items: list = []
    summary_note = ""
    llm_ok = False
    try:
        if llm_call is not None:
            out = llm_call(stats_json, [a["type"] for a in anomalies])
        else:
            from app.agents.common import agent_call
            from agent_prompts import track_verify_prompt

            out = agent_call(
                agent="track_verify",
                cache_key="trackverify:evidence-v2:" + hashlib.md5(
                    stats_json.encode("utf-8")).hexdigest()[:12],
                system_prompt=track_verify_prompt.SYSTEM_PROMPT,
                user_prompt=track_verify_prompt.build_user_prompt(stats_json),
                schema=TrackVerifyOutput,
                ttl_seconds=86400,
                model_level=ModelLevel.DEEP,
            )
        llm_ok = True
        summary_note = (getattr(out, "summary_note", "") or "").strip()
        llm_items = list(getattr(out, "agent_suggestions", []) or [])
    except Exception as exc:  # noqa: BLE001 LLM 失败走模板兜底，不阻塞链路
        logger.warning("选股验证 LLM 建议生成失败，转模板兜底: %s", exc)

    inserted: list[dict] = []
    deduped = 0
    blocked_unvalidated = 0
    for item in llm_items:
        if not _allow_llm_proposal(item, stats):
            blocked_unvalidated += 1
            logger.warning("选股验证建议因缺少对照证据而阻止收紧条文: %s",
                           getattr(item, "rule_name", ""))
            continue
        if repo.has_pending_suggestion(item.rule_name, item.target_agent):
            deduped += 1
            continue
        sid = repo.insert_agent_suggestion(
            0, item.target_agent, item.rule_name,
            item.current_value, item.suggested_value, item.reason, item.evidence,
            target_kind=item.target_kind,
            rule_type=item.rule_type, priority=item.priority,
            problem_desc=item.problem_desc, rule_text=item.rule_text,
            expected_effect=item.expected_effect, risk_note=item.risk_note,
            file_path=item.file_path, insert_position=item.insert_position,
            suggestion_source="llm", dedupe=True)
        if sid:
            inserted.append({"id": sid, "rule_name": item.rule_name,
                             "suggestion_source": "llm"})
        else:
            deduped += 1

    fallbacks: list[dict] = []
    # 证据不足主动不提案、或建议已存在，都不是生成失败。
    if not llm_ok:
        for tpl in _template_suggestions(stats, anomalies):
            if repo.has_pending_suggestion(tpl["rule_name"], tpl["target_agent"]):
                deduped += 1
                continue
            sid = repo.insert_agent_suggestion(
                0, tpl["target_agent"], tpl["rule_name"],
                tpl["current_value"], tpl["suggested_value"],
                tpl["reason"], tpl["evidence"],
                target_kind=tpl["target_kind"],
                rule_type=tpl["rule_type"], priority=tpl["priority"],
                problem_desc=tpl["problem_desc"], rule_text=tpl["rule_text"],
                expected_effect=tpl["expected_effect"], risk_note=tpl["risk_note"],
                file_path=tpl["file_path"], insert_position=tpl["insert_position"],
                suggestion_source="template", dedupe=True)
            if sid:
                fallbacks.append({"id": sid, "rule_name": tpl["rule_name"],
                                  "suggestion_source": "template"})
            else:
                deduped += 1
    return {"suggestions": inserted, "fallbacks": fallbacks,
            "deduped": deduped, "blocked_unvalidated": blocked_unvalidated,
            "summary_note": summary_note}


def auto_audit_generated_suggestions(suggestions_result: dict) -> dict:
    """对本次新生成的选股验证建议立即触发 AI 审核；只写 audit_log/audit_verdict，不采纳生效。"""
    ids: list[int] = []
    for key in ("suggestions", "fallbacks"):
        for item in suggestions_result.get(key, []) or []:
            sid = item.get("id") if isinstance(item, dict) else None
            if sid:
                ids.append(int(sid))
    out = {"requested": len(ids), "pass": 0, "fail": 0, "errors": []}
    if not ids:
        return out
    try:
        from app.agents.audit import trigger_audit_for_suggestion
    except Exception as exc:  # noqa: BLE001 审核模块不可用不影响建议落库
        out["errors"].append({"stage": "import", "error": str(exc)[:300]})
        return out
    for sid in ids:
        try:
            res = trigger_audit_for_suggestion(sid)
            verdict = str(res.get("verdict") or "")
            if verdict == "pass":
                out["pass"] += 1
            elif verdict == "fail":
                out["fail"] += 1
        except Exception as exc:  # noqa: BLE001 单条审核失败隔离
            out["errors"].append({"id": sid, "error": str(exc)[:300]})
    return out


# ==================== 主链路（cron 与手动入口共用，幂等） ====================

def _default_price_lookup(stock_code: str, select_date: str):
    """真实日K拉取（行情源 TTL 3600 天然合并同日多标的重叠请求）"""
    from app.datasource.fallback import get_datasource

    src = get_datasource()
    start = f"{select_date[:4]}0101"
    end = time.strftime("%Y-%m-%d")
    return src.fetch_daily_kline(stock_code, start, end)


def _init_candidates() -> int:
    """初始化：候选池中未追踪的全部 (code, select_date) 补齐追踪行（自愈）。
    评级取 grade 优先、confidence_tier 兜底；基准价取选中日快照 price（无则 0 由计算兜底）；
    因子分从 stock_score.detail.factors 提取（无则 None 诚实留空，不造假）。"""
    initialized = 0
    for cand in repo.list_untracked_candidates():
        base = 0.0
        try:
            base = float((cand.get("snapshot") or {}).get("price") or 0)
        except (TypeError, ValueError):
            base = 0.0
        rating = repo.get_candidate_rating(cand["stock_code"], cand["trade_date"])
        # 评级重做-C：从 stock_score 提取六因子分值
        factor_scores = repo.get_score_factors(cand["stock_code"], cand["trade_date"])
        repo.upsert_track_verify(cand["stock_code"], cand["stock_name"],
                                 cand["trade_date"], rating, base,
                                 factor_scores=factor_scores)
        initialized += 1
    return initialized


def register_new_candidates() -> int:
    """登记候选池中尚未追踪的标的，供 Discover 完成落库后即时挂接。

    仅创建幂等的 candidate_track_verify 行，不拉取行情、不计算 T+N；
    后续验证任务仍负责按交易日填充实际表现。
    """
    return _init_candidates()


def backfill_factor_scores() -> dict:
    """回填已有追踪行的 factor_scores（用于已存在但创建时未提取因子分的行）。
    幂等：已有 factor_scores 的行跳过；无对应 stock_score 的行跳过。
    返回 {"filled": int, "skipped": int, "no_score": int}"""
    filled = skipped = no_score = 0
    for row in repo.list_track_verify(limit=500):
        if row.get("factor_scores"):  # 已有则跳过
            skipped += 1
            continue
        factors = repo.get_score_factors(row["stock_code"], row["select_date"])
        if factors is None:
            no_score += 1
            continue
        repo.update_track_verify(row["id"], factor_scores=factors)
        filled += 1
    logger.info("因子分回填: %s", {"filled": filled, "skipped": skipped, "no_score": no_score})
    return {"filled": filled, "skipped": skipped, "no_score": no_score}


def _verify_rows(price_lookup, include_finished: bool = False) -> tuple[int, int, list[str]]:
    """计算：遍历未到期行，拉日K计算 T+N；到期行收尾 is_finished=1。返回
    (updated, finished_new, errors)"""
    updated = finished_new = 0
    errors: list[str] = []
    lookup = price_lookup or _default_price_lookup
    rows = repo.list_track_verify(limit=500) if include_finished else repo.list_track_verify(is_finished=0)
    for row in rows:
        try:
            kline = lookup(row["stock_code"], row["select_date"])
            norm = _norm_kline(kline)
            if norm is None:
                errors.append(f"{row['stock_code']} {row['select_date']} 行情为空")
                continue
            dates, closes = norm
            dates, closes = confirmed_kline_points(dates, closes)
            if not dates:
                errors.append(f"{row['stock_code']} {row['select_date']} 无已确认日K")
                continue
            metrics = compute_tn_metrics(dates, closes,
                                         row["base_close_price"], row["select_date"])
        except Exception as exc:  # noqa: BLE001 单行失败跳过，下次自动重试（诚实降级）
            errors.append(f"{row['stock_code']} {row['select_date']}: {exc}")
            continue

        latest_close = closes[-1]
        periods = {}
        for key, n in (("t3", 3), ("t5", 5), ("t10", 10)):
            pct = metrics[key]["pct"]
            periods[key] = {"win": pct > 0 if pct is not None else None,
                            "countable": pct is not None}
        verify_result = {
            "base_close": row["base_close_price"] or latest_close,
            "latest_close": latest_close,
            "latest_date": dates[-1],
            "daily_path": build_daily_path(
                dates, closes, row["base_close_price"], row["select_date"]),
            "periods": periods,
            "drawdown": {"max_pct": metrics["max_drawdown"],
                         "min_close_date": metrics["min_close_date"]},
            "notes": metrics["notes"],
        }
        repo.update_track_verify(
            row["id"], t3_pct=metrics["t3"]["pct"], t5_pct=metrics["t5"]["pct"],
            t10_pct=metrics["t10"]["pct"], max_drawdown=metrics["max_drawdown"],
            verify_result=verify_result, is_finished=1 if metrics["due"] else 0)
        updated += 1
        if metrics["due"] and not row.get("is_finished"):
            finished_new += 1
    return updated, finished_new, errors


def run_verify_chain(backfill: bool = False, price_lookup=None, llm_call=None) -> dict:
    """候选池 T+N 验证主链路（每日 16:00 cron 与手动入口共用，幂等）：
    ① 初始化新候选 → ② 计算 T+N → ③ 到期收尾 → ④ 有新增到期（或回填）→ 统计+建议生成。
    price_lookup / llm_call 可注入（测试用假数据，对齐 hot_money_review 模式）。"""
    if not cache.acquire_lock("track_verify", ttl_seconds=_LOCK_TTL):
        return {"skipped": "track_verify 锁被占用（每日任务或手动验证正在执行）"}
    try:
        initialized = _init_candidates()
        updated, finished_new, errors = _verify_rows(price_lookup, include_finished=backfill)
        result: dict = {"initialized": initialized, "updated": updated,
                        "finished_new": finished_new,
                        "errors": errors[:_MAX_ERRORS], "stats": None, "suggestions": []}
        if finished_new > 0 or backfill:
            rows = repo.list_track_verify()
            stats = compute_stats(rows, period="t5")
            anomalies = detect_anomalies(stats)
            # 评级重做-C：因子相关性计算
            correlation = compute_factor_correlation(rows, period="t5")
            result["stats"] = stats
            result["anomalies"] = anomalies
            result["factor_correlation"] = correlation
            result["suggestions"] = generate_suggestions(stats, anomalies, llm_call=llm_call)
            if llm_call is None:
                result["audit"] = auto_audit_generated_suggestions(result["suggestions"])
            # 评级重做-C：因子校准建议（模板兜底，走人工审核闭环）
            cal_suggestions = _template_calibration_suggestions(correlation)
            cal_inserted: list[dict] = []
            for tpl in cal_suggestions:
                if repo.has_pending_suggestion(tpl["rule_name"], tpl["target_agent"]):
                    continue
                sid = repo.insert_agent_suggestion(
                    0, tpl["target_agent"], tpl["rule_name"],
                    tpl["current_value"], tpl["suggested_value"],
                    tpl["reason"], tpl["evidence"],
                    target_kind=tpl["target_kind"],
                    rule_type=tpl["rule_type"], priority=tpl["priority"],
                    problem_desc=tpl["problem_desc"], rule_text=tpl["rule_text"],
                    expected_effect=tpl["expected_effect"], risk_note=tpl["risk_note"],
                    file_path=tpl["file_path"], insert_position=tpl["insert_position"],
                    suggestion_source="template", dedupe=True)
                if sid:
                    cal_inserted.append({"id": sid, "rule_name": tpl["rule_name"],
                                         "suggestion_source": "template"})
                else:
                    result.setdefault("suggestions", {}).setdefault("deduped", 0)
                    result["suggestions"]["deduped"] += 1
            if llm_call is None and cal_inserted:
                result["factor_audit"] = auto_audit_generated_suggestions(
                    {"suggestions": cal_inserted, "fallbacks": []})
        logger.info("候选T+N验证完成: 初始化%s 更新%s 到期%s 错误%s",
                    initialized, updated, finished_new, len(errors))
        return result
    except Exception as exc:  # noqa: BLE001 整体容错，失败不阻塞调度
        logger.error("候选T+N验证链路异常: %s", exc)
        return {"error": str(exc)}
    finally:
        cache.release_lock("track_verify")


# ==================== 复盘反哺选股（批次H）：组合归因 / 周期复利 ====================
# 纯计算、零 LLM。贡献度口径写死（见各函数 docstring），供 Review/Score 注入与复盘页三段 UI。
# 铁律：缺数据字段显式 null，不补 0、不伪造；失败降级返回空结构不阻塞调用方。

def _curve_points(items: list[dict], closes: dict, dates: list[str], total_cost: float) -> list[dict]:
    """纯函数（可单测）：组合曲线 = 每日 Σ(单票当日浮盈亏) / 当前总成本 × 100。
    items=[{code, cost_ps, shares, entry_date}]；closes={code: {date: close}}；
    dates 为升序交易日列表；建仓日之前的日期不计入、缺行情日该票当日不计入（不伪造 0）。"""
    pts = []
    for d in dates:
        pnl_sum = 0.0
        for it in items:
            if it.get("entry_date") and d < it["entry_date"]:
                continue  # 建仓前不计入
            close = closes.get(it["code"], {}).get(d)
            if close is None:
                continue
            pnl_sum += (close - it["cost_ps"]) * it["shares"]
        pts.append({"date": d,
                    "total_pnl_pct": round(pnl_sum / total_cost * 100, 2) if total_cost else 0.0})
    return pts


def _daily_closes(codes: list[str], days: int) -> dict[str, dict[str, float]]:
    """每只近 days 日K收盘 → {code: {date: close}}；单只失败返回空 dict（该票当日不计入）"""
    out: dict[str, dict[str, float]] = {}
    if not codes:
        return out
    from app.datasource.fallback import get_datasource

    end = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - (days + 20) * 86400))  # +20 缓冲覆盖周末/停牌
    src = get_datasource()
    for code in codes:
        try:
            kl = src.fetch_daily_kline(code, start, end)
            if kl is not None and not kl.empty:
                out[code] = {str(r["date"])[:10]: float(r["close"]) for _, r in kl.iterrows()}
        except Exception as exc:  # noqa: BLE001 单只失败不影响其余
            logger.warning("组合归因·日K取数失败 %s: %s", code, exc)
    return out


def build_portfolio_attribution(period_days: int = 30) -> dict:
    """组合归因（纯计算，零 LLM）：当前持仓视角的组合盈亏曲线 + 贡献者 + 最大拖累者。

    口径（写死，供单测锁定）：
    - 组合曲线：第 d 日 = Σ_持仓 [(close_d − 每股成本) × 现股数] / 当前持仓总成本 × 100；
      以当前持仓回看 period_days（简化：持仓不变、缺行情日不计入、建仓前不计入）；
    - 贡献度：单票当前浮盈亏金额 / 当前持仓总成本 × 100（正绿/负红）；
    - 拖累分析：贡献度最负的持仓 → "最大拖累者 X (Y%)"；无负贡献 → None。
    数据源：holding_view 实时行情行 + 每只日K；无持仓/读取失败返回空结构不阻塞。"""
    from datetime import date
    from app.services.holding_view import build_holding_view

    view = build_holding_view()
    rows = view["rows"]
    empty = {"portfolio_curve": [], "contributors": [], "drag_analysis": None,
             "total_cost": 0.0, "period_days": period_days}
    if not rows:
        return empty

    total_cost = 0.0
    items = []
    for r in rows:
        cost_ps = float(r.get("entry_price") or 0)
        shares = float(r.get("shares") or 0)
        cost_amt = float(r.get("cost") or (cost_ps * shares) or 0)
        total_cost += cost_amt
        pa = r.get("pnl_amount")
        items.append({"code": r["stock_code"], "cost_ps": cost_ps, "shares": shares,
                      "entry_date": str(r.get("entry_date") or "")[:10],
                      "pnl_amount": float(pa) if pa is not None else None,
                      "name": r.get("stock_name") or r["stock_code"]})
    if total_cost <= 0:
        return empty

    closes = _daily_closes([it["code"] for it in items], period_days)
    dates = sorted(set().union(*[set(c) for c in closes.values()]) if closes else [])
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - period_days * 86400))
    curve = [p for p in _curve_points(items, closes, dates, total_cost) if p["date"] >= start]

    contributors = []
    for it in items:
        pa = it["pnl_amount"]
        holding_days = None
        if it["entry_date"]:
            try:
                holding_days = max(0, (date.today() - date.fromisoformat(it["entry_date"])).days)
            except ValueError:
                holding_days = None
        contributors.append({
            "stock_code": it["code"], "stock_name": it["name"],
            "contribution_pct": round(pa / total_cost * 100, 2) if pa is not None else None,
            "pnl_amount": round(pa, 2) if pa is not None else None,
            "holding_days": holding_days,
        })
    contributors.sort(key=lambda x: (x["contribution_pct"] is None, x["contribution_pct"] or 0))

    drag = None
    neg = [c for c in contributors if c["contribution_pct"] is not None and c["contribution_pct"] < 0]
    if neg:
        drag = f"最大拖累者 {neg[0]['stock_code']} ({neg[0]['contribution_pct']}%)"
    return {"portfolio_curve": curve, "contributors": contributors, "drag_analysis": drag,
            "total_cost": round(total_cost, 2), "period_days": period_days}


def build_stock_cycle_attribution(stock_code: str) -> dict:
    """周期复利（纯计算，零 LLM）：该股历史多次操作的汇总（供 Score 历史胜率维度回流 + Review 折叠展示）。

    口径（写死，供单测锁定）：每个持仓记录 = 1 个周期；
    - 周期盈亏 = 卖出额 − 买入额（已了结周期，即存在卖出流水）；
    - 未了结周期（无卖出）盈亏为 null，不参与总盈亏/胜率/拖累率（标 unrealized_cycles）；
    - win_rate = 盈利周期 / 已了结周期数；drag_rate = 亏损周期 / 已了结周期数；
    - 平均持仓天数 = 各周期（末次卖出日 − 首次买入日；未了结用 今日 − 建仓日）均值；
    - 最佳/最差周期 = 已了结周期中盈亏最大/最小者。
    无任何持仓记录 → has_history=False（调用方标「无历史数据」，不加分不扣分）。"""
    try:
        holdings = [h for h in repo.list_holdings() if h["stock_code"] == stock_code]
    except Exception as exc:  # noqa: BLE001 读失败按无历史处理，不阻塞打分
        logger.warning("周期复利·持仓读取失败 %s: %s", stock_code, exc)
        return {"stock_code": stock_code, "has_history": False, "cycle_count": 0,
                "closed_cycle_count": 0, "total_pnl": None, "avg_hold_days": None,
                "win_rate": None, "drag_rate": None, "best_cycle": None, "worst_cycle": None}

    empty = {"stock_code": stock_code, "has_history": False, "cycle_count": 0,
             "closed_cycle_count": 0, "total_pnl": None, "avg_hold_days": None,
             "win_rate": None, "drag_rate": None, "best_cycle": None, "worst_cycle": None}
    if not holdings:
        return empty

    from datetime import date
    today = date.today()
    cycles = []
    for h in holdings:
        trades = repo.get_trades(h["id"])
        buys = [t for t in trades if t.side == "buy"]
        sells = [t for t in trades if t.side == "sell"]
        entry = str(h.get("entry_date") or "")[:10]
        if sells:
            pnl = round(sum(t.amount for t in sells) - sum(t.amount for t in buys), 2)
            d_end = date.fromisoformat(sells[-1].trade_date)
            d_start = date.fromisoformat(buys[0].trade_date) if buys else d_end
            hold_days = (d_end - d_start).days
        else:
            pnl = None
            hold_days = (today - date.fromisoformat(entry)).days if entry else None
        cycles.append({"entry_date": entry, "pnl": pnl, "hold_days": hold_days})

    closed = [c for c in cycles if c["pnl"] is not None]
    n_closed = len(closed)
    wins = sum(1 for c in closed if c["pnl"] > 0)
    losses = sum(1 for c in closed if c["pnl"] < 0)
    hd = [c["hold_days"] for c in cycles if c["hold_days"] is not None]
    best = max(closed, key=lambda c: c["pnl"]) if closed else None
    worst = min(closed, key=lambda c: c["pnl"]) if closed else None
    return {
        "stock_code": stock_code,
        "has_history": True,
        "cycle_count": len(holdings),
        "closed_cycle_count": n_closed,
        "unrealized_cycles": len(cycles) - n_closed,
        "total_pnl": round(sum(c["pnl"] for c in closed), 2) if closed else None,
        "avg_hold_days": round(sum(hd) / len(hd), 1) if hd else None,
        "win_rate": round(wins / n_closed * 100, 1) if n_closed else None,
        "drag_rate": round(losses / n_closed * 100, 1) if n_closed else None,
        "best_cycle": best,
        "worst_cycle": worst,
    }
