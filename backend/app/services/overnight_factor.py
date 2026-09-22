"""美股隔夜因子（只读观察因子，不参与现有决策链路）

【刚性代码逻辑】只做行情聚合与分档统计，不含任何市场判断。
  - 21:30 拉配置的美股列表 → 等权平均涨跌幅 → 分档（低开/偏空/噪声区/偏多/高开）
  - prediction 仅档位映射：低开/高开押注方向，其余不押注
  - 内部一致性：up_count<=3 且因子为正 → notes 提示"假信号，被个别票拉起，降权"
"""
from statistics import mean

from app.core.config import settings
from app.datasource import us_quote
from app.db import repo


def _band_of(factor_value: float) -> str:
    """涨跌幅分档（边界按 > 与 <= 处理避免重叠）"""
    if factor_value <= -2.0:
        return "低开"
    if factor_value <= -0.8:
        return "偏空"
    if factor_value < 0.8:
        return "噪声区"
    if factor_value < 2.0:
        return "偏多"
    return "高开"


def _prediction_of(band: str) -> str:
    """档位 → 押注方向：偏空/低开押低开，偏多/高开押高开，噪声区不押注

    对齐回测口径：偏空档高开概率 34.6%（低开 65.4%）、偏多档高开概率 61.1%，
    均明显偏离抛硬币，纳入押注；仅 |因子|<0.8% 噪声区明确不押注。
    """
    if band in ("低开", "偏空"):
        return "低开"
    if band in ("偏多", "高开"):
        return "高开"
    return "不押注"


def compute_overnight_factor(trade_date: str | None = None) -> dict:
    """拉取配置的美股列表 → 等权平均涨跌幅 → 分档/押注/统计 → 组装 dict"""
    stocks = [s.strip() for s in settings.overnight_factor_stocks.split(",") if s.strip()]
    quotes = us_quote.fetch_us_quotes(stocks)
    pcts = [q["change_pct"] for q in quotes if q.get("change_pct") is not None]
    factor_value = round(mean(pcts), 4) if pcts else 0.0
    band = _band_of(factor_value)
    prediction = _prediction_of(band)
    up_count = sum(1 for p in pcts if p > 0)
    notes = None
    if up_count <= 3 and factor_value > 0:
        notes = "假信号，被个别票拉起，降权"
    result = {
        "factor_value": factor_value,
        "band": band,
        "prediction": prediction,
        "up_count": up_count,
        "stocks_detail": quotes,
        "notes": notes,
    }
    if trade_date:
        result["trade_date"] = trade_date
    return result


def get_latest() -> dict | None:
    """最新一条隔夜因子（含全部字段，stocks_detail 原样返回）"""
    return repo.get_latest_us_overnight_factor()


def get_history(limit: int = 10) -> list[dict]:
    """最近 N 条隔夜因子历史（按 trade_date 倒序）"""
    return repo.get_us_overnight_factor_history(limit)
