from app.agents.position import _data_freshness, _plan_input_fingerprint


def test_position_input_fingerprint_changes_with_dynamic_input():
    base = {
        "indicators": {"latest_close": 10.0, "latest_date": "2026-09-07"},
        "capital": 100000.0,
    }
    first = _plan_input_fingerprint("600001", "2026-09-07",
                                    {"score": 80, "grade": "A"}, base)
    changed = {**base, "indicators": {**base["indicators"], "latest_close": 10.5}}
    second = _plan_input_fingerprint("600001", "2026-09-07",
                                     {"score": 80, "grade": "A"}, changed)
    assert first != second


def test_position_freshness_does_not_infer_realtime_from_grade():
    assert _data_freshness("2026-09-07", "2026-09-07") == "same_day_as_of"
    assert _data_freshness("2026-09-04", "2026-09-07") == "prior_close"
    assert _data_freshness("", "2026-09-07") == "unknown"
