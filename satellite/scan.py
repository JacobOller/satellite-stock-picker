"""Live scan orchestration: universe -> data ingestion -> scoring ->
ranker -> sized, formatted alert, per plan.md's Architecture diagram.

This wires up the mechanism only. It is NOT scheduled to run
automatically and does NOT push a live notification anywhere — per
CLAUDE.md's "Before trusting a strategy change live" rule, turning this
into an actual daily push is a decision for the user to make once
satisfied with backtest results (plan.md's Phase 2 go/no-go item is
still open as of 2026-08-02). Run manually via `run_scan` to see what
today's alert *would* say.

I/O-heavy by nature (network calls to yfinance/Finnhub), so — like
satellite/data/prices.py and fundamentals*.py — this isn't unit tested
with synthetic data; satellite/alert.py (the pure formatting step) is.
"""

from __future__ import annotations

import pandas as pd

from satellite.alert import format_alert
from satellite.data.fundamentals_finnhub import get_fundamentals as get_finnhub_fundamentals
from satellite.data.fundamentals_finnhub import refresh_fundamentals_cache as refresh_finnhub_fundamentals
from satellite.data.prices import load_cached_prices, refresh_price_cache
from satellite.ranker import select_top_ideas
from satellite.risk import add_suggested_sizes
from satellite.scoring.composite import compute_composite_scores
from satellite.scoring.fundamental import raw_fundamental_metrics
from satellite.scoring.technical import raw_technical_metrics

MIN_PRICE_BARS = 210  # sma200 + slack, matches satellite.scoring.technical.MIN_BARS_REQUIRED


def collect_universe_scores(symbols: list[str], max_fundamentals_symbols: int | None = None) -> pd.DataFrame:
    """Refresh cached prices + fundamentals for symbols and compute
    composite scores. Uses Finnhub for fundamentals (60 calls/min free
    tier vs. FMP's ~250/day total) so a large-universe scan doesn't blow
    the daily budget — see satellite/data/fundamentals_finnhub.py.
    """
    refresh_price_cache(symbols)
    refresh_finnhub_fundamentals(symbols, max_symbols=max_fundamentals_symbols)

    fundamental_rows: dict[str, dict] = {}
    technical_rows: dict[str, dict] = {}
    for symbol in symbols:
        price_df = load_cached_prices(symbol)
        if price_df is None or len(price_df) < MIN_PRICE_BARS:
            continue
        technical_rows[symbol] = raw_technical_metrics(price_df)

        fi = get_finnhub_fundamentals(symbol)
        if fi is not None:
            fundamental_rows[symbol] = raw_fundamental_metrics(fi)

    technical_df = pd.DataFrame.from_dict(technical_rows, orient="index")
    fundamental_df = pd.DataFrame.from_dict(fundamental_rows, orient="index")
    return compute_composite_scores(fundamental_df, technical_df)


def run_scan(
    symbols: list[str],
    account_value: float,
    existing_holdings: set[str] | None = None,
    max_fundamentals_symbols: int | None = None,
) -> tuple[pd.DataFrame, str]:
    """Full pipeline: score the given symbols, rank into top new ideas
    (excluding existing_holdings, capped at MAX_CONCURRENT_POSITIONS),
    size them against account_value, and format the alert text.

    Returns (sized_ideas_df, alert_text). Does not send/push anything —
    the caller decides what to do with alert_text.
    """
    scored = collect_universe_scores(symbols, max_fundamentals_symbols=max_fundamentals_symbols)
    ranked = select_top_ideas(scored, existing_holdings=existing_holdings)
    sized = add_suggested_sizes(ranked, account_value)
    alert_text = format_alert(sized, as_of=pd.Timestamp.now().normalize())
    return sized, alert_text


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from satellite.config import PRICE_CACHE_DIR

    # Dry run over whatever's already price-cached, so this doesn't kick
    # off a full 3,588-symbol universe fetch just by being invoked.
    cached_symbols = sorted(p.stem for p in Path(PRICE_CACHE_DIR).glob("*.parquet") if p.stem != "SPY")
    account_value = float(sys.argv[1]) if len(sys.argv) > 1 else 50_000.0
    print(f"Dry run over {len(cached_symbols)} already-cached symbols, account_value=${account_value:,.0f}")
    _, alert_text = run_scan(cached_symbols, account_value)
    print(alert_text)
