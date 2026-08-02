import pandas as pd
import pytest

from satellite.backtest.portfolio import benchmark_daily_returns, daily_portfolio_returns


def _make_price_df(closes: list[float], start="2024-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1_000_000] * len(closes)},
        index=idx,
    )


def test_daily_portfolio_returns_single_position_matches_price_pct_change():
    price_df = _make_price_df([100.0, 110.0, 121.0, 133.1])
    trades = pd.DataFrame({"date": [price_df.index[0]], "symbol": ["A"]})
    result = daily_portfolio_returns(trades, {"A": price_df}, holding_days=3)
    assert result.iloc[0] == pytest.approx(0.10)
    assert result.iloc[1] == pytest.approx(0.10)
    assert result.iloc[2] == pytest.approx(0.10)


def test_daily_portfolio_returns_overlapping_positions_are_equal_weighted():
    # Two symbols, same entry date, opposite moves -> should net out to ~0
    up = _make_price_df([100.0, 110.0, 121.0])
    down = _make_price_df([100.0, 90.0, 81.0])
    trades = pd.DataFrame({"date": [up.index[0], up.index[0]], "symbol": ["UP", "DOWN"]})
    result = daily_portfolio_returns(trades, {"UP": up, "DOWN": down}, holding_days=2)
    assert result.iloc[0] == pytest.approx(0.0)
    assert result.iloc[1] == pytest.approx(0.0)


def test_daily_portfolio_returns_staggered_cohorts_overlap():
    # Position A enters day 0, holds 4 days. Position B enters day 2 (while
    # A is still open), holds 4 days. On days 2-4 both should contribute.
    closes = [100.0 * (1.1**i) for i in range(10)]
    price_df = _make_price_df(closes)
    trades = pd.DataFrame({"date": [price_df.index[0], price_df.index[2]], "symbol": ["A", "A"]})
    result = daily_portfolio_returns(trades, {"A": price_df}, holding_days=4)
    # every day it's the same symbol so equal weighting shouldn't change the
    # per-day return (both cohorts see the same 10% day-over-day move)
    assert result.apply(lambda v: v == pytest.approx(0.10)).all()


def test_daily_portfolio_returns_empty_trades():
    result = daily_portfolio_returns(pd.DataFrame(columns=["date", "symbol"]), {}, holding_days=5)
    assert result.empty


def test_benchmark_daily_returns_continuous_holding():
    price_df = _make_price_df([100.0, 110.0, 121.0])
    result = benchmark_daily_returns(price_df, price_df.index[0], price_df.index[-1])
    assert list(result.round(6)) == [pytest.approx(0.10), pytest.approx(0.10)]
