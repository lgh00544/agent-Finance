"""板块轮动·批次C 归因子子 Agent：top10 板块启动归因（LIGHT；reason_chain 证据 K227 引用真实字段）"""
import json
import logging
import time
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents.common import agent_call
from app.db import repo
from app.db.models import SectorLaunchReason
from app.db.session import SessionLocal
from app.llm.structured import ModelLevel
from agent_prompts.sector_launch_prompt import SYSTEM, build_prompt

logger = logging.getLogger(__name__)

TOP_N = 10
LIMIT_UP_PCT = 9.8   # 连板判定：当日涨幅 ≥9.8%（主板近似；ST/科创板容忍差异）
CAUSAL_METHODOLOGY_VERSION = "sector_causal_loop_v1"
_VALID_TIME_ALIGNMENTS = {"before", "near", "background", "after", "unknown"}
_VALID_LAYERS = {"social", "news", "policy", "industry", "company", "capital"}
_VALID_EVIDENCE_LEVELS = {"L1", "L2", "L3", "L4"}
_VALID_CAUSE_LABELS = {
    "verified_cause", "probable_cause", "background_support",
    "related_signal", "post_move_explanation", "unusable_rumor",
}


class ReasonChainItem(BaseModel):
    """证据链单条：evidence_key 必须来自证据 JSON 真实字段（K227）"""
    evidence_key: str = Field(description="证据字段名（证据 JSON 白名单内）")
    inference: str = Field(description="通过该数据判定的推理")


class CausalChainItem(BaseModel):
    """因果链单条；evidence_keys 必须能回指本次采集证据。"""
    layer: str = Field(default="unknown", description="social/news/policy/industry/company/capital")
    claim: str = Field(default="", description="该层的事实或判断")
    evidence_keys: list[str] = Field(default_factory=list, description="给定证据 JSON 内的字段名")
    evidence_level: str = Field(default="L4", description="L1/L2/L3/L4")
    time_alignment: str = Field(default="unknown", description="before/near/background/after/unknown")
    cause_label: str = Field(default="related_signal",
                              description="verified_cause/probable_cause/background_support/"
                                           "related_signal/post_move_explanation/unusable_rumor")


class SectorLaunchOutput(BaseModel):
    """启动归因输出契约"""
    reason_tags: str = Field(description="归因标签，逗号分隔：policy/news/fund/oversold/earnings/overseas/rotation")
    reason_text: str = Field(description="一段白话归因")
    reason_chain: list[ReasonChainItem] = Field(description="证据链，每条引用 evidence 内真实字段")
    confidence: float = Field(ge=0, le=1, description="置信度 0-1")
    causal_chain: list[CausalChainItem] = Field(
        default_factory=list, description="八段式中的催化分层全量链，引用 evidence_keys")
    industry_transmission: list[str] = Field(
        default_factory=list, description="消息/政策/产业如何传导到板块交易")
    company_mapping: dict = Field(
        default_factory=dict, description="direct_core/indirect_related/emotion_proxy 三类公司映射")
    capital_behavior: dict = Field(
        default_factory=dict, description="龙头、扩散、成交、弱市防御等资金验证")
    falsification: dict = Field(
        default_factory=dict, description="t1_invalid_if/t3_invalid_if/t5_invalid_if")


def _limit_up_streak(kline) -> int | None:
    """从日 K 末尾往回数连续涨停天数（兼容 DataFrame/list-of-dict；缺口 → None）"""
    if kline is None:
        return None
    if hasattr(kline, "columns") and "change_pct" in kline.columns:
        vals = kline["change_pct"].tolist()
    elif isinstance(kline, (list, tuple)):
        vals = [r.get("change_pct") for r in kline]
    else:
        return None
    if not vals:
        return None
    streak = 0
    for pct in reversed(vals):
        if pct is None:
            break
        try:
            if float(pct) >= LIMIT_UP_PCT:
                streak += 1
            else:
                break
        except (TypeError, ValueError):
            break
    return streak


def _latest_field(rows, key) -> float | None:
    """取资金流最新一行字段（fetch_fund_flow 返回 DataFrame；缺 → None）"""
    if rows is None or getattr(rows, "empty", False):
        return None
    try:
        v = rows.iloc[-1].get(key) if hasattr(rows, "iloc") else rows[-1].get(key)
    except (IndexError, KeyError, TypeError):
        return None
    return None if v is None else float(v)


def _index_change_pct(rows, trade_date: str) -> float | None:
    """从指数日线收盘计算指定交易日涨跌幅；缺数据返回 None。"""
    if rows is None or getattr(rows, "empty", False):
        return None
    try:
        records = rows.to_dict("records") if hasattr(rows, "to_dict") else list(rows)
    except (TypeError, ValueError):
        return None
    normalized = []
    for row in records:
        try:
            date_key = str(row.get("date") or "")[:10]
            close = float(row.get("close"))
        except (AttributeError, TypeError, ValueError):
            continue
        if date_key:
            normalized.append((date_key, close, row.get("change_pct")))
    normalized.sort(key=lambda item: item[0])
    for idx, (date_key, close, change_pct) in enumerate(normalized):
        if date_key != trade_date:
            continue
        try:
            if change_pct is not None:
                return float(change_pct)
        except (TypeError, ValueError):
            pass
        if idx == 0 or normalized[idx - 1][1] == 0:
            return None
        return (close / normalized[idx - 1][1] - 1) * 100
    return None


def _news_evidence(news) -> list[dict]:
    """保留少量新闻元数据，支持时间匹配；不把新闻数量冒充因果证据。"""
    if news is None or getattr(news, "empty", False):
        return []
    try:
        records = news.to_dict("records") if hasattr(news, "to_dict") else list(news)
    except (TypeError, ValueError):
        return []
    out = []
    for row in records[-5:]:
        if not isinstance(row, dict):
            continue
        item = {}
        for key in ("title", "published_at", "source", "url"):
            value = row.get(key)
            if value is not None and str(value):
                item[key] = str(value)
        if item:
            out.append(item)
    return out


def _market_confirmation(ev: dict) -> dict:
    rank = ev.get("rank_no")
    change = ev.get("change_pct")
    confirmed = None
    if rank is not None and change is not None:
        try:
            confirmed = int(rank) <= TOP_N and float(change) > 0
        except (TypeError, ValueError):
            confirmed = None
    return {
        "market_confirmed": confirmed,
        "rank_no": rank,
        "change_pct": change,
        "up_count": ev.get("up_count"),
        "leading_limit_up_streak": ev.get("leading_limit_up_streak"),
        "relative_index_strength": ev.get("relative_index_strength"),
        "optional_metrics": {"limit_up_count": None},
    }


def _model_dump(value) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _normalise_causal_chain(items, evidence: dict) -> list[dict]:
    out = []
    for item in items or []:
        data = _model_dump(item)
        refs = [key for key in data.get("evidence_keys", []) if key in evidence]
        label = data.get("cause_label") if data.get("cause_label") in _VALID_CAUSE_LABELS else "related_signal"
        alignment = data.get("time_alignment")
        if alignment not in _VALID_TIME_ALIGNMENTS:
            alignment = "unknown"
        layer = data.get("layer") if data.get("layer") in _VALID_LAYERS else "unknown"
        evidence_level = data.get("evidence_level")
        if evidence_level not in _VALID_EVIDENCE_LEVELS:
            evidence_level = "L4"
        if not refs:
            label = "related_signal"
        out.append({
            "layer": layer,
            "claim": data.get("claim") or "",
            "evidence_keys": refs,
            "evidence_level": evidence_level,
            "time_alignment": alignment,
            "cause_label": label,
        })
    return out


def _confidence_result(raw: float, evidence: dict, causal_chain: list[dict],
                       industry_transmission: list[str], capital_behavior: dict) -> tuple[float, dict]:
    """按证据和闭环完整度计算置信度上限，保留 raw 供审计。"""
    value = max(0.0, min(1.0, float(raw)))
    market = (evidence.get("market_confirmation") or {}).get("market_confirmed")
    valid_chain = [item for item in causal_chain if item["evidence_keys"]]
    has_timing = any(item["time_alignment"] in {"before", "near"} for item in valid_chain)
    has_hard_evidence = any(item["evidence_level"] in {"L1", "L2"} for item in valid_chain)
    cap = 0.9
    cap_reason = "L1/L2、时间匹配、传导和资金验证均满足"
    if market is False:
        cap, cap_reason = 0.25, "盘面未确认"
    elif not valid_chain:
        cap, cap_reason = 0.45, "没有可回指采集证据的因果链"
    elif not industry_transmission:
        cap, cap_reason = 0.50, "缺少产业传导"
    elif not has_timing:
        cap, cap_reason = 0.50, "缺少 before/near 时间匹配"
    elif not has_hard_evidence:
        cap, cap_reason = 0.70, "缺少 L1/L2 硬证据"
    elif not capital_behavior:
        cap, cap_reason = 0.85, "缺少资金验证"
    final = min(value, cap)
    return final, {"raw_confidence": value, "cap_reason": cap_reason, "final_confidence": final}


def _prepare_evidence(ev: dict, out: SectorLaunchOutput) -> tuple[dict, float, str, str]:
    """把 LLM 归因放入证据信封；摘要链仍保持旧字段兼容。"""
    evidence = dict(ev)
    evidence["methodology_version"] = CAUSAL_METHODOLOGY_VERSION
    evidence["market_confirmation"] = _market_confirmation(ev)
    causal_chain = _normalise_causal_chain(out.causal_chain, ev)
    industry_transmission = [str(item) for item in (out.industry_transmission or []) if str(item)]
    company_mapping = out.company_mapping or {}
    capital_behavior = out.capital_behavior or {}
    falsification = out.falsification or {}
    evidence.update({
        "causal_chain": causal_chain,
        "industry_transmission": industry_transmission,
        "company_mapping": company_mapping,
        "capital_behavior": capital_behavior,
        "falsification": falsification,
    })
    final_confidence, confidence_caps = _confidence_result(
        out.confidence, evidence, causal_chain, industry_transmission, capital_behavior)
    evidence["confidence_caps"] = confidence_caps
    labels = [item["cause_label"] for item in causal_chain if item["cause_label"] in _VALID_CAUSE_LABELS]
    tags = [tag.strip() for tag in str(out.reason_tags or "").split(",") if tag.strip()]
    for label in labels:
        if label not in tags:
            tags.append(label)
    summary = [{"evidence_key": i.evidence_key, "inference": i.inference}
               for i in out.reason_chain if i.evidence_key in ev]
    if not summary:
        fallback_key = next((key for key, value in ev.items() if value is not None), "sector_name")
        summary = [{"evidence_key": fallback_key, "inference": "证据链引用不足，暂不确认具体启动原因。"}]
    return evidence, final_confidence, ",".join(tags), json.dumps(summary, ensure_ascii=False)


def collect_evidence(sector_name: str, trade_date: str) -> dict | None:
    """代码层证据采集：快照字段（已落库）+ 领涨股连板/主力净流入/新闻 + 板块箱位；缺数据 None 不编造"""
    row = next((r for r in repo.list_sector_daily_by_date(trade_date)
                if r["sector_name"] == sector_name), None)
    if row is None:
        return None
    ev = {"sector_name": row["sector_name"], "change_pct": row["change_pct"],
          "rank_no": row["rank_no"], "up_count": row["up_count"],
          "down_count": row["down_count"], "volume_ratio": row["volume_ratio"],
          "turnover_rate": row["turnover_rate"],
          "leading_stock_name": row["leading_stock_name"],
          "leading_stock_code": row["leading_stock_code"],
          "leading_chg": row["leading_chg"]}
    from app.datasource.akshare_source import AkshareSource
    src = AkshareSource()
    code = row["leading_stock_code"]
    start = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=40)).strftime("%Y-%m-%d")
    try:
        ev["leading_limit_up_streak"] = _limit_up_streak(src.fetch_daily_kline(code, start, trade_date))
    except Exception:  # noqa: BLE001 单维度失败标注缺失不阻断
        ev["leading_limit_up_streak"] = None
    try:
        flow = src.fetch_fund_flow(code)
        ev["main_net_inflow"] = _latest_field(flow, "main_net_inflow")
        ev["main_net_pct"] = _latest_field(flow, "main_net_pct")
    except Exception:  # noqa: BLE001
        ev["main_net_inflow"] = ev["main_net_pct"] = None
    try:
        news = src.fetch_news(code)
        ev["news_count"] = len(news) if news is not None and not getattr(news, "empty", False) else 0
        ev["news_evidence"] = _news_evidence(news)
    except Exception:  # noqa: BLE001
        ev["news_count"] = ev["news_evidence"] = None
    try:
        index_start = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
        index_change = _index_change_pct(
            src.fetch_index_daily("sh000001", index_start, trade_date), trade_date)
        ev["index_change_pct"] = index_change
        ev["relative_index_strength"] = (
            float(row["change_pct"]) - index_change
            if index_change is not None and row.get("change_pct") is not None else None
        )
    except Exception:  # noqa: BLE001
        ev["index_change_pct"] = ev["relative_index_strength"] = None
    try:
        box = src.fetch_board_box_positions([sector_name]).get(sector_name, {})
        ev["main_box_pct"] = box.get("main_box_pct")
        ev["box60_pct"] = box.get("box60_pct")
    except Exception:  # noqa: BLE001
        ev["main_box_pct"] = ev["box60_pct"] = None
    return ev


def _upsert_launch_reason(row: dict) -> None:
    with SessionLocal() as db:
        db.add(SectorLaunchReason(
            trade_date=row["trade_date"], sector_name=row["sector_name"],
            rank_no=row["rank_no"], reason_tags=row["reason_tags"],
            reason_text=row["reason_text"], reason_chain=row["reason_chain"],
            evidence=row["evidence"], confidence=row["confidence"]))
        db.commit()


def run_launch_reason(trade_date: str | None = None) -> dict:
    """对 top10 板块各一次 LIGHT 归因，落 sector_launch_reason（同 trade_date 删后插幂等）"""
    today = trade_date or time.strftime("%Y-%m-%d")
    rows = repo.list_sector_daily_by_date(today)[:TOP_N]
    if not rows:
        return {"success": False, "error": f"{today} 无全板块日快照", "count": 0}
    with SessionLocal() as db:
        db.execute(text("DELETE FROM sector_launch_reason WHERE trade_date = :d"), {"d": today})
        db.commit()
    done = []
    for row in rows:
        ev = collect_evidence(row["sector_name"], today)
        if ev is None:
            continue
        try:
            out = agent_call("sector_launch_reason", f"sector_launch:{today}:{row['sector_name']}",
                             SYSTEM, build_prompt(ev), SectorLaunchOutput,
                             model_level=ModelLevel.LIGHT, with_profile=False)
        except Exception as exc:  # noqa: BLE001 单板块失败不阻塞整体
            logger.warning("板块 %s 归因失败（跳过）: %s", row["sector_name"], exc)
            continue
        evidence, confidence, tags, reason_chain = _prepare_evidence(ev, out)
        _upsert_launch_reason({
            "trade_date": today, "sector_name": row["sector_name"],
            "rank_no": row["rank_no"], "reason_tags": tags,
            "reason_text": out.reason_text,
            "reason_chain": reason_chain,
            "evidence": evidence, "confidence": confidence,
        })
        done.append(row["sector_name"])
    return {"success": True, "trade_date": today, "count": len(done), "sectors": done}
