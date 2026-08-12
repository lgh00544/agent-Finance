"""市场研判底座（Market Intel）测试：
1. classify_board_groups 避险/进取归类（关键词分组 + 客观聚合 + 空表/缺列标注）
2. raw_to_text 缺失字段明确标注（不编造）
3. repo upsert/get/list 幂等读写
4. market_intel_node：mock agent_call 验证落库字段齐全 + 失败降级不抛断
5. collect_market_data：数据段独立容错（单段失败不影响整体）
"""
import pandas as pd
import pytest
from sqlalchemy import delete

from app.db import repo
from app.db.models import MarketIntel
from app.db.session import SessionLocal, init_db

DATE = "2026-08-12"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(delete(MarketIntel))
        db.commit()


# ==================== 1. classify_board_groups ====================

def test_classify_groups_basic():
    from app.datasource.akshare_source import classify_board_groups

    board = pd.DataFrame({
        "board_name": ["房地产开发", "白酒", "通信设备", "半导体", "银行", "未知板块"],
        "change_pct": [2.1, 1.5, -0.8, 1.2, 0.3, 0.5],
        "volume_ratio": [2.1, 0.9, 1.5, 1.8, 0.7, 1.0],
    })
    r = classify_board_groups(board)
    assert any("房地产" in x for x in r["defensive"])
    assert "白酒" in r["defensive"] and "银行" in r["defensive"]
    assert "通信设备" in r["aggressive"] and "半导体" in r["aggressive"]
    assert "未知板块" in r["unclassified"]
    assert r["stats"]["defensive"]["count"] == 3
    assert r["stats"]["aggressive"]["avg_volume_ratio"] == 1.65
    assert r["stats"]["defensive"]["avg_change_pct"] == 1.3


def test_classify_groups_missing_data_noted():
    """空表/缺列：如实标注缺失，不编造"""
    from app.datasource.akshare_source import classify_board_groups

    assert classify_board_groups(None)["stats"]["defensive"] is None
    r = classify_board_groups(pd.DataFrame())  # 空表
    assert r["stats"]["note"]
    board = pd.DataFrame({"board_name": ["白酒", "半导体"], "change_pct": [1.0, -0.5]})  # 无量比列
    r2 = classify_board_groups(board)
    assert r2["stats"]["defensive"]["avg_volume_ratio"] is None  # 缺列 → None 不编造
    assert r2["stats"]["aggressive"]["avg_volume_ratio"] is None


# ==================== 2. raw_to_text 缺失标注 ====================

def test_raw_to_text_marks_missing():
    from app.agents.market_intel import raw_to_text

    raw = {"trade_date": DATE, "data_source": "akshare",
           "index_recent_5d": "（数据缺失）",
           "index_volume_ratios": "（数据缺失）",
           "board_structure": "（数据缺失）",
           "board_volume_ratio_available": False,
           "risk_groups": {"defensive": [], "aggressive": [], "unclassified": [],
                           "stats": {"defensive": None, "aggressive": None,
                                     "note": "归类数据缺失"}}}
    text = raw_to_text(raw)
    assert "数据缺失" in text
    assert "不编造" in text
    assert "（无/数据缺失）" in text


def test_raw_to_text_normal_payload():
    from app.agents.market_intel import raw_to_text

    raw = {
        "trade_date": DATE, "data_source": "akshare",
        "index_close": 3946.6, "index_pos_60d": "45%",
        "index_recent_5d": [{"date": DATE, "close": 3946.6}],
        "index_volume_ratios": [{"date": DATE, "volume_ratio": 0.89, "close": 3946.6}],
        "board_structure": "共 80 个板块，上涨 45 / 下跌 35",
        "board_volume_ratio_available": True,
        "board_top": [{"board_name": "白酒", "change_pct": 2.1}],
        "risk_groups": {"defensive": ["白酒"], "aggressive": ["半导体"], "unclassified": [],
                        "stats": {"defensive": {"count": 1}, "aggressive": {"count": 1}}},
        "market_advance_decline": {"up": 3000, "down": 2000, "flat": 100},
    }
    text = raw_to_text(raw)
    assert "0.89" in text
    assert "上涨 45 / 下跌 35" in text
    assert "避险池板块" in text and "进取池板块" in text


# ==================== 3. repo 幂等读写 ====================

def test_repo_upsert_get_list():
    repo.upsert_market_intel(DATE, "存量博弈", "增量资金不足", "避险",
                             {"放量板块": ["地产"]}, {"精选": "防御"}, {"观察点1": "量比回升"},
                             "存量博弈，风险偏好避险", {"trade_date": DATE, "raw": 1})
    row = repo.get_market_intel(DATE)
    assert row is not None
    assert row["phase"] == "存量博弈" and row["risk_appetite"] == "避险"
    assert row["volume_signal"]["放量板块"] == ["地产"]
    assert row["summary"] and row["raw"]["raw"] == 1
    # 幂等覆盖：再写一次同日期
    repo.upsert_market_intel(DATE, "主升", "增量进场", "进取", {}, {}, {}, "新总结", {})
    row2 = repo.get_market_intel(DATE)
    assert row2["phase"] == "主升" and row2["summary"] == "新总结"
    # 日期列表
    assert DATE in repo.list_market_intel_dates()
    # 最新一日
    assert repo.get_latest_market_intel()["trade_date"] == DATE
    # 不存在日期
    assert repo.get_market_intel("2099-01-01") is None


# ==================== 4. market_intel_node ====================

def test_market_intel_node_persists(monkeypatch):
    """mock agent_call：LLM 输出 → 落库字段齐全"""
    from app.agents import market_intel as mi

    class _Out:
        phase = "存量博弈"
        core_conflict = "增量资金不足，量比持续走低"
        risk_appetite = "避险"
        volume_signal = {"放量板块": ["地产"], "缩量板块": ["半导体"]}
        operative_meaning = {"精选方向": "防御", "回避方向": "追高"}
        next_day_watch = {"观察点1": "量比回升"}
        summary = "存量博弈，风险偏好避险，明日观察量能"

    monkeypatch.setattr(mi, "agent_call", lambda **kw: _Out())
    monkeypatch.setattr(mi, "collect_market_data",
                        lambda: {"trade_date": DATE, "data_source": "test",
                                 "board_structure": "（数据缺失）"})
    state = mi.market_intel_node({"trade_date": DATE})
    assert "error" not in state or not state["error"]
    assert state["market_intel"]["phase"] == "存量博弈"
    row = repo.get_market_intel(DATE)
    assert row["core_conflict"] == "增量资金不足，量比持续走低"
    assert row["risk_appetite"] == "避险"
    assert row["raw"]["data_source"] == "test"  # 原始数据可追溯


def test_market_intel_node_failure_degrades(monkeypatch):
    """LLM 调用失败：仅标注 error，不抛断"""
    from app.agents import market_intel as mi

    def _boom(**kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr(mi, "agent_call", _boom)
    state = mi.market_intel_node({"trade_date": DATE})
    assert "市场研判失败" in (state.get("error") or "")
    assert repo.get_market_intel(DATE) is None  # 不落脏数据


# ==================== 5. collect_market_data 单段容错 ====================

def test_collect_market_data_section_isolation(monkeypatch):
    """单数据段失败不影响整体：其余段照常聚合，缺失段标注"""
    from app.agents import market_intel as mi

    class _FakeSource:
        def fetch_index_daily(self, *a, **k):
            raise ConnectionError("index down")

        def fetch_index_volume_ratios(self, days=6):
            return pd.DataFrame({"date": [DATE], "volume_ratio": [0.9], "close": [3946.6]})

        def fetch_industry_spot(self):
            raise ConnectionError("board down")

        def fetch_spot_universe(self):
            return pd.DataFrame({"change_pct": [1.0, -0.5]})

    monkeypatch.setattr(mi, "get_datasource", lambda: _FakeSource())
    raw = mi.collect_market_data()
    assert raw["index_recent_5d"] == "（数据缺失）"
    assert raw["board_structure"] == "（数据缺失）"
    assert raw["index_volume_ratios"][0]["volume_ratio"] == 0.9  # 正常段不受影响
    assert raw["market_advance_decline"]["up"] == 1
    assert raw["risk_groups"]["stats"]["note"]  # 板块缺失 → 归类如实标注
