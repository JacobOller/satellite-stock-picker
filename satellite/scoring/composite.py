"""Composite scoring: blends fundamental, technical, and quant sub-scores
per plan.md's factor weights. Pure function over already-collected raw
metric DataFrames — no I/O — so it runs identically live and in backtest.

Weights are a placeholder starting guess (satellite.config
DEFAULT_FACTOR_WEIGHTS); they must be validated via the backtester before
being trusted in a live alert (see CLAUDE.md "Before trusting a strategy
change live").
"""

from __future__ import annotations

import pandas as pd

from satellite.config import DEFAULT_FACTOR_WEIGHTS
from satellite.scoring.fundamental import score_fundamentals
from satellite.scoring.quant import score_quant
from satellite.scoring.technical import score_technicals


def _weighted_mean_skipna(row: pd.Series, weights: dict) -> float | None:
    total_weight = 0.0
    weighted_sum = 0.0
    for key, weight in weights.items():
        value = row.get(key)
        if value is not None and pd.notna(value):
            weighted_sum += value * weight
            total_weight += weight
    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def compute_composite_scores(
    fundamental_raw_df: pd.DataFrame,
    technical_raw_df: pd.DataFrame,
    weights: dict | None = None,
) -> pd.DataFrame:
    """fundamental_raw_df and technical_raw_df must be indexed by symbol,
    with columns as produced by raw_fundamental_metrics /
    raw_technical_metrics respectively (collected across the universe).

    Returns a DataFrame indexed by symbol with columns: fundamental_score,
    technical_score, quant_score (+ quant's value/momentum/quality/size
    sub-scores), and composite_score.
    """
    weights = weights or DEFAULT_FACTOR_WEIGHTS

    combined_raw = fundamental_raw_df.join(technical_raw_df, how="outer")

    fundamental_score = score_fundamentals(fundamental_raw_df)
    technical_score = score_technicals(technical_raw_df)
    quant_df = score_quant(combined_raw)

    result = pd.DataFrame(
        {
            "fundamental_score": fundamental_score,
            "technical_score": technical_score,
            "quant_score": quant_df["quant_score"],
        }
    )
    result = result.join(quant_df[["value", "momentum", "quality", "size"]])

    column_weights = {
        "fundamental_score": weights.get("fundamental", 0),
        "technical_score": weights.get("technical", 0),
        "quant_score": weights.get("quant", 0),
    }
    result["composite_score"] = result.apply(
        lambda row: _weighted_mean_skipna(row, column_weights), axis=1
    )
    return result.sort_values("composite_score", ascending=False)
