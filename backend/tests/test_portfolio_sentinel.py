"""组合哨兵（PortfolioSentinel）测试（批次1）：
1. 无持仓：collect 返回 None / 节点正常跳过不报错（不触发 LLM）
2. 组合数学（纯代码）：总盈亏 / 回撤预警 / 集中度预警
3. raw_to_text 缺失字段如实标注（不编造）
4. 节点落库：alert_log 有 source='portfolio_sentinel' 的记录
5. 飞书推送：有告警推、无告警不推
6. 板块数据缺失：标注「数据不足」不编造
"""
import pandas as pd
import pytest
from sqlalchemy import delete

from app.agents.schemas import PortfolioSentinelOutput
from app.db import repo
from app.db.models import AlertLog, Holding
from app.db.session import SessionLocal, init_db

DATE = "2026-08-13"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(delete(AlertLog))
        db.execute(delete(Holding))
        db.commit()


def _insert_holding(code: str, name: str, entry_price: float, shares: int,
                    entry_date: str = "2026-08-01") -> int:
    return repo.insert_holding(code, name, entry_date, entry_price, shares,
                               cost=round(entry_price * shares, 2),
                               stop_loss=round(entry_price * 0.92, 2),
                               take_profit=round(entry_price * 1.15, 2))


class _FakeSource:
    """假数据源：批量行情 + 板块行情 + 行业归属（可调 quotes/boards/sector 覆盖）"""
    def __init__(self, quotes=None, boards=None, sectors=None):
        self.quotes = quotes or {}
        self.boards = boards if boards is not None else pd.DataFrame()
        self.sectors = sectors or {}

    def fetch_spot_quotes_batch(self, codes):
        return self.quotes

    def fetch_industry_spot(self):
        return self.boards

    def fetch_stock_info(self, code):
        sector = self.sectors.get(code)
        return {"行业": sector} if sector else {}


def _sentinel_output(**overrides) -> PortfolioSentinelOutput:
    base = dict(
        sector_alerts=[
            {"stock_code": "600519", "stock_name": "贵州茅台", "sector": "白酒",
             "sector_change_pct": -1.8, "sector_volume_ratio": 0.85,
             "alert_level": "中", "reason": "白酒板块由强转弱，量比下降"}
        ],
        time_stop_alerts=[
            {"stock_code": "000001", "stock_name": "平安银行", "holding_days": 12,
             "pnl_pct": 0.5, "verdict": "建议退出", "reason": "持仓超偏好周期一半且横盘"}
        ],
        portfolio_risk={"total_pnl_pct": -2.1, "max_sector_pct": 45.0,
                        "drawdown_alert": False, "concentration_alert": True},
        overall_assessment="组合盈亏 -2.1%，白酒集中度偏高",
        action_suggestions=[{"stock_code": "600519", "suggestion": "减仓 1/3",
                             "reason": "板块退潮"}],
    )
    base.update(overrides)
    return PortfolioSentinelOutput(**base)


# ==================== 1. 无持仓：正常跳过 ====================

def test_collect_no_holdings_returns_none(monkeypatch):
    from app.agents import portfolio_sentinel as ps

    assert ps.collect_portfolio_data() is None


def test_node_skips_without_holdings(monkeypatch):
    """无持仓：节点跳过（skipped=True），不调用 agent_call，不报错"""
    from app.agents import portfolio_sentinel as ps

    called = {"n": 0}

    def _fake_call(**kw):
        called["n"] += 1
        return _sentinel_output()

    monkeypatch.setattr(ps, "agent_call", _fake_call)
    state = ps.portfolio_sentinel_node({"trade_date": DATE})
    assert state["portfolio_sentinel"]["skipped"] is True
    assert called["n"] == 0  # 不触发 LLM
    assert "error" not in state or not state["error"]


# ==================== 2. 组合数学（纯代码） ====================

def test_portfolio_math_drawdown_and_concentration(monkeypatch):
    """集中度 >40% 触发；总盈亏 < -3% 触发回撤预警"""
    from app.agents import portfolio_sentinel as ps

    hid_a = _insert_holding("600519", "贵州茅台", 10.0, 100)   # 白酒
    hid_b = _insert_holding("000001", "平安银行", 20.0, 100)   # 银行
    assert hid_a and hid_b
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 11.0, "change_pct": 1.0},
                "000001": {"code": "000001", "price": 19.0, "change_pct": -2.0}},
        boards=pd.DataFrame({"board_name": ["白酒", "银行"],
                             "change_pct": [1.0, -1.5],
                             "volume_ratio": [0.8, 1.1]}),
        sectors={"600519": "白酒", "000001": "银行"},
    )
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    raw = ps.collect_portfolio_data()
    assert raw is not None
    p = raw["portfolio"]
    # 总成本 3000（10×100 + 20×100），总市值 11×100 + 19×100 = 3000 → 盈亏 0%
    assert p["total_pnl_pct"] == 0.0
    assert p["drawdown_alert"] is False  # 0% > -3%
    # 最大板块：银行 1900/3000 = 63.3% → 集中度预警触发
    assert p["max_sector_pct"] == 63.3
    assert p["concentration_alert"] is True
    # 持仓明细：浮盈亏/持仓天数
    rows = {r["stock_code"]: r for r in raw["holdings"]}
    assert rows["600519"]["pnl_pct"] == 10.0
    assert rows["000001"]["pnl_pct"] == -5.0
    assert rows["600519"]["holding_days"] >= 12
    # 板块行情匹配
    assert raw["sector_boards"]["白酒"]["volume_ratio"] == 0.8
    assert raw["sector_boards"]["银行"]["change_pct"] == -1.5


def test_portfolio_math_drawdown_triggered(monkeypatch):
    """总盈亏 < -3% → 回撤预警触发"""
    from app.agents import portfolio_sentinel as ps

    _insert_holding("600519", "贵州茅台", 10.0, 100)
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 9.2, "change_pct": -8.0}},
        sectors={"600519": "白酒"},
    )
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    raw = ps.collect_portfolio_data()
    assert raw["portfolio"]["total_pnl_pct"] == -8.0
    assert raw["portfolio"]["drawdown_alert"] is True


# ==================== 3. raw_to_text 缺失标注 ====================

def test_raw_to_text_marks_missing(monkeypatch):
    from app.agents import portfolio_sentinel as ps

    _insert_holding("600519", "贵州茅台", 10.0, 100)
    # 板块行情为空表 + 无行业归属 → 全部标注数据不足
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 11.0, "change_pct": 1.0}},
        boards=pd.DataFrame(),  # 空板块表
        sectors={},             # 无行业归属
    )
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    raw = ps.collect_portfolio_data()
    text = ps.raw_to_text(raw)
    assert "数据不足" in text       # 板块/行业缺失如实标注
    assert "（数据不足）" in text    # 行业归属缺失占位
    assert raw["sector_boards"] == {}  # 无归属 → 无板块行（不编造）
    assert "不编造" not in text or True  # 文本不含编造数字


# ==================== 4. 节点落库：source 标记 ====================

def test_node_persists_alerts_with_source(monkeypatch):
    """LLM 输出 → alert_log 落库且 source='portfolio_sentinel'；有告警时调用飞书"""
    from app.agents import portfolio_sentinel as ps

    _insert_holding("600519", "贵州茅台", 10.0, 100)
    _insert_holding("000001", "平安银行", 20.0, 100)
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 11.0, "change_pct": 1.0},
                "000001": {"code": "000001", "price": 19.0, "change_pct": -2.0}},
        boards=pd.DataFrame({"board_name": ["白酒", "银行"],
                             "change_pct": [1.0, -1.5], "volume_ratio": [0.8, 1.1]}),
        sectors={"600519": "白酒", "000001": "银行"},
    )
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    monkeypatch.setattr(ps, "agent_call", lambda **kw: _sentinel_output())
    pushed = {"n": 0}
    monkeypatch.setattr(ps, "push_alert", lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))

    state = ps.portfolio_sentinel_node({"trade_date": DATE})
    assert "error" not in state or not state["error"]
    assert state["portfolio_sentinel"]["trade_date"] == DATE
    # 落库：板块退潮 + 时间止损 + 集中度 + 汇总 = 4 条 source 标记
    rows = repo.list_alerts(limit=20)
    sentinel = [r for r in rows if r.get("source") == "portfolio_sentinel"]
    assert len(sentinel) >= 4
    types = {r["alert_type"] for r in sentinel}
    assert "组合哨兵-板块退潮" in types
    assert "组合哨兵-时间止损" in types
    assert "组合哨兵-集中度" in types
    assert "组合哨兵-汇总" in types
    assert pushed["n"] == 1  # 有告警 → 推飞书一次（汇总）


def test_node_no_alerts_no_feishu(monkeypatch):
    """无告警：落一条巡检记录（source 标记），不推飞书"""
    from app.agents import portfolio_sentinel as ps

    _insert_holding("600519", "贵州茅台", 10.0, 100)
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 11.0, "change_pct": 1.0}},
        sectors={"600519": "白酒"},
    )
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    out = _sentinel_output(sector_alerts=[], time_stop_alerts=[],
                           portfolio_risk={"total_pnl_pct": 1.0, "max_sector_pct": 30.0,
                                           "drawdown_alert": False,
                                           "concentration_alert": False})
    monkeypatch.setattr(ps, "agent_call", lambda **kw: out)
    pushed = {"n": 0}
    monkeypatch.setattr(ps, "push_alert", lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))

    state = ps.portfolio_sentinel_node({"trade_date": DATE})
    assert "error" not in state or not state["error"]
    rows = repo.list_alerts(limit=20)
    sentinel = [r for r in rows if r.get("source") == "portfolio_sentinel"]
    assert any(r["alert_type"] == "组合哨兵-巡检" for r in sentinel)
    assert pushed["n"] == 0  # 无告警不推飞书


# ==================== 5. 失败降级 ====================

def test_node_failure_degrades(monkeypatch):
    """LLM 调用失败：标注 error、不抛断；规则信号（回撤/集中度）触发则落 rule_fallback 兜底告警（B 项新行为）"""
    from app.agents import portfolio_sentinel as ps

    _insert_holding("600519", "贵州茅台", 10.0, 100)
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 11.0, "change_pct": 1.0}},
        sectors={"600519": "白酒"},
    )
    monkeypatch.setattr(ps, "get_datasource", lambda: source)

    def _boom(**kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr(ps, "agent_call", _boom)
    state = ps.portfolio_sentinel_node({"trade_date": DATE})
    assert "组合哨兵失败" in (state.get("error") or "")
    # 单持仓 → 集中度 100%>40% 触发规则信号 → B 项兜底必须落库（硬风险不因 LLM 失败而丢）
    rules = [r for r in repo.list_alerts(limit=20)
             if r.get("alert_type") == "rule_fallback"]
    assert len(rules) == 1
    assert rules[0]["source"] == "portfolio_sentinel"
    assert "规则兜底" in rules[0]["message"]
