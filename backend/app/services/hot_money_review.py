"""游资信号有效性统计与权重迭代建议（自进化闭环·代码侧）

职责边界（【刚性代码逻辑】）：只做客观统计与建议生成，不做市场判断；
所有"该游资该笔信号准不准"的定性研判在提示词层（review_prompt 游资复盘规则）。

【系统监管红线】权重迭代规则：
- 代码只生成建议（agent_suggestion 落 pending），任何降/升档、权重调整
  必须经人工审核确认后才生效（apply_tier_suggestion 仅在 status=approved 后执行）；
- 统计事实落库可追溯：win_rate_5d（信号后 5 日跑赢大盘的胜率）+ last_review_at；
- 温和策略不机械：信号数 < 3 不产生档位建议（样本不足只记统计事实）；
  胜率 < 40% → 降档建议（一线→二线→观察）；≥ 60% → 升档建议；40%~60% 保持；
  观察档连续误判 → 建议在候选/评分提示词标注"谨慎/反向参考"（人工决定是否写入）。
"""
import logging
import time

from app.db import repo

logger = logging.getLogger(__name__)

# 档位阶梯（温和策略：一次只动一档；观察档不再降、一线不再升）
_DOWNGRADE = {"一线": "二线", "二线": "观察", "观察": "观察"}
_UPGRADE = {"一线": "一线", "二线": "一线", "观察": "二线"}
_WIN_LOW = 0.4    # 胜率 < 40% → 降档建议
_WIN_HIGH = 0.6   # 胜率 ≥ 60% → 升档建议
_MIN_SIGNALS = 3  # 可统计信号数下限（低于不产生档位建议，防小样本误判）
_BENCH_INDEX = "000300"  # 大盘基准：沪深300

_TIER_PATTERN = ("一线", "二线", "观察")


def collect_signals(profile: dict) -> list[dict]:
    """某游资的买入信号集合：主席位+协同席位在龙虎榜的净买入流水（口径 1d）。
    归一化匹配（简称 seat_code vs 龙虎榜全称 seat_name）；同一 (标的,日期) 去重取净买最大。
    返回 [{stock_code, stock_name, trade_date, net_buy, seat_name}]；无信号返回 []。"""
    seats = {repo.normalize_seat(profile.get("seat_code") or "")}
    seats |= {repo.normalize_seat(s) for s in (profile.get("co_seats") or [])}
    seats.discard("")
    flows = repo.list_lhb_flows(lhb_type="1d", limit=2000)
    by_key: dict[tuple, dict] = {}
    for f in flows:
        seat = repo.normalize_seat(f.get("seat_name") or "")
        if seat not in seats:
            continue
        net = float(f.get("net_buy") or 0.0)
        if net < 0:
            continue  # 只统计净买入信号（买入方向）
        key = (f.get("stock_code"), f.get("trade_date"))
        if key not in by_key or net > by_key[key]["net_buy"]:
            by_key[key] = {"stock_code": f.get("stock_code"),
                           "stock_name": f.get("stock_name", ""),
                           "trade_date": f.get("trade_date"),
                           "net_buy": net, "seat_name": f.get("seat_name")}
    return sorted(by_key.values(), key=lambda s: s["trade_date"], reverse=True)


def _forward_5d_returns(stock_df, index_df, trade_date: str) -> tuple | None:
    """信号日 t0 收盘 → 后第 5 个交易日收盘的累计涨跌幅（标的 vs 大盘）。
    数据不足（t0 后不足 5 个交易日 / 任一缺失）→ None，该信号不计入统计。"""
    def _norm(df):
        if df is None or df.empty:
            return []
        out = []
        for _, r in df.iterrows():
            d = str(r.get("date") or "").strip()[:10]
            close = r.get("close")
            try:
                c = float(close)
            except (TypeError, ValueError):
                continue
            if d and c == c:
                out.append((d, c))
        return out

    s, i = _norm(stock_df), _norm(index_df)
    if not s or not i:
        return None
    s_map, i_map = dict(s), dict(i)
    if trade_date not in s_map or trade_date not in i_map:
        return None
    dates = [d for d, _ in s]
    try:
        t0 = dates.index(trade_date)
    except ValueError:
        return None
    if t0 + 5 >= len(dates):
        return None
    t5 = dates[t0 + 5]
    if t5 not in i_map:
        return None
    stock_ret = (s_map[t5] / s_map[trade_date] - 1) * 100
    index_ret = (i_map[t5] / i_map[trade_date] - 1) * 100
    return round(stock_ret, 2), round(index_ret, 2)


def real_price_lookup(stock_code: str, trade_date: str) -> tuple | None:
    """真实行情回溯（调度/面板触发迭代用）：标的 vs 沪深300 信号后 5 日涨跌幅。
    行情不足/接口失败 → None（该信号不计入统计，诚实降级）。"""
    try:
        from app.datasource.fallback import get_datasource

        src = get_datasource()
        start = f"{trade_date[:4]}0101"
        end = time.strftime("%Y-%m-%d")
        stock = src.fetch_daily_kline(stock_code, start, end)
        index = src.fetch_daily_kline(_BENCH_INDEX, start, end)
        return _forward_5d_returns(stock, index, trade_date)
    except Exception as exc:  # noqa: BLE001 单信号回溯失败跳过，不阻塞迭代
        logger.warning("游资信号行情回溯失败 %s/%s: %s", stock_code, trade_date, exc)
        return None


def compute_win_rate(signals: list[dict], price_lookup=None) -> dict:
    """信号胜率统计：跑赢大盘 = 1 次有效。返回 {countable, wins, win_rate, skipped, details}"""
    lookup = price_lookup or real_price_lookup
    details = []
    wins = countable = 0
    skipped = []
    for s in signals:
        got = lookup(s["stock_code"], s["trade_date"])
        if got is None:
            skipped.append(f"{s['stock_code']} {s['trade_date']}")
            continue
        stock_ret, index_ret = got
        countable += 1
        win = stock_ret > index_ret
        wins += int(win)
        details.append({"stock_code": s["stock_code"],
                        "stock_name": s.get("stock_name", ""),
                        "trade_date": s["trade_date"], "net_buy": s["net_buy"],
                        "stock_ret_5d": stock_ret, "index_ret_5d": index_ret,
                        "win": win})
    return {"countable": countable, "wins": wins,
            "win_rate": round(wins / countable, 4) if countable else None,
            "skipped": skipped, "details": details}


def _tier_suggestion(profile: dict, wr: dict) -> dict | None:
    """按胜率生成降/升档建议（温和策略，样本不足不产建议）。
    返回 agent_suggestion 载荷（target_agent=discover：候选/评分提示词标注入口）；
    观察档连续误判 → reason 标注"谨慎/反向参考"（写入提示词由人工决定）。"""
    rate = wr.get("win_rate")
    countable = wr.get("countable", 0)
    if rate is None or countable < _MIN_SIGNALS:
        return None
    tier = profile.get("tier") or "观察"
    if rate < _WIN_LOW:
        new_tier = _DOWNGRADE.get(tier, "观察")
        reason = (f"信号后5日胜率 {rate:.0%}（{wr['wins']}/{countable}）低于 40%，"
                  f"属连续误判游资；建议降档 {tier}→{new_tier} 并降低其信号权重")
        if new_tier == tier:
            reason += "（已处观察档，不再降）"
        reason += "；建议在候选/评分提示词标注'谨慎/反向参考'（人工决定是否写入）"
    elif rate >= _WIN_HIGH:
        new_tier = _UPGRADE.get(tier, tier)
        if new_tier == tier:
            return None  # 已处最高档一线，无上升空间
        reason = (f"信号后5日胜率 {rate:.0%}（{wr['wins']}/{countable}）≥ 60%，"
                  f"信号稳定有效；建议升档 {tier}→{new_tier}")
    else:
        return None  # 40%~60%：保持，不机械调整
    return {
        "target_agent": "discover",
        "target_kind": "profile",
        "rule_name": f"游资[{profile.get('actor_name', '')}]梯队/权重调整",
        "current_value": tier,
        "suggested_value": new_tier,
        "reason": reason,
        "evidence": (f"统计口径：席位 {profile.get('seat_code')}"
                     f"（协同 {('、'.join(profile.get('co_seats') or []) or '无')}）龙虎榜净买入信号 "
                     f"后 5 个交易日跑赢沪深300 计有效；样本 {wr['wins']}/{countable}，"
                     f"跳过 {len(wr.get('skipped') or [])} 条（行情不足）"),
    }


def run_win_rate_iteration(price_lookup=None) -> dict:
    """全量胜率迭代（代码侧，温和策略）：
    1) 逐游资收集买入信号 → 统计胜率（可注入行情回溯器，测试用假数据）；
    2) 统计事实落库（win_rate_5d/last_review_at，可追溯）；
    3) 生成降/升档建议落 agent_suggestion（pending 待人工审核），不自动改档位。
    返回 {"updated": [...], "suggestions": [...], "errors": [...]}"""
    now_str = time.strftime("%Y-%m-%d %H:%M")
    updated, suggestions, errors = [], [], []
    for profile in repo.list_hot_money_profiles():
        try:
            signals = collect_signals(profile)
            wr = compute_win_rate(signals, price_lookup)
            repo.update_profile_win_rate(profile["id"], wr["win_rate"], now_str)
            updated.append({"actor_name": profile["actor_name"],
                            "tier": profile["tier"],
                            "win_rate_5d": wr["win_rate"],
                            "countable": wr["countable"]})
            sug = _tier_suggestion(profile, wr)
            if sug:
                sid = repo.insert_agent_suggestion(
                    review_id=0, target_agent=sug["target_agent"],
                    rule_name=sug["rule_name"],
                    current_value=sug["current_value"],
                    suggested_value=sug["suggested_value"],
                    reason=sug["reason"], evidence=sug["evidence"],
                    target_kind=sug["target_kind"])
                suggestions.append({"id": sid, "actor_name": profile["actor_name"],
                                    "rule_name": sug["rule_name"],
                                    "current_value": sug["current_value"],
                                    "suggested_value": sug["suggested_value"]})
        except Exception as exc:  # noqa: BLE001 单游资统计失败不阻断整体
            errors.append({"actor_name": profile.get("actor_name"), "error": str(exc)})
            logger.warning("游资胜率统计失败 %s: %s", profile.get("actor_name"), exc)
    return {"updated": updated, "suggestions": suggestions, "errors": errors}


def apply_tier_suggestion(suggestion_id: int) -> dict:
    """人工审核后应用档位建议（【监管红线】仅 approved 状态可执行）：
    读取建议 suggested_value 档位 → 更新该游资档案 tier；
    pending/rejected → 拒绝执行并报错（代码绝不自动改权重生效）。"""
    sug = repo.get_agent_suggestion(suggestion_id)
    if sug is None:
        raise ValueError(f"建议不存在: {suggestion_id}")
    if sug.status != "approved":
        raise ValueError(f"档位建议必须经人工审核（approved）后才能生效，当前状态: {sug.status}")
    new_tier = str(sug.suggested_value or "").strip()
    if new_tier not in _TIER_PATTERN:
        raise ValueError(f"建议档位无效: {sug.suggested_value}")
    # rule_name 形如 游资[赵老哥]梯队/权重调整 → 提取游资名
    rule_name = str(sug.rule_name or "")
    actor = rule_name.split("[", 1)[1].split("]", 1)[0] if "[" in rule_name else ""
    profile = repo.get_profile_by_actor(actor) if actor else None
    if profile is None:
        raise ValueError(f"游资档案不存在: {actor}")
    repo.upsert_hot_money_profile(profile["actor_name"], profile["seat_code"],
                                  tier=new_tier, style_tags=profile.get("style_tags"),
                                  good_themes=profile.get("good_themes"),
                                  co_seats=profile.get("co_seats"),
                                  source=profile.get("source") or "手动")
    logger.info("游资档位建议已人工确认生效: %s %s→%s（suggestion_id=%s）",
                actor, profile["tier"], new_tier, suggestion_id)
    return {"actor_name": actor, "old_tier": profile["tier"],
            "new_tier": new_tier, "suggestion_id": suggestion_id}
