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
_INST_COLS = {"证券代码": "code", "证券简称": "name", "机构数": "inst_count",
              "机构数变化": "inst_change", "持股比例": "hold_pct",
              "持股比例增幅": "hold_pct_change", "占流通股比例": "float_pct",
              "占流通股比例增幅": "float_pct_change"}
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
        df = self._fetch("spot_em", "spot_em", primary, ttl_seconds=60, fallback=fallback,
                         normalize=lambda d: _normalize(d, _SPOT_COLS))
        return _to_json_safe(df)

    # ---------------- 单股实时行情（持仓监控链路，60s 内缓存） ----------------
    def fetch_spot_quote(self, code: str) -> dict:
        """单股最新实时行情【刚性代码逻辑】：东财盘口 → 雪球单股 → 全市场快照匹配；
        TTL 30s 确保监控每次执行拿到最新价；全部失败返回 {}（调用方用日K收盘兜底并标注）。
        返回 {"code","name","price","change_pct","time"}，price/change_pct 解析失败为 None。
        """
        def parse_bid_ask(df: pd.DataFrame) -> pd.DataFrame:
            # 东财盘口 item/value 列（最新价/涨幅）；构造为标准单行；解析失败返回空表（不缓存坏数据）
            kv = {str(r["item"]): r["value"] for _, r in df.iterrows()}
            try:
                price = float(kv["最新"])
                change_pct = float(kv.get("涨幅") or kv.get("涨跌幅") or 0.0)
            except (TypeError, ValueError, KeyError):
                return pd.DataFrame()
            return pd.DataFrame([{"code": code, "name": kv.get("名称"), "price": price,
                                  "change_pct": change_pct,
                                  "time": kv.get("时间") or kv.get("最新时间") or ""}])

        def parse_xq(df: pd.DataFrame) -> pd.DataFrame:
            kv = {str(r["item"]): r["value"] for _, r in df.iterrows()}
            try:
                price = float(kv["现价"])
                change_pct = float(kv.get("涨幅") or 0.0)
            except (TypeError, ValueError, KeyError):
                return pd.DataFrame()
            return pd.DataFrame([{"code": code, "name": kv.get("名称"), "price": price,
                                  "change_pct": change_pct, "time": kv.get("时间") or ""}])

        def primary():
            return parse_bid_ask(self._call_with_timeout(ak.stock_bid_ask_em, symbol=code))

        def fallback():
            # 雪球单股（独立于东财/新浪的轻量实时源，请求开销低）
            prefix = "SH" if code.startswith("6") else ("BJ" if code.startswith(("4", "8", "9")) else "SZ")
            return parse_xq(ak.stock_individual_spot_xq(symbol=f"{prefix}{code}"))

        df = self._fetch(f"spot_quote:{code}", "spot_quote", primary, ttl_seconds=30,
                         fallback=fallback, required=False)
        if df is None or df.empty:
            quote = self._quote_from_universe(code)
        else:
            row = df.iloc[0]
            quote = {"code": code, "name": str(row.get("name") or ""),
                     "price": float(row["price"]),
                     "change_pct": float(row.get("change_pct") or 0.0),
                     "time": str(row.get("time") or "")}
        return quote

    def _quote_from_universe(self, code: str) -> dict:
        """第三级兜底：全市场快照匹配该股实时行情（快照本身东财→新浪双降级，缓存复用）"""
        try:
            df = self.fetch_spot_universe()
            if df is None or df.empty or "code" not in df.columns:
                return {}
            row = df[df["code"].astype(str) == code]
            if row.empty:
                return {}
            r = row.iloc[0]
            try:
                price = float(r.get("price"))
            except (TypeError, ValueError):
                price = None
            try:
                change_pct = float(r.get("change_pct"))
            except (TypeError, ValueError):
                change_pct = None
            return {"code": code, "name": str(r.get("name") or ""), "price": price,
                    "change_pct": change_pct, "time": ""}
        except Exception as exc:  # noqa: BLE001 兜底失败返回空，调用方走日K收盘
            logger.warning("快照匹配实时行情失败 %s: %s", code, exc)
            return {}

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

    def fetch_index_spot(self) -> pd.DataFrame:
        """三大指数实时行情（东财指数快照：上证系列 + 深证系列，60s 缓存防限流）；
        顶部状态栏使用，返回含 code/name/price/change_pct 的 DataFrame"""
        def call():
            parts = [
                ak.stock_zh_index_spot_em(symbol="上证系列指数"),
                ak.stock_zh_index_spot_em(symbol="深证系列指数"),
            ]
            return pd.concat(parts, ignore_index=True)
        def fallback():
            # 新浪指数快照（东财限流/宕机降级）；代码列带 sh/sz 前缀，与东财格式一致，保留供下方 keep 过滤
            return ak.stock_zh_index_spot_sina()
        df = self._fetch("index_spot", "index_spot", call, ttl_seconds=60, fallback=fallback,
                         required=False,
                         normalize=lambda d: _normalize(d, _SPOT_COLS))
        if df is None or df.empty or "code" not in df.columns:
            return pd.DataFrame(columns=["code", "name", "price", "change_pct"])
        keep = {"sh000001", "sz399001", "sz399006"}  # 上证指数/深证成指/创业板指
        out = df[df["code"].astype(str).isin(keep)]
        return _to_json_safe(out)

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

    # ---------------- 个股增量数据（v2.0 候选富化） ----------------
    def fetch_stock_info(self, code: str) -> dict:
        """个股基本信息（item/value 两列 → dict，含 行业/上市时间等）；失败返回 {}"""
        def call():
            return self._call_with_timeout(ak.stock_individual_info_em, symbol=code)
        df = self._fetch(f"stockinfo:{code}", "stockinfo", call, ttl_seconds=86400, required=False)
        if df is None or df.empty or "item" not in df.columns:
            return {}
        return {str(k): v for k, v in zip(df["item"].astype(str), df["value"]) if k is not None}

    def fetch_shareholder_detail(self, code: str) -> dict:
        """股东户数最新一期（户数/较上期增减比例等）；失败返回 {}"""
        def call():
            return self._call_with_timeout(ak.stock_zh_a_gdhs_detail_em, symbol=code)
        df = self._fetch(f"gdhs:{code}", "gdhs", call, ttl_seconds=86400, required=False)
        if df is None or df.empty:
            return {}
        row = df.iloc[0]
        out: dict = {}
        for cn, key in [("股东户数统计截止日期", "report_date"), ("股东户数-本次", "holder_count"),
                        ("股东户数-上次", "holder_prev"), ("股东户数-增减", "holder_diff"),
                        ("股东户数-增减比例", "holder_change_pct")]:
            if cn in df.columns:
                out[key] = row[cn]
        return out

    def fetch_institute_hold_map(self) -> dict[str, dict]:
        """机构持股全景（全市场一次拉取，缓存 6 小时）→ {code: {hold_pct, float_pct}}；失败返回 {}"""
        def call():
            return ak.stock_institute_hold()
        df = self._fetch("inst_hold", "inst_hold", call, ttl_seconds=21600, required=False,
                         normalize=lambda d: _normalize(d, _INST_COLS))
        if df is None or df.empty or "code" not in df.columns:
            return {}
        return {str(r["code"]).zfill(6): {"hold_pct": r.get("hold_pct"),
                                          "float_pct": r.get("float_pct")}
                for _, r in df.iterrows()}

    def fetch_market_fund_flow(self) -> dict:
        """大盘资金流（东财）：最新一日各指数主力净流入/净占比摘要；失败返回 {}（非必需数据）"""
        def call():
            return ak.stock_market_fund_flow()
        df = self._fetch("mkt_flow", "mkt_flow", call, ttl_seconds=600, required=False)
        if df is None or df.empty:
            return {}
        row = df.iloc[-1]
        summary: dict = {"date": str(row.get("日期", ""))}
        for col in df.columns:
            if "主力净流入" in str(col):
                summary[str(col)] = row[col]
        return summary

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
