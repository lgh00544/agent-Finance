"""资本视图计算服务：游资/龙虎榜/资金流 三维快照 + K189 对倒 + 30 日统计

【刚性代码逻辑】纯代码聚合计算，不做市场判断；K189 对倒为纯代码判定（铁律4 不交 LLM）。
Schema: {recent_actors, coordination, wash_suspect, stats_30d, theme_resonance,
         source, missing_data} + 三维明细（dragon_tiger_rows / capital_flow_rows）。
硬约束：
- 缺数据 → null + missing_data 明列，不补零不补均值（K227）；
- 30 日无数据 → recent_actors=[]、coordination="数据不足"，绝不写"无动作"；
- 单源必标 source="sse_only"（铁律3 诚实标注，当前实测仅东财可用）；
- 未知营业部不硬绑席位映射 → 不入 recent_actors，留给 LLM 研判占位（铁律4）。
结果 86400s 缓存（SimpleCache.get_or_set），force 由路由删键击穿。
"""
import json
import logging
import time
from datetime import datetime, timedelta

from app.cache import cache
from app.datasource.fallback import get_datasource
from app.db import repo

logger = logging.getLogger(__name__)

_SOURCE = "sse_only"        # 单源诚实标注（K227 铁律3）
_K189_DAYS = 5              # K189 对倒窗口：同标的近 5 个交易日
_K189_AMT = 1000e4          # 单次金额 ≥ 1000 万（元）
_VIEW_DAYS = 30             # 资本视图统计窗口：近 30 个上榜交易日
_LOOKAHEAD = 5              # 胜率/盈亏比：龙虎榜净买信号后 5 交易日收益
_FETCH_DAYS = 60            # 抓取窗口（日历日，覆盖 >30 上榜交易日）
_TTL = 86400


class SimpleCache:
    """极简缓存封装：app.cache 单例 + get_or_set（key 与路由删键对齐；86400s）"""

    def __init__(self, backend=cache) -> None:
        self._backend = backend

    def get(self, key: str):
        raw = self._backend.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def set(self, key: str, value, ttl: int = _TTL) -> None:
        self._backend.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl)

    def get_or_set(self, key: str, ttl: int = _TTL, loader=None):
        val = self.get(key)
        if val is not None:
            return val
        val = loader()
        if val is not None:
            self.set(key, val, ttl)
        return val


def _num(v) -> float:
    try:
        f = float(v)
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0


def _closes_map(kl: list) -> dict:
    """[(date, close)] → {date: close}（同日多行取最后）"""
    out: dict[str, float] = {}
    for d, c in kl:
        out[d] = c
    return out


# ---------------- 数据读取（模块级，测试可 monkeypatch） ----------------

def _flows_for_stock(stock_code: str) -> list:
    """标的近 60 日龙虎榜流水（升序；失败返回空表不阻塞）"""
    try:
        rows = repo.list_lhb_flows(stock_code=stock_code, limit=500)
        return sorted(rows, key=lambda f: str(f.get("trade_date") or ""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("龙虎榜流水读取失败 %s: %s", stock_code, exc)
        return []


def _kline(code: str) -> list:
    """日K → [(date, close)] 升序；空/异常返回 []"""
    try:
        start = (datetime.now() - timedelta(days=_FETCH_DAYS + 30)).strftime("%Y-%m-%d")
        k = get_datasource().fetch_daily_kline(code, start, time.strftime("%Y-%m-%d"))
        rows = []
        for _, r in k.iterrows():
            try:
                rows.append((str(r["date"])[:10], float(r["close"])))
            except (TypeError, ValueError, KeyError):
                continue
        return sorted(rows)
    except Exception as exc:  # noqa: BLE001
        logger.warning("资本视图日K读取失败 %s: %s", code, exc)
        return []


def _fund_flow_rows(code: str) -> list:
    """个股资金流 → 近 30 日行（升序；失败空表）"""
    try:
        ff = get_datasource().fetch_fund_flow(code)
        rows = []
        for _, r in ff.tail(_VIEW_DAYS + 5).iterrows():
            try:
                rows.append({"trade_date": str(r.get("date"))[:10],
                             "main_net_inflow": _num(r.get("main_net_inflow")),
                             "super_large_net": _num(r.get("super_large_net")),
                             "large_net": _num(r.get("large_net")),
                             "medium_net": _num(r.get("medium_net")),
                             "small_net": _num(r.get("small_net"))})
            except (TypeError, ValueError, KeyError):
                continue
        return [r for r in rows if r.get("trade_date")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("资本视图资金流读取失败 %s: %s", code, exc)
        return []


def _stock_industry(code: str) -> str:
    """标的行业（题材共振用；失败返回 ''）"""
    try:
        info = get_datasource().fetch_stock_info(code)
        return str(info.get("行业") or "") if info else ""
    except Exception:  # noqa: BLE001
        return ""


# ---------------- 纯计算 ----------------

def _window(flows: list, trade_date: str, n: int) -> list:
    """flows 中 ≤ trade_date 的最近 n 个上榜交易日的流水"""
    dates = sorted({str(f.get("trade_date")) for f in flows
                    if f.get("trade_date") and str(f["trade_date"]) <= trade_date})
    keep = set(dates[-n:])
    return [f for f in flows if (f.get("trade_date") or "") in keep]


def _recent_actors(flows: list, trade_date: str) -> list:
    """近 30 日命中游资（席位 → hot_money_profile；未知营业部不硬绑，留 LLM 研判）。"""
    prof_by_seat = {p["seat_code"]: p for p in (repo.list_hot_money_profiles() or [])}
    agg: dict[str, dict] = {}
    for f in _window(flows, trade_date, _VIEW_DAYS):
        seat = (f.get("seat_name") or "").strip()
        if not seat or seat not in prof_by_seat:
            continue
        p = prof_by_seat[seat]
        name = p["actor_name"]
        a = agg.setdefault(name, {"name": name, "seat": seat, "tier": p.get("tier") or "观察",
                                  "net_buy": 0.0, "days": set()})
        a["net_buy"] += _num(f.get("net_buy"))
        a["days"].add(str(f.get("trade_date")))
    return [{"name": n, "seat": a["seat"], "tier": a["tier"], "net_buy": round(a["net_buy"], 2),
             "days_active": len(a["days"])} for n, a in agg.items()]


def _coordination(actors: list) -> str:
    """协调判定（30 日无数据 → 数据不足，绝不写"无动作"）"""
    if not actors:
        return "数据不足"
    buys = [a for a in actors if (a.get("net_buy") or 0) > 0]
    if len(buys) >= 2:
        return "多游资同买"
    if len(buys) == 1:
        return "单家动作"
    return "无显著动作"


def _wash_suspect_k189(recent: list) -> bool:
    """K189 对倒（纯代码，不交 LLM）：近 5 日窗口内，同营业部买+卖两侧共存
    且单次金额 ≥ 1000 万 → True。"""
    by_seat: dict[str, dict] = {}
    for f in recent:
        seat = (f.get("seat_name") or "").strip()
        if not seat:
            continue
        v = by_seat.setdefault(seat, {"buy": 0.0, "sell": 0.0, "max": 0.0})
        b, s = abs(_num(f.get("buy_amt"))), abs(_num(f.get("sell_amt")))
        if b > 0:
            v["buy"] += b
            v["max"] = max(v["max"], b)
        if s > 0:
            v["sell"] += s
            v["max"] = max(v["max"], s)
    return any(v["buy"] > 0 and v["sell"] > 0 and v["max"] >= _K189_AMT
               for v in by_seat.values())


def _stats_30d(flows: list, trade_date: str, kl: list) -> tuple[dict, list]:
    """近 30 日龙虎榜净买信号 → 信号后 5 交易日收益（胜率/盈亏比）。
    平均持仓天数无法从龙虎榜观测 → null + missing_data 明列（K227 诚实）。"""
    missing: list[str] = []
    closes = _closes_map(kl)
    order = [d for d, _ in kl]
    rets: list[float] = []
    for f in _window(flows, trade_date, _VIEW_DAYS):
        if (f.get("net_buy") or 0) <= 0:
            continue
        d = str(f.get("trade_date") or "")
        if d not in closes:
            continue
        i = next((k for k, x in enumerate(order) if x >= d), None)
        j = i + _LOOKAHEAD if i is not None else None
        if i is None or j is None or j >= len(order) or closes.get(order[i], 0) <= 0:
            continue
        rets.append((closes[order[j]] / closes[order[i]] - 1) * 100)
    if not rets:
        missing.append("stats_30d")
        return {"胜率": None, "盈亏比": None, "平均持仓天数": None}, missing
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    payoff = round(avg_win / avg_loss, 2) if (losses and avg_loss > 0) else None
    if payoff is None:
        missing.append("stats_30d.盈亏比")
    missing.append("stats_30d.平均持仓天数")  # 无持仓周期观测源，恒缺
    return {"胜率": round(len(wins) / len(rets), 3) if rets else None,
            "盈亏比": payoff, "平均持仓天数": None}, missing


def _theme_resonance(actors: list, industry: str) -> bool | None:
    """题材共振：已识别游资擅长题材 与 标的行业 文本匹配；缺行业/题材 → None"""
    if not actors or not industry:
        return None
    names = {a["name"] for a in actors}
    themes = set()
    for p in (repo.list_hot_money_profiles() or []):
        if p["actor_name"] in names:
            themes |= {(t or "").strip() for t in (p.get("good_themes") or [])}
    themes.discard("")
    if not themes:
        return None
    return any(t in industry or industry in t for t in themes)


def _dragon_tiger_rows(flows: list, trade_date: str) -> list:
    """龙虎榜维：近 30 日逐日汇总（优先股票级行 seat_name=''；无则聚合席位行）"""
    out = []
    for d in sorted({str(f.get("trade_date")) for f in _window(flows, trade_date, _VIEW_DAYS)}):
        day = [f for f in flows if str(f.get("trade_date")) == d]
        stock_rows = [f for f in day if not (f.get("seat_name") or "").strip()]
        if not stock_rows:
            agg = {"net_buy": sum(_num(f.get("net_buy")) for f in day),
                   "buy_amt": sum(_num(f.get("buy_amt")) for f in day),
                   "sell_amt": sum(_num(f.get("sell_amt")) for f in day)}
        else:
            agg = {"net_buy": sum(_num(f.get("net_buy")) for f in stock_rows),
                   "buy_amt": sum(_num(f.get("buy_amt")) for f in stock_rows),
                   "sell_amt": sum(_num(f.get("sell_amt")) for f in stock_rows)}
        seats = [f for f in day if (f.get("seat_name") or "").strip()]
        top = max(seats, key=lambda f: abs(_num(f.get("net_buy"))), default=None)
        out.append({"trade_date": d, "net_buy": round(agg["net_buy"], 2),
                    "buy_amt": round(agg["buy_amt"], 2), "sell_amt": round(agg["sell_amt"], 2),
                    "top_seat": (top.get("seat_name") if top else ""),
                    "top_seat_net": round(_num(top.get("net_buy")), 2) if top else 0.0,
                    "disclosure_reason": (day[0].get("disclosure_reason") if day else "")})
    return out


# ---------------- 主入口 ----------------

def compute_capital_view(stock_code: str, trade_date: str | None = None) -> dict:
    """资本视图主入口：三维 + stats 计算 → 4 表落库 → 返回（86400s 缓存；force 路由删键）。"""
    trade_date = trade_date or time.strftime("%Y-%m-%d")
    return SimpleCache().get_or_set(
        f"capital_view:{trade_date}:{stock_code}", _TTL,
        lambda: _compute(stock_code, trade_date))


def _compute(stock_code: str, trade_date: str) -> dict:
    missing: list[str] = []
    flows = [f for f in _flows_for_stock(stock_code)
             if (f.get("trade_date") or "") <= trade_date]
    kl = _kline(stock_code)
    if not kl:
        missing.append("kline")
    actors = _recent_actors(flows, trade_date)
    coordination = _coordination(actors)
    recent = _window(flows, trade_date, _K189_DAYS)
    wash = _wash_suspect_k189(recent)
    stats, stats_missing = _stats_30d(flows, trade_date, kl)
    missing += stats_missing
    industry = _stock_industry(stock_code)
    theme = _theme_resonance(actors, industry)
    if theme is None:
        missing.append("theme_resonance")
    dt_rows = _dragon_tiger_rows(flows, trade_date)
    cf_rows = _fund_flow_rows(stock_code)
    if not cf_rows:
        missing.append("capital_flow")
    out = {
        "stock_code": stock_code, "trade_date": trade_date,
        "recent_actors": actors,
        "coordination": coordination,
        "wash_suspect": bool(wash),
        "stats_30d": stats,
        "theme_resonance": theme,
        "source": _SOURCE,
        "missing_data": sorted(set(missing)),
        "dragon_tiger_rows": dt_rows,
        "capital_flow_rows": cf_rows,
    }
    try:
        repo.upsert_capital_view({
            "trade_date": trade_date, "stock_code": stock_code, "source": _SOURCE,
            "recent_actors": [{k: a[k] for k in ("name", "seat", "tier", "net_buy", "days_active")} for a in actors],
            "dragon_tiger_rows": dt_rows, "capital_flow_rows": cf_rows,
            "stats": {"wash_suspect": wash, "coordination": coordination,
                      "win_rate": stats.get("胜率"), "payoff_ratio": stats.get("盈亏比"),
                      "avg_hold_days": stats.get("平均持仓天数"), "theme_resonance": theme,
                      "source": _SOURCE, "missing_data": missing},
            "raw": out,
        })
    except Exception as exc:  # noqa: BLE001 落库失败不阻塞视图返回
        logger.warning("资本视图落库失败 %s/%s: %s", stock_code, trade_date, exc)
    return out


# ---------------- 注入文本 ----------------

def _compact_money(v) -> str:
    """金额友好格式（元 → 亿/万；无千分位逗号，防 CSV 候选表分列错位）"""
    f = _num(v)
    if abs(f) >= 1e8:
        return f"{f / 1e8:.2f}亿"
    if abs(f) >= 1e4:
        return f"{f / 1e4:.1f}万"
    return f"{f:.0f}元"


def build_capital_view_line(cv: dict) -> str:
    """单标的资本视图 → 紧凑行文（Discover 候选表列用；以「；」分隔避免 CSV 逗号破坏字段）"""
    if not cv:
        return ""
    parts = []
    actors = cv.get("recent_actors") or []
    if actors:
        a_items = []
        for a in actors:
            sign = "+" if (a.get("net_buy") or 0) >= 0 else ""
            a_items.append(f"{a['name']}({a.get('tier') or '观察'},{sign}{_compact_money(a.get('net_buy'))}/"
                           f"{a.get('days_active')}日)")
        parts.append("游资[" + "；".join(a_items) + "]")
    else:
        parts.append("游资(30日内无已识别游资；未知营业部留 LLM 研判)")
    parts.append(f"协调={cv.get('coordination') or '数据不足'}")
    parts.append(f"对倒={'是' if cv.get('wash_suspect') else '否'}")
    st = cv.get("stats_30d") or {}
    wr = st.get("胜率")
    pr = st.get("盈亏比")
    wr_s = f"{wr * 100:.0f}%" if isinstance(wr, (int, float)) else "—"
    pr_s = f"{pr:.2f}" if isinstance(pr, (int, float)) else "—"
    parts.append(f"30日胜率={wr_s} 盈亏比={pr_s} 平均持仓=—")
    if cv.get("theme_resonance") is not None:
        parts.append("题材共振=" + ("是" if cv["theme_resonance"] else "否"))
    return "　".join(parts)