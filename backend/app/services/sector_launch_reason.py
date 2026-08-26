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


class ReasonChainItem(BaseModel):
    """证据链单条：evidence_key 必须来自证据 JSON 真实字段（K227）"""
    evidence_key: str = Field(description="证据字段名（证据 JSON 白名单内）")
    inference: str = Field(description="通过该数据判定的推理")


class SectorLaunchOutput(BaseModel):
    """启动归因输出契约"""
    reason_tags: str = Field(description="归因标签，逗号分隔：policy/news/fund/oversold/earnings/overseas/rotation")
    reason_text: str = Field(description="一段白话归因")
    reason_chain: list[ReasonChainItem] = Field(description="证据链，每条引用 evidence 内真实字段")
    confidence: float = Field(ge=0, le=1, description="置信度 0-1")


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
    except Exception:  # noqa: BLE001
        ev["news_count"] = None
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
        _upsert_launch_reason({
            "trade_date": today, "sector_name": row["sector_name"],
            "rank_no": row["rank_no"], "reason_tags": out.reason_tags,
            "reason_text": out.reason_text,
            "reason_chain": json.dumps([{"evidence_key": i.evidence_key, "inference": i.inference}
                                        for i in out.reason_chain], ensure_ascii=False),
            "evidence": ev, "confidence": out.confidence,
        })
        done.append(row["sector_name"])
    return {"success": True, "trade_date": today, "count": len(done), "sectors": done}
