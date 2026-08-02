"""Backtest performance metrics. Pure functions over return series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def hit_rate(returns: pd.Series) -> float | None:
    clean = returns.dropna()
    if clean.empty:
        return None
    return float((clean > 0).mean())


def average_return(returns: pd.Series) -> float | None:
    clean = returns.dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def return_distribution_stats(returns: pd.Series) -> dict:
    clean = returns.dropna()
    if clean.empty:
        return {"count": 0}
    return {
        "count": int(clean.count()),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "std": float(clean.std()),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "p25": float(clean.quantile(0.25)),
        "p75": float(clean.quantile(0.75)),
    }


def max_drawdown(equity_curve: pd.Series) -> float | None:
    """equity_curve: cumulative growth-of-$1 series (monotonic time index)."""
    clean = equity_curve.dropna()
    if clean.empty:
        return None
    running_max = clean.cummax()
    drawdown = clean / running_max - 1
    return float(drawdown.min())


def equity_curve_from_returns(period_returns: pd.Series) -> pd.Series:
    """Build a growth-of-$1 curve from a time-ordered series of per-period
    returns (e.g. one row per rebalance date, average return of that
    period's picks).
    """
    return (1 + period_returns.fillna(0)).cumprod()


def compare_to_benchmark(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> dict:
    """Both series should be aligned on the same period index (e.g. one
    value per rebalance date). Returns strategy vs. benchmark summary
    stats plus average excess return.
    """
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1, keys=["strategy", "benchmark"]).dropna()
    if aligned.empty:
        return {"count": 0}
    excess = aligned["strategy"] - aligned["benchmark"]
    return {
        "count": int(len(aligned)),
        "strategy_mean_return": float(aligned["strategy"].mean()),
        "benchmark_mean_return": float(aligned["benchmark"].mean()),
        "mean_excess_return": float(excess.mean()),
        "win_rate_vs_benchmark": float((excess > 0).mean()),
        "strategy_max_drawdown": max_drawdown(equity_curve_from_returns(aligned["strategy"])),
        "benchmark_max_drawdown": max_drawdown(equity_curve_from_returns(aligned["benchmark"])),
    }
