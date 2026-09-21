import threading
import types

import pandas as pd
import pytest

from app.core.config import settings
from app.datasource.akshare_source import AkshareSource
from app.datasource.base import DataSourceError
from app.services import factor_ic
from app.services.factor_ic import calc_ic, calc_ir, judge_status, run_backtest
from app.services.factor_registry import FactorDef


def _definition(fid="f01", name="测试因子", category="动量"):
    return FactorDef(id=fid, name=name, category=category, func=lambda *_: None,
                     has_quantile=True, weight_hint=0.2)


def test_calc_ic_positive_spearman():
    assert calc_ic([1, 2, 3, 4], [0.1, 0.2, 0.3, 0.4]) == 1.0


def test_calc_ic_all_missing():
    assert calc_ic([None, None], [0.1, 0.2]) is None


def test_calc_ir_requires_three_eligible_months():
    rows = [{"ic": 0.1, "sample_size": 100}, {"ic": 0.2, "sample_size": 100},
            {"ic": 0.3, "sample_size": 100}]
    assert calc_ir(rows) is not None
    assert calc_ir(rows[:2]) is None


def test_run_backtest_missing_factor_is_explicit():
    records = {"2026-01": [{"factor_values": {"f01": None}, "forward_return": 0.1}]}
    result = run_backtest(records, [_definition()])
    assert result[0]["ic"] is None and result[0]["sample_size"] == 0


def test_judge_status_after_three_weak_months():
    assert judge_status([0.01, 0.0, -0.1]) == "deprecated_candidate"
    assert judge_status([0.01, 0.0, 0.02]) == "active"


def test_job_flags_budget_shortfall_as_insufficient(monkeypatch):
    """预算采不满 MIN_SAMPLE 时必须可识别（cron 据此判断 ir 是否会被回退成 NULL）。"""

    class Source:
        def fetch_trade_calendar(self):
            return ["2026-07-31"]

        def fetch_spot_universe(self):
            return pd.DataFrame({"code": ["600000", "000001", "600002"]})

        def fetch_daily_kline(self, code, start, end):
            return None

        def fetch_industry_spot(self):
            return None

    ticks = iter([0.0, 0.0, 1e6])  # 第 2 只起即判定超预算
    monkeypatch.setattr(factor_ic, "time", types.SimpleNamespace(monotonic=lambda: next(ticks, 1e6)))
    monkeypatch.setattr(factor_ic, "get_datasource", lambda: Source())
    monkeypatch.setattr(factor_ic, "_month_ends", lambda calendar, months: ["2026-07-31"])
    monkeypatch.setattr(factor_ic, "persist_history", lambda rows: len(rows))
    monkeypatch.setattr(factor_ic, "COLLECT_BUDGET_SECONDS", 1)

    out = factor_ic.run_factor_ic_backtest_job(months=1)
    assert out["budget_exhausted"] is True
    assert out["sufficient"] is False
    assert out["max_sample"] < factor_ic.MIN_SAMPLE
    assert out["collected_codes"] < out["codes"]
    assert "预算不足" in out["reason"]


def _failing_source(error):
    """取数即抛出指定异常的替身；异常类型与文案决定 _classify_error 走哪个分支。"""
    class Source:
        def fetch_trade_calendar(self):
            raise error

    return Source()


def _job_with_failing_source(monkeypatch, error):
    monkeypatch.setattr(factor_ic, "get_datasource", lambda: _failing_source(error))
    return factor_ic.run_factor_ic_backtest_job(months=1)


def test_job_returns_structured_reason_on_timeout(monkeypatch):
    """取数硬超时须返回结构化 dict（error_kind=timeout），不得抛异常。"""
    out = _job_with_failing_source(
        monkeypatch, DataSourceError("数据源 tool_trade_date_hist_sina 超时 5s 无返回"))
    assert out["error_kind"] == "timeout"
    assert out["rows"] == 0 and out["sufficient"] is False
    assert "超时" in out["reason"]


def test_job_returns_structured_reason_on_connection_failure(monkeypatch):
    """连接/DNS 失败须归类为 connection，文案与超时不同，且不抛异常。"""
    out = _job_with_failing_source(
        monkeypatch, DataSourceError("数据源 spot_em 失败: Max retries ... getaddrinfo failed"))
    assert out["error_kind"] == "connection"
    assert "连接失败" in out["reason"] and "超时" not in out["reason"]


def test_job_returns_structured_reason_on_unexpected_error(monkeypatch):
    """非网络异常（如 RuntimeError）须归类为 unexpected，文案指向「需排查」且不串类。"""
    out = _job_with_failing_source(monkeypatch, RuntimeError("板块字段解析失败"))
    assert out["error_kind"] == "unexpected"
    assert "需排查" in out["reason"]
    assert "超时" not in out["reason"] and "连接失败" not in out["reason"]


def test_job_classifies_wrapped_timeout_message_as_timeout(monkeypatch):
    """消息内嵌 TimeoutError() 的 DataSourceError 也须判为 timeout（防单独上线时 timeout 分支失效）。"""
    out = _job_with_failing_source(
        monkeypatch, DataSourceError("数据源 spot_universe 重试失败: TimeoutError()"))
    assert out["error_kind"] == "timeout"
    assert "超时" in out["reason"] and "连接失败" not in out["reason"]


def test_integration_hard_timeout_survives_retry_wrapper(monkeypatch):
    """A→B 集成：真实硬超时的 DataSourceError 经 _call_with_retry 包装后仍判 timeout。

    两阶段各自独立 Event —— 共用同一 Event 时第二阶段阻塞函数会立刻返回，超时根本不触发（假阴性）。
    """
    monkeypatch.setattr(settings, "datasource_timeout", 2)
    monkeypatch.setattr(settings, "datasource_retry_times", 0)
    monkeypatch.setattr(settings, "datasource_retry_delay", 0)
    src = AkshareSource()

    phase1_release = threading.Event()

    def blocking_phase1(symbol):  # 不接受 timeout 参数；靠 Event 阻塞触发硬超时
        phase1_release.wait(30)

    try:
        with pytest.raises(DataSourceError) as excinfo1:
            src._call_with_timeout(blocking_phase1, "600000")
    finally:
        phase1_release.set()  # 放行后台线程，避免退出时被 join 拖住
    err1 = excinfo1.value
    assert isinstance(err1, DataSourceError)
    assert factor_ic._classify_error(err1) == "timeout"
    reason1 = factor_ic._job_reason([], 0, 0, {}, error_kind="timeout", error_msg=str(err1))
    assert reason1 and "取数超时" in reason1

    phase2_release = threading.Event()

    def blocking_phase2(symbol):
        phase2_release.wait(30)

    def call():
        return src._call_with_timeout(blocking_phase2, "600000")

    try:
        with pytest.raises(DataSourceError) as excinfo2:
            src._call_with_retry("probe_kline", call, None)
    finally:
        phase2_release.set()
    err2 = excinfo2.value
    assert factor_ic._classify_error(err2) == "timeout"
    reason2 = factor_ic._job_reason([], 0, 0, {}, error_kind="timeout", error_msg=str(err2))
    assert reason2 and "取数超时" in reason2


def test_job_skips_backtest_and_persist_when_zero_collection(monkeypatch):
    """零采集批次必须早退：不得调用 run_backtest / persist_history（防写坏 factor_ic_history）。"""
    calls: list[str] = []

    class Source:
        def fetch_trade_calendar(self):
            return pd.bdate_range("2026-01-01", "2026-09-18").strftime("%Y-%m-%d").tolist()

        def fetch_spot_universe(self):
            return pd.DataFrame()  # 非交易日：全市场快照为空 → codes 为空

    monkeypatch.setattr(factor_ic, "get_datasource", lambda: Source())
    monkeypatch.setattr(factor_ic, "run_backtest", lambda records: calls.append("run_backtest") or [])
    monkeypatch.setattr(factor_ic, "persist_history",
                        lambda rows: calls.append("persist_history") or len(rows))

    out = factor_ic.run_factor_ic_backtest_job(months=3)
    assert calls == []
    assert out["rows"] == 0
    assert out["skipped"] is True
    assert out["sufficient"] is False
    assert "未采集" in out["reason"]


def test_persist_skips_all_zero_sample_batch(monkeypatch):
    """整批零样本必须被批次级护栏拦下：SessionLocal 不许被进入（证明未触库）。"""
    entered: list[bool] = []

    class BoomSession:
        def __enter__(self):
            entered.append(True)
            raise AssertionError("全批零样本不应触库")

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(factor_ic, "SessionLocal", lambda: BoomSession())
    rows = [{"factor_id": f"f{index:02d}", "period": "2026-08", "sample_size": 0, "ic": None}
            for index in range(3)]
    assert factor_ic.persist_history(rows) == 0
    assert entered == []


def _frame(start="2026-06-01", end="2026-09-15"):
    dates = pd.bdate_range(start, end).strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({"date": dates, "open": 1.0, "high": 1.0, "low": 1.0,
                         "close": [float(i + 1) for i in range(len(dates))], "volume": 100.0})


def _stub_store(monkeypatch, frame=None, error=None):
    """替身本地仓库：按需返回整段 frame / 空 / 混口径异常，并记录回写行。"""
    writes: list[dict] = []

    class Store:
        class MixedAdjustError(ValueError):
            pass

        @staticmethod
        def load_frame(code, start, end):
            if error is not None:
                raise error
            return None if frame is None else frame.copy()

        @staticmethod
        def upsert_bars(rows):
            writes.extend(rows)
            return len(rows)

    monkeypatch.setattr(factor_ic, "kline_store", Store)
    return writes


class _LocalOnlySource:
    """本地库已覆盖时，任何远端日K调用都算失败。"""

    def fetch_daily_kline(self, *args, **kwargs):
        raise AssertionError("本地库已覆盖区间时不得回退远端")

    def fetch_industry_spot(self):
        return None

    def fetch_financial(self, code):
        return None

    def fetch_fund_flow(self, code):
        return None

    def fetch_news(self, code):
        return None


def test_local_kline_used_when_window_covered(monkeypatch):
    _stub_store(monkeypatch, _frame())
    out = factor_ic._local_kline("600000", "2026-06-16", "2026-09-14")
    assert out is not None and not out.empty and {"date", "close"}.issubset(out.columns)


def test_local_kline_falls_back_when_window_head_missing(monkeypatch):
    """区间首段缺失（回补未完成/新股）时必须回退远端，不能用半段历史算 IC。"""
    _stub_store(monkeypatch, _frame("2026-08-01", "2026-09-15"))
    assert factor_ic._local_kline("600000", "2026-06-16", "2026-09-14") is None


def test_local_kline_falls_back_on_mixed_adjust(monkeypatch):
    class Store:
        class MixedAdjustError(ValueError):
            pass

        @staticmethod
        def load_frame(code, start, end):
            raise Store.MixedAdjustError("mixed")

    monkeypatch.setattr(factor_ic, "kline_store", Store)
    assert factor_ic._local_kline("600000", "2026-06-16", "2026-09-14") is None


def test_collect_prefers_local_warehouse_and_covers_every_code(monkeypatch):
    """命中本地库时不得回退远端；并发采集须覆盖全部代码且预算未耗尽。"""
    _stub_store(monkeypatch, _frame())
    monkeypatch.setattr(factor_ic.factor_registry, "list_active", lambda: [_definition("f01")])
    stats: dict = {}
    records = factor_ic.collect_month_records(
        _LocalOnlySource(), ["2026-07-31"], ["600000", "000001", "600002"], 60, stats=stats)
    assert stats["attempted"] == 3
    assert stats["budget_exhausted"] is False
    assert sorted(row["code"] for row in records["2026-07"]) == ["000001", "600000", "600002"]


def test_collect_falls_back_to_remote_when_local_missing(monkeypatch):
    """本地无覆盖时必须回退远端日K（本地化只是加速，不得改变数据来源语义）。"""
    calls: list[str] = []
    writes = _stub_store(monkeypatch, None)
    monkeypatch.setattr(factor_ic.factor_registry, "list_active", lambda: [_definition("f01")])

    class Source:
        def fetch_daily_kline(self, code, start, end):
            calls.append(code)
            return _frame()

        def fetch_industry_spot(self):
            return None

        def fetch_financial(self, code):
            return None

        def fetch_fund_flow(self, code):
            return None

        def fetch_news(self, code):
            return None

    records = factor_ic.collect_month_records(Source(), ["2026-07-31"], ["600000", "000001"], 60, stats={})
    assert sorted(calls) == ["000001", "600000"]
    assert len(records["2026-07"]) == 2
    # 首轮远端取数须回写本地仓库（下一轮同票才能走本地）
    assert {row["stock_code"] for row in writes} == {"600000", "000001"}
    assert all(row["adjust"] == "qfq" and row["trade_date"] for row in writes)
