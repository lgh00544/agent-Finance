"""
数据源工厂与降级包装（麦蕊智数增强源装配点）

设计约束（与 v2.0 补强一致）：
  - 基础数据（全市场快照/日K/新闻/行业/财务/交易日历）：仅走 akshare 主源
    （其内部已有东财→新浪双通道降级），不调用麦蕊，避免消耗配额；
  - 高级字段（资金流/股东户数）：麦蕊优先（MAIRUI_ENABLE=true 时）→ 失败回退 akshare，
    全程中文日志记录原因，不报错中断主链路；
  - 默认关闭（MAIRUI_ENABLE=false）时 get_datasource() 直接返回 akshare 实例，
    无任何额外依赖与性能损耗，行为与之前完全一致。
上层业务代码（Agent 节点）不感知具体数据源，只依赖本工厂（数据源抽象层规范）。
【刚性代码逻辑】只做数据源装配与降级转发，不做任何市场判断。
"""
import logging

import pandas as pd

from app.core.config import settings
from app.datasource.akshare_source import AkshareSource
from app.datasource.base import DataSource
from app.datasource.mairui_source import MairuiSource

logger = logging.getLogger(__name__)


class FallbackSource(DataSource):
    """包装主源（akshare）+ 增强源（麦蕊，可空）：高级字段优先增强源，失败回退主源"""

    def __init__(self, primary: AkshareSource, extra: MairuiSource | None = None) -> None:
        self._primary = primary
        self._extra = extra

    # ---------------- 基础数据：仅走主源（不消耗麦蕊配额） ----------------
    def fetch_spot_universe(self) -> pd.DataFrame:
        return self._primary.fetch_spot_universe()

    def fetch_suspended(self) -> pd.DataFrame:
        return self._primary.fetch_suspended()

    def fetch_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._primary.fetch_index_daily(symbol, start_date, end_date)

    def fetch_daily_kline(self, code: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        return self._primary.fetch_daily_kline(code, start_date, end_date, adjust)

    def fetch_financial(self, code: str) -> pd.DataFrame:
        return self._primary.fetch_financial(code)

    def fetch_news(self, code: str) -> pd.DataFrame:
        return self._primary.fetch_news(code)

    def fetch_industry_spot(self) -> pd.DataFrame:
        return self._primary.fetch_industry_spot()

    def fetch_index_spot(self) -> pd.DataFrame:
        return self._primary.fetch_index_spot()

    def fetch_spot_quote(self, code: str) -> dict:
        return self._primary.fetch_spot_quote(code)

    def fetch_industry_cons(self, board_name: str) -> pd.DataFrame:
        return self._primary.fetch_industry_cons(board_name)

    def fetch_trade_calendar(self) -> list[str]:
        return self._primary.fetch_trade_calendar()

    def fetch_stock_info(self, code: str) -> dict:
        return self._primary.fetch_stock_info(code)

    def fetch_institute_hold_map(self) -> dict[str, dict]:
        return self._primary.fetch_institute_hold_map()

    def fetch_market_fund_flow(self) -> dict:
        return self._primary.fetch_market_fund_flow()

    # ---------------- 高级字段：麦蕊优先 → akshare 回退 ----------------
    def fetch_fund_flow(self, code: str) -> pd.DataFrame:
        if self._extra is not None:
            df = self._extra.fetch_fund_flow(code)
            if df is not None and not df.empty:
                logger.info("资金流 %s 已由麦蕊提供", code)
                return df
            logger.warning("资金流 %s 麦蕊数据不可用，回退 akshare", code)
        return self._primary.fetch_fund_flow(code)

    def fetch_shareholder_detail(self, code: str) -> dict:
        if self._extra is not None:
            out = self._extra.fetch_shareholder_detail(code)
            if out:
                logger.info("股东户数 %s 已由麦蕊提供", code)
                return out
            logger.warning("股东户数 %s 麦蕊数据不可用，回退 akshare", code)
        return self._primary.fetch_shareholder_detail(code)


def get_datasource() -> DataSource:
    """数据源工厂：默认仅 akshare（零额外依赖）；MAIRUI_ENABLE=true 时装配麦蕊增强包装"""
    primary = AkshareSource()
    if not settings.mairui_enable:
        return primary
    try:
        extra = MairuiSource()
        logger.info("麦蕊增强数据源已启用（MAIRUI_ENABLE=true），高级字段优先取麦蕊")
        return FallbackSource(primary, extra)
    except Exception as exc:  # noqa: BLE001 装配失败不阻塞主链路
        logger.warning("麦蕊数据源装配失败，仅使用 akshare: %s", exc)
        return primary
