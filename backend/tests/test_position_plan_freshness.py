"""Plan generation must persist the timestamp of the supplied price facts."""
import pytest

from app.agents import position
from app.agents.schemas import PositionOutput
from app.services import sector_rotation_pattern


@pytest.mark.parametrize("indicators,expected_status,expected_date", [
    ({"latest_close": 10, "latest_date": "2026-09-08"}, "same_day_as_of", "2026-09-08"),
    ({"latest_close": 10, "latest_date": "2026-09-07"}, "prior_close", "2026-09-07"),
    ({}, "unknown", None),
])
def test_plan_persists_fact_freshness(monkeypatch, indicators, expected_status, expected_date):
    output = PositionOutput(
        stock_code="600001", market_regime="test", total_pct=10,
        batches=[{"tranche": 1, "price_zone": "9.8~10.2", "ratio_pct": 10,
                  "trigger_note": "test"}],
        stop_loss=9.2, take_profit=12, rationale="test",
    )
    saved = {}
    quant_inputs = []

    def fake_quantify(*args):
        quant_inputs.append(args)
        return {"current_price": args[-2]}

    def fake_insert(*args, **kwargs):
        saved.update(kwargs)
        return 123

    monkeypatch.setattr(position, "agent_call", lambda **kwargs: output)
    monkeypatch.setattr(sector_rotation_pattern, "build_regime_context", lambda date: "")
    monkeypatch.setattr(position.plan_quant, "quantify", fake_quantify)
    monkeypatch.setattr(position.repo, "insert_plan", fake_insert)

    result = position.llm_plan({
        "stock_code": "600001", "stock_name": "TestStock", "trade_date": "2026-09-08",
        "score_result": {"grade": "B", "score": 60, "detail": {}, "risk_list": []},
        "basic_info": {"indicators": indicators}, "plan_source": "candidate", "trace": [],
    })

    assert result["position_plan"]["plan_id"] == 123
    assert result["stage"] == "plan_position"
    assert saved["source"] == "candidate"
    assert saved["detail"]["freshness"] == expected_status
    assert saved["detail"]["data_as_of"] == expected_date
    assert saved["detail"]["analysis_generated_at"]
    assert quant_inputs[0][-1] == (expected_date or "")
    assert quant_inputs[0][-2] == indicators.get("latest_close", 0)
