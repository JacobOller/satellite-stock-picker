import pandas as pd

from satellite.risk import Position, add_suggested_sizes, satellite_exposure, suggested_position_size


def test_suggested_position_size_basic():
    assert suggested_position_size(10_000, max_allocation_pct=0.1) == 1_000


def test_satellite_exposure_empty():
    result = satellite_exposure([], account_value=10_000)
    assert result["position_count"] == 0
    assert result["total_value"] == 0
    assert result["pct_of_account"] == 0
    assert result["open_slots"] == 8  # default MAX_CONCURRENT_POSITIONS


def test_satellite_exposure_with_positions():
    positions = [Position("AAPL", 1000.0), Position("MSFT", 2000.0)]
    result = satellite_exposure(positions, account_value=10_000)
    assert result["position_count"] == 2
    assert result["total_value"] == 3000.0
    assert result["pct_of_account"] == 0.3
    assert result["open_slots"] == 6


def test_satellite_exposure_zero_account_value_no_divide_error():
    result = satellite_exposure([], account_value=0)
    assert result["pct_of_account"] is None


def test_add_suggested_sizes_attaches_columns():
    df = pd.DataFrame({"composite_score": [90, 80]}, index=["AAPL", "MSFT"])
    out = add_suggested_sizes(df, account_value=10_000, max_allocation_pct=0.1)
    assert (out["suggested_position_size"] == 1000).all()
    assert (out["suggested_position_pct"] == 0.1).all()
    # original columns untouched
    assert list(out["composite_score"]) == [90, 80]
