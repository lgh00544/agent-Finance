"""子任务A·第二数据源收口：多源采信 + 诚实标注（K227 不伪造第二源数据）

覆盖：
1. second_source_status() 诚实标注（当前仅东财可用、采信待第二源；零网络调用）；
2. 两源相近 → confidence 0.9 采信（净买取均值）；单源 → 0.5 置信度不足降级；
3. 单源聚合注入时如实标注"当前仅东财可用、采信待第二源"（aggregate/second_source 字段 +
   注入文本风险提示 + 留痕 final_conclusion）；
4. DRAGON_TIGER_SECOND_SOURCE 开关：none 时跳过第二源（新浪），auto 时聚合上榜确认行。
"""
import pandas as pd
import pytest

from app.core.config import settings
from app.datasource import dragon_tiger_source as dts
from app.db import repo
from app.db.session import init_db
from app.services import hot_money as hm


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    repo.seed_default_hot_money_profiles()


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setattr(settings, "dragon_tiger_enable", True)


# ================= 1. 第二源现状诚实标注 =================

def test_second_source_status_honest():
    """第二源现状如实标注：当前仅东财可用、采信待第二源（不伪造第二源数据，K227）"""
    ss = dts.second_source_status()
    assert ss["available"] is False
    assert ss["main_source"] == "eastmoney"
    assert "仅东财可用" in ss["annotation"] and "采信待第二源" in ss["annotation"]
    # 候选源逐条说明原因（同花顺需 JS token / 新浪无金额明细）
    assert "ths" in ss["candidates"] and "sina" in ss["candidates"]
    assert "hexin-v" in ss["candidates"]["ths"]
    assert "无金额" in ss["candidates"]["sina"]


def test_second_source_hint_text():
    """hot_money 服务层 hint：与数据源层标注一致"""
    assert "采信待第二源" in hm.second_source_hint()


# ================= 2. 多源采信 / 单源降级 =================

def _seed(trade_date, code, name, seats_sources):
    repo.insert_lhb_flows([
        {"trade_date": trade_date, "stock_code": code, "stock_name": name,
         "lhb_type": "1d", "disclosure_reason": "日涨幅偏离值达7%",
         "seat_name": seat, "buy_amt": abs(net) + 1e6, "sell_amt": max(0.0, -net),
         "net_buy": net, "confidence": 0.8, "source": src}
        for seat, net, src in seats_sources
    ])


def test_two_sources_close_verified_confidence_09():
    """两源相近（差值<10%）→ 采信：confidence 0.9，净买取均值"""
    _seed("2026-08-11", "600001", "采信股", [
        ("", 1.0e8, "eastmoney"), ("", 1.02e8, "sina"),  # 差值约 2%
    ])
    v = hm.verify_net_buy("2026-08-11", "600001", "1d")
    assert v["verified"] is True
    assert v["confidence"] == 0.9
    assert v["net_buy"] == pytest.approx(1.01e8, rel=0.01)


def test_single_source_degrades_with_honest_annotation():
    """单源 → 降级：confidence 0.5 仅参考；aggregate 如实标注第二源现状"""
    _seed("2026-08-11", "600002", "单源股", [("", 5e7, "eastmoney")])
    agg = hm.aggregate_for_stock("600002", "单源股", "2026-08-11")
    assert agg is not None
    assert agg["confidence"] == 0.5 and agg["multi_source_verified"] is False
    assert agg["note"] == "数据置信度不足（多源校验未通过或单源），仅参考"
    assert "采信待第二源" in (agg.get("second_source") or "")


def test_t1_fallback_to_latest_lhb_date():
    """T+1 注入打通：目标日期无流水时回退到 ≤ 目标日期的最近龙虎榜交易日（数据按交易日落库）"""
    _seed("2026-08-16", "600010", "T1回退股", [
        ("中信证券上海分公司", 4e7, "eastmoney"),
        ("", 4.2e7, "sina"),  # 双源近似 → 采信
    ])
    # 评分当日（2026-08-17）尚无当日龙虎榜 → 自动回退 2026-08-16 数据并采信
    agg = hm.aggregate_for_stock("600010", "T1回退股", "2026-08-17")
    assert agg is not None
    assert agg["lhb_date"] == "2026-08-16"
    assert agg["multi_source_verified"] is True
    assert agg["lhb_1d_net_buy"] == pytest.approx(4.1e7, rel=0.02)
    # 注入文本标注实际龙虎榜日期（LLM 不误读为当日数据）
    ctx = hm.build_hot_money_context({"600010": agg}, "2026-08-17")
    assert "龙虎榜 2026-08-16" in ctx
    # 无任何历史数据仍返回 None（不伪造）
    assert hm.aggregate_for_stock("999999", "无数据股", "2026-08-17") is None


def test_two_sources_verified_no_annotation():
    """两源采信 → 不再标注第二源现状（标注仅用于置信度不足场景）"""
    _seed("2026-08-11", "600003", "采信股B", [
        ("", 1.0e8, "eastmoney"), ("", 1.01e8, "sina"),
    ])
    agg = hm.aggregate_for_stock("600003", "采信股B", "2026-08-11")
    assert agg["multi_source_verified"] is True
    assert not agg.get("second_source")


def test_context_risk_includes_honest_annotation():
    """注入文本：单源标的风险提示含"仅东财可用、采信待第二源"（LLM 可见，如实标注）"""
    _seed("2026-08-11", "600004", "标注股", [("中信证券上海分公司", 2e7, "eastmoney")])
    agg = hm.aggregate_for_stock("600004", "标注股", "2026-08-11")
    ctx = hm.build_hot_money_context({"600004": agg}, "2026-08-11")
    assert "采信待第二源" in ctx
    assert "置信度不足" in ctx


# ================= 3. 第二源开关（DRAGON_TIGER_SECOND_SOURCE） =================

class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_EM_PAYLOAD = {"result": {"data": [
    {"SECURITY_CODE": "601138", "SECURITY_NAME_ABBR": "工业富联",
     "TRADE_DATE": "2026-08-12 00:00:00", "EXPLANATION": "日涨幅偏离值达7%",
     "BILLBOARD_NET_AMT": 4e7, "BILLBOARD_BUY_AMT": 5e7, "BILLBOARD_SELL_AMT": 1e7},
]}}
_EM_SEATS_PAYLOAD = {"result": {"data": [
    {"SECURITY_CODE": "601138", "OPERATEDEPT_NAME": "中信证券股份有限公司上海分公司",
     "BUY": 3e7, "SELL": 1e7, "NET": 2e7},
]}}


@pytest.fixture(autouse=True)
def _fake_http(monkeypatch):
    def _fake_get(url, referer=None, params=None, timeout=None, **kw):
        report = (params or {}).get("reportName")
        if report == dts._EM_STOCKS_REPORT:
            return _FakeResp(_EM_PAYLOAD)
        if report == dts._EM_BUY_REPORT:
            return _FakeResp(_EM_SEATS_PAYLOAD)
        return _FakeResp({"result": {"data": []}})

    monkeypatch.setattr(dts, "http_get", _fake_get)


class _FakeAk:
    """假 akshare：新浪每日明细（上榜原因确认行）"""

    def stock_lhb_detail_daily_sina(self, date=None):
        return pd.DataFrame([
            {"股票代码": "601138", "股票名称": "工业富联", "指标": "日涨幅偏离值达7%"},
        ])


def test_second_source_switch_auto_aggregates_sina(monkeypatch):
    """auto：聚合东财 + 新浪上榜确认（股票级两行）"""
    monkeypatch.setattr(dts, "ak", _FakeAk())
    monkeypatch.setattr(settings, "dragon_tiger_second_source", "auto")
    seats, stocks = dts.DragonTigerSource().fetch_and_merge("2026-08-12")
    assert not seats.empty
    sources = sorted(stocks["source"].unique())
    assert sources == ["eastmoney", "sina"]
    # 新浪行无金额明细（上榜确认），多源校验不采信 → 保持置信度不足降级
    sina_row = stocks[stocks["source"] == "sina"].iloc[0]
    assert sina_row["stock_code"] == "601138"
    assert "net_buy" not in sina_row or pd.isna(sina_row.get("net_buy")) \
        or sina_row.get("net_buy") in (0.0, None)


def test_second_source_switch_none_skips_sina(monkeypatch):
    """none：明确只用东财单源（新浪不上榜确认，无第二源聚合）"""
    monkeypatch.setattr(dts, "ak", _FakeAk())
    monkeypatch.setattr(settings, "dragon_tiger_second_source", "none")
    seats, stocks = dts.DragonTigerSource().fetch_and_merge("2026-08-12")
    assert not stocks.empty
    assert sorted(stocks["source"].unique()) == ["eastmoney"]
