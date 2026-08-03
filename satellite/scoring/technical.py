"""Technical factor group: trend, momentum, relative strength.

Pure functions over price DataFrames (columns: Open, High, Low, Close,
Volume; DatetimeIndex) so the same code runs identically in the live scan
and the backtester — no I/O here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_BARS_REQUIRED = 210  # need ~200 bars for SMA200 plus a little slack


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.where(avg_loss != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def period_return(close: pd.Series, lookback: int) -> float | None:
    if len(close) <= lookback:
        return None
    past = close.iloc[-lookback - 1]
    if past == 0 or pd.isna(past):
        return None
    return float(close.iloc[-1] / past - 1)


def raw_technical_metrics(price_df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None) -> dict:
    """Compute a single symbol's raw technical indicators as of the last
    row of price_df. Returns a dict with None values where insufficient
    history exists, so callers can filter incomplete rows before scoring.
    """
    close = price_df["Close"].dropna()
    metrics: dict = {
        "last_price": float(close.iloc[-1]) if len(close) else None,
        "sma50": None,
        "sma200": None,
        "above_sma50": None,
        "above_sma200": None,
        "sma50_above_sma200": None,
        "rsi14": None,
        "macd_hist": None,
        "momentum_1m": period_return(close, 21),
        "momentum_3m": period_return(close, 63),
        "momentum_6m": period_return(close, 126),
        "rel_strength_3m": None,
    }

    if len(close) >= 50:
        sma50 = sma(close, 50)
        metrics["sma50"] = float(sma50.iloc[-1])
        metrics["above_sma50"] = bool(close.iloc[-1] > sma50.iloc[-1])
    if len(close) >= 200:
        sma200 = sma(close, 200)
        metrics["sma200"] = float(sma200.iloc[-1])
        metrics["above_sma200"] = bool(close.iloc[-1] > sma200.iloc[-1])
        if metrics["sma50"] is not None:
            metrics["sma50_above_sma200"] = bool(metrics["sma50"] > sma200.iloc[-1])
    if len(close) >= 15:
        metrics["rsi14"] = float(rsi(close).iloc[-1])
    if len(close) >= 35:
        _, _, hist = macd(close)
        metrics["macd_hist"] = float(hist.iloc[-1])

    if benchmark_df is not None and "Close" in benchmark_df:
        bench_close = benchmark_df["Close"].dropna()
        sym_ret = metrics["momentum_3m"]
        bench_ret = period_return(bench_close, 63)
        if sym_ret is not None and bench_ret is not None:
            metrics["rel_strength_3m"] = sym_ret - bench_ret

    return metrics


def _percentile_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="keep") * 100


def score_technicals(df: pd.DataFrame) -> pd.Series:
    """Cross-sectional 0-100 technical score across the universe. df must
    have columns: above_sma50, above_sma200, sma50_above_sma200,
    momentum_3m, momentum_6m, rel_strength_3m (as produced by
    raw_technical_metrics, collected into a DataFrame indexed by symbol).

    raw_technical_metrics also computes rsi14/macd_hist, but they're
    deliberately NOT read here. Tested 2026-08-02: wiring them into the
    momentum component (ranked same-direction as price momentum) measurably
    hurt the full-S&P-500 backtest -- avg return per idea +8.53% -> +4.09%,
    hit rate 65.22% -> 58.42%, max drawdown -35.73% -> -43.23% (identical
    config otherwise). Reverted per CLAUDE.md's "run scoring changes through
    the backtester before trusting them" rule. If revisiting, treat this as
    a new experiment to re-validate, not a "finish the plan.md spec" fix.
    """
    trend_component = (
        df[["above_sma50", "above_sma200", "sma50_above_sma200"]].astype("float").mean(axis=1) * 100
    )
    momentum_component = pd.concat(
        [_percentile_rank(df["momentum_3m"]), _percentile_rank(df["momentum_6m"])], axis=1
    ).mean(axis=1)
    rel_strength_component = _percentile_rank(df["rel_strength_3m"])

    combined = pd.concat(
        [trend_component, momentum_component, rel_strength_component],
        axis=1,
        keys=["trend", "momentum", "rel_strength"],
    )
    return combined.mean(axis=1, skipna=True)
