"""批次3：选股反馈闭环 + 候选池表现摘要（dev SQLite，不触网）：
1. get_selection_performance_summary()：紧凑文本（总体/分评级/异常事实/引导句）；
   无数据空串不报错；pl_ratio None 降级「无亏损样本」；缓存 selection:perf_summary:t5 生效
2. common.agent_call 注入位5.5：仅 discover/discover_final 注入，sell 不注入
3. 前端 render.selection_stat_cards：4 卡 + 胜率三档配色 + 涨幅正红负绿 + None 降级；
   候选池页接线（源码级：选股表现统计卡在可建仓统计卡之前）
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.agents.schemas import DiscoverOutput, SellOutput
from app.cache import cache
from app.db import repo
from app.db.models import CandidateTrackVerify
from app.db.session import SessionLocal, init_db

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PERF_KEY = "selection:perf_summary:t5"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _cleanup():
    """隔离批次3测试副作用：清空追踪验证行 + 失效 track_verify 查询缓存 + 表现摘要缓存"""
    cache.delete_prefix("dbq:track_verify:")
    cache.delete(_PERF_KEY)
    with SessionLocal() as db:
        db.execute(delete(CandidateTrackVerify))
        db.commit()
    yield
    cache.delete_prefix("dbq:track_verify:")
    cache.delete(_PERF_KEY)
    with SessionLocal() as db:
        db.execute(delete(CandidateTrackVerify))
        db.commit()


def _seed_row(code: str, name: str, date: str, rating: str, t5_pct: float,
              max_dd: float | None = None) -> int:
    rid = repo.upsert_track_verify(code, name, date, rating, 10.0)
    repo.update_track_verify(rid, t5_pct=t5_pct, max_drawdown=max_dd, is_finished=1)
    cache.delete_prefix("dbq:track_verify:")  # update_track_verify 不失效查询缓存
    return rid


# ==================== 1. get_selection_performance_summary ====================

def test_perf_summary_returns_compact_text():
    from app.services import track_verify as tv
    # A 档 3 行（≥3 展示分评级），B/C 档样本不足不展示
    _seed_row("600001", "甲", "2026-08-01", "A", 10.0, max_dd=-2.0)
    _seed_row("600002", "乙", "2026-08-01", "A", 5.0, max_dd=-1.0)
    _seed_row("600003", "丙", "2026-08-01", "A", -3.0, max_dd=-4.0)
    _seed_row("600004", "丁", "2026-08-02", "B", 2.0)
    _seed_row("600005", "戊", "2026-08-02", "B", -1.0)
    _seed_row("600006", "己", "2026-08-03", "C", 8.0)
    text = tv.get_selection_performance_summary("t5")
    assert text
    assert "近 6 只候选" in text
    assert "胜率" in text and "平均涨幅" in text and "盈亏比" in text
    assert "分评级" in text and "A 档" in text        # A n=3 ≥3 → 展示；B/C 不足不展示
    assert "B 档" not in text and "C 档" not in text
    assert "此为参考信息，不改变已有规则" in text      # 引导声明


def test_perf_summary_empty_when_no_data():
    from app.services import track_verify as tv
    assert tv.get_selection_performance_summary("t5") == ""


def test_perf_summary_pl_ratio_none_degraded():
    """全为盈利样本 → pl_ratio 为 None → 注入「无亏损样本」降级，不报错"""
    from app.services import track_verify as tv
    _seed_row("600001", "甲", "2026-08-01", "A", 3.0)
    _seed_row("600002", "乙", "2026-08-02", "B", 5.0)
    text = tv.get_selection_performance_summary("t5")
    assert "无亏损样本" in text


def test_perf_summary_anomaly_facts():
    """胜率过低异常：仅列事实 desc + 数据，不报错"""
    from app.services import track_verify as tv
    _seed_row("600001", "甲", "2026-08-01", "A", 5.0)
    _seed_row("600002", "乙", "2026-08-01", "A", -5.0)
    _seed_row("600003", "丙", "2026-08-01", "A", -6.0)
    _seed_row("600004", "丁", "2026-08-01", "B", -4.0)
    text = tv.get_selection_performance_summary("t5")
    assert "异常提示" in text
    assert "胜率低于" in text


def test_perf_summary_cached():
    from app.services import track_verify as tv
    _seed_row("600001", "甲", "2026-08-01", "A", 3.0)
    assert cache.get(_PERF_KEY) is None
    text1 = tv.get_selection_performance_summary("t5")
    assert text1
    assert cache.get(_PERF_KEY) == text1       # 首次后写入缓存
    assert tv.get_selection_performance_summary("t5") == text1  # 第二次命中缓存


def test_perf_summary_only_t5_not_none():
    """过滤 t5_pct 为 null 的行：有行但无 T+5 数据 → 返回空串"""
    from app.services import track_verify as tv
    rid = repo.upsert_track_verify("600099", "只入未到期", "2026-08-01", "A", 10.0)
    repo.update_track_verify(rid, is_finished=0)  # t5_pct 保持 None
    cache.delete_prefix("dbq:track_verify:")
    assert tv.get_selection_performance_summary("t5") == ""


# ==================== 2. common.agent_call 注入位5.5 ====================

def test_inject_only_discover(monkeypatch):
    """discover 注入选股表现回顾，sell 不注入（隔离隔离，防误伤其他 agent）"""
    from app.agents import common
    from app.llm.structured import ModelLevel

    _seed_row("600001", "甲", "2026-08-01", "A", 3.0)
    captured: dict[str, str] = {}

    def _fake(agent, cache_key, sys_prompt, user_prompt, schema,
              ttl_seconds=86400, model_level=ModelLevel.DEEP):
        captured[agent] = user_prompt
        return object()

    monkeypatch.setattr(common, "call_llm_cached", _fake)
    common.agent_call("discover", "k1", "sys", "user1", DiscoverOutput)
    common.agent_call("discover_final", "k2", "sys", "user2", DiscoverOutput)
    common.agent_call("sell", "k3", "sys", "user3", SellOutput)

    assert "选股表现回顾" in captured["discover"]
    assert "选股表现回顾" in captured["discover_final"]
    assert "选股表现回顾" not in captured["sell"]
    assert "此为参考信息，不改变已有规则" in captured["discover"]


# ==================== 3. 前端 selection_stat_cards + 页面接线 ====================

def _load_render():
    spec = importlib.util.spec_from_file_location(
        "render", _PROJECT_ROOT / "streamlit" / "render.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selection_stat_cards_basic():
    render = _load_render()
    cards = render.selection_stat_cards(
        {"n": 6, "wins": 4, "win_rate": 66.7, "avg_pct": 3.5, "pl_ratio": 6.25})
    assert len(cards) == 4
    by_label = {c["label"]: c for c in cards}
    assert by_label["近期选股胜率"]["value"] == "66.7%"
    assert by_label["近期选股胜率"]["tone"] == "ok"       # ≥50 → 绿
    assert by_label["平均涨幅"]["value"] == "+3.50%"
    assert by_label["平均涨幅"]["tone"] == "up"            # 正 → 红
    assert by_label["盈亏比"]["value"] == "6.25"
    assert by_label["样本量"]["value"] == "6 笔"


def test_selection_stat_cards_three_tiers_and_none():
    render = _load_render()
    # 胜率三档：≥50 ok / <40 err / 其余 warn
    assert render.selection_stat_cards({"n": 5, "win_rate": 55, "avg_pct": 1, "pl_ratio": 1})[0]["tone"] == "ok"
    assert render.selection_stat_cards({"n": 5, "win_rate": 35, "avg_pct": -2, "pl_ratio": None})[0]["tone"] == "err"
    assert render.selection_stat_cards({"n": 5, "win_rate": 45, "avg_pct": 0, "pl_ratio": None})[0]["tone"] == "warn"
    # 涨幅正红负绿
    assert render.selection_stat_cards({"n": 5, "win_rate": 45, "avg_pct": -2, "pl_ratio": None})[1]["tone"] == "down"
    # None 降级
    cards = render.selection_stat_cards({"n": 5, "win_rate": None, "avg_pct": None, "pl_ratio": None})
    assert cards[0]["value"] == "无数据" and cards[0]["tone"] == "mute"
    assert cards[1]["value"] == "无数据"
    assert cards[2]["value"] == "—"


def test_candidate_page_wired_before_tradeable_cards():
    """候选池页接线：选股表现统计卡调用在可建仓统计卡之前"""
    src = (_PROJECT_ROOT / "streamlit" / "pages" / "1_每日候选池.py").read_text(encoding="utf-8")
    assert "track_verify_stats" in src
    assert "selection_stat_cards" in src
    assert src.index("选股表现统计卡") < src.index("可建仓统计卡")
