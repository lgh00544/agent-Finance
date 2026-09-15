from app.services.market_condition_aware_weight import (
    FACTOR_DIMENSIONS,
    WEIGHT_PROFILES,
    resolve_weights,
)


def test_four_fixed_profiles_are_complete_and_sum_to_one():
    assert set(WEIGHT_PROFILES) == {"牛市", "熊市", "震荡市", "防御市"}
    for profile in WEIGHT_PROFILES.values():
        assert tuple(profile) == FACTOR_DIMENSIONS
        assert sum(profile.values()) == 1.0


def test_actual_market_bands_switch_profiles():
    strong, _ = resolve_weights({"band": "强势期"})
    mild, _ = resolve_weights({"band": "温和期"})
    transition, _ = resolve_weights({"band": "过渡期"})
    defense, _ = resolve_weights({"band": "防御期"})
    assert strong == WEIGHT_PROFILES["牛市"]
    assert mild == WEIGHT_PROFILES["震荡市"]
    assert transition == WEIGHT_PROFILES["熊市"]
    assert defense == WEIGHT_PROFILES["防御市"]


def test_missing_or_unknown_market_condition_returns_reason():
    assert resolve_weights(None) == (None, "MarketCondition 缺失")
    weights, reason = resolve_weights({"band": "未知"})
    assert weights is None and "未知市况档位" in reason
