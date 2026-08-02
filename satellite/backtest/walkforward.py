"""Walk-forward validation harness, per plan.md's Backtesting plan ("train
weights on one period, test on a later out-of-sample period") and
CLAUDE.md's "Before trusting a strategy change live" rule.

Windows are sliced by rebalance-date position (train_size/test_size/step
are counts of rebalance dates, not calendar days) so behavior is
deterministic regardless of trading-day gaps.

Current scope: searches the technical-vs-quant weight balance only —
fundamental weight tuning needs point-in-time fundamentals, which aren't
wired in yet (see satellite/backtest/engine.py). The mechanism (train,
pick best weights, evaluate out-of-sample on test) is the reusable part;
extending weight_grid to include a fundamental component is a drop-in
change once that data exists.
"""

from __future__ import annotations

import pandas as pd

from satellite.backtest.engine import make_weighted_score_fn, period_returns, run_backtest
from satellite.backtest.metrics import average_return

DEFAULT_WEIGHT_GRID = [
    {"fundamental": 0.0, "technical": 1.0, "quant": 0.0},
    {"fundamental": 0.0, "technical": 0.7, "quant": 0.3},
    {"fundamental": 0.0, "technical": 0.5, "quant": 0.5},
    {"fundamental": 0.0, "technical": 0.3, "quant": 0.7},
    {"fundamental": 0.0, "technical": 0.0, "quant": 1.0},
]


def walk_forward_windows(
    rebalance_dates: list[pd.Timestamp], train_size: int, test_size: int, step: int
) -> list[tuple[list[pd.Timestamp], list[pd.Timestamp]]]:
    """Slice rebalance_dates into (train_dates, test_dates) windows. Each
    window's test period immediately follows its train period; step
    controls how far the next window's train start advances.
    """
    windows = []
    start = 0
    n = len(rebalance_dates)
    while start + train_size + test_size <= n:
        train_dates = rebalance_dates[start : start + train_size]
        test_dates = rebalance_dates[start + train_size : start + train_size + test_size]
        windows.append((train_dates, test_dates))
        start += step
    return windows


def run_walk_forward(
    price_data: dict[str, pd.DataFrame],
    rebalance_dates: list[pd.Timestamp],
    train_size: int,
    test_size: int,
    step: int,
    top_n: int = 5,
    holding_days: int = 42,
    weight_grid: list[dict] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (window_summary_df, all_test_trades_df).

    For each window: evaluate every weight_grid candidate on the train
    dates (mean forward return of that window's picks), pick the best,
    then run it out-of-sample on the test dates. This is what keeps the
    test-period numbers honest — the weights are chosen without seeing
    test-period outcomes.
    """
    weight_grid = weight_grid or DEFAULT_WEIGHT_GRID
    windows = walk_forward_windows(rebalance_dates, train_size, test_size, step)

    summaries = []
    all_test_trades = []

    for i, (train_dates, test_dates) in enumerate(windows):
        best_weights, best_train_score = None, float("-inf")
        for weights in weight_grid:
            score_fn = make_weighted_score_fn(weights)
            train_trades = run_backtest(price_data, train_dates, top_n=top_n, holding_days=holding_days, score_fn=score_fn)
            train_score = average_return(train_trades["forward_return"]) if not train_trades.empty else None
            if train_score is not None and train_score > best_train_score:
                best_train_score, best_weights = train_score, weights

        if best_weights is None:
            continue

        test_score_fn = make_weighted_score_fn(best_weights)
        test_trades = run_backtest(price_data, test_dates, top_n=top_n, holding_days=holding_days, score_fn=test_score_fn)
        test_avg_return = average_return(test_trades["forward_return"]) if not test_trades.empty else None

        summaries.append(
            {
                "window": i,
                "train_start": train_dates[0] if train_dates else None,
                "train_end": train_dates[-1] if train_dates else None,
                "test_start": test_dates[0] if test_dates else None,
                "test_end": test_dates[-1] if test_dates else None,
                "best_weights": best_weights,
                "train_avg_return": best_train_score,
                "test_avg_return": test_avg_return,
                "test_trade_count": len(test_trades),
            }
        )
        if not test_trades.empty:
            all_test_trades.append(test_trades)

    summary_df = pd.DataFrame(summaries)
    trades_df = pd.concat(all_test_trades, ignore_index=True) if all_test_trades else pd.DataFrame(
        columns=["date", "symbol", "score", "forward_return"]
    )
    return summary_df, trades_df
