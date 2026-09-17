from app.factors.data_adapter import DataAdapter, factor
from app.services.factor_registry import register


def _strength(data: DataAdapter, keywords: tuple[str, ...], missing: str):
    news = data.news_rows()
    if not news:
        return factor(None, f"data_missing:{missing}")
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
