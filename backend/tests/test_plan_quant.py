"""建仓计划量化计算层测试（plan_quant.quantify 纯计算，mock 账户快照不触网）：

1. 基础量化：单票金额 = 评级分级上限 × 总资产；股数 100 股整数倍
2. 分级上限：A 级 30% / B 级 20%
3. 账户可用资金（C2 约束）不足 → 自动缩减并标注
4. 盈亏比 ≥3:1 达标；<3:1 → 仓位自动降档（0.7×）并标注风险
5. 初始止损：C3（成本×0.92）与 LLM 止损取更严（价位更高）
6. 分档明细：金额/股数/累计占比（比例归一化）
7. 价格区间中值解析
8. 计划来源标记：insert_plan source 落库 + list_plans 返回
"""
import types

import pytest

from app.db import repo
from app.db.session import init_db
from app.services import plan_quant


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _account(monkeypatch):
    """账户快照：总资产 100000，当前持仓市值 20000（可用 = 100000×0.6 − 20000 = 40000）"""
    monkeypatch.setattr(plan_quant, "settings",
                        types.SimpleNamespace(total_capital=100000))
    monkeypatch.setattr(plan_quant.holding_view, "build_holding_view",
                        lambda: {"rows": [{"market_value": 20000.0}]})


_BATCHES = [
    {"tranche": 1, "price_zone": "9.5-10.5", "ratio_pct": 30.0,
     "trigger_note": "回调至 MA20 附近缩量企稳"},
    {"tranche": 2, "price_zone": "10.5-11.5", "ratio_pct": 40.0,
     "trigger_note": "回踩 MA10 支撑量能健康"},
    {"tranche": 3, "price_zone": "11.5-12.5", "ratio_pct": 30.0,
     "trigger_note": "放量突破前高趋势确认"},
]


def test_quantify_basic_b_grade():
    """B 级：单票上限 20%×10 万 = 2 万；受可用资金 4 万约束不缩减；股数 100 整数倍"""
    q = plan_quant.quantify("600001", "测试A", "B", _BATCHES,
                            stop_loss=8.8, take_profit=13.0,
                            latest_close=10.0, latest_date="2026-08-09")
    assert q["position_cap_pct"] == 20.0
    assert q["position_amount"] == 20000.0
    assert q["available_capital"] == 40000.0
    assert q["position_shares"] % 100 == 0, "股数必须为 100 股整数倍"
    assert q["reduced"] is False
    assert q["breakeven_ok"] is True, "盈亏比应达标"
    assert q["expected_total_pct"] == 40.0  # (20000+20000)/100000
    # 每档金额与股数
    amounts = [b["amount"] for b in q["batches"]]
    assert amounts == [6000.0, 8000.0, 6000.0]
    assert all(b["shares"] % 100 == 0 for b in q["batches"])
    assert q["batches"][-1]["cum_pct"] == 100.0


def test_quantify_grade_cap_a_30():
    """A 级单票上限 30%×10 万 = 3 万"""
    q = plan_quant.quantify("600001", "测试A", "A", _BATCHES,
                            stop_loss=8.8, take_profit=13.0, latest_close=10.0)
    assert q["position_cap_pct"] == 30.0
    assert q["position_amount"] == 30000.0


def test_quantify_available_capital_shrink():
    """可用资金不足（市值 60000 → 可用 0）→ 计划金额缩减到 0 并标注"""
    plan_quant.holding_view.build_holding_view = \
        lambda: {"rows": [{"market_value": 60000.0}]}
    q = plan_quant.quantify("600001", "测试A", "B", _BATCHES,
                            stop_loss=8.8, take_profit=13.0, latest_close=10.0)
    assert q["available_capital"] == 0.0
    assert q["position_amount"] == 0.0
    assert any("缩减" in n for n in q["notes"])


def test_quantify_breakeven_reduce():
    """盈亏比不足 3:1 → 仓位自动降低至 0.7× 并标注风险"""
    # 止盈贴近成本（10.8 vs 成本 10）→ 止盈空间小 → 盈亏比 = 0.8/0.8 = 1:1 不足 3:1
    q = plan_quant.quantify("600001", "测试A", "B", _BATCHES,
                            stop_loss=8.0, take_profit=10.8, latest_close=10.0)
    assert q["breakeven_ratio"] is not None and q["breakeven_ratio"] < 3.0
    assert q["reduced"] is True
    assert q["position_amount"] == 14000.0  # 20000 × 0.7
    assert any("不足 3:1" in n for n in q["notes"])


def test_quantify_stop_takes_stricter():
    """初始止损 = max(C3 成本×0.92, LLM 止损)（价位更高者更严）"""
    # 成本基准 = 首档中值 10.0；C3 = 9.2；LLM 止损 9.5 更严 → 取 9.5
    q = plan_quant.quantify("600001", "测试A", "B", _BATCHES,
                            stop_loss=9.5, take_profit=13.0, latest_close=10.0)
    assert q["initial_stop"] == 9.5
    assert q["c3_stop"] == 9.2
    # LLM 止损 8.5（更松）→ C3 兜底 9.2
    q2 = plan_quant.quantify("600001", "测试A", "B", _BATCHES,
                             stop_loss=8.5, take_profit=13.0, latest_close=10.0)
    assert q2["initial_stop"] == 9.2


def test_zone_mid_parse():
    assert plan_quant._zone_mid("9.5-10.5") == 10.0
    assert plan_quant._zone_mid("61.5-62.5") == 62.0
    assert plan_quant._zone_mid("10") == 10.0
    assert plan_quant._zone_mid("") is None


def test_lots_rounding():
    """金额 → 股数：向下取整到 100 股整数倍"""
    assert plan_quant._lots(9999, 10.0) == 900
    assert plan_quant._lots(10000, 10.0) == 1000
    assert plan_quant._lots(7000, 62.0) == 100   # 7000/62≈112 股 → 100 股整数倍
    assert plan_quant._lots(1500, 62.0) == 0     # 不足一手 → 0 股
    assert plan_quant._lots(0, 10.0) == 0


def test_plan_source_marking():
    """来源标记：candidate/manual 落库并在列表返回；旧调用默认 manual
    （用专属代码 + code 过滤查询，避免与全量共享的 dbq 缓存/其它测试数据串扰）"""
    cid = repo.insert_plan("609999", "测试C", "2026-08-09", 50.0,
                           [{"tranche": 1, "price_zone": "10~10.5", "ratio_pct": 100.0}],
                           9.2, 12.0, "联动生成", source="candidate")
    mid = repo.insert_plan("609998", "测试D", "2026-08-09", 40.0,
                           [{"tranche": 1, "price_zone": "10~10.5", "ratio_pct": 100.0}],
                           9.0, 11.0, "手动生成")
    assert repo.list_plans(code="609999", limit=10)[0]["source"] == "candidate"
    assert repo.list_plans(code="609998", limit=10)[0]["source"] == "manual"
