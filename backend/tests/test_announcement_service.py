"""个股公告查询服务测试（对话链路增量能力）：
代码解析 / 公告类型定性 / 读库优先 / 实时抓取去重入库 / 当日抓取标记 /
异常兜底（无公告/接口失败/非法代码）不编造 / agent_chat 对话触发注入与 payload。
外部接口全部 mock（禁网），断言流程行为与结构化输出，不断言业务结论。"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.agents import common
from app.db import repo
from app.services import agent_chat
from app.services import announcement_service as ann_svc


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from app.db.session import init_db
    init_db()


def _recent_date(days_ago: int = 1) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _news_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "title": r["title"], "content": r.get("content", "正文"), "source": "东方财富-公告",
        "url": f"https://data.eastmoney.com/notices/detail/601138/{r['title']}.html",
        "published_at": r.get("published_at", _recent_date()),
    } for r in rows])


class FakeSource:
    """mock 数据源：可返回指定 DataFrame 或抛异常；统计 fetch_news 调用次数"""

    def __init__(self, df=None, exc: Exception | None = None):
        self.df = df
        self.exc = exc
        self.calls = 0

    def fetch_news(self, code: str):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.df


def _patch_source(monkeypatch, source: FakeSource):
    monkeypatch.setattr(ann_svc, "get_datasource", lambda: source)


# ================= 代码解析 =================

def test_parse_stock_code_basic():
    assert ann_svc.parse_stock_code("601138 最近有没有公告") == "601138"
    assert ann_svc.parse_stock_code("帮我看看000001的利空") == "000001"
    assert ann_svc.parse_stock_code("没有代码的问题") is None
    assert ann_svc.parse_stock_code("") is None
    assert ann_svc.parse_stock_code("123456789012345") is None  # 长数字串不误匹配


# ================= 公告类型定性 =================

def test_classify_announcement_types():
    cases = [
        ("关于非公开发行A股股票预案", "定增"),
        ("回购股份方案公告", "回购"),
        ("业绩预增公告", "业绩预告"),
        ("重大合同中标公告", "重大合同"),
        ("股东减持股份计划", "高管增减持"),
        ("收到监管函", "监管函"),
        ("股权质押公告", "股权质押"),
        ("立案调查公告", "立案调查"),
        ("重大资产重组停牌", "重组并购"),
        ("关于分红派息的公告", "分红派息"),
        ("限售股上市流通", "解禁"),
        ("召开股东大会通知", "其他"),
    ]
    for title, expect in cases:
        assert ann_svc.classify_announcement(title) == expect, title


# ================= 读库优先（不请求外部） =================

def test_fetch_reads_db_first(monkeypatch):
    """库中已有近 7 日公告 → 直接读库返回，不触发外部抓取；字段完整"""
    code = "600001"
    repo.add_news(code, "", "回购股份方案公告", "正文", "东方财富-公告",
                  "https://e.com/1.html", _recent_date())
    source = FakeSource(df=_news_df([{"title": "不应触发的抓取"}]))
    _patch_source(monkeypatch, source)

    result = ann_svc.fetch_latest_announcement(code)
    assert result["fetched"] is True
    assert source.calls == 0  # 库命中，未请求外部接口
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["title"] == "回购股份方案公告"
    assert item["ann_type"] == "回购"
    assert item["published_at"].startswith(_recent_date())
    assert "https://e.com/1.html" in item["url"]
    assert "正文" in item["summary"]
    assert "已查询到" in result["message"]


# ================= 库空 → 实时抓取 + 去重入库 + 当日标记 =================

def test_fetch_fetches_stores_and_dedups(monkeypatch):
    """库中无近期数据 → 触发外部抓取并入库；再次调用当日标记生效不再请求外部接口"""
    code = "601138"
    source = FakeSource(df=_news_df([
        {"title": "回购股份方案公告", "content": "公司拟回购不超过5亿元"},
        {"title": "回购股份方案公告", "content": "重复标题不应再次入库"},  # 同标题去重
        {"title": "业绩预增公告", "content": "预计净利润同比增长50%"},
    ]))
    _patch_source(monkeypatch, source)

    result = ann_svc.fetch_latest_announcement(code)
    assert source.calls == 1
    assert len(result["items"]) == 2  # 去重后 2 条
    titles = {it["title"] for it in result["items"]}
    assert titles == {"回购股份方案公告", "业绩预增公告"}
    assert result["items"][0]["ann_type"] == "回购"
    assert "5亿元" in result["items"][0]["summary"]

    # 第二次调用：当日抓取标记生效，不再请求外部接口，直接读库
    result2 = ann_svc.fetch_latest_announcement(code)
    assert source.calls == 1
    assert len(result2["items"]) == 2
    assert result2["items"][0]["title"] == "回购股份方案公告"


def test_fetch_no_announcement(monkeypatch):
    """抓取返回空 → 明确输出「未查询到」，不编造"""
    code = "600002"
    source = FakeSource(df=_news_df([]))
    _patch_source(monkeypatch, source)
    result = ann_svc.fetch_latest_announcement(code)
    assert result["items"] == []
    assert "未查询到该标的近期公开公告" in result["message"]


def test_fetch_source_error_graceful(monkeypatch):
    """外部接口失败 → 明确告知失败原因，不崩不编造"""
    code = "600003"
    source = FakeSource(exc=RuntimeError("接口超时"))
    _patch_source(monkeypatch, source)
    result = ann_svc.fetch_latest_announcement(code)
    assert result["items"] == []
    assert "失败" in result["message"]


# ================= 非法代码 =================

def test_fetch_invalid_code():
    for bad in ("abc", "12345", "1234567", ""):
        result = ann_svc.fetch_latest_announcement(bad)
        assert result["items"] == []
        assert "无法解析" in result["message"], bad


# ================= repo 读取方法（近 N 日过滤） =================

def test_get_recent_news_days_filter():
    code = "600004"
    repo.add_news(code, "", "近期公告", "x", "东财", "u1", _recent_date(days_ago=1))
    repo.add_news(code, "", "超期公告", "x", "东财", "u2", _recent_date(days_ago=20))
    rows = repo.get_recent_news(code, days=7)
    assert len(rows) == 1
    assert rows[0]["title"] == "近期公告"
    assert repo.get_recent_news("600004", days=7)[0]["url"] == "u1"


# ================= agent_chat 对话触发 =================

def _fake_answer(**kwargs):
    def _call(*args, **kw):
        return agent_chat.ChatAnswer(
            answer="该股近期公告以回购为主，中性偏积极，需结合量价验证。",
            confidence=70, sources=["公告查询（东财）", "公开行情数据"], scope_note="",
            announcement_verdict={
                "sentiment": "中性", "reason": "回购属护盘性质，力度有限",
                "cross_check": "近期股价未明显反应，警惕借利好出货",
                "risk_note": "公告单一维度不得直接给买卖建议",
            })
    return _call


def test_ask_agent_announcement_triggered(monkeypatch):
    """问题含公告关键词+6位代码 → 注入公告上下文与研判标准，payload 带公告数据与研判"""
    captured = {}

    def _spy_call(*args, **kw):
        captured["system_prompt"] = kw.get("system_prompt", "")
        captured["user_prompt"] = kw.get("user_prompt", "")
        return _fake_answer()(*args, **kw)

    monkeypatch.setattr(common, "agent_call", _spy_call)
    monkeypatch.setattr(repo, "add_news", lambda *a, **k: True)
    monkeypatch.setattr(ann_svc, "get_datasource",
                        lambda: FakeSource(df=_news_df([{"title": "回购股份方案公告"}])))
    # 清空 601138 当日抓取标记与库内记录，保证走抓取路径
    from app.cache import cache
    cache.delete("announcement:fetched:601138")

    payload = agent_chat.ask_agent("discover", "601138 最近有没有公告？")
    assert "601138" in captured["user_prompt"]
    assert "个股公告研判标准" in captured["system_prompt"]
    assert "借利好出货" in captured["system_prompt"]  # K189 红线注入
    assert payload["announcement"]["stock_code"] == "601138"
    assert payload["announcement"]["items"]
    assert payload["announcement_verdict"]["sentiment"] == "中性"
    assert "回购" in payload["answer"]


def test_ask_agent_announcement_not_triggered(monkeypatch):
    """普通问题不注入公告上下文（关键词+代码双条件）"""
    captured = {}

    def _spy_call(*args, **kw):
        captured["system_prompt"] = kw.get("system_prompt", "")
        captured["user_prompt"] = kw.get("user_prompt", "")
        return agent_chat.ChatAnswer(answer="回答", confidence=60,
                                     sources=["知识库"], scope_note="")

    monkeypatch.setattr(common, "agent_call", _spy_call)
    payload = agent_chat.ask_agent("score", "怎么理解吸筹末期？")
    assert "个股公告研判标准" not in captured["system_prompt"]
    assert "601138" not in captured["user_prompt"]
    assert "announcement" not in payload


def test_ask_agent_keyword_without_code_asks_user(monkeypatch):
    """命中公告关键词但无 6 位代码 → 提示用户补充代码，不抓取不编造"""
    captured = {}

    def _spy_call(*args, **kw):
        captured["user_prompt"] = kw.get("user_prompt", "")
        return agent_chat.ChatAnswer(answer="请提供具体股票代码", confidence=40,
                                     sources=[], scope_note="")

    monkeypatch.setattr(common, "agent_call", _spy_call)
    agent_chat.ask_agent("discover", "最近有没有利好公告？")
    assert "请用户补充具体股票代码" in captured["user_prompt"]
