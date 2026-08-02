from satellite.data.fundamentals_finnhub import extract_factor_inputs


def test_extract_factor_inputs_maps_known_fields():
    raw = {
        "symbol": "X",
        "profile": {"marketCapitalization": 5000.0, "finnhubIndustry": "Technology"},
        "metric": {"peTTM": 22.5, "pbAnnual": 4.0, "roeTTM": 0.18},
    }
    result = extract_factor_inputs(raw)
    assert result["market_cap"] == 5000.0
    assert result["sector"] == "Technology"
    assert result["pe_ratio"] == 22.5
    assert result["pb_ratio"] == 4.0
    assert result["roe"] == 0.18
    assert result["fcf_yield"] is None


def test_extract_factor_inputs_missing_fields_are_none():
    raw = {"symbol": "X", "profile": {}, "metric": {}}
    result = extract_factor_inputs(raw)
    assert result["pe_ratio"] is None
    assert result["roic"] is None
    assert result["market_cap"] is None
