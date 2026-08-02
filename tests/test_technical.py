import numpy as np
import pandas as pd
import pytest

from satellite.scoring.technical import (
    period_return,
    raw_technical_metrics,
    rsi,
    score_technicals,
    sma,
)


def _make_price_df(closes: list[float], start="2024-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


def test_sma_basic():
    close = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = sma(close, 3)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[4] == 4.0


def test_rsi_all_gains_is_100():
    close = pd.Series(range(1, 30), dtype=float)  # strictly increasing
    result = rsi(close, window=14)
    assert result.iloc[-1] == 100.0


def test_rsi_all_losses_is_0():
    close = pd.Series(range(30, 1, -1), dtype=float)  # strictly decreasing
    result = rsi(close, window=14)
    assert result.iloc[-1] == 0.0


def test_period_return_none_when_not_enough_history():
    close = pd.Series([1.0, 2.0, 3.0])
    assert period_return(close, lookback=5) is None


def test_period_return_computes_correctly():
    close = pd.Series([100.0, 110.0, 121.0])
    assert period_return(close, lookback=2) == pytest.approx(0.21)


def test_raw_technical_metrics_short_history_has_none_indicators():
    df = _make_price_df([100.0 + i for i in range(30)])
    metrics = raw_technical_metrics(df)
    assert metrics["sma50"] is None
    assert metrics["sma200"] is None
    assert metrics["last_price"] == df["Close"].iloc[-1]


def test_raw_technical_metrics_full_history_has_indicators():
    closes = [100.0 + i * 0.5 for i in range(250)]  # steady uptrend
    df = _make_price_df(closes)
    metrics = raw_technical_metrics(df)
    assert metrics["sma50"] is not None
    assert metrics["sma200"] is not None
    assert metrics["above_sma50"] is True
    assert metrics["above_sma200"] is True
    assert metrics["momentum_3m"] > 0


def test_score_technicals_ranks_stronger_trend_higher():
    df = pd.DataFrame(
        {
            "above_sma50": [True, False],
            "above_sma200": [True, False],
            "sma50_above_sma200": [True, False],
            "momentum_3m": [0.2, -0.1],
            "momentum_6m": [0.3, -0.2],
            "rel_strength_3m": [0.1, -0.05],
        },
        index=["STRONG", "WEAK"],
    )
    scores = score_technicals(df)
    assert scores["STRONG"] > scores["WEAK"]
