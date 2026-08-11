"""每日候选池 v2.0 补强测试：
市况档位映射 / v2 输出 Schema 校验 / 增量数据纯数学计算 / 富化表结构 / 市况落库闭环
（不触网、不测任何主观结论；LLM 层只测结构校验）"""
import pandas as pd
import pytest
from pydantic import ValidationError

from app.agents.discover import (_enrich_candidate_data, _final_table_text,
                                 _fmt_money, _market_note)
from app.agents.schemas import DiscoverCandidate, MarketConditionOutput
from app.core.config import market_band_info
from app.db import repo
from app.db.session import init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


# ==================== 市况档位映射（人工映射表，纯规则） ====================

def test_market_band_info_boundaries():
    assert market_band_info(0) == (5, "防御期")
    assert market_band_info(20) == (5, "防御期")
    assert market_band_info(21) == (10, "过渡期")
    assert market_band_info(35) == (10, "过渡期")
    assert market_band_info(36) == (15, "温和期")
    assert market_band_info(45) == (15, "温和期")
    assert market_band_info(46) == (20, "强势期")
    assert market_band_info(50) == (20, "强势期")
    assert market_band_info(999) == (20, "强势期")  # 越界兜底取最末档


# ==================== v2.0 输出 Schema（强制字段） ====================

def _valid_candidate() -> dict:
    return {
        "stock_code": "600519", "stock_name": "贵州茅台", "reason": "量价健康",
        "risk_notice": "估值偏高",
        "stock_type": "吸筹末期-优选型",
        "confidence_tier": "建议关注", "confidence_pct": 72.0,
        # v3.0 白盒维度归因（主结论）
        "dimensions": [
            {"dim": "基本面", "score": 72, "verdict": "支持", "advice": "估值合理"},
            {"dim": "技术趋势", "score": 65, "verdict": "中性", "advice": "量能不足"},
            {"dim": "资金/游资", "score": 60, "verdict": "中性", "advice": "无游资数据"},
            {"dim": "舆情/风险", "score": 75, "verdict": "支持", "advice": "无利空"},
            {"dim": "行业景气", "score": 70, "verdict": "支持", "advice": "板块向好"},
        ],
        "final_advice": "综合评估：3/5 维支持，可低吸建仓，止损-8%，主要风险…",
        "macro_view": "宏观判断", "meso_view": "中观判断", "micro_view": "微观判断",
        "volume_analysis": "主力小幅流入", "risks": ["风险A", "风险B"],
        "focus_type": "低吸",
    }


def test_discover_candidate_v2_valid():
    c = DiscoverCandidate(**_valid_candidate())
    assert c.confidence_tier in ("谨慎观察", "建议关注", "强烈推荐")
    assert c.focus_type in ("低吸", "突破", "观察")


def test_discover_candidate_dimensions_parsed():
    """v3.0：dimensions 数组正确解析（dim/score/verdict/advice），final_advice 原文保留"""
    c = DiscoverCandidate(**_valid_candidate())
    assert len(c.dimensions) == 5
    dims = {d.dim: d for d in c.dimensions}
    assert set(dims) == {"基本面", "技术趋势", "资金/游资", "舆情/风险", "行业景气"}
    assert dims["基本面"].score == 72 and dims["基本面"].verdict == "支持"
    assert dims["资金/游资"].advice == "无游资数据"
    assert c.final_advice.startswith("综合评估：3/5 维支持")


def test_discover_candidate_dimensions_default_empty():
    """兼容：旧 LLM 输出（无 dimensions/final_advice）解析为默认值，不抛错"""
    data = _valid_candidate()
    del data["dimensions"], data["final_advice"]
    c = DiscoverCandidate(**data)
    assert c.dimensions == [] and c.final_advice == ""


def test_discover_candidate_requires_two_risks():
    data = _valid_candidate()
    data["risks"] = ["仅一个风险"]
    with pytest.raises(ValidationError):
        DiscoverCandidate(**data)


def test_discover_candidate_rejects_bad_enums():
    data = _valid_candidate()
    data["confidence_tier"] = "强烈看多"
    with pytest.raises(ValidationError):
        DiscoverCandidate(**data)
    data = _valid_candidate()
    data["focus_type"] = "追高"
    with pytest.raises(ValidationError):
        DiscoverCandidate(**data)


def test_market_condition_output_validation():
    out = MarketConditionOutput(dim_index=6, dim_sector=5, dim_money=4,
                                dim_sentiment=6, dim_risk=7, summary="温和")
    assert out.dim_index + out.dim_risk <= 20
    with pytest.raises(ValidationError):
        MarketConditionOutput(dim_index=11, dim_sector=5, dim_money=4,
                              dim_sentiment=6, dim_risk=7, summary="超界")


# ==================== 金额格式化（纯展示） ====================

def test_fmt_money():
    assert _fmt_money(120000000.0) == "1.20亿"
    assert _fmt_money(-50000000.0) == "-5000.0万"
    assert _fmt_money(20000000.0) == "2000.0万"
    assert _fmt_money(5000.0) == "5000"
    assert _fmt_money(None) == ""
    assert _fmt_money(float("nan")) == ""


# ==================== 增量数据纯数学计算（v2.0 富化） ====================

class _FakeSource:
    """模拟数据源：只返回固定原始数据，验证计算正确性"""

    def __init__(self, kline, flow, info=None, gdhs=None):
        self._kline = kline
        self._flow = flow
        self._info = info
        self._gdhs = gdhs

    def fetch_stock_info(self, code):
        return self._info if self._info is not None else {"行业": "白酒"}

    def fetch_daily_kline(self, code, start_date, end_date, adjust="qfq"):
        return self._kline

    def fetch_fund_flow(self, code):
        return self._flow

    def fetch_shareholder_detail(self, code):
        return self._gdhs if self._gdhs is not None else {"holder_change_pct": -3.2}


def _make_kline():
    """8 个交易日：收盘 10→12，高点 12.3，用于验证 5日涨幅/52周区间/收窄幅度"""
    dates = pd.date_range("2026-07-24", periods=8).strftime("%Y-%m-%d")
    return pd.DataFrame({
        "date": dates,
        "close": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 11.0, 12.0],
        "high": [10.2, 10.2, 10.2, 10.2, 10.2, 10.2, 11.2, 12.3],
        "low": [9.8] * 8,
    })


def _make_flow():
    """10 日资金流：主力累计 3/5/10 日可精确验证"""
    dates = pd.date_range("2026-07-20", periods=10).strftime("%Y-%m-%d")
    mains = [1e7, 2e7, 3e7, 4e7, 5e7, 6e7, 7e7, 8e7, 9e7, -5e7]
    return pd.DataFrame({
        "date": dates,
        "main_net_inflow": mains,
        "super_large_net": [-5e7] * 10,
        "large_net": [2e7] * 10,
        "medium_net": [-1e7] * 10,
        "small_net": [-1e7] * 10,
    })


def test_enrich_candidate_data_pure_math():
    source = _FakeSource(_make_kline(), _make_flow())
    out = _enrich_candidate_data(source, {"600519": {"float_pct": 12.5}},
                                 "600519", "贵州茅台", "2026-07-29")

    assert out["industry"] == "白酒"
    # 5日涨幅 = (12.0/10.0-1)*100
    assert out["pct_change_5d"] == pytest.approx(20.0)
    # 52周区间与距高点
    assert out["high_52w"] == 12.3
    assert out["low_52w"] == 9.8
    assert out["dist_52w_high_pct"] == pytest.approx(-2.44)
    # 盘中涨幅收窄 = (当日最高-收盘)/昨收*100
    assert out["intraday_narrow_pct"] == pytest.approx((12.3 - 12.0) / 11.0 * 100, abs=0.01)
    # 资金结构（当日）
    assert out["super_large_net"] == -5e7
    assert out["large_net"] == 2e7
    # 阶段主力累计：3/5/10 日（尾部 3/5/10 行求和）
    assert out["main_net_3d"] == 1.2e8       # 8e7+9e7-5e7
    assert out["main_net_5d"] == 2.5e8       # 6e7+7e7+8e7+9e7-5e7
    assert out["main_net_10d"] == 4.0e8      # 全部 10 日求和
    # 股东面与机构持股
    assert out["holder_change_pct"] == -3.2
    assert out["inst_hold_pct"] == 12.5


def test_enrich_candidate_data_missing_fields():
    """数据缺失时字段为 None/空，不抛异常（单项失败降级）"""
    source = _FakeSource(pd.DataFrame(), pd.DataFrame(), info={}, gdhs={})
    out = _enrich_candidate_data(source, {}, "600519", "贵州茅台", "2026-07-29")
    assert out == {"industry": ""}


def test_enrich_fund_flow_strict_same_day_no_fallback():
    """严格当日有效：当日资金流全空 → 不再回退 T-1，资金字段一律缺失（读取层标「当日不可用」）"""
    dates = ["2026-08-08", "2026-08-09", "2026-08-11"]
    flow = pd.DataFrame({
        "date": dates,
        "main_net_inflow": [1e8, 2e8, float("nan")],
        "super_large_net": [1e7, 2e7, float("nan")],
        "large_net": [5e6, 6e6, float("nan")],
        "medium_net": [3e6, 4e6, float("nan")],
        "small_net": [-2e6, -1e6, float("nan")],
    })
    source = _FakeSource(pd.DataFrame(), flow, info={}, gdhs={})
    out = _enrich_candidate_data(source, {}, "600519", "贵州茅台", "2026-08-11")
    # 当日(08-11)全空 → 不得回退取 08-08/08-09 的历史值
    assert out.get("super_large_net") is None
    assert out.get("large_net") is None
    assert out.get("main_net_3d") is None       # 不得用历史 1e8+2e8 求和冒充当日累计


def test_enrich_fund_flow_same_day_only():
    """仅当日有效：资金流含多日时只取 trade_date 当日行，累计窗口以当日为锚点"""
    dates = ["2026-08-07", "2026-08-08", "2026-08-11"]
    flow = pd.DataFrame({
        "date": dates,
        "main_net_inflow": [1e8, 2e8, 3e8],
        "super_large_net": [1e7, 2e7, 4e7],
        "large_net": [5e6, 6e6, 8e6],
        "medium_net": [3e6, 4e6, 5e6],
        "small_net": [-2e6, -1e6, 3e6],
    })
    source = _FakeSource(pd.DataFrame(), flow, info={}, gdhs={})
    out = _enrich_candidate_data(source, {}, "600519", "贵州茅台", "2026-08-11")
    assert out["super_large_net"] == 4e7       # 当日 08-11，非 08-08 的 2e7
    assert out["large_net"] == 8e6
    # 累计窗口以当日为锚点：tail 3 = 1e8+2e8+3e8（仅 3 日有效数据）
    assert out["main_net_3d"] == 6e8
    assert out["main_net_5d"] == 6e8
    assert out["main_net_10d"] == 6e8


def test_enrich_fund_flow_missing_trade_date_no_data():
    """严格当日有效：资金流里没有 trade_date 当日 → 不取最新历史行，资金字段缺失"""
    dates = ["2026-07-20", "2026-07-21", "2026-07-22"]
    flow = pd.DataFrame({
        "date": dates,
        "main_net_inflow": [1e8, 2e8, 3e8],
        "super_large_net": [1e7, 2e7, 3e7],
        "large_net": [5e6, 6e6, 7e6],
    })
    source = _FakeSource(pd.DataFrame(), flow, info={}, gdhs={})
    out = _enrich_candidate_data(source, {}, "600519", "贵州茅台", "2026-07-31")
    assert out.get("super_large_net") is None
    assert out.get("large_net") is None
    assert out.get("main_net_3d") is None


def test_enrich_fund_flow_all_nan_no_crash():
    """资金流全行为空 → 字段为 None，不抛异常"""
    flow = pd.DataFrame({
        "date": ["2026-08-11"],
        "main_net_inflow": [float("nan")],
        "super_large_net": [float("nan")],
        "large_net": [float("nan")],
        "medium_net": [float("nan")],
        "small_net": [float("nan")],
    })
    source = _FakeSource(pd.DataFrame(), flow, info={}, gdhs={})
    out = _enrich_candidate_data(source, {}, "600519", "贵州茅台", "2026-08-11")
    assert out.get("super_large_net") is None
    assert out.get("main_net_3d") is None


def test_final_table_text_includes_v2_columns():
    shortlist = [{"code": "600519", "name": "贵州茅台", "price": 1500.0, "change_pct": 1.2,
                  "amount": 5e8, "volume_ratio": 1.5, "turnover_rate": 2.0,
                  "pe_dynamic": 30.0, "pb": 8.0, "total_mv": 1.8e12, "circ_mv": 1.8e12,
                  "pct_change_60d": 8.0, "pct_change_ytd": 5.0}]
    enrichment = {"600519": {"industry": "白酒", "pct_change_5d": 20.0,
                             "dist_52w_high_pct": -2.44, "intraday_narrow_pct": 2.73,
                             "super_large_net": -5e7, "large_net": 2e7,
                             "main_net_3d": 1.2e8, "main_net_5d": 3e8,
                             "holder_change_pct": -3.2, "inst_hold_pct": 12.5}}
    text = _final_table_text(shortlist, enrichment)
    lines = text.splitlines()
    header = lines[0]
    assert "industry" in header and "pct_change_5d" in header
    assert "dist_52w_high_pct" in header and "intraday_narrow_pct" in header
    assert "main_net_3d" in header and "inst_hold_pct" in header
    body = lines[1]
    assert "白酒" in body and "-5000.0万" in body and "1.20亿" in body
    assert "600519" in body


# ==================== 市况摘要注入文本 ====================

def test_market_note_text():
    state = {"market_condition": {"total_score": 42, "band": "温和期", "cap": 15,
                                  "summary": "板块轮动正常"}, "market_cap": 15}
    note = _market_note(state)
    assert "42" in note and "温和期" in note and "15" in note
    state2 = {"market_condition": None, "market_cap": 20}
    assert "默认上限 20" in _market_note(state2)


# ==================== 市况落库闭环 ====================

def test_market_condition_upsert_and_read():
    repo.upsert_market_condition("2026-08-04", 42,
                                 {"index": 9, "sector": 8, "money": 8,
                                  "sentiment": 9, "risk": 8}, 15, "板块轮动正常")
    mc = repo.get_latest_market_condition()
    assert mc is not None
    assert mc["total_score"] == 42
    assert mc["band"] == "温和期"
    assert mc["cap"] == 15
    assert mc["dims"]["money"] == 8
    # created_at 为真实落库时间（当前日期），只校验格式不依赖具体运行日
    assert len(mc["created_at"]) >= 16 and mc["created_at"][:10].count("-") == 2

    repo.upsert_market_condition("2026-08-04", 10, {"index": 2, "sector": 2, "money": 2,
                                                    "sentiment": 2, "risk": 2}, 5, "弱势")
    mc2 = repo.get_latest_market_condition()
    assert mc2["total_score"] == 10 and mc2["cap"] == 5 and mc2["band"] == "防御期"


# ==================== 硬性规则注入（HARD_RULES 已生效） ====================

def test_hard_rules_contains_v2_rules():
    from app.agents.common import HARD_RULES

    joined = "\n".join(HARD_RULES)
    for keyword in ("板块权限硬约束", "派发期一票否决", "一日游避雷", "超买否决",
                    "科创板", "北交所", "52周高点", "换手率"):
        assert keyword in joined, f"HARD_RULES 缺少: {keyword}"
