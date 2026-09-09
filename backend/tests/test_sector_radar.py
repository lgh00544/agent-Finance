"""行业消息雷达 MVP：新表幂等、映射、K228 与反馈治理。"""
import pandas as pd
import pytest
from sqlalchemy import delete

from app.db import models, repo
from app.db.session import SessionLocal, init_db
from app.services import sector_dict, sector_radar
from app.services.sector_radar import SectorInterpretDraft


@pytest.fixture(autouse=True)
def _db_ready():
    init_db()
    with SessionLocal() as db:
        for table in (models.SectorNewsFeedback, models.SectorNewsShadowVerify,
                      models.SectorNewsAIInterpret, models.SectorNewsArticle,
                      models.SectorDictV1):
            db.execute(delete(table))
        db.commit()


def _article_row(content="宁德时代发布储能新品，机构称储能产业链需求改善。"):
    return {
        "source_scope": "company_signal", "source_type": "company_news",
        "source_name": "证券时报", "external_id": "u1", "title": "储能需求改善",
        "content": content, "source_url": "https://example.com/a",
        "published_at": "2026-09-07", "content_hash": "h1",
        "sector_codes": ["new_energy"], "stock_codes": ["300750"],
        "mapping_method": "exact_entity", "mapping_confidence": 0.8,
        "status": "accepted",
    }


def test_article_idempotent_and_feedback_not_change_dict():
    before = sector_dict.ensure_default_dict()
    aid1, is_new1 = repo.add_sector_news_article(_article_row())
    aid2, is_new2 = repo.add_sector_news_article(_article_row())
    feedback = sector_radar.feedback(aid1, None, "dismiss", "误标")

    assert aid1 == aid2
    assert is_new1 is True and is_new2 is False
    assert feedback["ok"] is True
    assert len(repo.list_sector_dict()) == before


def test_mapping_unmapped_and_multi_sector():
    mapped = sector_dict.map_text("宁德时代与光刻设备产业链均有新进展")
    unmapped = sector_dict.map_text("普通消费新闻没有明确行业词")

    assert {"new_energy", "semiconductor"}.issubset(set(mapped["sector_codes"]))
    assert mapped["mapping_method"] == "exact_entity"
    assert unmapped["mapping_method"] == "unmapped"


def test_k228_accepts_exact_quote_and_blocks_recommendation():
    aid, _ = repo.add_sector_news_article(_article_row())
    articles = repo.get_sector_news_articles([aid])
    ok = SectorInterpretDraft(
        polarity="positive", summary="储能需求改善", impact_mechanism="可能改善行业订单",
        information_score=0.8, direction_confidence=0.6,
        quote_evidence=[{"article_id": aid, "quote": "储能产业链需求改善"}],
        affected_stock_codes=["300750"], stock_relation_basis="原文明确提及")
    blocked = SectorInterpretDraft(
        polarity="positive", summary="建议持有龙头", impact_mechanism="行业可能受益",
        information_score=0.8, direction_confidence=0.6,
        quote_evidence=[{"article_id": aid, "quote": "储能产业链需求改善"}])

    assert sector_radar.enforce_k228(ok, articles)["validator_status"] == "accepted"
    assert sector_radar.enforce_k228(blocked, articles)["validator_status"] == "blocked"


def test_collect_stores_company_signal_without_agent_prompt(monkeypatch):
    class DS:
        def fetch_industry_cons(self, name):
            return pd.DataFrame([{"code": "300750"}])

        def fetch_news(self, code):
            return pd.DataFrame([{"title": "宁德时代储能订单增长",
                                  "content": "宁德时代储能订单增长，储能产业链需求改善。",
                                  "published_at": "2026-09-07",
                                  "source": "证券时报", "url": "https://example.com/a"}])

    monkeypatch.setattr(sector_radar, "get_datasource", lambda: DS())
    result = sector_radar.collect_sector_radar("new_energy", max_sectors=1,
                                               max_stocks=1, sleep_seconds=0)
    rows = repo.list_sector_news_articles("new_energy", 7)

    assert result["articles_new"] == 1
    assert rows[0]["source_scope"] == "company_signal"
    assert rows[0]["mapping_method"] in ("exact_entity", "exact_keyword")


def test_collect_keeps_200_when_industry_cons_fails(monkeypatch):
    class DS:
        def fetch_industry_cons(self, name):
            raise RuntimeError("remote disconnected")

        def fetch_news(self, code):
            return pd.DataFrame()

    monkeypatch.setattr(sector_radar, "get_datasource", lambda: DS())
    result = sector_radar.collect_sector_radar("new_energy", max_sectors=1,
                                               max_stocks=1, sleep_seconds=0)

    assert result["articles_new"] == 0
    assert result["errors"]
    assert "industry_cons" in result["errors"][0]


def test_collect_uses_seed_codes_when_industry_cons_fails(monkeypatch):
    seen_codes = []

    class DS:
        def fetch_industry_cons(self, name):
            raise RuntimeError("remote disconnected")

        def fetch_news(self, code):
            seen_codes.append(code)
            return pd.DataFrame([{"title": "宁德时代储能订单增长",
                                  "content": "宁德时代储能订单增长，储能产业链需求改善。",
                                  "published_at": "2026-09-07",
                                  "source": "证券时报", "url": "https://example.com/seed"}])

    monkeypatch.setattr(sector_radar, "get_datasource", lambda: DS())
    result = sector_radar.collect_sector_radar("new_energy", max_sectors=1,
                                               max_stocks=1, sleep_seconds=0)

    assert seen_codes == ["300750"]
    assert result["articles_new"] == 1
    assert result["sectors_with_articles"] == 1
    assert result["stock_codes_scanned"] == 1
    assert result["stock_codes_with_articles"] == 1
    assert result["seed_fallback_sectors"] == 1
    assert any("seed_codes" in err for err in result["errors"])


def test_collect_skips_low_value_h_share_disclosure(monkeypatch):
    class DS:
        def fetch_industry_cons(self, name):
            raise RuntimeError("remote disconnected")

        def fetch_news(self, code):
            return pd.DataFrame([{"title": "中际旭创:H股公告(翌日披露报表)",
                                  "content": "已发行股份或库存股份变动",
                                  "published_at": "2026-09-07",
                                  "source": "东方财富-公告", "url": "https://example.com/low"}])

    monkeypatch.setattr(sector_radar, "get_datasource", lambda: DS())
    result = sector_radar.collect_sector_radar("ai_compute", max_sectors=1,
                                               max_stocks=1, sleep_seconds=0)

    assert result["articles_new"] == 0
    assert result["articles_skipped_low_value"] == 1


def test_list_hides_existing_low_value_disclosure():
    repo.add_sector_news_article({
        **_article_row("已发行股份或库存股份变动"),
        "title": "中际旭创:H股公告(翌日披露报表)",
        "content_hash": "low-value",
    })

    result = sector_radar.list_radar(days=7)

    assert result["items"] == []
