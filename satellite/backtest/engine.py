"""Backtest replay engine: walks a set of rebalance dates, scores the
universe as-of each date (no look-ahead — only data up to that date is
visible to the score function), picks the top N, and measures forward
returns over a fixed holding period.

Current limitation: FMP free tier makes point-in-time historical
fundamentals expensive to assemble (separate historical statements pulls
per symbol per date), so `default_technical_score_fn` below scores on
technicals only. This still exercises the full replay + metrics pipeline
end-to-end on real cached price data. Wiring in point-in-time fundamentals
is phase 2 work (plan.md: "Implement all three factor groups fully" /
walk-forward weight tuning) — swap in a fundamentals-aware score_fn once
that exists; run_backtest itself doesn't need to change.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from satellite.scoring.composite import compute_composite_scores
from satellite.scoring.technical import raw_technical_metrics, score_technicals

ScoreFn = Callable[[pd.Timestamp, list[str], dict[str, pd.DataFrame]], pd.Series]

_FUNDAMENTAL_COLUMNS = [
    "pe_ratio",
    "pb_ratio",
    "fcf_yield",
    "roe",
    "gross_margin",
    "net_margin",
    "roic",
    "market_cap",
]


def forward_return(price_df: pd.DataFrame, entry_date: pd.Timestamp, holding_days: int) -> float | None:
    """Return over `holding_days` trading bars starting at the first bar
    on/after entry_date. None if there isn't enough future data yet.
    """
    close = price_df["Close"]
    future = close[close.index >= entry_date]
    if len(future) <= holding_days:
        return None
    entry_price = future.iloc[0]
    exit_price = future.iloc[holding_days]
    if entry_price == 0 or pd.isna(entry_price):
        return None
    return float(exit_price / entry_price - 1)


def default_technical_score_fn(
    as_of: pd.Timestamp, symbols: list[str], price_data: dict[str, pd.DataFrame]
) -> pd.Series:
    rows = {}
    for symbol in symbols:
        df = price_data.get(symbol)
        if df is None:
            continue
        history = df[df.index <= as_of]
        if len(history) < 60:  # need some minimum runway for indicators
            continue
        rows[symbol] = raw_technical_metrics(history)
    if not rows:
        return pd.Series(dtype=float)
    metrics_df = pd.DataFrame.from_dict(rows, orient="index")
    return score_technicals(metrics_df)


def technical_quant_score_fn(
    as_of: pd.Timestamp,
    symbols: list[str],
    price_data: dict[str, pd.DataFrame],
    weights: dict | None = None,
) -> pd.Series:
    """Composite score using technical + quant groups only. Fundamental
    inputs are unavailable point-in-time (see backtest/engine.py module
    docstring), so the fundamental columns are passed through as NaN —
    compute_composite_scores' weighted-mean-skipna redistributes weight
    to whichever groups have data, and quant's value/quality/size
    sub-factors (which depend on those same fundamental columns) collapse
    to NaN too, leaving quant effectively momentum-only for now. Still
    useful for validating the harness and for tuning the
    technical-vs-quant balance once fundamentals aren't part of the mix.
    """
    rows = {}
    for symbol in symbols:
        df = price_data.get(symbol)
        if df is None:
            continue
        history = df[df.index <= as_of]
        if len(history) < 60:
            continue
        rows[symbol] = raw_technical_metrics(history)
    if not rows:
        return pd.Series(dtype=float)

    technical_df = pd.DataFrame.from_dict(rows, orient="index")
    fundamental_df = pd.DataFrame(index=technical_df.index, columns=_FUNDAMENTAL_COLUMNS, dtype=float)
    composite = compute_composite_scores(fundamental_df, technical_df, weights=weights)
    return composite["composite_score"]


def make_weighted_score_fn(weights: dict) -> ScoreFn:
    """Factory: bind a fixed weights dict to technical_quant_score_fn so
    it matches the plain ScoreFn signature run_backtest expects.
    """

    def _fn(as_of: pd.Timestamp, symbols: list[str], price_data: dict[str, pd.DataFrame]) -> pd.Series:
        return technical_quant_score_fn(as_of, symbols, price_data, weights=weights)

    return _fn


def run_backtest(
    price_data: dict[str, pd.DataFrame],
    rebalance_dates: list[pd.Timestamp],
    top_n: int = 5,
    holding_days: int = 42,  # ~2 months of trading days, mid-point of "weeks-months" holding period
    score_fn: ScoreFn = default_technical_score_fn,
) -> pd.DataFrame:
    """Returns a trades DataFrame: one row per (rebalance_date, symbol)
    pick, with columns [date, symbol, score, forward_return].
    """
    symbols = list(price_data.keys())
    records = []

    for as_of in rebalance_dates:
        scores = score_fn(as_of, symbols, price_data)
        if scores.empty:
            continue
        picks = scores.sort_values(ascending=False).head(top_n)
        for symbol, score in picks.items():
            ret = forward_return(price_data[symbol], as_of, holding_days)
            records.append({"date": as_of, "symbol": symbol, "score": score, "forward_return": ret})

    return pd.DataFrame.from_records(records, columns=["date", "symbol", "score", "forward_return"])


def period_returns(trades_df: pd.DataFrame) -> pd.Series:
    """Average forward_return of that period's picks, indexed by date —
    the per-rebalance-period "strategy return" used for equity curve /
    benchmark comparison."""
    if trades_df.empty:
        return pd.Series(dtype=float)
    return trades_df.groupby("date")["forward_return"].mean()


def benchmark_period_returns(
    benchmark_df: pd.DataFrame, rebalance_dates: list[pd.Timestamp], holding_days: int
) -> pd.Series:
    values = {date: forward_return(benchmark_df, date, holding_days) for date in rebalance_dates}
    return pd.Series(values)
