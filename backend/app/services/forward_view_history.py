"""预测性选股 2.5：前瞻回填闭环（Discover 子 Agent 链路内嵌，纯统计零 LLM）

职责：
- save_forward_view：discover 前瞻三态（强/中性/弱）落库快照（code+date 唯一，重复更新；
  horizon_clarity=低 → missing_data 跳过，诚实不落库）
- fill_forward_view_actual：每日 16:00 回填 t5_pct_actual（复用 track_verify.t5_pct，不新算）
- calibrate_forward_view_prior：每周日 04:00 校准先验（回算近 30 日准确率写日志，不入库）
- compute_recent_forward_view_accuracy：近 lookback 日准确率统计（score_prompt 注入用，TTL 缓存）

红线：不调 LLM 预测数字（纯统计）；缺数据诚实 null/missing_data，不补 0 不补均值；
不改 6 因子权重；不覆盖 K 红线研判。
"""
import logging
from datetime import date, timedelta

from app.cache import cache
from app.db import repo

logger = logging.getLogger(__name__)

# horizon_bias → 前瞻三态（§3.5：强/中性/弱；延续/回归/回吐 由 discover LLM 输出）
_VIEW_BY_BIAS = {"延续": "强", "回归": "中性", "回吐": "弱"}
# clarity=低 → 预测数据不足（missing_data），不落库不参与校准
_MISSING_CLARITY = "低"
_CALIBRATION_TTL = 3600  # 前瞻先验摘要缓存（1 小时，防 score_prompt 逐股重算落库）


def save_forward_view(stock_code: str, trade_date: str, horizon_bias: str,
                      horizon_clarity: str, signals: dict | None = None) -> bool:
    """落库一条前瞻快照（幂等 upsert；trade_date+stock_code 唯一，重复则更新）。
    clarity=低 → missing_data 跳过；bias 未知 → 跳过。返回是否落库成功。"""
    clarity = (horizon_clarity or "").strip()
    if clarity == _MISSING_CLARITY:
        logger.info("前瞻快照跳过（missing_data，clarity=%s）: %s/%s", clarity, trade_date, stock_code)
        return False
    view = _VIEW_BY_BIAS.get((horizon_bias or "").strip())
    if view is None:
        logger.info("前瞻快照跳过（未知 bias=%s）: %s/%s", horizon_bias, trade_date, stock_code)
        return False
    repo.upsert_forward_view(stock_code, trade_date, view, signals or {})
    return True


def fill_forward_view_actual() -> dict:
    """每日 16:00 回填 t5_pct_actual（范围：选入日 ≤ today-5 且 IS NULL）。
    实际涨跌复用 track_verify.t5_pct（不新算）；无追踪行/无值 → 诚实留空跳过（不补 0）。"""
    cutoff = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    pending = repo.list_unfilled_forward_view(cutoff_date=cutoff)
    filled = 0
    for row in pending:
        actual = repo.get_track_verify_t5_pct(row["stock_code"], row["trade_date"])
        if actual is None:
            continue  # 追踪行无 T+5 数据（诚实留空，不补 0）
        repo.update_forward_view_actual(row["id"], actual, _accuracy_bucket(row["forward_view"], actual))
        filled += 1
    logger.info("前瞻T+5回填 %s: 填充 %s / 待回填 %s", cutoff, filled, len(pending))
    return {"filled": filled, "pending": len(pending), "cutoff": cutoff}


def _accuracy_bucket(forward_view: str, actual: float) -> str:
    """T+5 兑现判定（§3.5 口径）：correct / wrong / neutral"""
    if (forward_view == "强" and actual > 0) or (forward_view == "弱" and actual < 0):
        return "correct"
    if (forward_view == "强" and actual < -3) or (forward_view == "弱" and actual > 3):
        return "wrong"
    return "neutral"


def calibrate_forward_view_prior(lookback_days: int = 30) -> dict:
    """每周日 04:00 校准先验：回算近 lookback 日准确率写日志（不入库，供决策人参考）"""
    stats = compute_recent_forward_view_accuracy(lookback_days=lookback_days)
    logger.info("前瞻先验校准(%s日): %s", lookback_days, stats)
    return stats


def compute_recent_forward_view_accuracy(lookback_days: int = 30) -> dict:
    """近 lookback 日前瞻准确率（score_prompt 注入 / 校准 cron 用）。
    TTL 缓存 1 小时，避免逐股评分重复落库；无样本诚实返回 0 + n=0。"""
    key = f"forward:calibration:{lookback_days}"
    try:
        cached = cache.get(key)
        if cached:
            return cached
    except Exception:  # noqa: BLE001 缓存读失败直接重算
        pass
    stats = repo.compute_forward_view_accuracy(lookback_days=lookback_days)
    try:
        cache.set(key, stats, _CALIBRATION_TTL)
    except Exception:  # noqa: BLE001 缓存写失败不影响返回
        pass
    return stats


def get_forward_calibration_text(lookback_days: int = 30) -> str:
    """前瞻先验校准摘要文本（score_prompt 注入用；缺样本显「样本不足」不编造）。"""
    try:
        c = compute_recent_forward_view_accuracy(lookback_days=lookback_days)
    except Exception as exc:  # noqa: BLE001 读取失败不注入（不阻塞评分）
        logger.warning("前瞻先验读取失败（跳过注入）: %s", exc)
        return ""
    if not c.get("strong_n") and not c.get("weak_n"):
        return "样本不足，暂无前瞻准确率统计（不编造）。"
    lines = [f"前瞻强 准确率 {c['strong']:.0%}（{c['strong_n']} 样本）" if c.get("strong_n") else "前瞻强 暂无有效样本"]
    lines.append(f"前瞻弱 准确率 {c['weak']:.0%}（{c['weak_n']} 样本）" if c.get("weak_n") else "前瞻弱 暂无有效样本")
    return "；".join(lines)
