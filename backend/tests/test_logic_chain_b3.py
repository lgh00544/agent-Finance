# 第3批逻辑链修复回归测试（S-1 / S-11 / S-5 / S-4 / S-7）。
#
# 纯计算与 mock 为主；涉及落库的用例走 dev SQLite（conftest 已把 SQLITE_PATH 指到临时目录）。
# 覆盖：
# 1. S-4 唯一常量源：core.config 四常量与 plan_quant / take_profit / red_line_check 同源同值，
#    position 提示词不再出现 60.0 / -30.0 / 0.92 字面量；
# 2. S-11 去重时序：cache.alert_seen 只读探测、alert_mark 投递成功后置位、alert_deduplicated 兼容；
# 3. S-1 确定性告警：止损 / 移动止盈 / 止盈三条触发 + 当日去重 + 投递失败可重试；
# 4. 红线越限落库：emit_red_line_alerts 投递成功才置位；
# 5. S-5 成本不变量：cost_invariant_delta / _assert_cost_invariant / 减仓重算 cost / 生命周期成本不回退；
# 6. S-7 评分 freshness：score_trading_day_age + get_score_for_position 的 N 交易日降级；
# 7. S-11 飞书投递：失败重试到上限并升级留痕；
# 8. 迁移：holding.cost_basis_initial 回填 + cost 不变量一次性归一。
import datetime as _dt
import inspect
import types

import pandas as pd
import pytest
from sqlalchemy import select

from app.api import routes
from app.cache import MemoryCache
from app.core.config import (
    C1_CONCENTRATION_CAP, C2_INTRADAY_DRAWDOWN_PCT, C2_TOTAL_POSITION_CAP, C3_STOP_FACTOR,
    GRADE_POSITION_CAP,
)
from app.db import repo
from app.db.models import Holding, TradeRecord
from app.db.session import SessionLocal, engine, init_db
from app.services import plan_quant, red_line_check, take_profit


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


# ==================== S-4 红线常量唯一源 ====================

def test_red_line_constants_single_source():
    assert GRADE_POSITION_CAP == {"A": 0.30, "B": 0.20, "C": 0.10}
    assert C1_CONCENTRATION_CAP == 60.0 and C2_TOTAL_POSITION_CAP == 60.0
    assert C2_INTRADAY_DRAWDOWN_PCT == 30.0 and C3_STOP_FACTOR == 0.92
    assert plan_quant.GRADE_CAP_PCT is GRADE_POSITION_CAP
    assert plan_quant.C2_TOTAL_CAP == pytest.approx(C2_TOTAL_POSITION_CAP / 100)
    assert take_profit.C1_SINGLE_CAP == pytest.approx(GRADE_POSITION_CAP["A"])
    assert take_profit.C2_TOTAL_CAP == pytest.approx(C2_TOTAL_POSITION_CAP / 100)
    assert take_profit.C3_STOP_PCT == C3_STOP_FACTOR
    assert red_line_check.C1_CAP_PCT == C1_CONCENTRATION_CAP
    assert red_line_check.C2_DRAWDOWN_PCT == C2_INTRADAY_DRAWDOWN_PCT
    assert red_line_check.C3_FACTOR == C3_STOP_FACTOR


def test_position_prompt_has_no_hardcoded_red_line():
    from app.agents import position

    src = inspect.getsource(position.collect_plan_input)
    assert "60.0" not in src and "-30.0" not in src and "0.92" not in src
    assert "C1_CONCENTRATION_CAP" in src and "C3_STOP_FACTOR" in src
    body = inspect.getsource(position.llm_plan)
    assert "GRADE_POSITION_CAP" in body and "C2_TOTAL_POSITION_CAP" in body
    assert "max_single_pct" not in body  # 40% 展示值不再进提示词


# ==================== S-11 去重时序 ====================

def test_alert_seen_readonly_and_mark_gates_dedup():
    cache = MemoryCache()
    assert cache.alert_seen("k") is False
    assert cache.alert_seen("k") is False        # 只读探测不占位
    cache.alert_mark("k", 60)
    assert cache.alert_seen("k") is True
    assert cache.alert_deduplicated("k", 60) is True
    assert cache.alert_deduplicated("k2", 60) is False   # 兼容旧语义：先占位后投递
    assert cache.alert_seen("k2") is True


# ==================== S-1 确定性风控告警 ====================

def _plan(**kw):
    base = {"stock_code": "600010", "stock_name": "测试甲", "current_price": 10.0,
            "c3_stop": 9.2, "current_stop": 9.2, "tp1": 11.0, "tp2": 12.0}
    base.update(kw)
    return base


def test_deterministic_alerts_stop_trailing_take_profit(monkeypatch):
    seen = []
    monkeypatch.setattr(take_profit, "cache", MemoryCache())
    monkeypatch.setattr(take_profit, "push_alert",
                        lambda *a, **k: {"result": "not_configured", "channel": "none"})
    monkeypatch.setattr(take_profit.repo, "insert_alert",
                        lambda *a, **k: seen.append(a[2]) or 1)

    take_profit._check_tp_alerts(_plan(current_price=9.0))            # 触及止损
    take_profit._check_tp_alerts(_plan(current_price=9.0))            # 当日去重
    take_profit._check_tp_alerts(_plan(stock_code="600011", current_price=10.0,
                                       trailing_stop=10.5))           # 移动止盈触发
    take_profit._check_tp_alerts(_plan(stock_code="600012", current_price=11.2))   # 止盈触发
    take_profit._check_tp_alerts(_plan(stock_code="600013", current_price=10.8))   # 接近止盈
    assert seen == ["触及止损", "移动止盈触发", "止盈触发", "接近止盈"]


def test_deterministic_alert_retries_when_delivery_failed(monkeypatch):
    seen = []
    monkeypatch.setattr(take_profit, "cache", MemoryCache())
    monkeypatch.setattr(take_profit, "push_alert",
                        lambda *a, **k: {"result": "failed", "channel": "none"})
    monkeypatch.setattr(take_profit.repo, "insert_alert",
                        lambda *a, **k: seen.append(a[2]) or 1)
    take_profit._check_tp_alerts(_plan(current_price=9.0))
    take_profit._check_tp_alerts(_plan(current_price=9.0))
    assert seen == ["触及止损", "触及止损"]   # 投递失败不置位 → 下一轮重试


def test_deterministic_plan_exposes_trailing_stop():
    row = {"stock_code": "600014", "stock_name": "测试乙", "entry_price": 10.0, "shares": 1000,
           "current_price": 10.6, "market_value": 10600.0, "stop_loss": 0.0,
           "take_profit": 0.0, "total_capital": 100000.0, "high_price": 11.0}
    plan = take_profit.compute_plan(row, {})
    assert plan["trailing_stop"] == 10.12           # max(11.0 × 0.92, 成本 10.0)
    assert plan["high_price"] == 11.0
    low_pnl = take_profit.compute_plan({**row, "current_price": 10.2}, {})
    assert low_pnl["trailing_stop"] is None          # 浮盈 <5% 不启用移动止盈


# ==================== 红线越限落库（S-1/S-11） ====================

def test_red_line_emit_dedup_after_delivery(monkeypatch):
    seen = []
    monkeypatch.setattr(red_line_check, "cache", MemoryCache())
    monkeypatch.setattr("app.services.feishu.push_alert",
                        lambda *a, **k: {"result": "not_configured", "channel": "none"})
    monkeypatch.setattr(red_line_check.repo, "insert_alert",
                        lambda *a, **k: seen.append(a[2]) or 1)
    rows = [{"stock_code": "600020", "stock_name": "测试丙", "c3_alert": True,
             "c3_stop_loss": 9.0}]
    first = red_line_check.emit_red_line_alerts(rows, "2026-01-05")
    second = red_line_check.emit_red_line_alerts(rows, "2026-01-05")
    assert first == {"emitted": 1, "deduplicated": 0, "failed": 0}
    assert second == {"emitted": 0, "deduplicated": 1, "failed": 0}
    assert seen == ["红线C3-硬止损"]


# ==================== S-5 成本不变量 ====================

def test_cost_invariant_delta_and_assert():
    assert repo.cost_invariant_delta(10.0, 1000, 10000.0) == 0.0
    assert repo.cost_invariant_delta(10.0, 1000, 20000.0) == pytest.approx(10000.0)
    assert repo.cost_invariant_delta(None, 1000, 1.0) is None
    assert repo.cost_invariant_delta(10.0, None, 1.0) is None
    assert repo.cost_invariant_delta(10.0, 1000, None) is None

    ok = types.SimpleNamespace(id=1, entry_price=10.0, shares=900, cost=9000.0)
    repo._assert_cost_invariant(ok)                       # 一致 → 不抛
    repo._assert_cost_invariant(types.SimpleNamespace(id=2, entry_price=None,
                                                      shares=900, cost=1.0))  # 缺数据不误杀
    bad = types.SimpleNamespace(id=3, entry_price=10.0, shares=900, cost=10000.0)
    with pytest.raises(ValueError, match="S-5"):
        repo._assert_cost_invariant(bad)


def test_exit_holding_recomputes_cost_and_keeps_lifecycle_basis(monkeypatch):
    monkeypatch.setattr(routes, "_submit_task", lambda kind, params: {"task_id": "t1"})
    monkeypatch.setattr(routes, "_request_user_id", lambda: 1)
    hid = repo.insert_holding("600030", "减仓测试", "2026-07-01", 10.0, 1000, 10000.0,
                              user_id=1)
    routes.exit_holding(hid, routes.ExitBody(price=11.0, shares=400, trade_date="2026-08-06"))
    with SessionLocal() as db:
        row = db.get(Holding, hid)
        assert row.shares == 600
        assert row.cost == pytest.approx(6000.0)                 # cost = entry_price × 剩余股数
        assert row.cost_basis_initial == pytest.approx(10000.0)  # 生命周期总成本不回退

    routes.exit_holding(hid, routes.ExitBody(price=11.0, shares=600, trade_date="2026-08-07"))
    with SessionLocal() as db:
        row = db.get(Holding, hid)
        assert row.status == "exited" and row.cost == 0.0
        assert row.cost_basis_initial == pytest.approx(10000.0)


def test_record_holding_trade_rejects_cost_drift():
    hid = repo.insert_holding("600031", "断言测试", "2026-07-01", 10.0, 1000, 10000.0)
    with pytest.raises(ValueError, match="S-5"):
        repo.record_holding_trade(hid, side="sell", price=11.0, shares=100,
                                  trade_date="2026-08-06", note="脏数据",
                                  before_shares=1000, after_shares=900,
                                  holding_fields={"shares": 900, "cost": 10000.0})
    with SessionLocal() as db:
        assert db.get(Holding, hid).shares == 1000                    # 事务整体回滚
        sells = [t for t in db.execute(
            select(TradeRecord).where(TradeRecord.holding_id == hid)).scalars().all()
            if t.side == "sell"]
        assert sells == []


def test_migration_backfills_lifecycle_cost_and_normalizes_invariant():
    from app.db.session import _ensure_holding_cost_basis_initial

    hid = repo.insert_holding("600032", "迁移测试", "2026-07-01", 10.0, 1000, 10000.0)
    with SessionLocal() as db:                     # 模拟历史脏数据：减仓未重算 cost + 新列缺失
        row = db.get(Holding, hid)
        row.shares = 600
        row.cost = 10000.0
        row.cost_basis_initial = None
        db.commit()
    _ensure_holding_cost_basis_initial(engine)
    with SessionLocal() as db:
        row = db.get(Holding, hid)
        assert row.cost_basis_initial == pytest.approx(10000.0)   # 回填 = 旧 cost（生命周期口径）
        assert row.cost == pytest.approx(6000.0)                  # 不变量一次性归一


def test_review_pnl_uses_lifecycle_cost_basis(monkeypatch):
    from app.agents import review

    holding = types.SimpleNamespace(
        id=7, stock_code="600041", stock_name="生命周期", entry_date="2026-07-01",
        entry_price=10.0, shares=400, stop_loss=0.0, take_profit=0.0, note="",
        cost=4000.0, cost_basis_initial=10000.0, status="holding", plan_id=None)
    trades = [
        types.SimpleNamespace(side="buy", price=10.0, shares=1000, amount=10000.0,
                              trade_date="2026-07-01"),
        types.SimpleNamespace(side="sell", price=11.0, shares=600, amount=6600.0,
                              trade_date="2026-08-05"),
    ]
    monkeypatch.setattr(review.repo, "get_holding", lambda hid: holding)
    monkeypatch.setattr(review.repo, "get_trades", lambda hid: trades)
    monkeypatch.setattr(review.repo, "get_plan", lambda pid: None)
    monkeypatch.setattr(review.repo, "get_plan_for_entry", lambda code, day: (None, "missing"))
    monkeypatch.setattr(review.repo, "get_latest_score", lambda code, as_of=None: None)
    monkeypatch.setattr(review.repo, "get_alerts_by_code", lambda *a, **k: [])
    monkeypatch.setattr(review.repo, "get_sell_decisions_by_code", lambda *a, **k: [])
    monkeypatch.setattr(review.repo, "list_traces", lambda **k: [])
    monkeypatch.setattr(review, "_portfolio_attribution", lambda *a: {})
    monkeypatch.setattr(review, "_cycle_attribution", lambda code: None)
    monkeypatch.setattr(review, "_portfolio_curve_summary", lambda: {})

    class _Source:
        def fetch_daily_kline(self, code, start, end):
            return pd.DataFrame()

    monkeypatch.setattr(review, "get_datasource", lambda: _Source())
    state = review.collect_review({"holding_id": 7, "trade_date": "2026-08-05", "trace": []})
    assert state["exit_suggest"]["pnl_pct"] == pytest.approx(-34.0)   # (6600−10000)/10000
    assert state["exit_suggest"]["pnl_pct"] != pytest.approx(65.0)    # 不得用剩余成本 4000


# ==================== S-7 评分 freshness ====================

def test_score_trading_day_age_calendar_and_fallback(monkeypatch):
    monkeypatch.setattr(repo.cache, "get", lambda key: "")
    assert repo.score_trading_day_age("2026-09-30", "2026-09-30") == 0
    assert repo.score_trading_day_age("2026-10-01", "2026-09-30") is None
    assert repo.score_trading_day_age("", "2026-09-30") is None
    day = _dt.date(2026, 10, 2)
    while day.weekday() != 4:                       # 回退到一个周五，避免依赖具体年份日历
        day -= _dt.timedelta(days=1)
    assert repo.score_trading_day_age(day.isoformat(),
                                      (day + _dt.timedelta(days=3)).isoformat()) == 1

    monkeypatch.setattr(
        repo.cache, "get",
        lambda key: "2026-09-21,2026-09-22,2026-09-23,2026-09-24,2026-09-25,"
                    "2026-09-28,2026-09-29,2026-09-30")
    assert repo.score_trading_day_age("2026-09-28", "2026-09-30") == 2


def test_get_score_for_position_downgrades_stale(monkeypatch):
    monkeypatch.setattr(
        repo.cache, "get",
        lambda key: "2026-09-21,2026-09-22,2026-09-23,2026-09-24,2026-09-25,"
                    "2026-09-28,2026-09-29,2026-09-30")
    holder = {}

    def _fake_latest(code, as_of=None):
        holder["as_of"] = as_of
        return holder.get("row")

    monkeypatch.setattr(repo, "get_latest_score", _fake_latest)
    row, meta = repo.get_score_for_position("600050", "2026-09-30")
    assert row is None and meta["stale"] is True and meta["reason"] == "no_score"
    assert holder["as_of"] == "2026-09-30"          # 必须带 as_of=trade_date 读取

    holder["row"] = types.SimpleNamespace(trade_date="2026-09-30", grade="B")
    row, meta = repo.get_score_for_position("600050", "2026-09-30")
    assert meta["stale"] is False and meta["age_trading_days"] == 0
    assert meta["max_trading_days"] == 3

    holder["row"] = types.SimpleNamespace(trade_date="2026-09-21", grade="A")
    row, meta = repo.get_score_for_position("600050", "2026-09-30")
    assert meta["stale"] is True and meta["reason"] == "stale"
    assert meta["age_trading_days"] == 7

    holder["row"] = types.SimpleNamespace(trade_date="2026-09-29", grade="A")
    row, meta = repo.get_score_for_position("600050", "2026-09-30")
    assert meta["stale"] is False


def test_run_position_rejects_stale_score(monkeypatch):
    from app.graph import router

    stale_row = types.SimpleNamespace(stock_code="600060", grade="A", score=90.0,
                                      trade_date="2026-09-01")
    monkeypatch.setattr(repo, "get_score_for_position",
                        lambda code, date, **kw: (stale_row, {
                            "as_of": date, "score_date": "2026-09-01", "grade": "A",
                            "stale": True, "age_trading_days": 19,
                            "max_trading_days": 3, "reason": "stale"}))
    with pytest.raises(ValueError, match="评级不足"):
        router.run_position("600060", trade_date="2026-09-30")


# ==================== S-11 飞书重试 / 升级 ====================

def test_feishu_retry_then_escalate(monkeypatch):
    from app.services import feishu

    attempts = []

    def _fail(url, json=None, timeout=None):
        attempts.append(1)
        raise RuntimeError("webhook down")

    monkeypatch.setattr(feishu.httpx, "post", _fail)
    monkeypatch.setattr(feishu.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(feishu.settings, "feishu_webhook_url", "http://hook.invalid")
    monkeypatch.setattr(feishu.settings, "feishu_bridge_alert_direct", False)
    result = feishu.push_alert("测试甲", "600070", "触及止损", "critical", "消息", "exit")
    assert result["result"] == "failed" and result["escalated"] is True
    assert len(attempts) == feishu._PUSH_RETRY_TIMES + 1


def test_feishu_retry_then_success(monkeypatch):
    from app.services import feishu

    attempts = []

    def _flaky(url, json=None, timeout=None):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("first fail")
        return types.SimpleNamespace(raise_for_status=lambda: None)

    monkeypatch.setattr(feishu.httpx, "post", _flaky)
    monkeypatch.setattr(feishu.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(feishu.settings, "feishu_webhook_url", "http://hook.invalid")
    monkeypatch.setattr(feishu.settings, "feishu_bridge_alert_direct", False)
    result = feishu.push_alert("测试甲", "600071", "止盈触发", "warning", "消息", "reduce")
    assert result["result"] == "delivered" and result["channel"] == "webhook"
    assert result["escalated"] is False and len(attempts) == 2


# ==================== 投递留痕字段 ====================

def test_list_alerts_exposes_push_trace():
    repo.insert_alert("600080", "推送留痕", "红线C3-硬止损", "critical", "消息", "exit", {},
                      True, source="red_line", push_channel="webhook", push_result="delivered")
    rows = [r for r in repo.list_alerts(limit=20) if r.get("stock_code") == "600080"]
    assert rows and rows[0]["push_channel"] == "webhook"
    assert rows[0]["push_result"] == "delivered"
