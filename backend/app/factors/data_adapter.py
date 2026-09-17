import math
from typing import Any

import pandas as pd

from app.services.factor_registry import FactorResult


def num(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(str(value).strip().replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def rows(value: Any) -> list[dict]:
    if isinstance(value, pd.DataFrame):
        return value.where(pd.notna(value), None).to_dict(orient="records")
    return [r for r in (value or []) if isinstance(r, dict)]


def latest(items: list[dict]) -> dict:
    return items[-1] if items else {}


def factor(value: Any, reason: str = "ok", quantile: float | None = None) -> FactorResult:
    return FactorResult(value=value, quantile=quantile, reason=reason)


class DataAdapter:
    def __init__(self, source=None, code: str = "", *, kline=None, indicators=None,
                 financial=None, fund_flow=None, news=None, sectors=None, quote=None,
                 hot_money=None, extra=None):
        self.source, self.code = source, code
        self.indicators = indicators or {}
        self.extra = extra or {}
        self._cache = {k: v for k, v in {
            "kline": kline, "financial": financial, "fund_flow": fund_flow,
            "news": news, "sectors": sectors, "quote": quote, "hot_money": hot_money,
        }.items() if v is not None}

    def _get(self, key: str, method: str, *args):
        if key in self._cache:
            return self._cache[key]
        try:
            value = getattr(self.source, method)(*args) if self.source else None
        except Exception:
            value = None
        self._cache[key] = value
        return value

    def kline_rows(self) -> list[dict]:
        return rows(self._get("kline", "fetch_daily_kline", self.code, self.extra.get("start_date", ""), self.extra.get("end_date", "")))

    def financial_rows(self) -> list[dict]:
        return rows(self._get("financial", "fetch_financial", self.code))

    def fund_rows(self) -> list[dict]:
        return rows(self._get("fund_flow", "fetch_fund_flow", self.code))

    def news_rows(self) -> list[dict]:
        return rows(self._get("news", "fetch_news", self.code))

    def sector_rows(self) -> list[dict]:
        return rows(self._get("sectors", "fetch_industry_spot"))

    def quote(self) -> dict:
        value = self._get("quote", "fetch_spot_quote", self.code)
        return value if isinstance(value, dict) else {}

    def hot_money(self) -> dict:
        value = self._cache.get("hot_money") or self.extra.get("hot_money")
        return value if isinstance(value, dict) else {}

    def find(self, *keys: str) -> Any:
        sources = [self.extra, self.quote(), latest(self.fund_rows()),
                   latest(self.financial_rows()), latest(self.sector_rows()), self.hot_money()]
        for source in sources:
            for key in keys:
                if isinstance(source, dict) and source.get(key) not in (None, ""):
                    return source[key]
        return None

    def industry(self) -> str | None:
        value = self.find("industry", "行业", "所属行业", "sector_name", "板块名称")
        return str(value) if value not in (None, "") else None

    def sector(self) -> dict:
        explicit = self.extra.get("sector_row")
        if isinstance(explicit, dict):
            return explicit
        industry = self.industry()
        matches = [r for r in self.sector_rows() if str(r.get("board_name") or r.get("sector_name") or "") == industry]
        return matches[0] if len(matches) == 1 else {}

    def quantile(self, fid: str, value: float) -> float | None:
        direct = (self.extra.get("quantiles") or {}).get(fid)
        if num(direct) is not None:
            return num(direct)
        peers = [num(x) for x in (self.extra.get("quantile_values") or {}).get(fid, [])]
        peers = [x for x in peers if x is not None]
        if peers:
            return round(sum(x <= value for x in peers) / len(peers) * 100, 2)
        return None

    def number(self, *keys: str) -> float | None:
        return num(self.find(*keys))
