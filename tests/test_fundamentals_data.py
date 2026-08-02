from satellite.data.fundamentals import extract_factor_inputs


def test_extract_factor_inputs_uses_first_available_key():
    raw = {
        "symbol": "X",
        "profile": {"marketCap": 123.0, "sector": "Tech"},
        "ratios_ttm": {"peRatioTTM": 15.0},  # only fallback key present, not priceToEarningsRatioTTM
        "key_metrics_ttm": {},
    }
    result = extract_factor_inputs(raw)
    assert result["market_cap"] == 123.0
    assert result["sector"] == "Tech"
    assert result["pe_ratio"] == 15.0


def test_extract_factor_inputs_missing_fields_are_none():
    raw = {"symbol": "X", "profile": {}, "ratios_ttm": {}, "key_metrics_ttm": {}}
    result = extract_factor_inputs(raw)
    assert result["pe_ratio"] is None
    assert result["roic"] is None
