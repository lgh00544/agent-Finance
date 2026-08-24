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
    - rating_inversion:    A/C 两档样本均≥3 且 C 档 avg_pct > A 档 avg_pct（评级倒挂）
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
    a, c = by_rating.get("A"), by_rating.get("C")
    if (a and c and a["n"] >= _MIN_SAMPLE and c["n"] >= _MIN_SAMPLE
            and a["avg_pct"] is not None and c["avg_pct"] is not None
            and c["avg_pct"] > a["avg_pct"]):
        anomalies.append({"type": "rating_inversion",
                          "desc": "C 档平均涨幅高于 A 档（评级正相关性倒挂）",
                          "data": {"A": {"n": a["n"], "avg_pct": a["avg_pct"]},
                                   "C": {"n": c["n"], "avg_pct": c["avg_pct"]}}})

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
    return json.dumps({"stats": stats, "anomalies": anomalies},
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


# ==================== 建议生成（LLM 为主 + 确定性模板兜底 + 来源标记） ====================

def _template_suggestions(stats: dict, anomalies: list[dict]) -> list[dict]:
    """确定性模板兜底（仅异常时产出，全部 suggestion_source=template）。
    分组样本 <3 的异常不产建议（detect_anomalies 已前置门槛）。"""
    out: list[dict] = []
    period_label = {"t3": "T+3", "t5": "T+5", "t10": "T+10"}.get(stats.get("period"), "T+N")
    for anom in anomalies:
        if anom["type"] == "rating_inversion":
            d = anom["data"]
            out.append({
                "target_agent": "discover", "target_kind": "prompt", "rule_type": "soft",
                "priority": "high",
                "rule_name": "候选池评级正相关性校验（倒挂告警）",
                "current_value": "评级 A/B/C 默认代表选股质量优劣，未单独校验与后续涨幅的相关性",
                "suggested_value": f"C 档平均{period_label}涨幅 {d['C']['avg_pct']}% 高于 A 档 "
                                   f"{d['A']['avg_pct']}%，需人工复核评级维度权重",
                "reason": "统计显示 C 档平均涨幅高于 A 档，评级与后续表现相关性倒挂，可能误导仓位分配",
                "evidence": (f"C 档 {d['C']['n']} 笔平均 {d['C']['avg_pct']}%，"
                             f"A 档 {d['A']['n']} 笔平均 {d['A']['avg_pct']}%"),
                "rule_text": ("候选评级 A/B/C 应体现选股质量差异：C 档平均 T+N 涨幅持续高于 A 档时，"
                              "需人工复核评级维度权重并调整评分提示词；倒挂持续期间降低 A 档独占权重，"
                              "以实际涨幅排序为准"),
                "problem_desc": "评级体系与后续表现相关性倒挂，可能误导仓位分配与关注优先级",
                "expected_effect": "恢复评级与表现的正常相关性，倒挂期避免高评级标的重仓",
                "risk_note": "小样本周期倒挂可能为噪声，需连续 2 个统计期确认后才调整",
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
                "suggested_value": f"最近 3 期胜率连续下降（{seq}），需警惕选股逻辑失效",
                "reason": "连续 3 期胜率下滑说明选股逻辑可能失效，需人工复核筛选标准",
                "evidence": seq,
                "rule_text": ("候选池按日胜率连续 3 期（每期样本≥3）下降时，应在选股提示词中"
                              "临时提高风险维度的权重并降低候选池规模，直至胜率回升后人工复核恢复"),
                "problem_desc": "选股逻辑失效初期无预警，可能持续扩大回撤",
                "expected_effect": "选股逻辑失效提前预警，及时收缩仓位控制回撤",
                "risk_note": "预警触发后由人工决定是否收紧，禁止系统自动改变选股逻辑",
                "file_path": "agent_prompts/discover_prompt.py", "insert_position": "候选池规模段",
            })
        elif anom["type"] == "win_rate_low":
            d = anom["data"]
            out.append({
                "target_agent": "discover", "target_kind": "prompt", "rule_type": "soft",
                "priority": "medium",
                "rule_name": "候选池选股胜率下限复核",
                "current_value": f"候选池{period_label}胜率 {d['win_rate']}%"
                                 f"（{d.get('wins', 0)}/{d['n']}）低于 {_WIN_LOW:.0f}%",
                "suggested_value": f"胜率 {d['win_rate']}% 低于 {_WIN_LOW:.0f}%，建议人工复核选股标准",
                "reason": "整体胜率过低说明选股标准可能过于激进或市场环境变化",
                "evidence": (f"n={d['n']} 胜率 {d['win_rate']}% 平均涨幅 {d['avg_pct']}% "
                             f"（{period_label}周期）"),
                "rule_text": ("候选池胜率低于 40% 且样本≥3 时，应触发选股标准复核：人工检查当前"
                              "市场环境档位与候选筛选条件是否过松，必要时收紧候选条件"),
                "problem_desc": "选股胜率持续偏低，候选池质量不足",
                "expected_effect": "及时收敛候选标准，减少无效候选对注意力的消耗",
                "risk_note": "仅提示复核，选股标准调整必须人工执行",
                "file_path": "agent_prompts/discover_prompt.py", "insert_position": "筛选条件段",
            })
    return out


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
                cache_key="trackverify:" + hashlib.md5(
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
    for item in llm_items:
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
            suggestion_source="llm")
        inserted.append({"id": sid, "rule_name": item.rule_name,
                         "suggestion_source": "llm"})

    fallbacks: list[dict] = []
    if not llm_ok or (llm_items and not inserted) or (not llm_items and anomalies):
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
                suggestion_source="template")
            fallbacks.append({"id": sid, "rule_name": tpl["rule_name"],
                              "suggestion_source": "template"})
    return {"suggestions": inserted, "fallbacks": fallbacks,
            "deduped": deduped, "summary_note": summary_note}


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
    评级取 grade 优先、confidence_tier 兜底；基准价取选中日快照 price（无则 0 由计算兜底）。"""
    initialized = 0
    for cand in repo.list_untracked_candidates():
        base = 0.0
        try:
            base = float((cand.get("snapshot") or {}).get("price") or 0)
        except (TypeError, ValueError):
            base = 0.0
        rating = repo.get_candidate_rating(cand["stock_code"], cand["trade_date"])
        repo.upsert_track_verify(cand["stock_code"], cand["stock_name"],
                                 cand["trade_date"], rating, base)
        initialized += 1
    return initialized


def _verify_rows(price_lookup) -> tuple[int, int, list[str]]:
    """计算：遍历未到期行，拉日K计算 T+N；到期行收尾 is_finished=1。返回
    (updated, finished_new, errors)"""
    updated = finished_new = 0
    errors: list[str] = []
    lookup = price_lookup or _default_price_lookup
    for row in repo.list_track_verify(is_finished=0):
        try:
            kline = lookup(row["stock_code"], row["select_date"])
            norm = _norm_kline(kline)
            if norm is None:
                errors.append(f"{row['stock_code']} {row['select_date']} 行情为空")
                continue
            dates, closes = norm
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
        if metrics["due"]:
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
        updated, finished_new, errors = _verify_rows(price_lookup)
        result: dict = {"initialized": initialized, "updated": updated,
                        "finished_new": finished_new,
                        "errors": errors[:_MAX_ERRORS], "stats": None, "suggestions": []}
        if finished_new > 0 or backfill:
            rows = repo.list_track_verify()
            stats = compute_stats(rows, period="t5")
            anomalies = detect_anomalies(stats)
            result["stats"] = stats
            result["anomalies"] = anomalies
            result["suggestions"] = generate_suggestions(stats, anomalies, llm_call=llm_call)
        logger.info("候选T+N验证完成: 初始化%s 更新%s 到期%s 错误%s",
                    initialized, updated, finished_new, len(errors))
        return result
    except Exception as exc:  # noqa: BLE001 整体容错，失败不阻塞调度
        logger.error("候选T+N验证链路异常: %s", exc)
        return {"error": str(exc)}
    finally:
        cache.release_lock("track_verify")
