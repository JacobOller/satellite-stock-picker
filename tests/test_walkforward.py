import pandas as pd

from satellite.backtest.walkforward import run_walk_forward, walk_forward_windows


def test_walk_forward_windows_basic_slicing():
    dates = list(range(10))  # plain ints stand in for dates here
    windows = walk_forward_windows(dates, train_size=4, test_size=2, step=2)
    assert windows[0] == ([0, 1, 2, 3], [4, 5])
    assert windows[1] == ([2, 3, 4, 5], [6, 7])
    assert windows[-1][1][-1] <= 9


def test_walk_forward_windows_stops_when_not_enough_dates():
    dates = list(range(5))
    windows = walk_forward_windows(dates, train_size=4, test_size=2, step=1)
    assert windows == []


def _make_price_df(closes, start="2024-01-01"):
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1_000_000] * len(closes)},
        index=idx,
    )


def test_run_walk_forward_produces_summary_and_trades():
    n = 300
    price_data = {
        "UP": _make_price_df([100.0 + i * 0.3 for i in range(n)]),
        "FLAT": _make_price_df([100.0] * n),
        "DOWN": _make_price_df([150.0 - i * 0.2 for i in range(n)]),
    }
    idx = price_data["UP"].index
    rebalance_dates = list(idx[210:280:10])  # after enough history for sma200

    summary_df, trades_df = run_walk_forward(
        price_data, rebalance_dates, train_size=3, test_size=2, step=2, top_n=1, holding_days=5
    )

    assert not summary_df.empty
    assert set(["window", "best_weights", "train_avg_return", "test_avg_return"]).issubset(summary_df.columns)
    # UP should dominate picks given it's the only sustained uptrend
    assert not trades_df.empty
    assert (trades_df["symbol"] == "UP").mean() > 0.5
