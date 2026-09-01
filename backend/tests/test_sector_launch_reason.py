"""板块轮动·批次C 归因子 Agent 测试（dev SQLite，不触网；akshare/LLM mock）

3 例：①证据采集字段齐全（含缺数据如实 None）②reason_chain 每条引用 evidence 真实字段（K227）
③同 trade_date 删后插幂等。
"""
import json
from datetime import date
from unittest import mock

import pandas as pd
import pytest
from sqlalchemy import select

from agent_prompts import market_intel_prompt, sector_launch_prompt
from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.db.models import SectorLaunchReason
from app.db.session import SessionLocal, init_db
from app.services import sector_launch_reason as slr


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _seed_snapshot(names):
    today = date.today().isoformat()
    repo.upsert_sector_daily_snapshot([
        {"trade_date": today, "sector_name": n, "change_pct": float(5 - i),
         "rank_no": i + 1, "up_count": 30, "down_count": 10,
         "volume_ratio": 1.5, "turnover_rate": 3.2,
         "leading_stock_name": f"领涨{i}", "leading_stock_code": f"60000{i}", "source": "em"}
        for i, n in enumerate(names)])
    return today


def _rows_for(trade_date):
    with SessionLocal() as db:
        return list(db.execute(
            select(SectorLaunchReason).where(SectorLaunchReason.trade_date == trade_date)
        ).scalars().all())


# ============ 1: 证据采集字段齐全 + 缺数据如实 None ============

def test_collect_evidence_fields_complete():
    today = _seed_snapshot(["半导体", "白酒"])
    with mock.patch.object(AkshareSource, "fetch_daily_kline",
                           return_value=pd.DataFrame({"change_pct": [10.0, 10.0, 10.0]})), \
         mock.patch.object(AkshareSource, "fetch_fund_flow",
                           return_value=pd.DataFrame({"date": [today], "main_net_inflow": [1.2e8], "main_net_pct": [5.0]})), \
         mock.patch.object(AkshareSource, "fetch_news",
                           return_value=pd.DataFrame({"title": ["x"] * 4})), \
         mock.patch.object(
             AkshareSource, "fetch_index_daily",
             return_value=pd.DataFrame({"date": [today, today], "close": [100.0, 102.0]})), \
         mock.patch.object(AkshareSource, "fetch_board_box_positions",
                           return_value={"半导体": {"main_box_pct": 80.0, "box60_pct": 60.0, "note": ""}}):
        ev = slr.collect_evidence("半导体", today)
    assert ev is not None
    assert ev["volume_ratio"] == 1.5 and ev["turnover_rate"] == 3.2
    assert ev["leading_limit_up_streak"] == 3   # 3 日连板
    assert ev["main_net_inflow"] == 1.2e8
    assert ev["news_count"] == 4
    assert ev["main_box_pct"] == 80.0 and ev["box60_pct"] == 60.0
    # 数据维度缺口 → 如实 None，不编造不报错
    with mock.patch.object(AkshareSource, "fetch_daily_kline", return_value=pd.DataFrame()), \
         mock.patch.object(AkshareSource, "fetch_fund_flow", return_value=pd.DataFrame()), \
         mock.patch.object(AkshareSource, "fetch_news", side_effect=RuntimeError("down")), \
         mock.patch.object(AkshareSource, "fetch_index_daily", return_value=pd.DataFrame()), \
         mock.patch.object(AkshareSource, "fetch_board_box_positions", return_value={}):
        ev2 = slr.collect_evidence("白酒", today)
    assert ev2["leading_limit_up_streak"] is None
    assert ev2["main_net_inflow"] is None
    assert ev2["news_count"] is None
    assert ev2["main_box_pct"] is None


def test_causal_evidence_schema_normalizes_and_caps_confidence():
    ev = {
        "sector_name": "种植业", "rank_no": 1, "change_pct": 4.0,
        "up_count": 42, "main_net_inflow": 1.2e8,
    }
    out = slr.SectorLaunchOutput(
        reason_tags="news",
        reason_text="待验证",
        reason_chain=[slr.ReasonChainItem(evidence_key="not_real", inference="不应保留")],
        confidence=0.9,
        causal_chain=[slr.CausalChainItem(
            layer="invalid", claim="线索", evidence_keys=["main_net_inflow"],
            evidence_level="invalid", time_alignment="invalid", cause_label="invalid")],
    )
    evidence, confidence, tags, reason_chain = slr._prepare_evidence(ev, out)
    assert evidence["methodology_version"] == "sector_causal_loop_v1"
    assert evidence["causal_chain"][0]["layer"] == "unknown"
    assert evidence["causal_chain"][0]["evidence_level"] == "L4"
    assert evidence["causal_chain"][0]["time_alignment"] == "unknown"
    assert evidence["causal_chain"][0]["cause_label"] == "related_signal"
    assert confidence == 0.5
    assert "related_signal" in tags
    assert json.loads(reason_chain)[0]["evidence_key"] == "sector_name"


def test_causal_evidence_confidence_uses_full_chain():
    ev = {
        "sector_name": "种植业", "rank_no": 1, "change_pct": 4.0,
        "news_count": 3, "relative_index_strength": 3.0,
    }
    out = slr.SectorLaunchOutput(
        reason_tags="news",
        reason_text="证据充分",
        reason_chain=[slr.ReasonChainItem(evidence_key="news_count", inference="有新闻")],
        confidence=0.78,
        causal_chain=[slr.CausalChainItem(
            layer="news", claim="消息催化", evidence_keys=["news_count"],
            evidence_level="L1", time_alignment="before", cause_label="verified_cause")],
        industry_transmission=["供给预期变化传导到板块估值"],
        capital_behavior={"breadth_expansion": True},
    )
    evidence, confidence, _, _ = slr._prepare_evidence(ev, out)
    assert confidence == 0.78
    assert evidence["confidence_caps"]["final_confidence"] == 0.78
    assert evidence["causal_chain"][0]["cause_label"] == "verified_cause"


def test_prompt_contains_causal_loop_hard_constraints():
    assert "盘面确认" in sector_launch_prompt.SYSTEM
    assert "time_alignment" in sector_launch_prompt.SYSTEM
    assert "industry_transmission" in sector_launch_prompt.SYSTEM
    assert "事后解释" in market_intel_prompt.SYSTEM_PROMPT
    assert "反证条件" in market_intel_prompt.SYSTEM_PROMPT


# ============ 2: reason_chain 非空且每条引用 evidence 真实字段（K227） ============

def test_reason_chain_cites_real_evidence(monkeypatch):
    names = ["半导体", "白酒", "银行", "券商", "军工", "煤炭", "有色", "医药", "地产", "电力"]
    today = _seed_snapshot(names)
    fake_ev = {"sector_name": "半导体", "change_pct": 4.0, "volume_ratio": 1.5,
               "turnover_rate": 3.2, "leading_limit_up_streak": 2,
               "main_net_inflow": 1.2e8, "news_count": 3,
               "main_box_pct": 80.0, "box60_pct": 60.0}

    monkeypatch.setattr(slr, "collect_evidence", lambda name, td: {**fake_ev, "sector_name": name})
    monkeypatch.setattr(
        slr, "agent_call",
        lambda agent, cache_key, system, user, schema, **kw: slr.SectorLaunchOutput(
            reason_tags="fund,news", reason_text="主力净流入放量+连板带动板块启动",
            reason_chain=[slr.ReasonChainItem(evidence_key="main_net_inflow", inference="主力大额净流入，资金面强驱动"),
                          slr.ReasonChainItem(evidence_key="volume_ratio", inference="量比放大，资金进场"),
                          slr.ReasonChainItem(evidence_key="news_count", inference="新闻热度高，催化充分")],
            confidence=0.7))
    res = slr.run_launch_reason(today)
    assert res["success"] is True and res["count"] == 10
    rows = _rows_for(today)
    assert len(rows) == 10
    for row in rows:
        chain = json.loads(row.reason_chain)
        assert len(chain) >= 1
        for item in chain:
            assert item["evidence_key"] in row.evidence   # K227：引用 evidence 真实字段


# ============ 3: 同 trade_date 删后插幂等 ============

def test_same_date_delete_then_insert_idempotent(monkeypatch):
    today = _seed_snapshot(["半导体", "白酒", "银行"])
    monkeypatch.setattr(slr, "collect_evidence", lambda name, td: {"sector_name": name})
    monkeypatch.setattr(
        slr, "agent_call",
        lambda agent, cache_key, system, user, schema, **kw: slr.SectorLaunchOutput(
            reason_tags="policy", reason_text="政策驱动",
            reason_chain=[slr.ReasonChainItem(evidence_key="sector_name", inference="板块主体明确")],
            confidence=0.6))
    r1 = slr.run_launch_reason(today)
    r2 = slr.run_launch_reason(today)
    assert r1["count"] == 3 and r2["count"] == 3
    rows = _rows_for(today)
    assert len(rows) == 3          # 删后插：两次 run 仍只 3 行
    assert len({row.sector_name for row in rows}) == 3
