"""MarketCondition 到六因子固定权重的只读映射。"""
from collections.abc import Mapping
from typing import Any

FACTOR_DIMENSIONS = ("动量", "催化", "估值", "资金", "质量", "主线")

WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "牛市": {"动量": 0.30, "催化": 0.25, "估值": 0.10, "资金": 0.20, "质量": 0.05, "主线": 0.10},
    "熊市": {"动量": 0.10, "催化": 0.05, "估值": 0.25, "资金": 0.10, "质量": 0.30, "主线": 0.20},
    "震荡市": {"动量": 0.20, "催化": 0.15, "估值": 0.20, "资金": 0.20, "质量": 0.10, "主线": 0.15},
    "防御市": {"动量": 0.05, "催化": 0.05, "估值": 0.30, "资金": 0.05, "质量": 0.35, "主线": 0.20},
}

BAND_TO_PROFILE = {
    "强势期": "牛市",
    "温和期": "震荡市",
    "过渡期": "熊市",
    "防御期": "防御市",
    "强势": "牛市",
    "牛市": "牛市",
    "震荡": "震荡市",
    "震荡市": "震荡市",
    "熊市": "熊市",
    "防御": "防御市",
    "防御市": "防御市",
}


def resolve_weights(market_condition: Mapping[str, Any] | None) -> tuple[dict[str, float] | None, str]:
    """解析市况档位，返回副本与降级原因。"""
    if not market_condition:
        return None, "MarketCondition 缺失"
    band = str(market_condition.get("band") or "").strip()
    if not band:
        return None, "MarketCondition 未提供 band"
    profile_name = BAND_TO_PROFILE.get(band)
    if profile_name is None:
        return None, f"未知市况档位: {band}"
    return dict(WEIGHT_PROFILES[profile_name]), ""


def build_weight_context(market_condition: Mapping[str, Any] | None) -> str:
    """构造注入评分模型的紧凑权重上下文。"""
    weights, reason = resolve_weights(market_condition)
    if weights is None:
        return f"动态因子权重不可用（{reason}），沿用模型默认权重。"
    band = str(market_condition.get("band") or "").strip()
    text = "；".join(f"{name} {weights[name]:.2f}" for name in FACTOR_DIMENSIONS)
    return f"MarketCondition={band}；固定动态因子权重：{text}。仅作评分参考，不改变硬规则。"


get_market_condition_weights = resolve_weights
