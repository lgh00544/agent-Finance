"""持仓监控时效性测试（不触网：akshare 全部 mock）：
1. 调度窗口边界：盘中 9:30-11:30 / 13:00-15:00、收盘校验 15:00-15:30
2. 实时行情解析与降级链：东财盘口 → 雪球单股 → 全市场快照
3. 交易数学：止损/止盈距离、盈亏比例、市值（基于当次最新价纯数学计算）
4. 告警等级变化重推：同日同类去重 + 30 分钟冷却
"""
from datetime import datetime

import pandas as pd
import pytest

from app.agents import monitor as monitor_agent
from app.datasource import akshare_source
from app.datasource.akshare_source import AkshareSource
from app.scheduler import jobs


# ================= 调度窗口 =================

def test_trading_window_boundaries():
    assert jobs._in_trading_window(datetime(2026, 8, 4, 9, 29)) is False
    assert jobs._in_trading_window(datetime(2026, 8, 4, 9, 30)) is True
    assert jobs._in_trading_window(datetime(2026, 8, 4, 11, 30)) is True
    assert jobs._in_trading_window(datetime(2026, 8, 4, 11, 31)) is False
    assert jobs._in_trading_window(datetime(2026, 8, 4, 12, 59)) is False
    assert jobs._in_trading_window(datetime(2026, 8, 4, 13, 0)) is True
    assert jobs._in_trading_window(datetime(2026, 8, 4, 15, 0)) is True
    assert jobs._in_trading_window(datetime(2026, 8, 4, 15, 1)) is False


def test_close_check_window_boundaries():
    assert jobs._in_close_check_window(datetime(2026, 8, 4, 14, 59)) is False
    assert jobs._in_close_check_window(datetime(2026, 8, 4, 15, 0)) is True
    assert jobs._in_close_check_window(datetime(2026, 8, 4, 15, 30)) is True
    assert jobs._in_close_check_window(datetime(2026, 8, 4, 15, 31)) is False


# ================= 交易数学（基于当次最新价纯数学计算） =================

def _holding(**kw):
    base = {"id": 1, "stock_code": "600519", "stock_name": "贵州茅台", "entry_date": "2026-07-20",
            "entry_price": 100.0, "shares": 100, "cost": 10000.0, "stop_loss": 90.0,
            "take_profit": 120.0, "target_pct": 0.0, "status": "holding"}
    base.update(kw)
    return type("H", (), base)()


def test_trade_math_basic():
    """最新价 110：止损距离=(90-110)/110、止盈距离=(120-110)/110、盈亏=10%、市值=11000"""
    m = monitor_agent._trade_math(110.0, _holding())
    assert m["stop_loss_distance_pct"] == -18.18
    assert m["take_profit_distance_pct"] == 9.09
    assert m["pnl_pct"] == 10.0
    assert m["market_value"] == 11000.0


def test_trade_math_price_none():
    """行情缺失：距离/盈亏/市值全 None（不伪造 0）"""
    m = monitor_agent._trade_math(None, _holding())
    assert m["stop_loss_distance_pct"] is None
    assert m["take_profit_distance_pct"] is None
    assert m["pnl_pct"] is None and m["market_value"] is None


def test_trade_math_no_stop_loss():
    """止损/止盈未设置（0）：距离 None；盈亏/市值仍正常"""
    m = monitor_agent._trade_math(110.0, _holding(stop_loss=0.0, take_profit=0.0))
    assert m["stop_loss_distance_pct"] is None
    assert m["take_profit_distance_pct"] is None
    assert m["pnl_pct"] == 10.0 and m["market_value"] == 11000.0


# ================= 实时行情拉取与降级 =================

class _Src:
    def __init__(self, quote):
        self._quote = quote

    def fetch_spot_quote(self, code):
        return self._quote


def test_fetch_realtime_quote_ok():
    src = _Src({"code": "600519", "name": "贵州茅台", "price": 110.5,
                "change_pct": 1.2, "time": "2026-08-04 14:30:00"})
    quote, stale = monitor_agent._fetch_realtime_quote(src, "600519", {})
    assert stale is False
    assert quote["price"] == 110.5


def test_fetch_realtime_quote_fallback_kline():
    """实时价不可用 → 日K最新收盘兜底（上一次有效数据）+ stale 标记"""
    indicators = {"recent_klines": [{"date": "2026-08-01", "close": 105.0},
                                    {"date": "2026-08-04", "close": 108.0}]}
    quote, stale = monitor_agent._fetch_realtime_quote(_Src({}), "600519", indicators)
    assert stale is True
    assert quote["price"] == 108.0


def test_fetch_realtime_quote_exception():
    """实时行情异常不抛错，兜底日K；无日K 时 price None"""

    class Boom:
        def fetch_spot_quote(self, code):
            raise RuntimeError("数据源不可达")

    quote, stale = monitor_agent._fetch_realtime_quote(Boom(), "600519", {})
    assert quote["price"] is None and stale is False


# ================= fetch_spot_quote 降级链（盘口→雪球→快照） =================

def _no_sleep(monkeypatch):
    monkeypatch.setattr(akshare_source.time, "sleep", lambda s: None)


def test_fetch_spot_quote_bid_ask(monkeypatch):
    """东财盘口 item/value → 解析最新价/涨幅（TTL 30s 缓存键按代码隔离）"""
    _no_sleep(monkeypatch)

    def fake_bid_ask(symbol, timeout=None):
        assert symbol == "600001"
        return pd.DataFrame({"item": ["最新", "涨幅", "名称"], "value": [12.34, 1.56, "测试股"]})

    monkeypatch.setattr(akshare_source.ak, "stock_bid_ask_em", fake_bid_ask)
    q = AkshareSource().fetch_spot_quote("600001")
    assert q["price"] == 12.34 and q["change_pct"] == 1.56
    assert q["name"] == "测试股"


def test_fetch_spot_quote_xq_fallback(monkeypatch):
    """东财盘口失败 → 雪球单股（SH/SZ 前缀）解析"""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(akshare_source.ak, "stock_bid_ask_em",
                        lambda symbol, timeout=None: (_ for _ in ()).throw(ConnectionError("东财拒绝连接")))

    def fake_xq(symbol):
        assert symbol == "SZ300001"
        return pd.DataFrame({"item": ["现价", "涨幅", "名称"], "value": [45.6, -2.3, "测试股"]})

    monkeypatch.setattr(akshare_source.ak, "stock_individual_spot_xq", fake_xq)
    q = AkshareSource().fetch_spot_quote("300001")
    assert q["price"] == 45.6 and q["change_pct"] == -2.3


def test_fetch_spot_quote_universe_fallback(monkeypatch):
    """盘口与雪球都失败 → 全市场快照匹配（快照本身东财→新浪双降级）"""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(akshare_source.ak, "stock_bid_ask_em",
                        lambda symbol, timeout=None: (_ for _ in ()).throw(ConnectionError("东财拒绝连接")))
    monkeypatch.setattr(akshare_source.ak, "stock_individual_spot_xq",
                        lambda symbol: (_ for _ in ()).throw(RuntimeError("雪球失败")))

    source = AkshareSource()
    monkeypatch.setattr(source, "fetch_spot_universe", lambda: pd.DataFrame(
        [{"code": "600002", "name": "测试股", "price": 9.99, "change_pct": 0.5}]))
    q = source.fetch_spot_quote("600002")
    assert q["price"] == 9.99 and q["name"] == "测试股"


def test_fetch_spot_quote_all_fail_empty(monkeypatch):
    """三级全失败 → 返回 {}（调用方用日K兜底并标注数据暂未更新）"""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(akshare_source.ak, "stock_bid_ask_em",
                        lambda symbol, timeout=None: (_ for _ in ()).throw(ConnectionError("东财拒绝连接")))
    monkeypatch.setattr(akshare_source.ak, "stock_individual_spot_xq",
                        lambda symbol: (_ for _ in ()).throw(RuntimeError("雪球失败")))

    source = AkshareSource()
    monkeypatch.setattr(source, "fetch_spot_universe", lambda: pd.DataFrame())
    q = source.fetch_spot_quote("600003")
    assert q == {}


# ================= 告警等级变化重推（去重 + 冷却） =================

def test_severity_changed_rules(monkeypatch):
    code, today = "600519", "2026-08-04"
    last_key = f"alert:last:{code}:{today}"
    state = {"last": "reduce|warning", "dedup": False}

    def fake_get(key):
        return state["last"] if key == last_key else None

    def fake_set(key, value, ttl_seconds):
        state["last"] = value

    def fake_dedup(key, ttl_seconds):
        return state["dedup"]

    monkeypatch.setattr(monitor_agent.cache, "get", fake_get)
    monkeypatch.setattr(monitor_agent.cache, "set", fake_set)
    monkeypatch.setattr(monitor_agent.cache, "alert_deduplicated", fake_dedup)

    sig = {"action": "exit", "severity": "critical"}
    # 等级/建议变化且无冷却 → 允许重推
    assert monitor_agent._severity_changed(code, today, sig) is True
    # 30 分钟冷却命中 → 不再重推
    state["dedup"] = True
    assert monitor_agent._severity_changed(code, today, sig) is False
    # 与已推信号相同 → 不重推
    state["dedup"] = False
    state["last"] = "exit|critical"
    assert monitor_agent._severity_changed(code, today, sig) is False


def test_severity_changed_no_last_record(monkeypatch):
    """无当日已推记录（首次告警）→ 不走等级变化重推（由主去重路径处理）"""
    monkeypatch.setattr(monitor_agent.cache, "get", lambda k: None)
    assert monitor_agent._severity_changed("600519", "2026-08-04",
                                           {"action": "reduce", "severity": "warning"}) is False
