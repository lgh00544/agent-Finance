"""行情数据源稳定性测试（不触网：HTTP 与 akshare 全部 mock）：
1. 断路器状态机：连续失败 → 临时降级（跳过主源直接走备用）；冷却到期探测成功切回 + 恢复计数
2. 日志去重：只有状态切换打 WARNING，降级期间无 WARNING 刷屏
3. 时段闸门：午间休盘不打实时接口走收盘快照；周末快照返回空表
4. 批量行情：东财 ulist 解析（data=null / 缺 f124 容错）；批量失败 → 快照过滤降级
5. 统计快照结构
"""
import logging
from datetime import datetime

import pandas as pd
import pytest

from app.core.config import settings
from app.datasource import akshare_source, market_hours
from app.datasource.akshare_source import AkshareSource, DataSourceError
from app.datasource.breaker import get_breaker, reset as breaker_reset
from app.datasource.http_client import _session
from app.services import datasource_stats


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """断路器状态隔离 + 固定交易日盘中 14:00 + 真实 sleep 禁用"""
    monkeypatch.setattr(market_hours, "_now", lambda: datetime(2026, 8, 4, 14, 0))
    monkeypatch.setattr(market_hours, "_load_calendar", lambda: set())
    monkeypatch.setattr(akshare_source.time, "sleep", lambda s: None)
    breaker_reset()
    yield
    breaker_reset()


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """DB 建表（quote_snapshot 测试用真实 SQLite；保持与 test_sector_snapshot 同模式）"""
    from app.db.session import init_db
    init_db()


def _boom():
    raise ConnectionError("东财拒绝连接")


def _stats_before():
    s = datasource_stats.snapshot()
    return s["recoveries"], s["degraded_use"]


# ================= 断路器状态机 =================

def test_breaker_opens_after_threshold(monkeypatch):
    monkeypatch.setattr(settings, "datasource_breaker_threshold", 3)
    breaker = get_breaker("tick")
    assert breaker.should_try() is True
    for _ in range(2):
        breaker.record_failure()
    assert breaker.is_degraded is False
    breaker.record_failure()
    assert breaker.is_degraded is True
    assert breaker.should_try() is False  # 降级期间不允许打主源


def test_call_with_retry_skips_primary_when_degraded(monkeypatch):
    """连续失败达阈值 → 降级后不再打主源，直接走备用"""
    monkeypatch.setattr(settings, "datasource_breaker_threshold", 2)
    calls = {"primary": 0, "fallback": 0}

    def primary():
        calls["primary"] += 1
        raise ConnectionError("东财拒绝连接")

    def fallback():
        calls["fallback"] += 1
        return pd.DataFrame([{"x": 1}])

    src = AkshareSource()
    # 一次调用 = 主源 2 次尝试（retry_times=1）→ 连续 2 次失败触发降级
    with pytest.raises(DataSourceError):
        src._call_with_retry("test", primary, None, kind="tick")
    assert get_breaker("tick").is_degraded
    assert calls["primary"] == 2
    # 降级期间：不打主源，直接走备用
    df = src._call_with_retry("test", primary, fallback, kind="tick")
    assert not df.empty
    assert calls["primary"] == 2
    assert calls["fallback"] == 1


def test_breaker_probe_recovers_after_cooldown(monkeypatch):
    """冷却到期后静默探测主源：成功切回 + 恢复计数 +1"""
    monkeypatch.setattr(settings, "datasource_breaker_threshold", 2)
    monkeypatch.setattr(settings, "datasource_breaker_cooldown", 600)
    rec_before, _ = _stats_before()
    src = AkshareSource()
    with pytest.raises(DataSourceError):
        src._call_with_retry("t", _boom, None, kind="tick")  # 2 次失败 → 降级
    assert get_breaker("tick").is_degraded
    # 冷却到期（cooldown 置 0）→ should_try 放行 → 主源成功 → 切回 + 恢复计数
    monkeypatch.setattr(settings, "datasource_breaker_cooldown", 0)
    df = src._call_with_retry("t", lambda: pd.DataFrame([{"x": 1}]), None, kind="tick")
    assert not df.empty
    assert get_breaker("tick").is_degraded is False
    assert datasource_stats.snapshot()["recoveries"] == rec_before + 1


def test_breaker_logs_once_on_transition(caplog, monkeypatch):
    """日志去重：降级切换仅 1 条 WARNING；降级期间无 WARNING"""
    monkeypatch.setattr(settings, "datasource_breaker_threshold", 3)
    monkeypatch.setattr(settings, "datasource_breaker_cooldown", 600)
    monkeypatch.setattr(settings, "datasource_retry_times", 0)  # 每次 1 次尝试
    src = AkshareSource()
    with caplog.at_level(logging.WARNING, logger="app.datasource.breaker"):
        for _ in range(4):
            with pytest.raises(DataSourceError):
                src._call_with_retry("t", _boom, None, kind="tick")
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1  # 仅进入降级那一条
    assert "临时降级" in warnings[0].getMessage()
    # 降级期间：跳过主源直接走备用，也不产生 WARNING（无备用时抛错走 DEBUG）
    caplog.clear()
    src = AkshareSource()
    with caplog.at_level(logging.WARNING, logger="app.datasource.breaker"):
        with pytest.raises(DataSourceError):
            src._call_with_retry("t", _boom, None, kind="tick")
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ================= 时段闸门 =================

def test_spot_quote_skips_realtime_during_lunch_break(monkeypatch):
    """午间休盘：不请求东财盘口，直接走收盘快照"""
    monkeypatch.setattr(market_hours, "_now", lambda: datetime(2026, 8, 4, 12, 0))
    called = []

    def fake_bid_ask(symbol, timeout=None):
        called.append(symbol)
        return pd.DataFrame({"item": ["最新", "涨幅"], "value": [1.0, 0.0]})

    monkeypatch.setattr(akshare_source.ak, "stock_bid_ask_em", fake_bid_ask)
    src = AkshareSource()
    monkeypatch.setattr(src, "fetch_spot_universe", lambda: pd.DataFrame(
        [{"code": "600001", "name": "测试股", "price": 9.99, "change_pct": 0.5}]))
    q = src.fetch_spot_quote("600001")
    assert called == []          # 未打实时接口
    assert q["price"] == 9.99    # 收盘快照兜底


def test_spot_universe_empty_on_weekend(monkeypatch):
    """周末：完全暂停实时请求，快照返回空表（不触网）"""
    monkeypatch.setattr(market_hours, "_now", lambda: datetime(2026, 8, 8, 10, 0))  # 周六
    monkeypatch.setattr(akshare_source.ak, "stock_zh_a_spot_em",
                        lambda: (_ for _ in ()).throw(AssertionError("非交易日不应请求")))

    df = AkshareSource().fetch_spot_universe()
    assert df.empty
    assert "code" in df.columns


# ================= 批量行情 =================

def _mock_session_get(monkeypatch, responder):
    monkeypatch.setattr(_session, "get",
                        lambda url, params=None, headers=None, timeout=None, **kw: responder(url))


def test_batch_ulist_parse(monkeypatch):
    """东财 ulist 批量解析：正常价 / data=null 容错 / f2 不可解析置 None"""
    payload = {"data": {"diff": [
        {"f12": "600519", "f14": "贵州茅台", "f2": 1500.5, "f3": 1.23, "f124": "150000"},
        {"f12": "000001", "f14": "平安银行", "f2": 12.34, "f3": -0.5, "f124": None},
        {"f12": "300999", "f14": "缺价股", "f2": "-", "f3": None, "f124": None},
    ]}}
    _mock_session_get(monkeypatch, lambda url: _FakeResp(payload))
    out = AkshareSource().fetch_spot_quotes_batch(["600519", "000001", "300999"])
    assert out["600519"]["price"] == 1500.5 and out["600519"]["name"] == "贵州茅台"
    assert out["000001"]["price"] == 12.34 and out["000001"]["change_pct"] == -0.5
    assert out["300999"]["price"] is None  # f2 不可解析容错


def test_batch_data_null_falls_back_to_universe(monkeypatch):
    """data=null（限流）→ 批量失败 → 快照过滤降级"""
    _mock_session_get(monkeypatch, lambda url: _FakeResp({"data": None}))
    src = AkshareSource()
    monkeypatch.setattr(src, "fetch_spot_universe", lambda: pd.DataFrame(
        [{"code": "600001", "name": "A", "price": 9.9, "change_pct": 0.2},
         {"code": "600002", "name": "B", "price": 8.8, "change_pct": -0.1}]))
    out = src.fetch_spot_quotes_batch(["600001", "600002"])
    assert out["600001"]["price"] == 9.9
    assert out["600002"]["change_pct"] == -0.1


def test_batch_network_failure_then_per_stock(monkeypatch):
    """主源与快照都失败 → 逐只 fetch_spot_quote 兜底"""
    _mock_session_get(monkeypatch, lambda url: (_ for _ in ()).throw(ConnectionError("网络断开")))
    src = AkshareSource()
    monkeypatch.setattr(src, "fetch_spot_universe", lambda: pd.DataFrame())
    monkeypatch.setattr(src, "fetch_spot_quote", lambda code: {
        "code": code, "name": "单只", "price": 5.5, "change_pct": 0.0, "time": ""})
    out = src.fetch_spot_quotes_batch(["600003", "600004"])
    assert out["600003"]["price"] == 5.5 and out["600004"]["price"] == 5.5


def test_batch_non_trading_hours_uses_snapshot(monkeypatch):
    """非交易时段：批量不请求实时接口，直接走收盘快照"""
    monkeypatch.setattr(market_hours, "_now", lambda: datetime(2026, 8, 4, 12, 0))
    _mock_session_get(monkeypatch, lambda url: (_ for _ in ()).throw(AssertionError("不应请求实时接口")))
    src = AkshareSource()
    monkeypatch.setattr(src, "fetch_spot_universe", lambda: pd.DataFrame(
        [{"code": "600005", "name": "C", "price": 7.7, "change_pct": 0.1}]))
    out = src.fetch_spot_quotes_batch(["600005"])
    assert out["600005"]["price"] == 7.7


# ================= 统计快照 =================

def test_stats_snapshot_structure():
    s = datasource_stats.snapshot()
    for field in ("date", "requests", "failures", "degraded_use", "recoveries",
                  "success_rate_pct", "kinds", "checked_at"):
        assert field in s
    kinds = {k["kind"] for k in s["kinds"]}
    assert kinds == {"tick", "snapshot"}
    assert all(k["current_source"] in ("primary", "degraded") for k in s["kinds"])
    assert s["requests"] == sum(k["requests"] for k in s["kinds"])


# ================= 腾讯批量行情 + 持仓价快照（持仓监控页稳定性根治） =================

class _TencentResp:
    status_code = 200

    def __init__(self, text):
        self.text = text


def test_tencent_batch_parse_and_prefix(monkeypatch):
    """腾讯批量：解析 price=fields[3]；6 位代码去前缀；6 开头加 sh、否则 sz（N 只 = 1 次 HTTP）"""
    payload = ('v_sh600487="1~白云机场~600487~62.18~62.02~60.89~...";\n'
               'v_sz002475="1~立讯精密~002475~54.65~54.00~53.00~..."')
    captured = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return _TencentResp(payload)

    src = AkshareSource()
    monkeypatch.setattr(src._quotes_session, "get", fake_get)
    out = src.fetch_tencent_batch(["600487", "002475"])
    assert out == {"600487": 62.18, "002475": 54.65}      # price=fields[3]，去前缀
    assert "sh600487" in captured["url"] and "sz002475" in captured["url"]


def test_tencent_batch_codes_normalized(monkeypatch):
    """代码左补零至 6 位；空白剔除；6 开头 sh、其余 sz"""
    captured = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return _TencentResp('v_sz006005="1~x~6005~13.5~13.0~..."')

    src = AkshareSource()
    monkeypatch.setattr(src._quotes_session, "get", fake_get)
    src.fetch_tencent_batch(["6005", " 002475 ", ""])
    # "6005".zfill(6) = "006005"（非 6 开头）→ sz；" 002475 " → "002475" → sz
    assert "sz006005,sz002475" in captured["url"]


def test_tencent_batch_all_failed_returns_empty(monkeypatch):
    """腾讯全失败（连拒/解析空）→ 返回 {}，调用方走 DB 快照兜底"""
    def fake_get(url, timeout=None):
        raise ConnectionError("腾讯不可达")

    src = AkshareSource()
    monkeypatch.setattr(src._quotes_session, "get", fake_get)
    assert src.fetch_tencent_batch(["600487"]) == {}
    # 解析无结果也算失败
    monkeypatch.setattr(src._quotes_session, "get",
                        lambda url, timeout=None: _TencentResp("v_sh600487=\"1~x~600487~~\""))
    assert src.fetch_tencent_batch(["600487"]) == {}       # price 缺字段跳过


def test_quote_snapshot_upsert_and_readback():
    """持仓价快照：整表删后插 + 10 分钟内读回（source 保留）"""
    from app.db import repo
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assert repo.upsert_quote_snapshot([
        {"stock_code": "600487", "name": "白云机场", "price": 62.18,
         "change_pct": None, "source": "tencent", "updated_at": now},
        {"stock_code": "000001", "name": "平安银行", "price": 11.41,
         "change_pct": 0.2, "source": "universe", "updated_at": now},
    ]) == 2
    df = repo.get_quote_snapshot(within_minutes=10)
    assert df is not None and set(df["code"]) == {"600487", "000001"}
    assert set(df["source"]) == {"tencent", "universe"}


def test_quote_snapshot_stale_returns_none():
    """全部过期（updated_at 超窗口）→ get 返回 None（走下一级全市场快照）"""
    from app.db import repo
    repo.upsert_quote_snapshot([
        {"stock_code": "600000", "name": "x", "price": 1.0,
         "change_pct": None, "source": "tencent",
         "updated_at": "2020-01-01 00:00:00"}])
    assert repo.get_quote_snapshot(within_minutes=10) is None
    repo.upsert_quote_snapshot([])  # 清表，避免污染后续
