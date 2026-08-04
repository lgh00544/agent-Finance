"""
Akshare 数据源实现（东财为主，新浪降级）
【刚性代码逻辑】仅做：数据采集、重试降级、列名规范化、缓存节流。
本层不做任何市场判断。

统一 fetch 封装：
  - 15s 超时（接口支持时传入 timeout 参数）
  - 指数退避重试 3 次（1.5s → 3s → 6s）
  - 东财接口失败时按可降级映射尝试新浪/同花顺备选接口
  - 结果按 中文列名 → 英文标准列 规范化
  - Redis/内存缓存按接口设置 TTL，避免高频请求触发限流
"""
import hashlib
import json
import logging
import time
from functools import wraps
from typing import Callable

import pandas as pd

from app.cache import cache
from app.core.config import settings
from app.datasource.base import DataSource, DataSourceError

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:  # pragma: no cover
    ak = None


# ---------------- 列名规范化映射（中文 → 英文标准列） ----------------
_SPOT_COLS = {
    "代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct",
    "涨跌额": "change_amount", "成交量": "volume", "成交额": "amount",
    "振幅": "amplitude", "最高": "high", "最低": "low", "今开": "open", "昨收": "pre_close",
    "量比": "volume_ratio", "换手率": "turnover_rate", "市盈率-动态": "pe_dynamic",
    "市净率": "pb", "总市值": "total_mv", "流通市值": "circ_mv",
    "60日涨跌幅": "pct_change_60d", "年初至今涨跌幅": "pct_change_ytd",
}
_KLINE_COLS = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount", "振幅": "amplitude",
    "涨跌幅": "change_pct", "涨跌额": "change_amount", "换手率": "turnover_rate",
}
_FUND_FLOW_COLS = {
    "日期": "date",
    "主力净流入-净额": "main_net_inflow", "主力净流入-净占比": "main_net_pct",
    "超大单净流入-净额": "super_large_net", "超大单净流入-净占比": "super_large_pct",
    "大单净流入-净额": "large_net", "大单净流入-净占比": "large_pct",
    "中单净流入-净额": "medium_net", "中单净流入-净占比": "medium_pct",
    "小单净流入-净额": "small_net", "小单净流入-净占比": "small_pct",
}
_FINANCIAL_SINA_COLS = {
    "日期": "report_date", "净资产收益率(%)": "roe", "净资产收益率-摊薄(%)": "roe_diluted",
    "主营业务收入增长率(%)": "revenue_yoy", "净利润增长率(%)": "profit_yoy",
    "资产负债率(%)": "debt_ratio", "销售净利率(%)": "net_margin",
    "销售毛利率(%)": "gross_margin",
}
_FINANCIAL_THS_COLS = {
    "报告期": "report_date", "营业总收入同比增长率(%)": "revenue_yoy",
    "净利润同比增长率(%)": "profit_yoy", "净资产收益率(%)": "roe",
    "资产负债率(%)": "debt_ratio", "销售毛利率(%)": "gross_margin",
}
_NEWS_COLS = {"关键词": "keyword", "新闻标题": "title", "新闻内容": "content",
              "发布时间": "published_at", "文章来源": "source", "新闻链接": "url"}
_NEWS_COLS_OLD = {"code": "code", "title": "title", "content": "content",
                  "public_time": "published_at", "url": "url"}
_INDEX_COLS = {"日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
               "最低": "low", "成交量": "volume", "成交额": "amount"}
_BOARD_COLS = {"板块名称": "board_name", "板块": "board_name",  # 东财/新浪列名变体
               "最新价": "price", "涨跌幅": "change_pct", "总市值": "total_mv",
               "换手率": "turnover_rate", "上涨家数": "up_count", "下跌家数": "down_count",
               "领涨股票": "leading_stock", "领涨股": "leading_stock", "股票名称": "leading_stock"}
_SUSPEND_COLS = {"代码": "code", "名称": "name", "停牌时间": "suspend_time",
                 "停牌原因": "reason", "预计复牌时间": "resume_time"}
_CONS_COLS = {"代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct",
              "成交额": "amount", "换手率": "turnover_rate"}


def _normalize(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """中文列名 → 英文标准列；无法识别的列丢弃"""
    if df is None or df.empty:
        return df
    rename = {k: v for k, v in mapping.items() if k in df.columns}
    out = df.rename(columns=rename)
    keep = set(mapping.values()) & set(out.columns)
    return out[[c for c in out.columns if c in keep]]


def _to_json_safe(df: pd.DataFrame) -> pd.DataFrame:
    """NaN → None，便于 JSON 序列化落库"""
    return df.where(pd.notna(df), None)


def _cache_key(scope: str) -> str:
    """scope 需包含全部标识参数（如 'kline:600519:20240101:20240801:qfq'）"""
    return "ak:" + hashlib.md5(scope.encode()).hexdigest()


def _market_of(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("4", "8", "9")):
        return "bj"
    return "sz"


class AkshareSource(DataSource):
    def __init__(self) -> None:
        if ak is None:
            raise DataSourceError("akshare 未安装")

    # ---------------- 统一 fetch 封装 ----------------
    def _fetch(self, scope: str, func_name: str, call: Callable, ttl_seconds: int,
               fallback: Callable | None = None, required: bool = True,
               normalize: Callable | None = None) -> pd.DataFrame:
        """带缓存 + 指数退避重试 + 降级的数据采集【刚性逻辑】。
        scope 必须包含全部标识参数（股票代码/日期等），作为缓存键。
        """
        key = _cache_key(scope)
        cached = cache.get(key)
        if cached:
            try:
                # pandas 3.x read_json 不解析 JSON 字符串（视为文件路径），改用 json.loads
                return pd.DataFrame(json.loads(cached))
            except (ValueError, TypeError):
                pass
        try:
            df = self._call_with_retry(func_name, call, fallback)
            if normalize is not None:
                df = normalize(df)
            if df is not None and not df.empty and "date" in df.columns:
                # 数据源日期类型不一（str/datetime.date/np.datetime64），统一为 YYYY-MM-DD
                df = df.copy()
                df["date"] = df["date"].astype(str).str.slice(0, 10)
            if ttl_seconds > 0 and df is not None and not df.empty:
                cache.set(key, df.to_json(orient="records", force_ascii=False), ttl_seconds)
            return df
        except DataSourceError:
            if not required:
                logger.warning("数据源 %s 失败，返回空表（非必需数据）", func_name)
                return pd.DataFrame()
            raise

    def _call_with_retry(self, func_name: str, call: Callable, fallback: Callable | None) -> pd.DataFrame:
        last_err: Exception | None = None
        delay = 1.5
        for attempt in range(1, 4):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001 数据源异常类型繁多，统一捕获
                last_err = exc
                logger.warning("akshare %s 第 %d 次失败: %s", func_name, attempt, exc)
                if fallback is not None:
                    try:
                        df = fallback()
                        logger.info("akshare %s 已降级到备用接口", func_name)
                        return df
                    except Exception as f_exc:  # noqa: BLE001
                        last_err = f_exc
                if attempt < 3:
                    time.sleep(delay)
                    delay *= 2
        raise DataSourceError(f"akshare {func_name} 3 次重试失败: {last_err}")

    # ---------------- 全市场快照 ----------------
    def fetch_spot_universe(self) -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(ak.stock_zh_a_spot_em)
        def fallback():
            df = ak.stock_zh_a_spot()  # 新浪
            # 新浪代码列带前缀（sh600000），剥离前缀统一
            if "代码" in df.columns:
                df["代码"] = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
            return df
        df = self._fetch("spot_em", "spot_em", primary, ttl_seconds=600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _SPOT_COLS))
        return _to_json_safe(df)

    def fetch_suspended(self) -> pd.DataFrame:
        today = time.strftime("%Y%m%d")
        def call():
            return self._call_with_timeout(ak.stock_tfp_em, date=today)
        df = self._fetch(f"tfp_em:{today}", "tfp_em", call, ttl_seconds=600,
                         normalize=lambda d: _normalize(d, _SUSPEND_COLS))
        return _to_json_safe(df)

    def fetch_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(
                ak.stock_zh_index_daily_em,
                symbol=symbol, start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
        def fallback():
            # 新浪指数日K（东财限流降级），客户端按日期区间过滤
            df = ak.stock_zh_index_daily(symbol=symbol)
            df["date"] = df["date"].astype(str)
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            keep = {"date", "open", "close", "high", "low", "volume"}
            return df[[c for c in df.columns if c in keep]]
        df = self._fetch(f"index_daily:{symbol}:{start_date}:{end_date}", "index_daily", primary,
                         ttl_seconds=3600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _INDEX_COLS))
        return _to_json_safe(df)

    # ---------------- 个股日 K ----------------
    def fetch_daily_kline(self, code: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(
                ak.stock_zh_a_hist, symbol=code, period="daily",
                start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""), adjust=adjust)
        def fallback():
            # 新浪日K（东财限流/宕机降级；列名已是英文，仅保留标准列）
            df = ak.stock_zh_a_daily(symbol=f"{_market_of(code)}{code}",
                                     start_date=start_date.replace("-", ""),
                                     end_date=end_date.replace("-", ""), adjust=adjust)
            keep = {"date", "open", "close", "high", "low", "volume", "amount"}
            out = df[[c for c in df.columns if c in keep]].copy()
            out["change_pct"] = out["close"].pct_change() * 100  # 新浪无涨跌幅列，按收盘价补算
            return out
        df = self._fetch(f"kline:{code}:{start_date}:{end_date}:{adjust}", "kline", primary,
                         ttl_seconds=3600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _KLINE_COLS))
        return _to_json_safe(df)

    # ---------------- 财务指标 ----------------
    def fetch_financial(self, code: str) -> pd.DataFrame:
        # 同花顺按单季度（主营收入同比/净利同比口径更准确），失败降级新浪
        def primary():
            return self._call_with_timeout(ak.stock_financial_abstract_ths, symbol=code, indicator="按单季度")
        def fallback():
            return self._call_with_timeout(ak.stock_financial_analysis_indicator, stock=code)
        df = self._fetch(f"fin:{code}", "fin", primary, ttl_seconds=86400, fallback=fallback,
                         normalize=lambda d: _normalize(
                             d, _FINANCIAL_THS_COLS if "报告期" in d.columns else _FINANCIAL_SINA_COLS))
        return _to_json_safe(df)

    # ---------------- 资金流向 ----------------
    def fetch_fund_flow(self, code: str) -> pd.DataFrame:
        market = _market_of(code)
        def call():
            return self._call_with_timeout(ak.stock_individual_fund_flow, stock=code, market=market)
        df = self._fetch(f"fundflow:{code}", "fundflow", call, ttl_seconds=1800,
                         normalize=lambda d: _normalize(d, _FUND_FLOW_COLS))
        return _to_json_safe(df)

    # ---------------- 新闻公告 ----------------
    def fetch_news(self, code: str) -> pd.DataFrame:
        def primary():
            # 新旧版本参数名兼容：新版 symbol / 旧版 stock
            try:
                return self._call_with_timeout(ak.stock_news_em, symbol=code)
            except TypeError:
                return self._call_with_timeout(ak.stock_news_em, stock=code)
        def fallback():
            return pd.DataFrame(columns=["title", "content", "published_at", "source", "url"])
        df = self._fetch(f"news:{code}", "news", primary, ttl_seconds=600, fallback=fallback,
                         normalize=lambda d: _normalize(
                             d, _NEWS_COLS if "新闻标题" in d.columns else _NEWS_COLS_OLD))
        return _to_json_safe(df)

    # ---------------- 行业板块 ----------------
    def fetch_industry_spot(self) -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(ak.stock_board_industry_name_em)
        def fallback():
            # 新浪行业板块（东财限流降级，列名与东财差异经 _BOARD_COLS 兼容）
            return self._call_with_timeout(ak.stock_sector_spot, indicator="新浪行业")
        df = self._fetch("industry_spot", "industry_spot", primary, ttl_seconds=600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _BOARD_COLS))
        return _to_json_safe(df)

    def fetch_industry_cons(self, board_name: str) -> pd.DataFrame:
        def call():
            return self._call_with_timeout(ak.stock_board_industry_cons_em, symbol=board_name)
        df = self._fetch(f"industry_cons:{board_name}", "industry_cons", call, ttl_seconds=3600,
                         normalize=lambda d: _normalize(d, _CONS_COLS))
        return _to_json_safe(df)

    # ---------------- 交易日历 ----------------
    def fetch_trade_calendar(self) -> list[str]:
        def call():
            df = ak.tool_trade_date_hist_sina()
            return df["trade_date"].astype(str).tolist()
        raw = cache.get("ak:trade_calendar")
        if raw:
            return raw.split(",")
        dates = self._call_with_retry("trade_calendar", call, None)
        cache.set("ak:trade_calendar", ",".join(dates), 86400)
        return dates

    def _call_with_timeout(self, func: Callable, *args, **kwargs):
        """优先传 timeout，接口签名不支持时降级不带超时调用"""
        try:
            return func(*args, **kwargs, timeout=settings.datasource_timeout)
        except TypeError:
            return func(*args, **kwargs)


def get_datasource() -> DataSource:
    return AkshareSource()
