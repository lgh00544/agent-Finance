"""市场研判深度化（v3.1）功能测试（dev SQLite，不触网）：
1. MarketIntelOutput 4 新字段带默认值实例化不报错；带新字段值保留；共 11 字段
2. classify_board_groups aggressive 是 list[str]；collect 段7 对字符串 aggressive 不抛异常、正确产出 board_list
3. market_intel_node 落库：有/无新字段两种情况（空值防御，未输出不并入空 key；落库段为替换）
4. common.py 拼接位5 注入：主线结构/量能成色 注入；主线结构 dict/str 类型防御；操作含义 dict 值摘要防 repr
5. common.py 拼接位5.5（批次3选股表现回顾）未被改动（与备份逐字节一致）
"""
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import delete

from app.agents.schemas import MarketIntelOutput
from app.cache import cache
from app.db import repo
from app.db.models import MarketIntel
from app.db.session import SessionLocal, init_db

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_COMMON = Path(r"D:\self\backend\app\agents\common.py")
_COMMON_BAK = Path(r"D:\self\backend\app\agents\common.py.bak_20260817_v31")


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _cleanup():
    """隔离：清空 market_intel 行 + 失效 dbq 缓存 + 选股表现/组合风险缓存键"""
    cache.delete_prefix("dbq:")
    cache.delete("selection:perf_summary:t5")
    cache.delete("portfolio_sentinel:last_risk")
    with SessionLocal() as db:
        db.execute(delete(MarketIntel))
        db.commit()
    yield
    cache.delete_prefix("dbq:")
    cache.delete("selection:perf_summary:t5")
    cache.delete("portfolio_sentinel:last_risk")
    with SessionLocal() as db:
        db.execute(delete(MarketIntel))
        db.commit()


class _FakeIntelSource:
    """覆盖 collect_market_data 全部数据段（段1-9）的假数据源"""
    def __init__(self):
        self.box_boards = None

    def fetch_index_daily(self, code, start, end):
        return pd.DataFrame({"date": ["2026-08-01", "2026-08-04"], "close": [3000.0, 3010.0],
                             "change_pct": [0.5, 0.3]})

    def fetch_index_volume_ratios(self, days=6):
        return pd.DataFrame({"date": ["2026-08-01"], "volume_ratio": [1.1]})

    def fetch_industry_spot(self):
        return pd.DataFrame({"board_name": ["半导体", "医药"], "change_pct": [3.0, -1.0],
                             "volume_ratio": [1.2, 0.9]})

    def fetch_spot_universe(self):
        return pd.DataFrame({"code": ["600001", "600002"], "name": ["甲", "乙"],
                             "change_pct": [2.0, 1.0], "volume_ratio": [1.5, 1.0]})

    def fetch_us_market_overnight(self):
        return {"available": False, "note": "数据缺失"}

    def fetch_board_box_positions(self, board_names):
        self.box_boards = list(board_names)
        return {b: {"main_box_pct": 80.0, "box60_pct": 30.0, "note": ""} for b in board_names}

    def fetch_market_total_volume_ratio(self):
        return {"available": False, "note": "数据缺失"}

    def fetch_industry_cons(self, board_name):
        return pd.DataFrame({"代码": ["600001"]})


def _seed_mi(volume_signal=None, operative_meaning=None, date="2026-08-13"):
    repo.upsert_market_intel(date, "分化", "增量vs存量", "中性",
                             volume_signal or {}, operative_meaning or {}, {}, "summary", {})


# ==================== 1. MarketIntelOutput schema ====================

def test_market_intel_schema_new_fields_defaults():
    """4 新字段带默认值：不传实例化不报错；传值保留"""
    o = MarketIntelOutput(phase="分化", core_conflict="c", risk_appetite="中性",
                          volume_signal={}, operative_meaning={}, next_day_watch={}, summary="s")
    assert o.main_structure == {} and o.box_view == {}
    assert o.volume_character == "" and o.stock_verification == []
    assert len(MarketIntelOutput.model_fields) == 11          # 原7 + 新4


def test_market_intel_schema_new_fields_with_values():
    o = MarketIntelOutput(phase="分化", core_conflict="c", risk_appetite="中性",
                          volume_signal={}, operative_meaning={}, next_day_watch={}, summary="s",
                          main_structure={"进攻主线": "半导体 3日"},
                          box_view={"半导体": {"main_box": 90}},
                          volume_character="量倍1.15温和放大",
                          stock_verification=[{"name": "甲", "verdict": "真强"}])
    assert o.main_structure["进攻主线"] == "半导体 3日"
    assert o.box_view["半导体"]["main_box"] == 90
    assert o.volume_character == "量倍1.15温和放大"
    assert o.stock_verification[0]["name"] == "甲"


# ==================== 2. classify_board_groups + 段7 ====================

def test_classify_board_groups_aggressive_is_list_of_str():
    from app.datasource.akshare_source import classify_board_groups
    board = pd.DataFrame({"board_name": ["半导体", "医药", "白酒", "银行"],
                          "change_pct": [3.0, 1.0, -2.0, -0.5]})
    rg = classify_board_groups(board)
    assert isinstance(rg.get("aggressive"), list)
    assert all(isinstance(b, str) for b in rg.get("aggressive") or [])


def test_market_intel_segment7_handles_string_aggressive(monkeypatch):
    """段7：aggressive 是 list[str]（板块名本身）时拼接不抛异常、正确产出 board_list"""
    from app.agents import market_intel as mi_mod

    src = _FakeIntelSource()
    monkeypatch.setattr(mi_mod, "get_datasource", lambda: src)
    monkeypatch.setattr(mi_mod, "classify_board_groups",
                        lambda board: {"defensive": [], "aggressive": ["半导体", "医药"],
                                       "unclassified": [], "stats": {}})
    raw = mi_mod.collect_market_data()
    assert "board_box_positions" in raw
    assert src.box_boards == ["半导体", "医药"]          # 去重限10，字符串板块名直达
    assert raw["board_box_positions"]["半导体"]["main_box_pct"] == 80.0


# ==================== 3. market_intel_node 落库（替换 + 空值防御） ====================

def _run_node(monkeypatch, output, date="2026-08-13"):
    from app.agents import market_intel as mi_mod

    monkeypatch.setattr(mi_mod, "get_datasource", lambda: _FakeIntelSource())
    monkeypatch.setattr(mi_mod, "classify_board_groups",
                        lambda board: {"defensive": [], "aggressive": [],
                                       "unclassified": [], "stats": {}})
    monkeypatch.setattr(mi_mod, "agent_call", lambda **kw: output)
    state = mi_mod.market_intel_node({"trade_date": date})
    assert "error" not in state or not state["error"]
    return state


def test_market_intel_node_merges_new_fields(monkeypatch):
    """LLM 输出新字段 → 并入 volume_signal/operative_meaning 落库，旧键保留"""
    out = MarketIntelOutput(
        phase="分化", core_conflict="c", risk_appetite="中性",
        volume_signal={"放量板块": "半导体"}, operative_meaning={"精选方向": "半导体"},
        next_day_watch={"w": "x"}, summary="s",
        main_structure={"进攻主线": "半导体 3日"},
        box_view={"半导体": {"main_box": 90, "box60": 40, "interpretation": "主升初期"}},
        volume_character="量倍1.15温和放大",
        stock_verification=[{"name": "甲", "change_pct": 2.0, "verdict": "真强", "basis": "b"}])
    _run_node(monkeypatch, out)
    row = repo.get_market_intel("2026-08-13")
    assert row is not None
    vs, om = row["volume_signal"], row["operative_meaning"]
    assert vs["量能成色"] == "量倍1.15温和放大"
    assert vs["主线结构"]["进攻主线"] == "半导体 3日"
    assert vs["放量板块"] == "半导体"                     # 旧键保留
    assert om["箱位理解"]["半导体"]["main_box"] == 90
    assert om["个股验证"][0]["name"] == "甲"


def test_market_intel_node_no_new_fields_no_empty_keys(monkeypatch):
    """LLM 未输出新字段 → 空值防御：volume_signal/operative_meaning 无空 key，不报错"""
    out = MarketIntelOutput(phase="分化", core_conflict="c", risk_appetite="中性",
                            volume_signal={"放量板块": "半导体"},
                            operative_meaning={"精选方向": "半导体"},
                            next_day_watch={"w": "x"}, summary="s")
    _run_node(monkeypatch, out)
    row = repo.get_market_intel("2026-08-13")
    vs, om = row["volume_signal"], row["operative_meaning"]
    assert vs.get("放量板块") == "半导体"
    assert "量能成色" not in vs and "主线结构" not in vs   # 未输出不并入空 key
    assert "箱位理解" not in om and "个股验证" not in om


# ==================== 4. common.py 拼接位5 注入 ====================

def _capture_agent_call(monkeypatch):
    from app.agents import common
    from app.llm.structured import ModelLevel
    from app.agents.schemas import ScoreOutput

    captured = {}

    def _fake(agent, cache_key, sys_prompt, user_prompt, schema,
              ttl_seconds=86400, model_level=ModelLevel.DEEP):
        captured["prompt"] = user_prompt
        return object()

    monkeypatch.setattr(common, "call_llm_cached", _fake)
    common.agent_call("score", "k", "sys", "user", ScoreOutput)
    return captured["prompt"]


def test_common_inject_main_structure_and_volume_character(monkeypatch):
    """拼接位5：主线结构（dict）+ 量能成色 注入 user_prompt"""
    _seed_mi(volume_signal={"主线结构": {"进攻主线": "半导体 3日"},
                            "量能成色": "量倍1.15温和放大"})
    prompt = _capture_agent_call(monkeypatch)
    assert "主线结构" in prompt
    assert "进攻主线:半导体 3日" in prompt
    assert "量能成色" in prompt


def test_common_inject_type_defense_str_main_structure(monkeypatch):
    """类型防御：主线结构是字符串时不抛异常、原文注入"""
    _seed_mi(volume_signal={"主线结构": "半导体为进攻主线", "量能成色": "量倍1.15"})
    prompt = _capture_agent_call(monkeypatch)
    assert "半导体为进攻主线" in prompt


def test_common_inject_op_brief_no_repr_leak(monkeypatch):
    """操作含义含 dict 值（箱位理解）→ 摘要版（'...'），不拼 Python repr"""
    _seed_mi(operative_meaning={"精选方向": "半导体",
                                "箱位理解": {"半导体": {"main_box": 90}}})
    prompt = _capture_agent_call(monkeypatch)
    assert "箱位理解:..." in prompt
    assert "{'半导体'" not in prompt


# ==================== 5. 拼接位5.5 未被改动 ====================

def test_common_55_block_unchanged():
    """拼接位5.5（批次3选股表现回顾）与备份逐字节一致（common.py 只改了拼接位5）"""
    cur = _COMMON.read_text(encoding="utf-8")
    bak = _COMMON_BAK.read_text(encoding="utf-8")

    def _block(text):
        start = text.index("# 拼接位5.5")
        end = text.index("version = repo.get_trade_profile().version")
        return text[start:end]

    assert _block(cur) == _block(bak)
