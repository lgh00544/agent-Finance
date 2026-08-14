"""移动止盈线 calc_trailing_stop 测试（批次1）：
1. 浮盈 <5% → None（沿用原固定止盈，不启用移动止盈）
2. 浮盈 ≥5% → 持仓期最高价 × 0.92
3. 移动止盈线不低于成本价（保底不亏）
4. 数据缺失/非法输入 → None（不编造）
"""
from app.services.take_profit import calc_trailing_stop


def test_below_5pct_returns_none():
    """浮盈不足 5%：返回 None（沿用原固定止盈）"""
    # 成本 10，现价 10.4（浮盈 4%），最高价 10.8
    assert calc_trailing_stop(10.0, 10.8, 10.4) is None
    # 最高价更高也不启用（门槛看浮盈）
    assert calc_trailing_stop(10.0, 12.0, 10.4) is None


def test_exact_5pct_enabled():
    """浮盈恰好 5%：启用（规则为「超过 5% 后启用」，5% 边界启用）"""
    # 成本 10，最高 12，现价 10.5（浮盈 5.0%）→ 12×0.92=11.04 > 成本，启用
    assert calc_trailing_stop(10.0, 12.0, 10.5) == 11.04


def test_over_5pct_uses_high_times_092():
    """浮盈超过 5%：移动止盈线 = 持仓期最高价 × 0.92"""
    # 成本 10，最高 12，现价 11（浮盈 10%）→ 12 × 0.92 = 11.04
    assert calc_trailing_stop(10.0, 12.0, 11.0) == 11.04
    # 现价 10.8（浮盈 8%）仍启用（最高价 12 不回落）
    assert calc_trailing_stop(10.0, 12.0, 10.8) == 11.04
    # 高位成本：最高 20，成本 18，现价 19 → 20×0.92 = 18.4 > 成本
    assert calc_trailing_stop(18.0, 20.0, 19.0) == 18.4


def test_trailing_line_not_below_cost():
    """移动止盈线不低于成本价（保底不亏）：最高价×0.92 < 成本时取成本"""
    # 成本 10，最高 10.6，现价 10.55（浮盈 5.5%）→ 10.6×0.92=9.752 < 10 → 保底 10
    assert calc_trailing_stop(10.0, 10.6, 10.55) == 10.0
    # 极端：最高价只比成本高 3%（浮盈 5.5% 但高点近）→ 仍保底成本价
    assert calc_trailing_stop(20.0, 21.1, 21.1) == 20.0


def test_missing_data_returns_none():
    """数据缺失/非法：返回 None，不编造"""
    assert calc_trailing_stop(10.0, None, 11.0) is None   # 无最高价
    assert calc_trailing_stop(10.0, 12.0, None) is None   # 无现价
    assert calc_trailing_stop(0.0, 12.0, 11.0) is None    # 成本 0
    assert calc_trailing_stop(10.0, 0.0, 11.0) is None    # 最高价 0
    assert calc_trailing_stop("x", 12.0, 11.0) is None    # 非法输入
    assert calc_trailing_stop(10.0, "y", 11.0) is None
    assert calc_trailing_stop(10.0, 12.0, "z") is None


def test_negative_price_returns_none():
    assert calc_trailing_stop(10.0, 12.0, -1.0) is None
    assert calc_trailing_stop(-5.0, 12.0, 11.0) is None
