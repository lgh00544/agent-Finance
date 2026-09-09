"""观察型行业消息雷达：证据化解读 + shadow 验证，不进入正式 Agent。"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta

import pandas as pd
from pydantic import BaseModel, Field

from app.core.config import settings
from app.datasource.fallback import get_datasource
from app.db import repo
from app.llm.structured import ModelLevel, llm_call_json
from app.services import sector_dict


BAN_TERMS = ("买入", "卖出", "加仓", "减仓", "建仓", "清仓", "目标价", "目标位",
             "仓位", "止盈", "止损", "强烈推荐", "建议持有", "值得布局", "首选标的")


class QuoteItem(BaseModel):
    article_id: int
    quote: str
    start: int | None = None
    end: int | None = None


class SectorInterpretDraft(BaseModel):
    polarity: str = Field(pattern="^(positive|negative|neutral|mixed|uncertain)$")
    summary: str
    impact_mechanism: str
    impact_horizon: str = "unknown"
    information_score: float = Field(ge=0, le=1)
    direction_confidence: float = Field(ge=0, le=1)
    quote_evidence: list[QuoteItem]
    affected_stock_codes: list[str] = []
    stock_relation_basis: str = ""


def article_hash(title: str, published_at: str, source_name: str, source_url: str = "") -> str:
    raw = "|".join([title.strip(), published_at.strip(), source_name.strip(), source_url.strip()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def enforce_k228(parsed: SectorInterpretDraft | dict, articles: list[dict]) -> dict:
    data = parsed.model_dump() if isinstance(parsed, BaseModel) else dict(parsed)
    article_by_id = {int(a["id"]): a for a in articles}
    output_text = "\n".join(str(data.get(k) or "") for k in (
        "summary", "impact_mechanism", "stock_relation_basis"))
    blocked = any(t in output_text for t in BAN_TERMS)
    checked_quotes = []
    for q in data.get("quote_evidence") or []:
        qd = q.model_dump() if isinstance(q, BaseModel) else dict(q)
        article = article_by_id.get(int(qd.get("article_id") or 0))
        quote = str(qd.get("quote") or "").strip()
        if not article or not quote:
            blocked = True
            continue
        if not all(article.get(k) for k in ("source_name", "source_url", "published_at", "content")):
            blocked = True
        content = str(article.get("content") or "")
        start = content.find(quote)
        if start < 0:
            blocked = True
            continue
        checked_quotes.append({**qd, "start": start, "end": start + len(quote)})
    if not checked_quotes:
        blocked = True
    codes = [c for c in (data.get("affected_stock_codes") or []) if str(c).strip()]
    basis = str(data.get("stock_relation_basis") or "")
    if codes and not any(k in basis for k in ("原文", "行业映射", "明确提及")):
        blocked = True
    if re.search(r"利好.{0,12}(\d{6}|[\u4e00-\u9fa5]{2,8})", output_text) and "行业" not in basis:
        blocked = True
    data["quote_evidence"] = checked_quotes
    data["human_review_required"] = bool(blocked)
    data["validator_status"] = "blocked" if blocked else "accepted"
    return data


def collect_sector_radar(sector_code: str = "", auto_interpret: bool = False,
                         max_sectors: int = 8, max_stocks: int = 5,
                         sleep_seconds: float = 2.0) -> dict:
    ds = get_datasource()
    sectors = sector_dict.list_active_sectors()
    if sector_code:
        sectors = [s for s in sectors if s["sector_code"] == sector_code]
    stats = {"sectors": len(sectors[:max_sectors]), "sectors_with_articles": 0,
             "stock_codes_scanned": 0, "stock_codes_with_articles": 0,
             "seed_fallback_sectors": 0, "articles_new": 0, "articles_seen": 0,
             "articles_skipped_low_value": 0, "interprets": 0, "errors": []}
    for sec in sectors[:max_sectors]:
        try:
            codes = _sector_codes(ds, sec["sector_name"])[:max_stocks]
        except Exception as exc:  # noqa: BLE001 数据源波动只影响当前行业
            stats["errors"].append(f"{sec['sector_name']}/industry_cons: {exc}")
            codes = sector_dict.seed_stock_codes(sec)[:max_stocks]
            if codes:
                stats["seed_fallback_sectors"] += 1
                stats["errors"].append(f"{sec['sector_name']}/seed_codes: 使用人工种子标的兜底")
        if not codes:
            codes = sector_dict.seed_stock_codes(sec)[:max_stocks]
            if codes:
                stats["seed_fallback_sectors"] += 1
                stats["errors"].append(f"{sec['sector_name']}/seed_codes: 行业成分为空，使用人工种子标的兜底")
        if not codes:
            stats["errors"].append(f"{sec['sector_name']}/codes: 无可抓取标的")
            continue
        new_article_ids: list[int] = []
        sector_has_articles = False
        for code in codes:
            stats["stock_codes_scanned"] += 1
            try:
                news = ds.fetch_news(code)
                stock_has_articles = False
                for _, row in (news.head(10) if isinstance(news, pd.DataFrame) else pd.DataFrame()).iterrows():
                    if _is_low_value_notice(row):
                        stats["articles_skipped_low_value"] += 1
                        continue
                    aid, is_new = _store_news_row(row, code, sec)
                    stats["articles_seen"] += 1
                    stats["articles_new"] += 1 if is_new else 0
                    stock_has_articles = True
                    sector_has_articles = True
                    if auto_interpret and is_new:
                        new_article_ids.append(aid)
                if stock_has_articles:
                    stats["stock_codes_with_articles"] += 1
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            except Exception as exc:  # noqa: BLE001 单只失败不影响行业雷达
                stats["errors"].append(f"{sec['sector_name']}/{code}: {exc}")
        if sector_has_articles:
            stats["sectors_with_articles"] += 1
        if auto_interpret:
            for offset in range(0, len(new_article_ids), 5):
                try:
                    result = run_interpret(sec["sector_code"], new_article_ids[offset:offset + 5])
                    stats["interprets"] += 1 if result.get("ok") else 0
                    if not result.get("ok"):
                        stats["errors"].append(f"{sec['sector_name']}/interpret: {result.get('message')}")
                except Exception as exc:  # noqa: BLE001 LLM/K228 异常不阻断抓取
                    stats["errors"].append(f"{sec['sector_name']}/interpret: {exc}")
    return stats


def run_interpret(sector_code: str, article_ids: list[int]) -> dict:
    articles = repo.get_sector_news_articles(article_ids)
    if not articles:
        return {"ok": False, "message": "未找到可解读的原文"}
    prompt = _interpret_prompt(sector_code, articles)
    draft = llm_call_json(
        "你是A股行业消息雷达，只输出JSON，只做行业影响解读，不给买卖建议。",
        prompt, SectorInterpretDraft, max_tokens=1200, model_level=ModelLevel.LIGHT)
    checked = enforce_k228(draft, articles)
    if checked["validator_status"] != "accepted":
        return {"ok": False, "message": "K228 blocked", "result": checked}
    iid = repo.add_sector_news_interpret({
        **checked, "article_ids": [a["id"] for a in articles],
        "sector_codes": sorted({c for a in articles for c in (a.get("sector_codes") or [])}),
        "model_version": settings.deepseek_default_model,
    })
    first_sector = _sector_by_code(sector_code)
    repo.add_sector_news_shadow({
        "interpret_id": iid, "sector_code": sector_code,
        "sector_name": first_sector.get("sector_name", sector_code),
        "signal_date": str(articles[0].get("published_at") or "")[:10] or time.strftime("%Y-%m-%d"),
        "base_index_value": _sector_close(first_sector.get("sector_name", sector_code),
                                          str(articles[0].get("published_at") or "")[:10]),
    })
    return {"ok": True, "interpret_id": iid, "result": checked}


def shadow_verify_worker(limit: int = 200) -> dict:
    ds = get_datasource()
    updated = 0
    for row in repo.list_sector_shadow_pending(limit):
        values = _shadow_values(ds, row)
        if values and repo.update_sector_shadow(row["id"], values):
            updated += 1
    return {"updated": updated}


def list_radar(sector_code: str = "", days: int = 7, date: str = "", source_scope: str = "") -> dict:
    sector_dict.ensure_default_dict()
    data = repo.list_sector_radar(sector_code, days, date, source_scope)
    items = [
        item for item in (data.get("items") or [])
        if not _is_low_value_notice((item.get("article") or {}))
    ]
    return {**data, "items": items, "total": len(items)}


def feedback(article_id: int | None, interpret_id: int | None,
             feedback_type: str, reason: str = "") -> dict:
    fid = repo.add_sector_news_feedback({
        "article_id": article_id, "interpret_id": interpret_id,
        "feedback_type": feedback_type, "reason": reason})
    return {"ok": True, "feedback_id": fid, "message": "反馈已进入待审核队列，不会自动修改字典"}


def _store_news_row(row, code: str, source_sector: dict) -> tuple[int, bool]:
    title = str(row.get("title") or "").strip()
    content = str(row.get("content") or title).strip()
    source = str(row.get("source") or "").strip()
    url = str(row.get("url") or "").strip()
    published_at = str(row.get("published_at") or "").strip()
    mapping = sector_dict.map_text(f"{title}\n{content}", source_sector)
    status = "accepted" if title and content and source and url and published_at else "human_review"
    return repo.add_sector_news_article({
        "source_scope": "company_signal", "source_type": "company_news",
        "source_name": source, "external_id": url,
        "title": title, "content": content[:4000], "source_url": url,
        "published_at": published_at,
        "content_hash": article_hash(title, published_at, source, url),
        "sector_codes": mapping["sector_codes"], "stock_codes": [code],
        "mapping_method": mapping["mapping_method"],
        "mapping_confidence": mapping["mapping_confidence"], "status": status})


def _is_low_value_notice(row) -> bool:
    title = str(row.get("title") or "").strip()
    content = str(row.get("content") or "").strip()
    text = f"{title}\n{content}"
    low_value_terms = (
        "翌日披露报表",
        "证券变动月报表",
        "已发行股份或库存股份变动",
        "股份发行人的证券变动月报表",
    )
    return any(term in text for term in low_value_terms)


def _sector_codes(ds, sector_name: str) -> list[str]:
    cons = ds.fetch_industry_cons(sector_name)
    if cons is None or getattr(cons, "empty", True):
        return []
    code_col = "code" if "code" in cons.columns else ("代码" if "代码" in cons.columns else None)
    return [] if not code_col else [str(c).zfill(6) for c in cons[code_col].dropna().tolist()]


def _sector_by_code(sector_code: str) -> dict:
    return next((s for s in sector_dict.list_active_sectors()
                 if s["sector_code"] == sector_code), {"sector_code": sector_code, "sector_name": sector_code})


def _interpret_prompt(sector_code: str, articles: list[dict]) -> str:
    compact = [{"id": a["id"], "title": a["title"], "content": a["content"][:1200],
                "source": a["source_name"], "published_at": a["published_at"]}
               for a in articles[:5]]
    return (
        f"sector_code={sector_code}\narticles={compact}\n"
        "输出JSON字段：polarity(positive/negative/neutral/mixed/uncertain), summary, "
        "impact_mechanism, impact_horizon, information_score(0-1证据完整度), "
        "direction_confidence(0-1), quote_evidence[{article_id,quote}], "
        "affected_stock_codes, stock_relation_basis。只谈行业影响。")


def _sector_close(sector_name: str, day: str) -> float | None:
    if not day:
        day = time.strftime("%Y-%m-%d")
    ds = get_datasource()
    start = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    hist = ds.fetch_industry_hist(sector_name, start, day)
    if hist is None or hist.empty or "close" not in hist.columns:
        return None
    closes = pd.to_numeric(hist["close"], errors="coerce").dropna()
    return None if closes.empty else float(closes.iloc[-1])


def _shadow_values(ds, row: dict) -> dict:
    signal_date = str(row.get("signal_date") or "").strip()
    if not signal_date:
        return {}
    start = (datetime.strptime(signal_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    end = time.strftime("%Y-%m-%d")
    hist = ds.fetch_industry_hist(row["sector_name"], start, end)
    if hist is None or hist.empty or "close" not in hist.columns:
        return {}
    date_col = "date" if "date" in hist.columns else hist.columns[0]
    hist = hist.copy()
    hist["__date"] = pd.to_datetime(hist[date_col], errors="coerce")
    hist["__close"] = pd.to_numeric(hist["close"], errors="coerce")
    hist = hist.dropna(subset=["__date", "__close"]).sort_values("__date").reset_index(drop=True)
    if hist.empty:
        return {}
    signal_dt = datetime.strptime(signal_date, "%Y-%m-%d")
    base_candidates = hist.index[hist["__date"] <= signal_dt].tolist()
    if not base_candidates:
        return {}
    base_idx = base_candidates[-1]
    base = float(row.get("base_index_value") or hist.loc[base_idx, "__close"])
    values = {"base_index_value": base}
    for n in (1, 3, 5):
        target_idx = base_idx + n
        if target_idx < len(hist):
            if row.get(f"t{n}_return") is None:
                values[f"t{n}_return"] = round(
                    (float(hist.loc[target_idx, "__close"]) - base) / base * 100, 4
                )
            if not row.get(f"t{n}_at"):
                values[f"t{n}_at"] = hist.loc[target_idx, "__date"].strftime("%Y-%m-%d")
    ret = values.get("t5_return", row.get("t5_return"))
    interpret = repo.get_sector_news_interpret(row["interpret_id"])
    if ret is not None and interpret and interpret.get("polarity") in ("positive", "negative"):
        values["direction_correct"] = (
            (interpret["polarity"] == "positive" and float(ret) > 0)
            or (interpret["polarity"] == "negative" and float(ret) < 0)
        )
    return values
