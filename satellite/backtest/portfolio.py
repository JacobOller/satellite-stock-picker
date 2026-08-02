"""Portfolio-level equity curve for backtests where holding_days exceeds
the rebalance step (see plan.md's Progress log open question). Chaining
each rebalance period's full-holding-period forward_return sequentially
(satellite.backtest.metrics.equity_curve_from_returns fed period_returns
directly) overstates volatility/drawdown, because it treats compounding
events as sequential when the underlying positions actually overlap in
time (holding_days=42 vs. a ~10-trading-day rebalance step means ~4
cohorts are open at once).

This instead marks every open position to market daily and equal-weights
whatever is open on a given day, which is what an investor who actually
held these overlapping positions would have experienced. Feed the result
into metrics.equity_curve_from_returns / max_drawdown as usual — those
two functions were always correct for what they claim to do (compound a
period-return series); the bug was upstream, in what was being fed to
them.
"""

from __future__ import annotations

import pandas as pd


def _position_daily_returns(price_df: pd.DataFrame, entry_date: pd.Timestamp, holding_days: int) -> pd.Series:
    """Day-over-day returns for a single position from its entry bar
    through holding_days bars later (inclusive), so the first value is
    the return of the bar right after entry.
    """
    close = price_df["Close"]
    future = close[close.index >= entry_date]
    if future.empty:
        return pd.Series(dtype=float)
    window = future.iloc[: holding_days + 1]
    if len(window) < 2:
        return pd.Series(dtype=float)
    return window.pct_change().dropna()


def daily_portfolio_returns(
    trades_df: pd.DataFrame, price_data: dict[str, pd.DataFrame], holding_days: int
) -> pd.Series:
    """trades_df: one row per (rebalance_date, symbol) position, as
    produced by satellite.backtest.engine.run_backtest / run_walk_forward.
    Returns a daily portfolio return series: on each trading day, the
    equal-weighted mean day-over-day return of every position currently
    open (entered within the last holding_days and not yet exited),
    across all rebalance cohorts open simultaneously that day.
    """
    if trades_df.empty:
        return pd.Series(dtype=float)

    position_returns = []
    for _, row in trades_df.iterrows():
        price_df = price_data.get(row["symbol"])
        if price_df is None:
            continue
        rets = _position_daily_returns(price_df, row["date"], holding_days)
        if not rets.empty:
            position_returns.append(rets)

    if not position_returns:
        return pd.Series(dtype=float)

    matrix = pd.concat(position_returns, axis=1)
    return matrix.mean(axis=1, skipna=True).sort_index()


def benchmark_daily_returns(benchmark_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """True continuous buy-and-hold daily returns for the benchmark over
    [start, end] — the correct comparison point for daily_portfolio_returns
    (a single continuous holding, not periodic re-entries), so its
    equity curve/drawdown aren't subject to the same overlap issue.
    """
    close = benchmark_df["Close"]
    window = close[(close.index >= start) & (close.index <= end)]
    if len(window) < 2:
        return pd.Series(dtype=float)
    return window.pct_change().dropna()
