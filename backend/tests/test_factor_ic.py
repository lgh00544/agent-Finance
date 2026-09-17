import types

import pandas as pd

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
