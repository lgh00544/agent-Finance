"""游资数据链·步骤三：多源校验 + 聚合服务 + 注入文本（不触网）"""
import pytest

from app.core.config import settings
from app.db import repo
from app.db.session import init_db
from app.services import hot_money as hm


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    repo.seed_default_hot_money_profiles()


def _seed_flows(trade_date, code, name, seats_sources):
    """seats_sources: [(seat, net, source), ...] → 写入席位级流水"""
    repo.insert_lhb_flows([
        {"trade_date": trade_date, "stock_code": code, "stock_name": name,
         "lhb_type": "1d", "disclosure_reason": "日涨幅偏离值达7%",
         "seat_name": seat, "buy_amt": abs(net) + 1e6, "sell_amt": max(0.0, -net),
         "net_buy": net, "confidence": 0.8, "source": src}
        for seat, net, src in seats_sources
    ])


def test_verify_two_sources_consistent():
    """≥2 源且差值<10% → 采信（confidence 0.9），净买取均值"""
    _seed_flows("2026-08-05", "600001", "验证股A", [
        ("", 1.0e8, "eastmoney"), ("", 1.02e8, "sina"),  # 差值约 2% < 10%
    ])
    v = hm.verify_net_buy("2026-08-05", "600001", "1d")
    assert v["verified"] is True
    assert v["confidence"] == 0.9
    assert v["net_buy"] == pytest.approx(1.01e8, rel=0.01)  # 均值


def test_verify_single_source_weak():
    """单源 → 不采信：confidence 0.5 + verified False（数据置信度不足）"""
    _seed_flows("2026-08-05", "600002", "验证股B", [("席位1", 5e7, "eastmoney")])
    v = hm.verify_net_buy("2026-08-05", "600002", "1d")
    assert v["verified"] is False and v["confidence"] == 0.5 and v["net_buy"] is None


def test_verify_two_sources_divergent():
    """≥2 源但差值≥10% → 不采信：置信度不足（硬规则：差值超阈值不纳入核心评分）"""
    _seed_flows("2026-08-05", "600003", "验证股C", [
        ("", 1.0e8, "eastmoney"), ("", 1.5e8, "sina"),
    ])
    v = hm.verify_net_buy("2026-08-05", "600003", "1d")
    assert v["verified"] is False and v["confidence"] == 0.5


def test_aggregate_suffix_fields_and_actor():
    """aggregate_for_stock：口径后缀字段（lhb_1d_net_buy/lhb_3d_net_buy）+ 游资映射"""
    repo.insert_lhb_flows([
        # 1d 双源采信（东财席位 + 新浪股票级）
        {"trade_date": "2026-08-06", "stock_code": "601138", "stock_name": "工业富联",
         "lhb_type": "1d", "seat_name": "中信证券上海分公司",
         "buy_amt": 5e7, "sell_amt": 1e7, "net_buy": 4e7, "confidence": 0.8, "source": "eastmoney"},
        {"trade_date": "2026-08-06", "stock_code": "601138", "stock_name": "工业富联",
         "lhb_type": "1d", "seat_name": "", "buy_amt": 4.2e7, "sell_amt": 0,
         "net_buy": 4.2e7, "confidence": 0.8, "source": "sina"},
    ])
    agg = hm.aggregate_for_stock("601138", "工业富联", "2026-08-06")
    assert agg is not None
    assert agg["lhb_1d_net_buy"] is not None and agg["lhb_1d_net_buy"] > 0  # 采信均值
    assert agg["lhb_3d_net_buy"] is None  # 无 3d 数据
    assert agg["actor"] == "赵老哥" and agg["tier"] == "一线"  # 席位映射命中种子
    assert agg["multi_source_verified"] is True


def test_aggregate_no_data_returns_none():
    """无龙虎榜数据 → None（LLM 保持"无游资席位数据标中性"）"""
    assert hm.aggregate_for_stock("999999", "无数据股", "2026-08-06") is None


def test_build_context_four_layers():
    """注入文本段：四层结构（核心结论/事实数据/风险提示）+ 口径后缀 + 置信度标注"""
    repo.insert_lhb_flows([
        {"trade_date": "2026-08-06", "stock_code": "600519", "stock_name": "贵州茅台",
         "lhb_type": "1d", "seat_name": "中信证券杭州延安路",
         "buy_amt": 3e7, "sell_amt": 1e7, "net_buy": 2e7, "confidence": 0.8, "source": "eastmoney"},
        {"trade_date": "2026-08-06", "stock_code": "600519", "stock_name": "贵州茅台",
         "lhb_type": "1d", "seat_name": "", "buy_amt": 2.1e7, "sell_amt": 0,
         "net_buy": 2.1e7, "confidence": 0.8, "source": "sina"},
    ])
    agg = hm.aggregate_for_stock("600519", "贵州茅台", "2026-08-06")
    ctx = hm.build_hot_money_context({"600519": agg}, "2026-08-06")
    assert "游资聚合" in ctx
    assert "lhb_1d_net_buy" in ctx            # 口径后缀字段
    assert "孙哥" in ctx                      # 席位映射命中（中信杭州延安路）
    assert "置信度" in ctx and "多源验证" in ctx
    assert "平行维度补充加权" in ctx           # 平行维度声明


def test_build_context_empty():
    """无数据 → 空串（不注入，LLM 保持标中性）"""
    assert hm.build_hot_money_context({}, "2026-08-06") == ""
    assert hm.build_hot_money_context({"600001": None}, "2026-08-06") == ""


def test_weak_note_when_not_verified():
    """单源（置信度不足）→ note 标注"数据置信度不足"，不纳入核心评分"""
    repo.insert_lhb_flows([
        {"trade_date": "2026-08-06", "stock_code": "600888", "stock_name": "弱置信股",
         "lhb_type": "1d", "seat_name": "中信证券上海分公司",
         "buy_amt": 2e7, "sell_amt": 0, "net_buy": 2e7, "confidence": 0.8, "source": "eastmoney"},
    ])
    agg = hm.aggregate_for_stock("600888", "弱置信股", "2026-08-06")
    assert agg["note"] == "数据置信度不足（多源校验未通过或单源），仅参考"
    assert agg["confidence"] == 0.5
