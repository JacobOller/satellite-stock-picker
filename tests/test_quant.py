import pandas as pd

from satellite.scoring.quant import score_quant


def _base_df():
    return pd.DataFrame(
        {
            "pe_ratio": [10.0, 30.0, 20.0],
            "pb_ratio": [1.0, 5.0, 3.0],
            "fcf_yield": [0.08, 0.02, 0.05],
            "momentum_3m": [0.2, -0.1, 0.05],
            "momentum_6m": [0.3, -0.2, 0.1],
            "roe": [0.2, 0.05, 0.1],
            "gross_margin": [0.5, 0.2, 0.35],
            "net_margin": [0.2, 0.05, 0.1],
            "roic": [0.2, 0.05, 0.1],
            "market_cap": [1e9, 5e11, 1e11],
        },
        index=["SMALL_CHEAP_STRONG", "MEGA_EXPENSIVE_WEAK", "MID"],
    )


def test_value_rank_favors_cheap():
    out = score_quant(_base_df())
    assert out.loc["SMALL_CHEAP_STRONG", "value"] > out.loc["MEGA_EXPENSIVE_WEAK", "value"]


def test_momentum_rank_favors_positive_momentum():
    out = score_quant(_base_df())
    assert out.loc["SMALL_CHEAP_STRONG", "momentum"] > out.loc["MEGA_EXPENSIVE_WEAK", "momentum"]


def test_size_rank_favors_smaller_market_cap():
    out = score_quant(_base_df())
    assert out.loc["SMALL_CHEAP_STRONG", "size"] > out.loc["MEGA_EXPENSIVE_WEAK", "size"]


def test_quant_score_is_average_of_subfactors():
    out = score_quant(_base_df())
    row = out.loc["MID"]
    expected = row[["value", "momentum", "quality", "size"]].mean()
    assert row["quant_score"] == expected
