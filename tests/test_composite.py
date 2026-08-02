import pandas as pd

from satellite.scoring.composite import compute_composite_scores


def _fundamental_df():
    return pd.DataFrame(
        {
            "pe_ratio": [10.0, 30.0],
            "pb_ratio": [1.0, 5.0],
            "fcf_yield": [0.08, 0.02],
            "roe": [0.2, 0.05],
            "gross_margin": [0.5, 0.2],
            "net_margin": [0.2, 0.05],
            "roic": [0.2, 0.05],
            "market_cap": [1e10, 1e11],
        },
        index=["STRONG", "WEAK"],
    )


def _technical_df():
    return pd.DataFrame(
        {
            "above_sma50": [True, False],
            "above_sma200": [True, False],
            "sma50_above_sma200": [True, False],
            "momentum_3m": [0.2, -0.1],
            "momentum_6m": [0.3, -0.2],
            "rel_strength_3m": [0.1, -0.1],
        },
        index=["STRONG", "WEAK"],
    )


def test_composite_score_is_not_none_when_all_inputs_present():
    result = compute_composite_scores(_fundamental_df(), _technical_df())
    assert result["composite_score"].notna().all()


def test_composite_score_ranks_strong_symbol_higher():
    result = compute_composite_scores(_fundamental_df(), _technical_df())
    assert result.loc["STRONG", "composite_score"] > result.loc["WEAK", "composite_score"]
    assert result.index[0] == "STRONG"  # sorted descending


def test_composite_respects_custom_weights():
    # An all-weight-on-technical blend should just equal the technical score.
    result = compute_composite_scores(
        _fundamental_df(),
        _technical_df(),
        weights={"fundamental": 0.0, "technical": 1.0, "quant": 0.0},
    )
    pd.testing.assert_series_equal(
        result["composite_score"], result["technical_score"], check_names=False
    )
