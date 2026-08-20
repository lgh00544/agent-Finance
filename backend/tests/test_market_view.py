"""市场概览只读视图测试（不触网：行情源与 repo 全部 mock）：
1. 三大指数实时行情：过滤/排序/数值（数学正确性）
2. 热门板块：涨幅前 5 客观排序 + 领涨龙头代码解析（名称匹配 → 成分股降级）
3. 账户摘要双数据路径：无基准估算（TOTAL_CAPITAL 锚定）→ 有基准用券商值
4. 失败降级：数据源异常返回空数据 + error 标注（前端展示用，不抛原始报错）
"""
import pandas as pd
import pytest
from unittest import mock

from app.services import holding_view, market_view


# ================= 三大指数 =================

def _index_spot():
    return pd.DataFrame([
        {"code": "sh000001", "name": "上证指数", "price": 3456.78, "change_pct": 0.85},
        {"code": "sz399001", "name": "深证成指", "price": 12345.67, "change_pct": -1.23},
        {"code": "sz399006", "name": "创业板指", "price": 2500.5, "change_pct": 2.5},
        {"code": "sh000300", "name": "沪深300", "price": 4100.0, "change_pct": 0.5},
        {"code": "sz399005", "name": "中小100", "price": 6800.0, "change_pct": -0.3},
    ])


def test_index_quotes_filters_majors_with_csi300(monkeypatch):
    """保留三大指数 + 沪深300（batch F 组合回撤分解的市场基准），保持固定顺序，数值正确"""
    monkeypatch.setattr(market_view, "get_datasource",
                        lambda: type("S", (), {"fetch_index_spot": lambda self: _index_spot()})())
    data = market_view.index_quotes()
    assert data["error"] is None
    codes = [it["code"] for it in data["indices"]]
    assert codes == ["sh000001", "sz399001", "sz399006", "sh000300"]
    up = data["indices"][0]
    assert up["name"] == "上证指数" and up["price"] == 3456.78 and up["change_pct"] == 0.85
    assert data["indices"][1]["change_pct"] == -1.23
    assert data["indices"][3]["code"] == "sh000300" and data["indices"][3]["name"] == "沪深300"


def test_index_quotes_failure_returns_error(monkeypatch):
    """指数行情失败：空列表 + error 标注（前端降级展示，不抛异常）"""

    def _boom():
        raise RuntimeError("东财限流")

    monkeypatch.setattr(market_view, "get_datasource",
                        lambda: type("S", (), {"fetch_index_spot": lambda self: _boom()})())
    data = market_view.index_quotes()
    assert data["indices"] == []
    assert data["error"] and "指数行情获取失败" in data["error"]


def test_index_quotes_empty_df(monkeypatch):
    """接口返回空表：空列表 + 无 error（不崩溃）"""
    monkeypatch.setattr(market_view, "get_datasource",
                        lambda: type("S", (), {"fetch_index_spot": lambda self: pd.DataFrame()})())
    data = market_view.index_quotes()
    assert data["indices"] == [] and data["error"] is None


# ================= 今日热门板块（v2：读 sector_snapshot DB 兜底） =================

def test_hot_sectors_delegates_to_snapshot(monkeypatch):
    """hot_sectors 委托 sector_snapshot.get_hot_sectors_with_fallback，返回 4 字段"""
    fb = {"sectors": [{"board_name": "半导体", "change_pct": 3.2,
                       "leading_stock": "中芯国际", "leading_code": "688981",
                       "rank_no": 1, "source": "em"}],
          "updated_at": "2026-08-19 13:00:00", "stale": False, "error": None}
    with mock.patch("app.services.sector_snapshot.get_hot_sectors_with_fallback",
                    return_value=fb):
        data = market_view.hot_sectors()
    assert data["error"] is None
    assert data["sectors"][0]["board_name"] == "半导体"
    assert data["sectors"][0]["leading_code"] == "688981"
    assert data["stale"] is False
    assert set(data.keys()) == {"sectors", "updated_at", "stale", "error"}


def test_hot_sectors_propagates_stale(monkeypatch):
    """DB 有陈旧数据 → hot_sectors 透传 stale=true"""
    fb = {"sectors": [{"board_name": "A", "change_pct": 1.0, "leading_stock": "x",
                       "leading_code": "1", "rank_no": 1, "source": "em"}],
          "updated_at": "2026-08-19 09:00:00", "stale": True, "error": None}
    with mock.patch("app.services.sector_snapshot.get_hot_sectors_with_fallback",
                    return_value=fb):
        data = market_view.hot_sectors()
    assert data["stale"] is True


def test_hot_sectors_error_path(monkeypatch):
    """非交易时段/失败 → hot_sectors 保留 error 标注（前端显示降级提示）"""
    fb = {"sectors": [], "updated_at": "", "stale": False,
          "error": "非交易时段，板块行情暂不可用"}
    with mock.patch("app.services.sector_snapshot.get_hot_sectors_with_fallback",
                    return_value=fb):
        data = market_view.hot_sectors()
    assert data["sectors"] == []
    assert data["error"] == "非交易时段，板块行情暂不可用"


# ================= 账户摘要（双数据路径） =================

def _holding(rid, code, name, price, shares):
    return {"id": rid, "stock_code": code, "stock_name": name, "entry_date": "2026-07-20",
            "entry_price": price, "shares": shares, "cost": price * shares,
            "stop_loss": 0.0, "take_profit": 0.0, "target_pct": 0.0, "status": "holding",
            "plan_id": None, "note": "", "created_at": "2026-08-01 10:00:00"}


def _mock_account(monkeypatch, holdings, spot, baseline=None, quote_exc=None):
    monkeypatch.setattr(holding_view.repo, "list_holdings", lambda status=None: holdings)
    monkeypatch.setattr(holding_view.repo, "list_plans", lambda code=None, limit=50: [])
    monkeypatch.setattr(holding_view.repo, "get_latest_account_baseline",
                        lambda: baseline)

    class _Source:
        def fetch_spot_universe(self):
            if quote_exc is not None:
                raise quote_exc
            return spot

    monkeypatch.setattr(holding_view, "get_datasource", lambda: _Source())


def test_account_summary_estimate_path(monkeypatch):
    """无基准：总资产 = TOTAL_CAPITAL + Σ盈亏（估算）；可用资金/仓位按持仓市值计算"""
    _mock_account(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", 100.0, 100),
                            _holding(2, "300750", "宁德时代", 200.0, 100)],
                  spot=pd.DataFrame([{"code": "600519", "name": "贵州茅台", "price": 110.0},
                                     {"code": "300750", "name": "宁德时代", "price": 190.0}]))
    acc = holding_view.build_account_summary()
    assert acc["source"] == "estimate" and acc["baseline"] is None
    assert acc["total_cost"] == 30000.0
    assert acc["market_value"] == 30000.0          # 11000 + 19000
    assert acc["pnl_amount"] == 0.0                # +1000 -1000
    assert acc["total_asset"] == 100000.0          # TOTAL_CAPITAL + 0
    assert acc["available_cash"] == 70000.0
    assert acc["position_pct"] == 30.0


def test_account_summary_baseline_path(monkeypatch):
    """有基准：总资产/可用资金/仓位占比用券商真实值；盈亏/成本仍实时计算"""
    baseline = {"id": 1, "trade_date": "2026-08-04", "total_asset": 150000.0,
                "available_cash": 90000.0, "position_pct": 40.0, "source": "ocr",
                "created_at": "2026-08-04 12:00:00"}
    _mock_account(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", 100.0, 100)],
                  spot=pd.DataFrame([{"code": "600519", "name": "贵州茅台", "price": 110.0}]),
                  baseline=baseline)
    acc = holding_view.build_account_summary()
    assert acc["source"] == "baseline"
    assert acc["total_asset"] == 150000.0
    assert acc["available_cash"] == 90000.0
    assert acc["position_pct"] == 40.0
    assert acc["pnl_amount"] == 1000.0
    assert acc["total_cost"] == 10000.0


def test_account_summary_quote_failure(monkeypatch):
    """行情整体失败且有持仓：市价相关项 None（不伪造 0）；无基准时总资产也 None"""
    _mock_account(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", 100.0, 100)],
                  spot=None, quote_exc=RuntimeError("数据源不可达"))
    acc = holding_view.build_account_summary()
    assert acc["quote_error"] and "行情获取失败" in acc["quote_error"]
    assert acc["pnl_amount"] is None and acc["position_pct"] is None
    assert acc["total_asset"] is None
    assert acc["total_cost"] == 10000.0


def test_account_summary_empty_holdings(monkeypatch):
    """无持仓：总资产 = TOTAL_CAPITAL，仓位 0%，无盈亏（不拉行情）"""
    _mock_account(monkeypatch, holdings=[], spot=None)
    acc = holding_view.build_account_summary()
    assert acc["source"] == "estimate"
    assert acc["total_asset"] == 100000.0
    assert acc["market_value"] == 0.0
    assert acc["position_pct"] == 0.0
    assert acc["pnl_amount"] == 0.0
    assert acc["available_cash"] == 100000.0
