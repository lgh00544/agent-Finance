"""批1.5 本地日线仓库测试：存储幂等 / 快照解析与分批 / 除权检出 / 回补续跑与重建 / 扫描本地优先。

全程离线：不触网（快照与日线源均用桩），库路径一律显式传入或临时环境变量，不碰 data/kline.db。
"""
import threading
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.services import kline_backfill, kline_ingest, kline_store, signal_scan

TRADE_DATE = "2026-09-18"


def _fields(name="测试", open_=10.0, pre=9.5, close=9.8, high=10.2, low=9.4,
            vol=1000, amt=9800, date=TRADE_DATE):
    """构造 hq.sinajs 34 字段快照行（索引映射与 kline_ingest._F 对齐）"""
    f = [""] * 34
    f[0], f[1], f[2], f[3], f[4], f[5] = name, f"{open_}", f"{pre}", f"{close}", f"{high}", f"{low}"
    f[8], f[9], f[30], f[31] = f"{vol}", f"{amt}", date, "15:00:00"
    return f


def _bars(code="600519", n=260, last=TRADE_DATE, close=10.0):
    """造 n 根连续日线，末根日期可指定（供扫描停牌判定与指标计算）"""
    end = datetime.strptime(last, "%Y-%m-%d")
    rows = []
    for i in range(n):
        day = (end - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d")
        price = close + i * 0.01
        rows.append({"stock_code": code, "trade_date": day, "open": price, "high": price * 1.01,
                     "low": price * 0.99, "close": price, "volume": 100000.0, "amount": price * 100000,
                     "source": "test", "adjust": "qfq"})
    return rows


class _Resp:
    def __init__(self, text, status=200):
        self.content = text.encode("gbk")
        self.status_code = status


class _Session:
    """伪 Session：按 URL 中的 symbol 返回快照；可指定某批抛错以验证容错"""

    def __init__(self, mapping, fail_symbols=()):
        self.mapping, self.fail_symbols, self.urls = mapping, set(fail_symbols), []

    def get(self, url, **kwargs):
        self.urls.append(url)
        body = []
        for sym in url.split("list=")[-1].split(","):
            code = sym[2:]
            if sym in self.fail_symbols:
                raise RuntimeError("boom")
            body.append(f'var hq_str_{sym}="{",".join(self.mapping[code])}";')
        return _Resp("\n".join(body))


class _Source:
    """伪日线源：返回 n 根**日期各异**的日线；长度不足/直接抛错用于验证 failed 计数"""

    def __init__(self, lengths=None, default=280):
        self.lengths, self.default, self.calls = lengths or {}, default, []

    def fetch_daily_kline(self, code, start, end):
        self.calls.append(code)
        n = self.lengths.get(code, self.default)
        if n == 0:
            raise RuntimeError("source-down")
        end_dt = datetime.strptime(TRADE_DATE, "%Y-%m-%d")
        dates = [(end_dt - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]
        return pd.DataFrame({"date": dates, "open": 1.0, "high": 1.0, "low": 1.0,
                             "close": 1.0, "volume": 1.0, "amount": 1.0})


class _NoRemote:
    def fetch_daily_kline(self, *args, **kwargs):
        raise AssertionError("本地已足 250 根，不应调用远端")


def test_upsert_and_load_roundtrip(tmp_path):
    db = str(tmp_path / "k.db")
    assert kline_store.upsert_bars(_bars(n=3), db) == 3
    got = kline_store.load_bars("600519", path=db)
    assert [r["trade_date"] for r in got] == sorted(r["trade_date"] for r in got)
    assert got[-1]["close"] == pytest.approx(10.02)


def test_upsert_is_idempotent_and_updates(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars([{"stock_code": "1", "trade_date": TRADE_DATE, "close": 1.0}], db)
    kline_store.upsert_bars([{"stock_code": "1", "trade_date": TRADE_DATE, "close": 9.9}], db)
    rows = kline_store.load_bars("1", path=db)
    assert len(rows) == 1 and rows[0]["close"] == pytest.approx(9.9)


def test_upsert_skips_rows_without_keys(tmp_path):
    db = str(tmp_path / "k.db")
    assert kline_store.upsert_bars([{"stock_code": "", "trade_date": TRADE_DATE, "close": 1.0}], db) == 0
    assert kline_store.stats(db)["rows"] == 0


def test_prev_close_and_has_enough_and_stats(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars(_bars(code="A", n=250), db)
    assert kline_store.prev_close("A", "2026-09-18", db) is not None
    assert kline_store.prev_close("A", "2000-01-01", db) is None
    assert kline_store.has_enough("A", 250, db) is True
    assert kline_store.has_enough("A", 251, db) is False
    info = kline_store.stats(db)
    assert info["rows"] == 250 and info["codes"] == 1
    assert info["min_date"] <= info["max_date"]


def test_load_frame_columns_and_delete_code(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars(_bars(code="A", n=5) + _bars(code="B", n=5), db)
    frame = kline_store.load_frame("A", path=db)
    assert list(frame.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert "change_pct" not in frame.columns  # 由库内统一口径推导，不在此重复算法
    assert kline_store.delete_code("A", db) == 5
    assert kline_store.load_bars("A", path=db) == [] and kline_store.stats(db)["rows"] == 5


def test_parse_bar_maps_fields_and_rejects_suspended():
    bar = kline_ingest.parse_bar("600519", _fields(open_=1262.99, pre=1266.98, close=1257.12,
                                                   high=1265.88, low=1256.1, vol=2489087,
                                                   amt=3135849108.0), "2026-09-20")
    assert bar["trade_date"] == TRADE_DATE and bar["close"] == pytest.approx(1257.12)
    assert bar["volume"] == pytest.approx(2489087) and bar["adjust"] == "none"
    assert kline_ingest.parse_bar("X", _fields(close=0), TRADE_DATE) is None
    assert kline_ingest.parse_bar("X", _fields(close=""), TRADE_DATE) is None


def test_fetch_snapshot_batches_and_tolerates_batch_failure():
    mapping = {f"60000{i}": _fields(name=f"S{i}") for i in range(5)}
    session = _Session(mapping, fail_symbols=("sh600003",))
    snap, errors = kline_ingest.fetch_snapshot(list(mapping), batch=2, session=session)
    assert len(session.urls) == 3            # 5 只 / 每批 2 → 3 批
    assert errors and "boom" in errors[0]     # 失败批被记录
    assert set(snap) == {"600000", "600001", "600004"}  # 仅失败批（600002/600003）被丢弃


def test_ingest_today_writes_bars(tmp_path):
    db = str(tmp_path / "k.db")
    mapping = {"600519": _fields(name="贵州茅台"), "000001": _fields(name="平安银行")}
    orig = kline_ingest.fetch_snapshot  # 桩替换快照取数，保证离线
    kline_ingest.fetch_snapshot = lambda codes, batch=100, timeout=15, session=None: (
        {c: mapping[c] for c in codes if c in mapping}, [])
    try:
        out = kline_ingest.ingest_today(trade_date=TRADE_DATE, codes=list(mapping), path=db, batch=10)
    finally:
        kline_ingest.fetch_snapshot = orig
    assert out["reason"] == "ok" and out["bars"] == 2 and out["trade_date"] == TRADE_DATE
    assert out["skipped"] == 0 and out["ex_div_codes"] == []
    assert kline_store.stats(db)["rows"] == 2


def test_ingest_today_detects_ex_dividend(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars([{"stock_code": "600519", "trade_date": "2026-09-17", "close": 1400.0}], db)
    orig = kline_ingest.fetch_snapshot
    kline_ingest.fetch_snapshot = lambda codes, batch=100, timeout=15, session=None: (
        {"600519": _fields(pre=1266.98, close=1257.12)}, [])
    try:
        out = kline_ingest.ingest_today(trade_date=TRADE_DATE, codes=["600519"], path=db)
    finally:
        kline_ingest.fetch_snapshot = orig
    assert out["ex_div_codes"] == ["600519"]  # 昨收 1266.98 vs 本地前收 1400 → 判为除权


def test_ingest_today_empty_universe_writes_nothing(tmp_path, monkeypatch):
    import app.datasource.fallback as fb

    class _Empty:
        def fetch_spot_universe(self):
            return pd.DataFrame()          # 隔离真实股票池（离线、确定性）

    monkeypatch.setattr(fb, "get_datasource", lambda: _Empty())
    db = str(tmp_path / "k.db")
    out = kline_ingest.ingest_today(trade_date=TRADE_DATE, codes=[], path=db)
    assert out["reason"] == "empty_universe" and out["bars"] == 0
    assert kline_store.stats(db)["rows"] == 0


def test_backfill_skips_sufficient_and_fills_missing(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars(_bars(code="A", n=250), db)
    source = _Source(default=280)
    out = kline_backfill.backfill(["A", "B"], path=db, source=source, sleep_between=0)
    assert out["skipped"] == 1 and out["ok"] == 1 and out["failed"] == 0
    assert source.calls == ["B"] and kline_store.has_enough("B", 250, db)


def test_backfill_rebuild_deletes_before_refetch(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars([{"stock_code": "A", "trade_date": "2020-01-01", "close": 1.0}], db)
    out = kline_backfill.backfill(["A"], path=db, source=_Source(default=280), rebuild=True, sleep_between=0)
    assert out["ok"] == 1 and out["skipped"] == 0
    dates = [r["trade_date"] for r in kline_store.load_bars("A", path=db)]
    assert "2020-01-01" not in dates and len(dates) == 280  # 旧段已删、整段重取


def test_backfill_counts_short_and_failed_sources(tmp_path):
    db = str(tmp_path / "k.db")
    out = kline_backfill.backfill(["SHORT", "DOWN"], path=db, sleep_between=0,
                                  source=_Source(lengths={"SHORT": 10, "DOWN": 0}))
    assert out["failed"] == 2 and out["ok"] == 0 and set(out["failed_codes"]) == {"SHORT", "DOWN"}


def test_scan_uses_local_bars_first(monkeypatch, tmp_path):
    monkeypatch.setenv("KLINE_DB_PATH", str(tmp_path / "scan.db"))
    kline_store.upsert_bars(_bars(code="600519", n=260, last=TRADE_DATE))
    ctx = {"trade_date": TRADE_DATE, "defs": signal_scan.list_all(), "source": _NoRemote(),
           "today": set(), "cooldown": set(), "start": "2025-07-28", "end": TRADE_DATE,
           "lock": threading.Lock(), "counters": {"local": 0, "remote": 0}}
    rows, errors = signal_scan._scan_one({"code": "600519", "name": "贵州茅台"}, ctx)
    assert errors == 0 and ctx["counters"] == {"local": 1, "remote": 0}
    assert isinstance(rows, list)


def test_scan_falls_back_to_remote_and_tolerates_ctx_without_counters(monkeypatch, tmp_path):
    monkeypatch.setenv("KLINE_DB_PATH", str(tmp_path / "scan2.db"))
    ctx = {"trade_date": TRADE_DATE, "defs": signal_scan.list_all(), "source": _Source(lengths={"X": 0}),
           "today": set(), "cooldown": set(), "start": "2025-07-28", "end": TRADE_DATE,
           "lock": threading.Lock(), "counters": {"local": 0, "remote": 0}}
    rows, errors = signal_scan._scan_one({"code": "X", "name": "x"}, ctx)
    assert errors == 1 and ctx["counters"] == {"local": 0, "remote": 1} and rows == []
    legacy = {"trade_date": TRADE_DATE, "defs": signal_scan.list_all(), "source": _Source(default=1),
              "today": set(), "cooldown": set(), "start": "2025-07-28", "end": TRADE_DATE}
    rows2, errors2 = signal_scan._scan_one({"code": "Y", "name": "y"}, legacy)
    assert (rows2, errors2) == ([], 0)  # 无 counters/lock 的旧 ctx（外部干跑工具）不得报错


# ==================== 批1.5 门禁与审计（复权口径 / 名称 / local-only）====================


def _bars_none(code="600519", n=260, last=TRADE_DATE, close=10.0):
    """与 _bars 同构但 adjust='none'（当日快照口径），供复权门禁测试"""
    rows = _bars(code=code, n=n, last=last, close=close)
    for r in rows:
        r["adjust"] = "none"
        r["stock_name"] = "测试"
    return rows


def test_upsert_persists_stock_name_and_name_map(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars(_bars_none(code="600519", n=3), db)
    assert kline_store.name_map(db) == {"600519": "测试"}


def test_empty_name_does_not_overwrite_existing(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars([{"stock_code": "600519", "trade_date": "2026-09-17",
                              "close": 1.0, "stock_name": "贵州茅台", "adjust": "qfq"}], db)
    kline_store.upsert_bars([{"stock_code": "600519", "trade_date": "2026-09-17",
                              "close": 1.0, "stock_name": "", "adjust": "qfq"}], db)
    assert kline_store.name_map(db) == {"600519": "贵州茅台"}


def test_mixed_adjust_raises_and_blocks_indicators(tmp_path):
    db = str(tmp_path / "k.db")
    kline_store.upsert_bars([{"stock_code": "X", "trade_date": "2026-09-17", "close": 1.0, "adjust": "qfq"},
                             {"stock_code": "X", "trade_date": "2026-09-18", "close": 1.1, "adjust": "none"}], db)
    with pytest.raises(kline_store.MixedAdjustError):
        kline_store.load_frame("X", path=db)


def test_ingest_skips_ex_dividend_bar_until_rebuild(tmp_path, monkeypatch):
    """除权票当天不落原始 bar（口径不同基准），只登记待重建，避免污染序列"""
    path = str(tmp_path / "k.db")
    monkeypatch.setenv("KLINE_DB_PATH", path)
    kline_store.upsert_bars([{"stock_code": "600519", "trade_date": "2026-09-17", "close": 10.0,
                              "adjust": "qfq", "stock_name": "贵州茅台"}], path)
    mapping = {"600519": _fields(pre=8.0, close=8.0)}          # 快照昨收 8.0 ≠ 本地前收 10.0
    monkeypatch.setattr(kline_ingest, "fetch_snapshot", lambda codes, **kw: (mapping, []))
    out = kline_ingest.ingest_today(TRADE_DATE, codes=["600519"], path=path)
    assert out["ex_div_codes"] == ["600519"]
    assert out["bars"] == 0                                     # 未写当日 bar
    dates = [r["trade_date"] for r in kline_store.load_bars("600519", path=path)]
    assert dates == ["2026-09-17"]                              # 本地序列保持干净


def test_local_only_marks_data_missing_and_never_touches_remote(tmp_path, monkeypatch):
    db = str(tmp_path / "k.db")
    monkeypatch.setenv("KLINE_DB_PATH", db)
    ctx = {"trade_date": TRADE_DATE, "start": "2025-07-25", "end": TRADE_DATE, "defs": [],
           "source": _NoRemote(), "today": set(), "cooldown": set(), "local_only": True,
           "lock": threading.Lock(), "counters": {"local": 0, "remote": 0},
           "missing": {"incomplete": 0, "data_missing": 0, "stale": 0}}
    rows, errors = signal_scan._scan_one({"code": "600519", "name": ""}, ctx)
    assert rows == [] and errors == 0
    assert ctx["counters"] == {"local": 0, "remote": 0}
    assert ctx["missing"]["data_missing"] == 1 and ctx["data_missing"] == ["600519"]


def test_local_only_marks_stale_when_last_bar_not_today(tmp_path, monkeypatch):
    db = str(tmp_path / "k.db")
    monkeypatch.setenv("KLINE_DB_PATH", db)
    kline_store.upsert_bars(_bars_none(code="600519", n=260, last="2026-09-17"), db)
    ctx = {"trade_date": TRADE_DATE, "start": "2025-07-25", "end": TRADE_DATE, "defs": [],
           "source": _NoRemote(), "today": set(), "cooldown": set(), "local_only": True,
           "lock": threading.Lock(), "counters": {"local": 0, "remote": 0},
           "missing": {"incomplete": 0, "data_missing": 0, "stale": 0}}
    rows, errors = signal_scan._scan_one({"code": "600519", "name": ""}, ctx)
    assert rows == [] and ctx["counters"]["local"] == 1
    assert ctx["missing"]["stale"] == 1 and ctx["stale"] == ["600519"]


def test_short_history_mark_persist_and_pending_exclusion(tmp_path):
    """短史票（源可取但 <MIN_BARS）持久标记：补数队列不再重试，足量后可清除（自我修复）"""
    db = str(tmp_path / "k.db")
    assert kline_store.short_codes(db) == set()
    kline_store.mark_short("920003", 214, db)
    assert kline_store.short_codes(db) == {"920003"}
    todo = kline_backfill.pending_codes(path=db, codes=["920003", "600519"])
    assert "920003" not in todo and "600519" in todo
    kline_store.clear_short("920003", db)
    assert kline_store.short_codes(db) == set()
    assert "920003" in kline_backfill.pending_codes(path=db, codes=["920003"])


def test_local_only_marks_unsupported_for_short_history(tmp_path, monkeypatch):
    """已知短史票在 local-only 下记 unsupported（不再混入 data_missing）"""
    db = str(tmp_path / "k.db")
    monkeypatch.setenv("KLINE_DB_PATH", db)
    ctx = {"trade_date": TRADE_DATE, "start": "2025-07-25", "end": TRADE_DATE, "defs": [],
           "source": _NoRemote(), "today": set(), "cooldown": set(), "local_only": True,
           "lock": threading.Lock(), "counters": {"local": 0, "remote": 0},
           "missing": {"incomplete": 0, "data_missing": 0, "stale": 0, "unsupported": 0},
           "unsupported_codes": {"600519"}}
    rows, errors = signal_scan._scan_one({"code": "600519", "name": ""}, ctx)
    assert rows == [] and errors == 0
    assert ctx["missing"]["unsupported"] == 1 and ctx["unsupported"] == ["600519"]
    assert "data_missing" not in ctx
