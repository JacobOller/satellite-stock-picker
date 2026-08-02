"""Fundamental factor group: valuation, profitability.

Pure functions. Raw metrics come from satellite.data.fundamentals'
extracted factor_inputs dict (already normalized field names, still
un-scored). Scoring is cross-sectional (percentile rank across the
universe) so valuation/profitability figures — which live on very
different scales — become comparable.

Earnings growth is a known gap in the v1 skeleton: FMP's growth
endpoints aren't wired up yet to conserve free-tier call budget (see
satellite/data/fundamentals.py). Revisit in phase 2.
"""

from __future__ import annotations

import pandas as pd


def raw_fundamental_metrics(factor_inputs: dict) -> dict:
    """Light cleanup pass over a single symbol's factor_inputs dict:
    clamp nonsensical values (e.g. negative P/E from negative earnings)
    to None so they don't distort percentile ranking.
    """
    pe = factor_inputs.get("pe_ratio")
    pb = factor_inputs.get("pb_ratio")
    return {
        "symbol": factor_inputs.get("symbol"),
        "pe_ratio": pe if pe is not None and pe > 0 else None,
        "pb_ratio": pb if pb is not None and pb > 0 else None,
        "fcf_yield": factor_inputs.get("fcf_yield"),
        "roe": factor_inputs.get("roe"),
        "gross_margin": factor_inputs.get("gross_margin"),
        "net_margin": factor_inputs.get("net_margin"),
        "roic": factor_inputs.get("roic"),
        "debt_to_equity": factor_inputs.get("debt_to_equity"),
        "market_cap": factor_inputs.get("market_cap"),
    }


def _percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    ranked = series.rank(pct=True, ascending=ascending, na_option="keep")
    return ranked * 100


def score_fundamentals(df: pd.DataFrame) -> pd.Series:
    """Cross-sectional 0-100 fundamental score across the universe. df
    must have columns: pe_ratio, pb_ratio, fcf_yield, roe, gross_margin,
    net_margin, roic (as produced by raw_fundamental_metrics, collected
    into a DataFrame indexed by symbol).

    Valuation: lower P/E and P/B rank higher (cheap); higher FCF yield
    ranks higher. Quality/profitability: higher ROE, margins, ROIC rank
    higher.
    """
    valuation_component = pd.concat(
        [
            _percentile_rank(df["pe_ratio"], ascending=False),
            _percentile_rank(df["pb_ratio"], ascending=False),
            _percentile_rank(df["fcf_yield"], ascending=True),
        ],
        axis=1,
    ).mean(axis=1, skipna=True)

    quality_component = pd.concat(
        [
            _percentile_rank(df["roe"], ascending=True),
            _percentile_rank(df["gross_margin"], ascending=True),
            _percentile_rank(df["net_margin"], ascending=True),
            _percentile_rank(df["roic"], ascending=True),
        ],
        axis=1,
    ).mean(axis=1, skipna=True)

    combined = pd.concat(
        [valuation_component, quality_component], axis=1, keys=["valuation", "quality"]
    )
    return combined.mean(axis=1, skipna=True)
