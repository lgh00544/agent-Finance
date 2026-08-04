"""
数据源抽象层：DataSource 协议 + 统一错误类型
实现类：akshare_source.AkshareSource（也可扩展 tushare_source 兼容）
统一职责：拉取原始数据 → 列名规范化为英文标准字段 → 返回 DataFrame
【刚性代码逻辑】本层不做任何市场判断，只做数据采集与规整。
"""
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataSourceError(RuntimeError):
    """数据源不可用（网络/限流/接口变更），调用方应降级或跳过"""


class DataSource(ABC):
    """数据源协议：全部返回列名规范化的 pandas DataFrame"""

    # ---------- 全市场/大盘 ----------
    @abstractmethod
    def fetch_spot_universe(self) -> pd.DataFrame:
        """全市场实时快照（东财，列：code/name/price/change_pct/volume/amount/...）"""

    @abstractmethod
    def fetch_suspended(self) -> pd.DataFrame:
        """当日停复牌列表（列：code/name/stop_reason/...）"""

    @abstractmethod
    def fetch_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """大盘指数日线（列：date/open/close/high/low/volume）"""

    @abstractmethod
    def fetch_index_spot(self) -> pd.DataFrame:
        """三大指数实时行情（列：code/name/price/change_pct；sh000001/sz399001/sz399006）"""

    # ---------- 个股 ----------
    @abstractmethod
    def fetch_spot_quote(self, code: str) -> dict:
        """单股实时行情（TTL 30s；返回 code/name/price/change_pct/time，全部失败返回 {}）"""

    @abstractmethod
    def fetch_daily_kline(self, code: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        """个股日 K（列：date/open/close/high/low/volume/amount/change_pct/turnover_rate）"""

    @abstractmethod
    def fetch_financial(self, code: str) -> pd.DataFrame:
        """财务指标（列：report_date/roe/revenue_yoy/profit_yoy/gross_margin/debt_ratio/...）"""

    @abstractmethod
    def fetch_fund_flow(self, code: str) -> pd.DataFrame:
        """个股资金流向（列：date/main_net_inflow/main_net_pct/...）"""

    @abstractmethod
    def fetch_news(self, code: str) -> pd.DataFrame:
        """个股新闻公告（列：title/content/published_at/source/url）"""

    @abstractmethod
    def fetch_industry_spot(self) -> pd.DataFrame:
        """行业板块行情（列：board_name/change_pct/...）"""

    @abstractmethod
    def fetch_industry_cons(self, board_name: str) -> pd.DataFrame:
        """行业成分股（列：code/name/...）"""

    # ---------- 交易日历 ----------
    @abstractmethod
    def fetch_trade_calendar(self) -> list[str]:
        """最近 N 个交易日列表（YYYY-MM-DD），用于调度只跑交易日"""


def to_float(value: Any, default: float = 0.0) -> float:
    """安全转浮点（DataFrame 里的 NaN/- 等脏值）"""
    try:
        if value is None or (isinstance(value, float) and value != value):  # NaN
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_get(df: pd.DataFrame, *candidates: str, default: Any = None) -> Any:
    """从 DataFrame 按候选列名取首个非空值（处理 akshare 列名漂移）"""
    for col in candidates:
        if col in df.columns:
            values = df[col].dropna()
            if len(values) > 0:
                return values.iloc[0]
    return default
