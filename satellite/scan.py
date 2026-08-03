"""Live scan orchestration: universe -> data ingestion -> scoring ->
ranker -> sized, formatted alert, per plan.md's Architecture diagram.

Go/no-go decision made 2026-08-03: this now backs a real daily cloud
routine (see plan.md Phase 3). The cloud environment has no access to
local secrets/cache, so the routine calls run_scan(..., use_fundamentals
=False) — technical+quant only, no API key needed (yfinance is keyless).
This also exactly matches what the walk-forward backtest validated,
since fundamentals were never backtestable on the free tier. Local runs
can still pass use_fundamentals=True (the default) for the fuller scan.

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

# Same column set satellite.backtest.engine.py's technical_quant_score_fn
# uses as an all-NaN placeholder when fundamentals aren't available, so
# compute_composite_scores degrades to technical+quant only the same way
# in both places (weighted-mean-skipna redistributes weight away from the
# missing group; quant's value/quality/size sub-factors collapse to NaN).
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


def collect_universe_scores(
    symbols: list[str], max_fundamentals_symbols: int | None = None, use_fundamentals: bool = True
) -> pd.DataFrame:
    """Refresh cached prices (+ fundamentals, if use_fundamentals) for
    symbols and compute composite scores. Uses Finnhub for fundamentals
    (60 calls/min free tier vs. FMP's ~250/day total) so a large-universe
    scan doesn't blow the daily budget — see
    satellite/data/fundamentals_finnhub.py.

    use_fundamentals=False skips the Finnhub fetch entirely and scores
    technical+quant only — for environments with no fundamentals API key
    available (e.g. the cloud routine, which has no access to local
    .env). This exactly matches what the walk-forward backtest validated
    (see plan.md): fundamentals were never included in a backtested
    result, so a live alert using them would be running unvalidated
    scoring logic, which CLAUDE.md's "backtest before trusting live"
    rule is meant to prevent.
    """
    refresh_price_cache(symbols)
    if use_fundamentals:
        refresh_finnhub_fundamentals(symbols, max_symbols=max_fundamentals_symbols)

    fundamental_rows: dict[str, dict] = {}
    technical_rows: dict[str, dict] = {}
    for symbol in symbols:
        price_df = load_cached_prices(symbol)
        if price_df is None or len(price_df) < MIN_PRICE_BARS:
            continue
        technical_rows[symbol] = raw_technical_metrics(price_df)

        if use_fundamentals:
            fi = get_finnhub_fundamentals(symbol)
            if fi is not None:
                fundamental_rows[symbol] = raw_fundamental_metrics(fi)

    technical_df = pd.DataFrame.from_dict(technical_rows, orient="index")
    if use_fundamentals and fundamental_rows:
        fundamental_df = pd.DataFrame.from_dict(fundamental_rows, orient="index")
    else:
        # No fundamentals requested, OR every fetch failed/returned nothing
        # (rate limit, outage, bad symbol list, etc.) -- either way,
        # fundamental_df must still have the expected columns so
        # score_fundamentals degrades to all-NaN gracefully instead of
        # raising KeyError on a totally empty, columnless DataFrame.
        fundamental_df = pd.DataFrame(index=technical_df.index, columns=_FUNDAMENTAL_COLUMNS, dtype=float)
    return compute_composite_scores(fundamental_df, technical_df)


def run_scan(
    symbols: list[str],
    account_value: float,
    existing_holdings: set[str] | None = None,
    max_fundamentals_symbols: int | None = None,
    use_fundamentals: bool = True,
) -> tuple[pd.DataFrame, str]:
    """Full pipeline: score the given symbols, rank into top new ideas
    (excluding existing_holdings, capped at MAX_CONCURRENT_POSITIONS),
    size them against account_value, and format the alert text.

    Returns (sized_ideas_df, alert_text). Does not send/push anything —
    the caller decides what to do with alert_text.
    """
    scored = collect_universe_scores(
        symbols, max_fundamentals_symbols=max_fundamentals_symbols, use_fundamentals=use_fundamentals
    )
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
