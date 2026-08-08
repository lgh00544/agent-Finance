"""持仓止盈/仓位管理计算服务测试（纯计算不触网，告警通道用 mock 验证）：
1. compute_plan 正常模式：TP1=min(前高,成本+10%)/TP2=黄金分割共振/阶梯止损/移动止盈/仓位指引
2. 降级模式（无K线）：固定比例估算，不报错不误导
3. 状态标签判定与优先级：接近止损 > 减仓预警 > 接近止盈 > 持有观察
4. C1 单票仓位红线校验
5. build_plans 同源入口（mock 行情视图）：行结构完整
6. 接近止盈/止盈触发告警通道：按日去重只推一次
"""
import pytest

from app.services import take_profit


def _row(cost=10.0, price=10.5, shares=1000, stop_loss=0.0, total_capital=100000.0,
          code="600001", name="测试A", mid=1):
    return {"id": mid, "stock_code": code, "stock_name": name,
            "entry_price": cost, "shares": shares, "current_price": price,
            "market_value": price * shares, "stop_loss": stop_loss,
            "take_profit": 0.0, "total_capital": total_capital}


def _ind(high=12.0, low=9.0, ma5=10.2, ma10=10.0, ma20=9.8, vol=1.0):
    return {"high_20d": high, "low_20d": low, "ma5": ma5, "ma10": ma10, "ma20": ma20,
            "volume_ratio_5": vol}


def test_compute_plan_normal_mode_points():
    """正常模式：TP1 = min(前高 12.0, 成本×1.10=11.0) = 11.0；
    TP2 = 黄金分割扩展 max(12.0+(12.0-9.0)×0.618, 12.0) ≈ 13.85；
    阶梯止损 = 成本 10.0 / TP1 11.0；C3 硬止损 = 9.2"""
    p = take_profit.compute_plan(_row(), _ind())
    assert p["tp1"] == 11.0
    assert p["tp2"] == round(12.0 + 3.0 * 0.618, 2) == 13.85
    assert p["c3_stop"] == 9.2
    assert p["current_stop"] == 9.2
    assert p["ladder_stop_1"] == 10.0
    assert p["ladder_stop_2"] == 11.0
    assert p["trailing_line"] == 10.2  # MA5
    assert p["degraded"] is False
    assert p["single_pct"] == 10.5
    assert p["c1_ok"] is True
    assert p["support"] == 9.0


def test_compute_plan_tp1_floor_and_tighter_manual_stop():
    """前高低于成本+8% 时 TP1 有保底下限；手动止损更严格（更高价）时以手动为准"""
    p = take_profit.compute_plan(_row(price=10.2), _ind(high=10.3, low=9.5))
    assert p["tp1"] == round(10.0 * 1.08, 2) == 10.8  # 前高 10.3 太低 → 保底 10.8
    p2 = take_profit.compute_plan(_row(price=10.5, stop_loss=9.5), _ind())
    assert p2["current_stop"] == 9.5  # 手动 9.5 高于 C3 9.2 → 更严，以手动为准
    assert p2["c3_stop"] == 9.2       # 硬底线仍展示


def test_compute_plan_status_labels():
    """状态标签优先级：接近止损 > 减仓预警 > 接近止盈 > 持有观察"""
    # 接近止损：现价 ≤ 止损×(1+3%)
    p = take_profit.compute_plan(_row(price=9.4), _ind())
    assert p["status"] == "接近止损" and p["status_tone"] == "err"
    # 减仓预警：跌破 MA10
    p = take_profit.compute_plan(_row(price=9.9), _ind(ma10=10.0))
    assert p["status"] == "减仓预警" and p["status_tone"] == "err"
    # 接近止盈：现价 ≥ TP1×(1-3%)
    p = take_profit.compute_plan(_row(price=10.7), _ind())
    assert p["status"] == "接近止盈" and p["status_tone"] == "warn"
    # 持有观察
    p = take_profit.compute_plan(_row(price=10.5), _ind())
    assert p["status"] == "持有观察" and p["status_tone"] == "info"


def test_compute_plan_position_guidance():
    """加仓需回调支撑+缩量；追高禁止；波段减仓需跌破 MA10+量能放大"""
    # 回调至支撑位附近 + 缩量 → 可加仓
    p = take_profit.compute_plan(_row(price=9.1), _ind(low=9.0, ma5=9.4, ma10=9.3, vol=0.8))
    assert p["add_condition"] and "可加仓至单票仓位上限 30%" in p["add_condition"]
    # 现价高于 MA5×1.03 → 追高风险，不建议加仓
    p = take_profit.compute_plan(_row(price=10.8), _ind(ma5=10.2))
    assert p["add_condition"] and "追高风险" in p["add_condition"]
    # 跌破 MA10 + 量能放大 → 先减半
    p = take_profit.compute_plan(_row(price=9.6), _ind(ma10=10.0, vol=1.5))
    assert p["reduce_condition"] and "先行减仓一半" in p["reduce_condition"]
    # C1 超限
    p = take_profit.compute_plan(_row(shares=5000, price=10.0, total_capital=100000.0), _ind())
    assert p["single_pct"] == 50.0 and p["c1_ok"] is False


def test_compute_plan_degraded_mode():
    """无K线（指标为空）→ 降级：固定比例估算，不报错；无均线信息"""
    p = take_profit.compute_plan(_row(), {})
    assert p["degraded"] is True
    assert p["tp1"] == 11.0 and p["tp2"] == 12.5
    assert p["ma5"] is None and p["support"] is None
    assert p["status"] in ("持有观察", "接近止盈")


def test_build_plans_same_source_entry(monkeypatch):
    """build_plans 入口：行情视图与持仓监控同源（mock），行结构完整；K线失败降级"""
    from app.services import holding_view
    fake_view = {"rows": [_row(cost=10.0, price=10.5, shares=1000, total_capital=100000.0)],
                 "quote_time": "2026-08-09 10:00", "quote_error": None, "total_capital": 100000.0}
    monkeypatch.setattr(holding_view, "build_holding_view", lambda: fake_view)

    class _NoNet:
        def fetch_daily_kline(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr(take_profit, "get_datasource", lambda: _NoNet())
    monkeypatch.setattr(take_profit, "_recent_anomaly", lambda code: False)

    result = take_profit.build_plans(trace=False, check_alerts=False)
    assert len(result["rows"]) == 1
    plan = result["rows"][0]
    assert plan["stock_code"] == "600001"
    assert plan["degraded"] is True
    assert plan["total_pct"] == 10.5
    assert plan["anomaly"] is False
    # 第二次调用命中缓存（结果结构一致）
    again = take_profit.build_plans(trace=False, check_alerts=False)
    assert again["rows"][0]["tp1"] == plan["tp1"]


def test_tp_alert_channel_deduplicated(monkeypatch):
    """接近止盈/止盈触发告警：独立通道写入，按 代码+日期 去重只推一次"""
    inserted = []
    monkeypatch.setattr(take_profit.repo, "insert_alert",
                        lambda *a, **k: inserted.append((a[0], a[2])) or 1)
    hit = {"stock_code": "600002", "stock_name": "测试B", "current_price": 11.0,
           "tp1": 10.0, "tp2": 12.0, "ladder_stop_1": 9.0}
    near = {"stock_code": "600003", "stock_name": "测试C", "current_price": 9.8,
            "tp1": 10.0, "tp2": 12.0, "ladder_stop_1": 9.0}
    take_profit._check_tp_alerts(hit)
    take_profit._check_tp_alerts(hit)      # 同日重复 → 去重不推
    take_profit._check_tp_alerts(near)
    take_profit._check_tp_alerts(near)
    assert [i[1] for i in inserted] == ["止盈触发", "接近止盈"]
