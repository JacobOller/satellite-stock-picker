import pandas as pd
import pytest

from satellite.backtest.engine import forward_return, period_returns, run_backtest
from satellite.backtest.metrics import (
    average_return,
    compare_to_benchmark,
    equity_curve_from_returns,
    hit_rate,
    max_drawdown,
    return_distribution_stats,
)


def _make_price_df(closes: list[float], start="2024-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1_000_000] * len(closes)},
        index=idx,
    )


def test_forward_return_basic():
    df = _make_price_df([100.0, 105.0, 110.0, 121.0])
    entry_date = df.index[0]
    ret = forward_return(df, entry_date, holding_days=3)
    assert ret == pytest.approx(0.21)


def test_forward_return_none_when_insufficient_future_data():
    df = _make_price_df([100.0, 105.0])
    ret = forward_return(df, df.index[0], holding_days=5)
    assert ret is None


def test_run_backtest_with_constant_score_fn():
    prices = {
        "UP": _make_price_df([100.0 + i for i in range(80)]),
        "DOWN": _make_price_df([100.0 - i * 0.5 for i in range(80)]),
    }

    def score_fn(as_of, symbols, price_data):
        # deterministic: always prefer UP over DOWN
        return pd.Series({"UP": 1.0, "DOWN": 0.0})

    rebalance_dates = [prices["UP"].index[10]]
    trades = run_backtest(prices, rebalance_dates, top_n=1, holding_days=5, score_fn=score_fn)
    assert len(trades) == 1
    assert trades.iloc[0]["symbol"] == "UP"
    assert trades.iloc[0]["forward_return"] > 0


def test_period_returns_averages_same_day_picks():
    trades = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")],
            "symbol": ["A", "B", "C"],
            "score": [1, 2, 3],
            "forward_return": [0.1, 0.2, -0.1],
        }
    )
    result = period_returns(trades)
    assert result[pd.Timestamp("2024-01-01")] == pytest.approx(0.15)
    assert result[pd.Timestamp("2024-02-01")] == pytest.approx(-0.1)


def test_metrics_hit_rate_and_average_return():
    returns = pd.Series([0.1, -0.05, 0.2, None])
    assert hit_rate(returns) == pytest.approx(2 / 3)
    assert average_return(returns) == pytest.approx((0.1 - 0.05 + 0.2) / 3)


def test_metrics_return_distribution_stats_empty():
    assert return_distribution_stats(pd.Series(dtype=float)) == {"count": 0}


def test_max_drawdown_detects_peak_to_trough():
    equity = pd.Series([1.0, 1.2, 0.9, 1.1])
    dd = max_drawdown(equity)
    assert dd == pytest.approx(0.9 / 1.2 - 1)


def test_equity_curve_from_returns_compounds():
    returns = pd.Series([0.1, 0.1])
    curve = equity_curve_from_returns(returns)
    assert curve.iloc[-1] == pytest.approx(1.1 * 1.1)


def test_compare_to_benchmark_excess_return():
    strategy = pd.Series([0.1, 0.2], index=[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")])
    benchmark = pd.Series([0.05, 0.05], index=[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")])
    result = compare_to_benchmark(strategy, benchmark)
    assert result["mean_excess_return"] == pytest.approx(0.1)
    assert result["win_rate_vs_benchmark"] == 1.0
