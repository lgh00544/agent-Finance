"""批次2：SellAgent 减仓比例（reduce_ratio）+ 组合级回撤联动（dev SQLite，不触网）：
1. SellOutput 新增 reduce_ratio 字段：partial 有值 / 默认 None / 值域 0-1 pydantic 拦截
2. sell_prompt：SCHEMA_DESC 含 reduce_ratio；SYSTEM_PROMPT 含减仓比例研判 + 组合风险上下文感知；
   build_user_prompt 注入【组合风险上下文】段（缺失默认「（无）」）
3. portfolio_sentinel_node 运行后 cache 暴露 portfolio_risk 快照（portfolio_sentinel:last_risk）
4. collect_sell_input 读 cache 注入 sell_input["portfolio_risk_context"]（快照存在/缺失两种）
5. llm_sell 把 portfolio_risk_context 传入 user_prompt（存在/缺失两种）
6. 前端 render.reduce_share_plan 换算：100 整数倍 / 不足 100 取 100 / 不超持仓 / 缺持仓返回 0
7. 页面 render_sell_decision 减仓建议展示接线（源码级，页面顶层重度渲染不入测试）
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from app.agents.schemas import SellOutput
from app.cache import cache
from app.db.models import AlertLog, Holding
from app.db.session import SessionLocal, init_db

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 本模块专用日期：避免与既有组合哨兵测试共用 2026-08-13 的飞书当日去重键（alert:portfolio_sentinel:summary:*）
_MODULE_DATE = "2099-12-31"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _cleanup_db_and_cache():
    """隔离批次2测试副作用：清空持仓/告警行 + 失效 alert 查询缓存 + 组合风险与去重缓存键，
    避免污染后续测试（既有 test_portfolio_sentinel 依赖 2026-08-13 去重键未被提前占用）"""
    cache.delete_prefix("dbq:alert:")
    cache.delete("portfolio_sentinel:last_risk")
    cache.delete(f"alert:portfolio_sentinel:summary:{_MODULE_DATE}")
    with SessionLocal() as db:
        db.execute(delete(AlertLog))
        db.execute(delete(Holding))
        db.commit()
    yield
    cache.delete_prefix("dbq:alert:")
    cache.delete("portfolio_sentinel:last_risk")
    cache.delete(f"alert:portfolio_sentinel:summary:{_MODULE_DATE}")
    with SessionLocal() as db:
        db.execute(delete(AlertLog))
        db.execute(delete(Holding))
        db.commit()


# ==================== 1. SellOutput reduce_ratio 字段 ====================

def _sell_kwargs(action: str = "partial", **over) -> dict:
    base = dict(stock_code="600519", action=action, confidence="medium",
                reasons=["信号转弱"], exit_price_zone="26.5", risk_warning="风险较大",
                check_list=["当日是否可卖"])
    base.update(over)
    return base


def test_sell_output_partial_carries_reduce_ratio():
    """partial 决策带 reduce_ratio，且 model_dump 保留（落库闭环）"""
    out = SellOutput(**_sell_kwargs(action="partial", reduce_ratio=0.33))
    assert out.reduce_ratio == 0.33
    dumped = out.model_dump()
    assert dumped["reduce_ratio"] == 0.33


def test_sell_output_reduce_ratio_default_none():
    """兼容：不传 reduce_ratio（旧 LLM 输出）→ 默认 None；hold/sell 通常不带值"""
    assert SellOutput(**_sell_kwargs(action="partial")).reduce_ratio is None
    assert SellOutput(**_sell_kwargs(action="hold")).reduce_ratio is None
    assert SellOutput(**_sell_kwargs(action="sell")).reduce_ratio is None


def test_sell_output_reduce_ratio_range_enforced():
    """值域 0.0-1.0，超出 pydantic 校验拦截"""
    with pytest.raises(ValidationError):
        SellOutput(**_sell_kwargs(action="partial", reduce_ratio=1.5))
    with pytest.raises(ValidationError):
        SellOutput(**_sell_kwargs(action="partial", reduce_ratio=-0.1))


# ==================== 2. sell_prompt 指引 ====================

def test_schema_desc_has_reduce_ratio():
    from agent_prompts import sell_prompt
    assert "reduce_ratio" in sell_prompt.SCHEMA_DESC


def test_system_prompt_has_reduce_ratio_and_risk_guidance():
    from agent_prompts import sell_prompt
    sp = sell_prompt.SYSTEM_PROMPT
    assert "减仓比例研判 reduce_ratio" in sp
    assert "0.2-0.6" in sp
    assert "组合风险上下文感知" in sp
    assert "组合数据不可用" in sp


def test_build_user_prompt_includes_risk_section():
    from agent_prompts import sell_prompt
    prompt = sell_prompt.build_user_prompt("持仓", "信号", "计划", "行情")
    assert "【组合风险上下文】" in prompt
    assert "（无）" in prompt  # 未传 → 默认不可用标注
    prompt2 = sell_prompt.build_user_prompt("持仓", "信号", "计划", "行情",
                                            portfolio_risk_context="组合总盈亏: -4.2%")
    assert "组合总盈亏: -4.2%" in prompt2


# ==================== 3. portfolio_sentinel_node 暴露快照 ====================

class _FakeSource:
    """假数据源：批量行情 + 板块行情 + 行业归属"""
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


def _sentinel_output() -> "object":
    from app.agents.schemas import PortfolioSentinelOutput
    return PortfolioSentinelOutput(
        sector_alerts=[], time_stop_alerts=[],
        portfolio_risk={"total_pnl_pct": -4.2, "max_sector_pct": 50.0,
                        "drawdown_alert": True, "concentration_alert": True},
        overall_assessment="组合盈亏 -4.2%，白酒集中度偏高",
        action_suggestions=[{"stock_code": "600519", "suggestion": "减仓",
                             "reason": "组合回撤预警"}],
    )


def _insert_holding(code: str, name: str, entry_price: float, shares: int) -> int:
    from app.db import repo
    return repo.insert_holding(code, name, "2026-08-01", entry_price, shares,
                               cost=round(entry_price * shares, 2),
                               stop_loss=round(entry_price * 0.92, 2),
                               take_profit=round(entry_price * 1.15, 2))


def test_sentinel_node_exposes_portfolio_risk_snapshot(monkeypatch):
    """节点运行后 cache 暴露 portfolio_risk 快照（JSON），SellAgent 只读可消费"""
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
    monkeypatch.setattr(ps, "push_alert", lambda *a, **k: False)

    state = ps.portfolio_sentinel_node({"trade_date": _MODULE_DATE})
    assert "error" not in state or not state["error"]
    raw = cache.get("portfolio_sentinel:last_risk")
    assert raw, "组合风险快照未写入 cache"
    risk = json.loads(raw)
    assert risk["total_pnl_pct"] == -4.2
    assert risk["max_sector_pct"] == 50.0
    assert risk["drawdown_alert"] is True
    assert risk["concentration_alert"] is True


# ==================== 4. collect_sell_input 注入 ====================

class _FakeHolding:
    stock_code = "600519"
    stock_name = "贵州茅台"
    entry_date = "2026-08-01"
    entry_price = 18.0
    shares = 900
    stop_loss = 16.5
    take_profit = 24.0
    target_pct = 10.0
    note = ""


class _KlineSource:
    def fetch_daily_kline(self, code, start, end):
        return pd.DataFrame({"close": [18.0, 18.5, 19.0, 18.8]})

    def fetch_news(self, code):
        return pd.DataFrame({"title": ["测试新闻"]})


def _mock_sell_deps(monkeypatch):
    from app.agents import sell as sell_mod
    monkeypatch.setattr(sell_mod.repo, "get_holding", lambda hid: _FakeHolding())
    monkeypatch.setattr(sell_mod, "get_datasource", lambda: _KlineSource())
    monkeypatch.setattr(sell_mod, "compute_indicators",
                        lambda kline: {"recent_klines": [{"date": "2026-08-09", "close": 18.8}]})
    monkeypatch.setattr(sell_mod.repo, "get_alerts_by_code", lambda code, limit=20: [])
    monkeypatch.setattr(sell_mod.repo, "get_latest_plan", lambda code: None)
    return sell_mod


def test_collect_injects_portfolio_risk_context(monkeypatch):
    """PortfolioSentinel 运行过（cache 有快照）→ sell_input 注入 portfolio_risk_context"""
    cache.set("portfolio_sentinel:last_risk",
              json.dumps({"total_pnl_pct": -4.2, "max_sector_pct": 50.0,
                          "drawdown_alert": True, "concentration_alert": True}), 1800)
    sell_mod = _mock_sell_deps(monkeypatch)
    state = sell_mod.collect_sell_input({"holding_id": 1})
    ctx = state["sell_input"]["portfolio_risk_context"]
    assert ctx["available"] is True
    assert ctx["total_pnl_pct"] == -4.2
    assert ctx["max_sector_pct"] == 50.0
    assert ctx["drawdown_alert"] is True
    assert ctx["concentration_alert"] is True


def test_collect_marks_unavailable_when_no_snapshot(monkeypatch):
    """PortfolioSentinel 未运行过（cache 无快照）→ 标注不可用，不报错，不影响其余输入"""
    sell_mod = _mock_sell_deps(monkeypatch)
    state = sell_mod.collect_sell_input({"holding_id": 1})
    assert "error" not in state or not state["error"]
    ctx = state["sell_input"]["portfolio_risk_context"]
    assert ctx["available"] is False
    assert "不可用" in ctx["note"]
    # 个股数据照常聚合
    assert state["sell_input"]["holding"]["shares"] == 900


# ==================== 5. llm_sell 传入 prompt ====================

def _capture_llm_sell(monkeypatch, sell_input):
    from app.agents import sell as sell_mod
    from app.agents.schemas import SellOutput

    out = SellOutput(stock_code="600519", action="partial", confidence="medium",
                     reasons=["组合回撤预警触发"], exit_price_zone="26.5",
                     risk_warning="风险较大", check_list=["当日是否可卖"], reduce_ratio=0.4)
    captured = {}

    def _fake(agent, cache_key, system_prompt, user_prompt, schema,
              ttl_seconds=86400, with_profile=True, with_knowledge=True, model_level=None):
        captured["prompt"] = user_prompt
        return out

    monkeypatch.setattr(sell_mod, "agent_call", _fake)
    monkeypatch.setattr(sell_mod.repo, "insert_sell_decision", lambda *a, **k: 1)
    state = {"stock_code": "600519", "stock_name": "贵州茅台", "trade_date": "2026-08-09",
             "holding_id": 1, "tech_index": {"recent_klines": []}, "sell_input": sell_input,
             "trace": []}
    sell_mod.llm_sell(state)
    return captured["prompt"]


def _base_sell_input() -> dict:
    return {"holding": {"entry_date": "2026-08-01", "entry_price": 18.0, "shares": 900,
                        "stop_loss": 16.5, "take_profit": 24.0, "target_pct": 10.0,
                        "note": "", "latest_close": 20.0, "pnl_pct": 11.1},
            "plan": {"rationale": "", "batches": [], "stop_loss": 0, "take_profit": 0},
            "monitor_signals": [], "news_titles": [], "hot_money": None}


def test_llm_sell_passes_portfolio_risk_context(monkeypatch):
    """快照可用 → user_prompt 含组合风险上下文（引用组合状态）"""
    sell_input = _base_sell_input()
    sell_input["portfolio_risk_context"] = {"available": True, "total_pnl_pct": -4.2,
                                            "max_sector_pct": 50.0, "drawdown_alert": True,
                                            "concentration_alert": True}
    prompt = _capture_llm_sell(monkeypatch, sell_input)
    assert "【组合风险上下文】" in prompt
    assert "组合总盈亏: -4.2%" in prompt
    assert "组合回撤预警: 触发" in prompt
    assert "集中度预警: 触发" in prompt


def test_llm_sell_marks_risk_unavailable(monkeypatch):
    """快照不可用 → user_prompt 标注「组合数据不可用」，不影响个股研判"""
    sell_input = _base_sell_input()
    sell_input["portfolio_risk_context"] = {"available": False,
                                            "note": "组合数据不可用（PortfolioSentinel 未运行或快照过期）"}
    prompt = _capture_llm_sell(monkeypatch, sell_input)
    assert "【组合风险上下文】" in prompt
    assert "组合数据不可用" in prompt


def test_llm_sell_handles_missing_risk_key(monkeypatch):
    """向后兼容：旧 sell_input 无 portfolio_risk_context 键 → 不报错，标注不可用"""
    prompt = _capture_llm_sell(monkeypatch, _base_sell_input())
    assert "【组合风险上下文】" in prompt
    assert "组合数据不可用" in prompt


# ==================== 6. 前端换算 render.reduce_share_plan ====================

def _load_render():
    spec = importlib.util.spec_from_file_location(
        "render", _PROJECT_ROOT / "streamlit" / "render.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reduce_share_plan_floor_to_100_lots():
    """向下取整到 100 股整数倍：900 股×33% → 200 股（2 手），剩余 700"""
    render = _load_render()
    assert render.reduce_share_plan(0.33, 900) == (200, 700)
    assert render.reduce_share_plan(0.5, 1000) == (500, 500)
    assert render.reduce_share_plan(0.6, 600) == (300, 300)


def test_reduce_share_plan_min_100():
    """不足 100 股向上取 100（最小可卖单位）：200 股×25% = 50 股 → 100 股"""
    render = _load_render()
    assert render.reduce_share_plan(0.25, 200) == (100, 100)
    assert render.reduce_share_plan(0.5, 150) == (100, 50)


def test_reduce_share_plan_caps_at_shares():
    """换算结果不超持仓：150 股×90% → 100 股（不超持仓）"""
    render = _load_render()
    assert render.reduce_share_plan(0.9, 150) == (100, 50)


def test_reduce_share_plan_missing_shares_returns_zero():
    """持仓股数缺失/为 0 → (0, 0)，调用方不展示不报错"""
    render = _load_render()
    assert render.reduce_share_plan(0.5, None) == (0, 0)
    assert render.reduce_share_plan(0.5, 0) == (0, 0)


# ==================== 7. 页面接线（源码级） ====================

def test_page_render_sell_decision_wired_for_reduce_ratio():
    """页面 render_sell_decision 已接减仓建议展示：调用 render.reduce_share_plan，
    仅 action=partial 展示「建议减仓」"""
    src = (_PROJECT_ROOT / "streamlit" / "pages" / "4_持仓监控.py").read_text(encoding="utf-8")
    assert "render.reduce_share_plan(" in src
    assert '== "partial"' in src
    assert "建议减仓" in src
