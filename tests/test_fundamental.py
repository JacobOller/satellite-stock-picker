import pandas as pd

from satellite.scoring.fundamental import raw_fundamental_metrics, score_fundamentals


def test_raw_fundamental_metrics_clamps_negative_pe_pb_to_none():
    inputs = {
        "symbol": "X",
        "pe_ratio": -12.0,
        "pb_ratio": -3.0,
        "fcf_yield": 0.05,
        "roe": 0.1,
        "gross_margin": 0.4,
        "net_margin": 0.1,
        "roic": 0.08,
        "debt_to_equity": 0.5,
        "market_cap": 1e9,
    }
    result = raw_fundamental_metrics(inputs)
    assert result["pe_ratio"] is None
    assert result["pb_ratio"] is None
    assert result["fcf_yield"] == 0.05


def test_raw_fundamental_metrics_keeps_positive_pe_pb():
    inputs = {"symbol": "X", "pe_ratio": 15.0, "pb_ratio": 2.0}
    result = raw_fundamental_metrics(inputs)
    assert result["pe_ratio"] == 15.0
    assert result["pb_ratio"] == 2.0


def test_score_fundamentals_favors_cheap_high_quality():
    df = pd.DataFrame(
        {
            "pe_ratio": [10.0, 40.0],
            "pb_ratio": [1.0, 8.0],
            "fcf_yield": [0.08, 0.01],
            "roe": [0.25, 0.05],
            "gross_margin": [0.5, 0.2],
            "net_margin": [0.2, 0.02],
            "roic": [0.2, 0.03],
        },
        index=["CHEAP_QUALITY", "EXPENSIVE_WEAK"],
    )
    scores = score_fundamentals(df)
    assert scores["CHEAP_QUALITY"] > scores["EXPENSIVE_WEAK"]


def test_score_fundamentals_handles_missing_values():
    df = pd.DataFrame(
        {
            "pe_ratio": [10.0, None],
            "pb_ratio": [1.0, None],
            "fcf_yield": [0.08, None],
            "roe": [0.25, 0.1],
            "gross_margin": [0.5, 0.3],
            "net_margin": [0.2, 0.1],
            "roic": [0.2, 0.1],
        },
        index=["A", "B"],
    )
    scores = score_fundamentals(df)
    assert scores.notna().all()
