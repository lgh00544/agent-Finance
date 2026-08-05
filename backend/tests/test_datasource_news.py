"""新闻数据源 vendored 修复 + 候选快照防误清空测试：
akshare 1.18.81 非法正则（pandas3+pyarrow 下 ArrowInvalid）修复后结构正确；
搜索接口空结果自动降级个股公告源；LLM 终选为空时保留当日已有候选快照
（不触网：requests.get 全部 mock）"""
import json

import pandas as pd
import pytest

from app.agents import discover
from app.agents.schemas import DiscoverOutput
from app.datasource import akshare_source
from app.datasource.akshare_source import (_clean_em_tags, _stock_announcements,
                                           _stock_news_em_fixed, _stock_news_fixed)


class _FakeResp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


def _jsonp(payload: dict) -> str:
    return "jQuery35101792940631092459_1764599530165(" + json.dumps(payload) + ")"


def _search_payload(rows: list[dict]) -> dict:
    return {"code": 0, "msg": "OK", "result": {"cmsArticleWebOld": rows, "passportWeb": []}}


# ================= 搜索接口（正则修复） =================

def test_news_search_parses_and_cleans(monkeypatch):
    """合法 JSONP + <em> 高亮 + 全角空格 → 正常解析且无 ArrowInvalid；列名规范化"""
    rows = [{"date": "2026-08-05 10:00:00", "mediaName": "证券时报", "code": "A123",
             "title": "标题(<em>核心</em>)", "content": "<em>正文</em>　含全角空格\r\n换行"}]
    monkeypatch.setattr("requests.get",
                        lambda *a, **k: _FakeResp(_jsonp(_search_payload(rows))))
    df = _stock_news_em_fixed("600519")
    assert list(df.columns) == ["关键词", "新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]
    assert df.iloc[0]["新闻标题"] == "标题核心"  # <em> 高亮及包裹括号整体清除（与上游语义一致）
    assert "<em>" not in df.iloc[0]["新闻内容"]
    assert "　" not in df.iloc[0]["新闻内容"]
    assert "换行" in df.iloc[0]["新闻内容"]
    assert df.iloc[0]["新闻链接"].startswith("http://finance.eastmoney.com/a/")


def test_news_search_empty_no_article(monkeypatch):
    """接口存活但无文章（如当前仅返回 profile 数据）→ 空表，走降级路径"""
    monkeypatch.setattr("requests.get",
                        lambda *a, **k: _FakeResp(_jsonp({"result": {"passportWeb": []}})))
    df = _stock_news_em_fixed("600519")
    assert df.empty


# ================= 个股公告降级源 =================

def test_announcements_fallback_chain(monkeypatch):
    """搜索空 → 自动降级公告：列表 + 正文两次调用，列名/内容/来源合规"""
    list_payload = {"data": {"list": [
        {"art_code": "AN202608050000001", "title": "关于召开股东大会的通知",
         "notice_date": "2026-08-05 00:00:00"},
        {"art_code": "AN202608050000002", "title": "业绩预告",
         "notice_date": "2026-08-04 00:00:00"},
    ]}}
    detail_payload = {"data": {"notice_content": "会议审议事项<em>要点</em>　详见正文"}}
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "security/ann" in url:
            return _FakeResp(json.dumps(list_payload))
        return _FakeResp(json.dumps(detail_payload))

    monkeypatch.setattr("requests.get", fake_get)
    df = _stock_news_fixed("600519")
    assert len(df) == 2
    assert df.iloc[0]["新闻标题"] == "关于召开股东大会的通知"
    assert df.iloc[0]["新闻内容"] == "会议审议事项要点详见正文"  # <em>/全角空格已清理
    assert df.iloc[0]["文章来源"] == "东方财富-公告"
    assert df.iloc[0]["新闻链接"].startswith("https://data.eastmoney.com/notices/detail/")
    assert any("security/ann" in c for c in calls)
    assert any("content/ann" in c for c in calls)


def test_announcements_detail_failure_nonblocking(monkeypatch):
    """单条正文失败不阻塞：行仍在，正文为空"""
    list_payload = {"data": {"list": [
        {"art_code": "AN1", "title": "公告标题", "notice_date": "2026-08-05 00:00:00"}]}}

    def fake_get(url, **kwargs):
        if "security/ann" in url:
            return _FakeResp(json.dumps(list_payload))
        raise RuntimeError("正文接口不可达")

    monkeypatch.setattr("requests.get", fake_get)
    df = _stock_announcements("600519")
    assert len(df) == 1
    assert df.iloc[0]["新闻内容"] == ""


def test_clean_em_tags_empty_frame():
    assert _clean_em_tags(pd.DataFrame()).empty


# ================= 终选为空时快照保留（防数据丢失） =================

def _empty_output():
    return DiscoverOutput(market_summary="测试市况", candidates=[])


def test_llm_final_empty_keeps_snapshot(monkeypatch):
    """终选 LLM 输出空候选 → 不得调用 replace_day_candidates 清空当日快照"""
    state = {"shortlist": [{"stock_code": "600519", "stock_name": "贵州茅台"}],
             "enrichment": {}, "data_enrichment": {}, "market_cap": 10,
             "trade_date": "2026-08-05", "universe": []}
    replaced = []
    monkeypatch.setattr(discover, "agent_call", lambda **k: _empty_output())
    monkeypatch.setattr(discover.repo, "upsert_candidate", lambda *a, **k: 1)
    monkeypatch.setattr(discover.repo, "replace_day_candidates",
                        lambda codes, date: replaced.append((codes, date)) or 0)
    out = discover.llm_final(state)
    assert out["candidates"] == []
    assert replaced == []  # 空结果不得触发快照替换
    assert any("保留当日已有候选快照" in t for t in out["trace"])


def test_llm_final_nonempty_still_replaces(monkeypatch):
    """终选有候选 → 正常执行快照替换（保留清理残留语义）"""
    from app.agents.schemas import DiscoverCandidate

    cand = DiscoverCandidate(
        stock_code="600519", stock_name="贵州茅台", reason="量价健康",
        risk_notice="估值偏高", stock_type="吸筹末期-优选型",
        confidence_tier="建议关注", confidence_pct=72.0,
        macro_view="m", meso_view="e", micro_view="s",
        volume_analysis="v", risks=["风险A", "风险B"], focus_type="低吸")
    state = {"shortlist": [cand.model_dump()], "enrichment": {}, "data_enrichment": {},
             "market_cap": 10, "trade_date": "2026-08-05",
             "universe": [{"code": "600519", "name": "贵州茅台"}]}
    replaced = []
    monkeypatch.setattr(discover, "agent_call",
                        lambda **k: DiscoverOutput(market_summary="测试市况", candidates=[cand]))
    monkeypatch.setattr(discover.repo, "upsert_candidate", lambda *a, **k: 1)
    monkeypatch.setattr(discover.repo, "replace_day_candidates",
                        lambda codes, date: replaced.append((codes, date)) or 0)
    out = discover.llm_final(state)
    assert out["candidates"][0]["stock_code"] == "600519"
    assert replaced == [({"600519"}, "2026-08-05")]  # 有结果才替换
