"""派发期自动判定：6 维计算 + 主入口（供 Monitor/Sell/Score 注入）

【刚性代码逻辑】只算 6 维分数 + phase 映射 + 缺失标注；不做最终买卖决策（LLM 保留一票否决）。
6 维阈值均参考权重（K175），非死条件；缺失数据 → null + missing_data，不补零不补均值。
"""
import json
import time
from datetime import datetime, timedelta

from app.cache import cache
from app.datasource.fallback import get_datasource

_PHASE_LABELS = ["拉升期", "初期派发", "砸盘期", "反弹期", "末跌期", "触底期"]
# 参考阈值（非死条件）：time=5日/20日动能比、space=距52周高%、vp=量价背离、cap=主力趋势、pattern=反转形态
_TR = {"time": 0.5, "space": 20.0, "vp": 0.3, "cap": 0, "pattern": 1}


def _kline(code: str, days: int = 260) -> list | None:
    """日K → [(date, close, volume)] 升序；空/异常返回 None"""
    try:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        k = get_datasource().fetch_daily_kline(code, start, time.strftime("%Y-%m-%d"))
        rows = []
        for _, r in k.iterrows():
            try:
                rows.append((str(r["date"])[:10], float(r["close"]), float(r.get("volume") or 0)))
            except (TypeError, ValueError):
                continue
        return sorted(rows) if len(rows) >= 20 else None
    except Exception:  # noqa: BLE001
        return None


def _rets(prices: list):
    """[(datetime,close)] → 最近 n 日累计涨跌幅（%）字典；不足 None"""
    closes = [p for _, p, _ in prices]
    last = closes[-1]
    out = {}
    for n in (5, 20, 250):
        s = closes[-n - 1] if len(closes) > n else None
        out[n] = (last / s - 1) * 100 if s and s > 0 else None
    return out


def time_dimension(kl) -> dict:
    r = _rets(kl)
    v5, v20 = r[5], r[20]
    value = (v5 / v20) if (v5 is not None and v20 and v20 != 0) else None
    return {"value": round(value, 3) if value is not None else None,
            "triggered": bool(value is not None and value < _TR["time"])}


def space_dimension(kl) -> dict:
    highs = [h for _, h, _ in kl[-260:]]
    low, high, last = min(highs), max(highs), kl[-1][1]
    value = (high - last) / high * 100 if high else None  # 距52周高%
    return {"value": round(value, 2) if value is not None else None,
            "triggered": bool(value is not None and value < _TR["space"])}


def volume_price_dimension(kl) -> dict:
    vols = [v for _, _, v in kl[-20:]]
    closes = [c for _, c, _ in kl[-20:]]
    if len(vols) < 20 or sum(vols[-20:]) <= 0 or sum(vols[-5:]) <= 0:
        return {"value": None, "triggered": False}
    v5, v20 = sum(vols[-5:]) / 5, sum(vols[-20:]) / 20
    r5 = (closes[-1] / closes[-5] - 1) if len(closes) >= 5 and closes[-5] else 0
    r20 = (closes[-1] / closes[0] - 1) if closes[0] else 0
    value = (v5 / v20 - 1) - (r5 - r20)  # 量能放大但涨幅收窄 → 背离为正
    return {"value": round(value, 3), "triggered": value > _TR["vp"]}


def capital_flow_dimension(code: str, trade_date: str) -> dict:
    try:
        ff = get_datasource().fetch_fund_flow(code)
        rows = [float(r.get("main_net_inflow") or 0) for _, r in ff.tail(5).iterrows()
                if r.get("main_net_inflow") is not None]
        if not rows:
            return {"value": None, "triggered": False}
        value = sum(1 for x in rows if x > 0) - sum(1 for x in rows if x < 0)  # 净流入日-净流出日
        return {"value": value, "triggered": value < _TR["cap"]}
    except Exception:  # noqa: BLE001
        return {"value": None, "triggered": False}


def pattern_dimension(kl) -> dict:
    """近 10 日反转形态计数（双顶/跌破近期平台，确定性检查）"""
    if not kl or len(kl) < 10:
        return {"value": None, "triggered": False}
    closes = [c for _, c, _ in kl[-10:]]
    cnt = 0
    if closes[-1] < min(closes[:-1]):  # 跌破 9 日平台（颈线）
        cnt += 1
    peak, peak_i = max(closes), closes.index(max(closes))
    if peak_i >= 3 and (closes[-1] - peak) / peak < -0.02:  # 冲高回落 >2%
        cnt += 1
    return {"value": cnt, "triggered": cnt >= _TR["pattern"]}


def policy_dimension() -> dict:
    return {"value": None, "triggered": False}  # 外部输入占位，无数据


def compute_distribution_phase(symbol: str, trade_date: str) -> dict:
    """主入口：6 维计算 → phase/confidence → 结构体（带 86400s 缓存）。
    返回 {phase, phase_label, confidence, six_dim, missing_data, trade_date}"""
    key = f"distribution_phase:{trade_date}:{symbol}"
    raw = cache.get(key)
    if raw:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            pass
    kl = _kline(symbol)
    dims = {
        "time": time_dimension(kl) if kl else {"value": None, "triggered": False},
        "space": space_dimension(kl) if kl else {"value": None, "triggered": False},
        "volume_price": volume_price_dimension(kl) if kl else {"value": None, "triggered": False},
        "capital_flow": capital_flow_dimension(symbol, trade_date),
        "pattern": pattern_dimension(kl) if kl else {"value": None, "triggered": False},
        "policy": policy_dimension(),
    }
    missing = [d for d, s in dims.items() if s["value"] is None]
    n = sum(1 for s in dims.values() if s["triggered"])
    phase = ({0: 0, 1: 1, 2: 1, 3: 2, 4: 3, 5: 4}.get(n, 5))
    confidence = "高" if not missing else ("中" if len(missing) <= 2 else "低")
    label = _PHASE_LABELS[phase] + ("?" if confidence == "低" else "")
    out = {"phase": phase, "phase_label": label, "confidence": confidence,
           "six_dim": dims, "missing_data": missing, "trade_date": trade_date}
    cache.set(key, json.dumps(out, ensure_ascii=False), 86400)
    return out