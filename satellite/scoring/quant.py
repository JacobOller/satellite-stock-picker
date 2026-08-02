"""Quant/factor group: cross-sectional ranking of value, momentum,
quality, and size relative to the rest of the universe (plan.md
"Scoring methodology" #3). This is deliberately a separate re-ranking of
the same raw metrics used by the fundamental/technical groups, not a new
data source — it's what makes scores comparable across sectors.
"""

from __future__ import annotations

import pandas as pd


def _percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    return series.rank(pct=True, ascending=ascending, na_option="keep") * 100


def score_quant(df: pd.DataFrame) -> pd.DataFrame:
    """df must have columns: pe_ratio, pb_ratio, fcf_yield, momentum_3m,
    momentum_6m, roe, gross_margin, net_margin, roic, market_cap (indexed
    by symbol — join fundamental + technical raw-metric frames first).

    Returns a DataFrame with value/momentum/quality/size sub-scores
    (0-100 each) plus a quant_score that averages all four.
    """
    value = pd.concat(
        [
            _percentile_rank(df["pe_ratio"], ascending=False),
            _percentile_rank(df["pb_ratio"], ascending=False),
            _percentile_rank(df["fcf_yield"], ascending=True),
        ],
        axis=1,
    ).mean(axis=1, skipna=True)

    momentum = pd.concat(
        [_percentile_rank(df["momentum_3m"]), _percentile_rank(df["momentum_6m"])], axis=1
    ).mean(axis=1, skipna=True)

    quality = pd.concat(
        [
            _percentile_rank(df["roe"]),
            _percentile_rank(df["gross_margin"]),
            _percentile_rank(df["net_margin"]),
            _percentile_rank(df["roic"]),
        ],
        axis=1,
    ).mean(axis=1, skipna=True)

    # Classic size-factor convention: smaller market cap ranks higher.
    size = _percentile_rank(df["market_cap"], ascending=False)

    out = pd.DataFrame({"value": value, "momentum": momentum, "quality": quality, "size": size})
    out["quant_score"] = out.mean(axis=1, skipna=True)
    return out
