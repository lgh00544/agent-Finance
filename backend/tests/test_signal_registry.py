"""批 1 信号基建测试：注册表 / 22 条信号 / 快照口径 / 扫描落表（不触网、不写生产库）。"""
import math

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, SignalTrigger
from app.indicators import compute_signal_snapshot
from app.services import signal_scan
from app.services.indicator import compute_indicators
from app.services.signal_registry import SignalResult, get, list_active, list_all

DEFS = list_all()
DEFS_BY_ID = {item.id: item for item in DEFS}
TRADE_DATE = "2026-09-16"


def _frame(n: int = 300, last_pct: float = 0.0, last_date: str | None = None) -> pd.DataFrame:
    """确定性上升 K 线（无随机数）；末根涨幅 last_pct、末根日期 last_date 可覆盖。"""
    close = [10.0 + 0.001 * i for i in range(n)]
    close[-1] = round(close[-2] * (1 + last_pct / 100.0), 4)
    dates = pd.date_range(end="2026-09-16", periods=n).strftime("%Y-%m-%d").tolist()
    if last_date is not None:
        dates[-1] = last_date
    return pd.DataFrame({
        "date": dates, "open": close, "close": close, "high": [c * 1.01 for c in close],
        "low": [c * 0.99 for c in close], "volume": [100000.0] * n,
        "change_pct": (pd.Series(close).pct_change().fillna(0.0) * 100).tolist(),
    })


def _kline(n: int = 300, last: list[dict] | None = None) -> pd.DataFrame:
    """供信号层用的最小 K 线；末尾若干根 OHLC 可覆盖（形态信号需要 2~3 根）。"""
    rows = [{"open": 10.0, "close": 10.0, "high": 10.2, "low": 9.8}] * n
    if last:
        rows[-len(last):] = last
    return pd.DataFrame(rows)


def _features(**patch) -> dict:
    """信号判定用 features 基线；各用例只覆盖自己关心的字段。"""
    base = dict(latest_close=10.0, high_250d=10.0, low_250d=10.0, boll_pctb=0.5, kdj_k=50.0, kdj_d=50.0,
                prev_kdj_k=50.0, prev_kdj_d=50.0, macd_dif=0.0, macd_dea=0.0, prev_macd_dif=0.0,
                prev_macd_dea=0.0, rsi14=50.0, prev_rsi14=50.0, ma5=10.0, prev_ma5=10.0, ma20=10.0,
                prev_ma20=10.0, ma60=10.0, prev_ma60=10.0, volume_ratio_5=1.0, change_pct=0.0,
                donchian_upper_20=10.05, donchian_lower_20=9.95, donchian_upper_55=10.05,
                donchian_lower_55=9.95)
    return {**base, **patch}


TRIGGERS = {
    "s01": ({"boll_pctb": 0.01}, []), "s02": ({"boll_pctb": 0.99}, []),
    "s03": ({"latest_close": 9.6, "high_250d": 10.0}, []), "s04": ({"latest_close": 10.4, "low_250d": 10.0}, []),
    "s05": ({"kdj_k": 15.0, "kdj_d": 12.0, "prev_kdj_k": 11.0, "prev_kdj_d": 13.0}, []),
    "s06": ({"prev_macd_dif": -0.1, "prev_macd_dea": 0.0, "macd_dif": 0.1, "macd_dea": 0.0}, []),
    "s07": ({"prev_macd_dif": 0.1, "prev_macd_dea": 0.0, "macd_dif": -0.1, "macd_dea": 0.0}, []),
    "s08": ({"prev_rsi14": 20.0, "rsi14": 60.0}, []), "s09": ({"prev_rsi14": 80.0, "rsi14": 40.0}, []),
    "s10": ({"prev_ma5": 9.9, "prev_ma20": 10.0, "ma5": 10.2, "ma20": 10.0}, []),
    "s11": ({"prev_ma20": 9.9, "prev_ma60": 10.0, "ma20": 10.2, "ma60": 10.0}, []),
    "s12": ({"latest_close": 10.2}, []), "s13": ({"latest_close": 9.8}, []),
    "s14": ({"latest_close": 10.2, "donchian_upper_55": 10.05}, []),
    "s15": ({"latest_close": 9.8, "donchian_lower_55": 9.95}, []),
    "s16": ({}, [{"open": 10.0, "close": 10.1, "high": 10.12, "low": 9.7}]),
    "s17": ({}, [{"open": 10.2, "close": 10.0, "high": 10.25, "low": 9.95},
                 {"open": 9.95, "close": 10.3, "high": 10.35, "low": 9.9}]),
    "s18": ({}, [{"open": 10.5, "close": 10.0, "high": 10.52, "low": 9.98},
                 {"open": 9.9, "close": 9.88, "high": 9.95, "low": 9.85},
                 {"open": 9.95, "close": 10.3, "high": 10.35, "low": 9.9}]),
    "s19": ({}, [{"open": 10.0, "close": 9.95, "high": 10.4, "low": 9.93}]),
    "s20": ({}, [{"open": 9.95, "close": 10.3, "high": 10.35, "low": 9.9},
                 {"open": 10.35, "close": 9.9, "high": 10.4, "low": 9.85}]),
    "s21": ({"latest_close": 10.2, "volume_ratio_5": 1.6}, []),
    "s22": ({"change_pct": -2.0, "volume_ratio_5": 0.6}, []),
}


def test_registry_22_signals_layers_directions():
    assert [item.id for item in DEFS] == [f"s{i:02d}" for i in range(1, 23)]
    layers, dirs = {}, {}
    for item in DEFS:
        layers[item.layer] = layers.get(item.layer, 0) + 1
        dirs[item.direction] = dirs.get(item.direction, 0) + 1
    assert layers == {"位置": 5, "动量": 6, "突破": 4, "形态": 5, "量价": 2}
    assert dirs == {"buy": 14, "sell": 8}


def test_registry_defaults_get_and_hardcoded_params():
    assert all(item.status == "candidate" for item in DEFS)
    assert all(item.min_bars == 250 for item in DEFS)
    assert list_active() == []
    assert get("s06").name == "macd_golden_daily" and get("s99") is None
    assert get("s01").params == {"window": 20, "std": 2.0}
    assert get("s06").params == {"fast": 12, "slow": 26, "signal": 9}


@pytest.mark.parametrize("defn", DEFS, ids=[item.id for item in DEFS])
def test_signal_callable_returns_valid_result(defn):
    short = defn.func(_features(), _kline(100), "600000")
    assert isinstance(short, SignalResult) and short.hit is False and short.reason == "insufficient_bars"
    out = defn.func(_features(), _kline(), "600000")
    assert isinstance(out, SignalResult) and isinstance(out.hit, bool)
    assert out.reason in ("ok", "not_triggered") or out.reason.startswith("data_missing:")


def test_every_signal_fires_on_its_own_conditions():
    assert len(TRIGGERS) == 22
    for sid, (patch, ohlc) in TRIGGERS.items():
        out = DEFS_BY_ID[sid].func(_features(**patch), _kline(last=ohlc), "600000")
        assert out.hit is True, f"{sid} 未触发：reason={out.reason}"


def test_signal_missing_field_reports_data_missing():
    out = DEFS_BY_ID["s21"].func(_features(volume_ratio_5=None), _kline(), "600000")
    assert out.hit is False and out.reason == "data_missing:volume_ratio_5"


def test_snapshot_boundaries_and_library_parity():
    assert compute_signal_snapshot(None) == {}
    assert compute_signal_snapshot(pd.DataFrame()) == {}
    assert compute_signal_snapshot(pd.DataFrame({"close": [1.0] * 300})) == {}
    frame = _frame()
    snap = compute_signal_snapshot(frame)
    base = compute_indicators(frame)
    for key in ("latest_close", "ma20", "macd_dif", "macd_dea", "volume_ratio_5"):
        assert snap[key] == base[key]
    assert compute_signal_snapshot(frame) == snap
    assert compute_signal_snapshot(frame.head(30))["high_250d"] is None


def test_snapshot_macd_fields_are_finite_for_factor_layer():
    snap = compute_signal_snapshot(_frame())
    for key in ("macd_dif", "macd_dea", "prev_macd_dif", "prev_macd_dea", "prev_ma20"):
        assert math.isfinite(snap[key]), key


class _FakeSource:
    """离线桩：*ST +5% / 普通股 +2% / 停牌股（末根日期非当日）。"""

    def fetch_spot_universe(self):
        return pd.DataFrame([{"code": "600000", "name": "浦发银行"},
                             {"code": "600002", "name": "*ST测试"},
                             {"code": "600003", "name": "停牌股"}])

    def fetch_daily_kline(self, code, start, end):
        if code == "600003":
            return _frame(last_date="2026-09-10")
        return _frame(last_pct=5.0 if code == "600002" else 2.0)


@pytest.fixture()
def scan_env(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "signal.db").replace("\\", "/"))
    Base.metadata.create_all(bind=engine, tables=[SignalTrigger.__table__])
    monkeypatch.setenv("KLINE_DB_PATH", str(tmp_path / "kline_store.db"))  # 隔离本地日线库（否则真库真票顶替假票）
    monkeypatch.setattr(signal_scan, "SessionLocal",
                        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
    monkeypatch.setattr(signal_scan, "get_datasource", lambda: _FakeSource())
    monkeypatch.setattr(signal_scan.market_hours, "is_trading_day", lambda: True)
    monkeypatch.setattr(signal_scan.market_hours, "_load_calendar",
                        lambda: {"2026-09-14", "2026-09-15", TRADE_DATE})
    return sessionmaker(bind=engine)


def test_scan_skips_non_trading_day_without_any_record(monkeypatch):
    monkeypatch.setattr(signal_scan.market_hours, "is_trading_day", lambda: False)
    monkeypatch.setattr(signal_scan, "get_datasource", lambda: pytest.fail("非交易日不得拉股票池"))
    out = signal_scan.scan_signal_triggers(TRADE_DATE, local_only=False)
    assert out["reason"] == "not_trading_day" and out["records"] == 0


def test_scan_flags_dedup_suspension_and_null_returns(scan_env):
    out = signal_scan.scan_signal_triggers(TRADE_DATE, local_only=False)
    assert out["reason"] == "ok" and out["universe"] == 3 and out["records"] > 0
    with scan_env() as db:
        rows = db.query(SignalTrigger).all()
        assert not any(row.stock_code == "600003" for row in rows)
        st_rows = [row for row in rows if row.stock_code == "600002"]
        normal = [row for row in rows if row.stock_code == "600000"]
        assert st_rows and all(row.is_st == 1 for row in st_rows)
        assert all(row.limit_up == 1 for row in st_rows)
        assert normal and all(row.is_st == 0 and row.limit_up == 0 for row in normal)
        assert all(row.dedup == 0 for row in rows)
        assert all(row.ret_5 is None and row.ret_10 is None and row.exec_price is None
                   and row.filled_at is None for row in rows)
        first = len(rows)
    assert signal_scan.scan_signal_triggers(TRADE_DATE, local_only=False)["records"] == 0
    with scan_env() as db:
        assert db.query(SignalTrigger).count() == first
        for row in db.query(SignalTrigger).all():
            row.trade_date = "2026-09-15"
        db.commit()
    signal_scan.scan_signal_triggers(TRADE_DATE, local_only=False)
    with scan_env() as db:
        fresh = db.query(SignalTrigger).filter(SignalTrigger.trade_date == TRADE_DATE).all()
        assert fresh and all(row.dedup == 1 for row in fresh)
