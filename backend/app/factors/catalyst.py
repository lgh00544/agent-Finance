from app.factors.data_adapter import DataAdapter, factor
from app.services.factor_registry import register


def _strength(data: DataAdapter, keywords: tuple[str, ...], missing: str):
    news = data.news_rows()
    if not news:
        return factor(None, f"data_missing:{missing}")
    # S-9/F-1：回测路径（extra 带 as_of 快照日）只统计快照日及之前已发布的新闻；
    # 无 published_at 的行无法确定时序，按「当时未发生」处理（诚实缺失），杜绝新闻前视。
    # 线上实时路径（无 as_of）行为不变：统计全部已取到的新闻。
    as_of = data.extra.get("as_of")
    if as_of:
        cutoff = str(as_of)[:10]
        news = [r for r in news
                if str(r.get("published_at") or "")[:10] and str(r.get("published_at"))[:10] <= cutoff]
        if not news:
            return factor(None, f"data_missing:{missing}:no_news_as_of")
    count = sum(any(k in f"{r.get('title', '')}{r.get('content', '')}" for k in keywords) for r in news)
    return factor(min(count, 3))


@register
def f06_earnings_catalyst(data: DataAdapter, code: str):
    return _strength(data, ("业绩", "预增", "预减", "年报", "季报", "盈利"), "earnings_news")


@register
def f07_policy_catalyst(data: DataAdapter, code: str):
    return _strength(data, ("政策", "国务院", "规划", "补贴", "降准", "监管"), "policy_news")


@register
def f08_industry_event(data: DataAdapter, code: str):
    return _strength(data, ("行业", "产业", "供需", "产能", "价格", "协会"), "industry_news")
