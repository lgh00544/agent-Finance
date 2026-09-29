import math
import unicodedata
from datetime import datetime, timedelta
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


# P0-6④：披露滞后缓冲（自然日）—— 只接受「报告期 + 缓冲 ≤ as_of」的期次。
# 报告期（report_date）是「数据所属期间」，披露日才是「市场可见时点」：2026-03-31 的一季报
# 到 4 月底才披露，若 3-31 的快照就用它，回测/打分等于用了当时市场还没看到的数据（前视）。
# 缓冲按 A 股法定披露截止日**分类**给（各报告期 → 截止日间隔的自然日数）：
#   年报 12-31 → 次年 4-30（120 天）、一季报 03-31 → 4-30（30 天）、
#   中报 06-30 → 8-31（62 天）、三季报 09-30 → 10-31（31 天）。
# 为什么不能一律取 120 天：统一 120 天会把「4 月底就已披露的一季报」误判成 7 月底才可见，
# 于是 5/6/7 三个月的快照会退回上年年报 —— 那不是保守，而是**口径错误**（当时的真实可得
# 数据被当成不可得），f11/f18-f21 的 IC 会被建立在一个并不存在的时间线上；反过来统一取
# 30 天又会让年报在 4 月前就可用（真前视）。故必须按报告期分类。
# 未识别的报告期一律退回最保守的 DISCLOSURE_LAG_DAYS；调用方可用 disclosure_lag_days=<int>
# 强制统一值（显式覆盖优先）。
DISCLOSURE_LAG_DAYS = 120                  # 兜底（未知报告期）/ 显式统一覆盖时的兼容默认值
_DISCLOSURE_LAG_BY_REPORT: dict[str, int] = {
    "12-31": 120, "03-31": 30, "06-30": 62, "09-30": 31,
}
# 资金流是行情数据（T+1 已可得），不是定期报告：单独给 1 天缓冲，不套用法定披露缓冲。
FUND_FLOW_LAG_DAYS = 1


def latest(items: list[dict], date_keys: tuple[str, ...] = ("report_date", "date"),
           as_of: str | None = None, disclosure_lag_days: int | None = None) -> dict:
    """取最新一期：以行内日期字段的最大值为准，不依赖列表位置。

    各数据源返回顺序并不统一（实查 financial / fund 均为「最新在前」降序），
    沿用 items[-1] 会取到最旧一期：f11/f18-f21 曾因此在读 2001 年财报、roe 恒为 None。
    rows 无可用日期字段时（如 sector_rows 的板块快照，源本身只有板块名/涨跌幅等、
    没有日期列）保留原行为 items[-1]，不静默改取 [0]。

    P0-6④（披露滞后约束）：给定 as_of（快照日）时只接受「报告期 + 披露缓冲 ≤ as_of」的期次，
    即只用当时市场已看到的那一期。缓冲默认按报告期查 _DISCLOSURE_LAG_BY_REPORT
    （年报 120 / 一季报 30 / 中报 62 / 三季报 31 天），传 disclosure_lag_days=<int> 则强制统一值。
    as_of 缺省（None）不做任何过滤 —— 线上实时打分路径与既有调用方/测试行为逐字不变
    （向后兼容优先）。
    有资格的行被滞后约束全部排除时返回 {}（空字典），绝不退回 items[-1]：宁可让调用方
    判空（因子记 data_missing），也不取未经披露校验的一期造成前视。
    日期按 YYYY-MM-DD 字符串比较（与取值口径一致）；as_of 非该格式时不新增过滤，不编造口径。
    """
    if not items:
        return {}
    dated = [(str(row.get(key)).strip(), row) for row in items for key in date_keys
             if str(row.get(key) or "").strip()]
    if not dated:
        return items[-1]          # 无日期字段（板块快照等）：保留原行为
    if as_of:
        try:
            base = datetime.strptime(str(as_of)[:10], "%Y-%m-%d")
        except (TypeError, ValueError):
            base = None           # as_of 不是 YYYY-MM-DD：保持原行为，由调用方保证格式
        if base is not None:
            def _disclosed(period: str) -> bool:
                """该报告期到 as_of 时是否已过法定披露截止日（按报告期分类缓冲）。"""
                lag = disclosure_lag_days
                if lag is None:
                    # period 形如 "YYYY-MM-DD..."，取 "MM-DD" 判报告类型
                    lag = _DISCLOSURE_LAG_BY_REPORT.get(period[5:10], DISCLOSURE_LAG_DAYS)
                limit = (base - timedelta(days=int(lag))).strftime("%Y-%m-%d")
                return period[:10] <= limit

            dated = [pair for pair in dated if _disclosed(pair[0])]
            if not dated:
                return {}
    return max(dated, key=lambda pair: pair[0])[1]


# M20：跨源同名 key 的来源白名单 —— 各数据源的同名字段量纲/口径并不通用
# （资金流净额「元」、板块快照「涨跌幅%」、实时行情是 tick 级快照），而 find() 原本
# 「谁先有谁命中」，于是 find("main_net_inflow") 落 fund、find("amount") 被 quote 抢答，
# 两者相除就静默错数量级（且 quote 与历史 fund 行不同期）。
# 只列「已知会产生数量级/同期性歧义」的 key；未列出的 key 行为完全不变（不引入大重构）。
# 需要绕过白名单时用 find_in(source_name, ...) 显式指定来源。
_KEY_SOURCES: dict[str, tuple[str, ...]] = {
    # 行业/板块名：只认调用方快照(extra)与板块行情(sector)，财报/资金流里的同名字段不同口径
    "industry": ("extra", "sector"),
    "行业": ("extra", "sector"),
    "所属行业": ("extra", "sector"),
    "sector_name": ("extra", "sector"),
    "板块名称": ("extra", "sector"),
    # 资金流净额（单位「元」）+ 成交额：f13 = 主力净额 / 成交额，分子分母必须同源同期。
    # quote 是实时 tick（与历史 fund 行不同期，且元/万元无元数据可校验）→ 排除；
    # 板块级「成交额」不得当作个股成交额 → 排除 sector；extra 是调用方显式给的同期快照，保留。
    "main_net_inflow": ("extra", "fund"),
    "main_inflow": ("extra", "fund"),
    "amount": ("extra", "fund"),
    "turnover_amount": ("extra", "fund"),
    "成交额": ("extra", "fund"),
}


def factor(value: Any, reason: str = "ok", quantile: float | None = None) -> FactorResult:
    return FactorResult(value=value, quantile=quantile, reason=reason)


_SECTOR_SUFFIXES = ("行业", "板块", "概念", "指数", "产业")


def _norm_sector(name: Any) -> str:
    """板块名归一化键：去全部空白 + NFKC（全角转半角）+ 小写 + 去尾部业务后缀。

    M19：东财行业快照的 board_name 与个股 industry 字段常只差后缀/空格/全半角
    （"半导体" vs "半导体行业" vs "半导体 "），原实现用 == 精确比较，
    任一差异都静默返回 {}，让 f22-f25 四个板块因子退化成 data_missing。
    复用说明：services/sector_dict.py 里只有内联的「去空白」处理（未导出为工具函数），
    且 factors 层直接依赖 services 层会引入 DB 侧依赖链，故在因子层本地实现。
    """
    text = unicodedata.normalize("NFKC", str(name or ""))
    # str.split() 按 Unicode 空白切分：覆盖半角/全角空格、NBSP、制表符等全部空白
    text = "".join(text.split()).lower()
    for suffix in _SECTOR_SUFFIXES:
        if len(text) > len(suffix) and text.endswith(suffix):
            return text[: -len(suffix)]      # 只剥一层，避免「行业板块」这类反复剥离
    return text


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

    def latest_financial(self) -> dict:
        """最新一期财报（P0-6④）：extra 带 as_of 快照日时叠加披露滞后约束，避免前视。

        无 as_of 时（线上实时路径，extra 只有 trade_date）与 latest() 原行为完全一致。
        """
        return latest(self.financial_rows(), as_of=self.extra.get("as_of"))

    def latest_fund(self) -> dict:
        """最新一期资金流（P0-6④）：资金流是行情数据（T+1 已可得），滞后按日计，
        不套用定期报告的 120 天法定披露缓冲；同样只在给定 as_of 时启用过滤。
        """
        return latest(self.fund_rows(), as_of=self.extra.get("as_of"),
                      disclosure_lag_days=FUND_FLOW_LAG_DAYS)

    def _sources(self) -> list[tuple[str, dict]]:
        """各数据源按优先级列名（M20）：find / find_in 共用同一份来源顺序。

        财务/资金流走 latest_financial()/latest_fund()：带 as_of 时启用披露滞后约束（P0-6④）。
        """
        return [("extra", self.extra), ("quote", self.quote()), ("fund", self.latest_fund()),
                ("financial", self.latest_financial()), ("sector", latest(self.sector_rows())),
                ("hot_money", self.hot_money())]

    def find(self, *keys: str) -> Any:
        """按来源优先级取第一个非空值；量纲/口径有歧义的 key 由 _KEY_SOURCES 限定来源（M20）。

        原有的「来源优先于 key 顺序」语义保持不变，只对白名单内的 key 追加来源校验：
        命中源不在白名单则继续往后找，全都不是允许来源时返回 None —— 宁可缺数
        （因子记 data_missing）也不返回跨源错数量级的数。
        """
        for name, source in self._sources():
            for key in keys:
                if not isinstance(source, dict) or source.get(key) in (None, ""):
                    continue
                allowed = _KEY_SOURCES.get(key)
                if allowed is None or name in allowed:
                    return source[key]
        return None

    def find_in(self, source_name: str, *keys: str) -> Any:
        """只在指定源内取 key（M20）：跨源量纲不可比时调用方须显式指定来源。

        source_name ∈ extra / quote / fund / financial / sector / hot_money；
        来源名非法时返回 None（不静默回退到全源查找）。
        """
        for name, source in self._sources():
            if name != source_name:
                continue
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
        key = _norm_sector(industry)
        if not key:
            self.extra["sector_match"] = "no_industry"
            return {}
        board_rows = self.sector_rows()
        # M19：两级匹配 —— ① 归一化后精确相等；② 唯一子串（"半导体" ⊂ "半导体及元件"）。
        # 仍不唯一/无匹配则返回 {}：宁缺勿错，错配的板块因子比缺失更危险。
        exact = [r for r in board_rows
                 if _norm_sector(r.get("board_name") or r.get("sector_name")) == key]
        if len(exact) == 1:
            self.extra["sector_match"] = "normalized"
            return exact[0]
        if exact:
            self.extra["sector_match"] = "ambiguous:%d" % len(exact)
            return {}
        fuzzy = [r for r in board_rows
                 if key in _norm_sector(r.get("board_name") or r.get("sector_name"))]
        if len(fuzzy) == 1:
            self.extra["sector_match"] = "substring"
            return fuzzy[0]
        # 原因只记在 extra（不影响返回结构与调用方签名）：无匹配 vs 多义可区分排查
        self.extra["sector_match"] = "no_match" if not fuzzy else "ambiguous_substring:%d" % len(fuzzy)
        return {}

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
