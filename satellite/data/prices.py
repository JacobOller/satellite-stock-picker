"""Price history ingestion via yfinance, cached to disk as parquet.

One file per symbol under PRICE_CACHE_DIR. Bulk refresh uses yfinance's
batched downloader (much faster / gentler on rate limits than one request
per ticker) and merges new bars into each symbol's cache incrementally.
"""

from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

from satellite.config import PRICE_CACHE_DIR, PRICE_REFRESH_HOURS

_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(symbol: str):
    return PRICE_CACHE_DIR / f"{symbol}.parquet"


def _is_fresh(symbol: str) -> bool:
    path = _cache_path(symbol)
    if not path.exists():
        return False
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours < PRICE_REFRESH_HOURS


def load_cached_prices(symbol: str) -> pd.DataFrame | None:
    path = _cache_path(symbol)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _save_prices(symbol: str, df: pd.DataFrame) -> None:
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    _cache_path(symbol).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_cache_path(symbol))


def refresh_price_cache(
    symbols: list[str],
    period: str = "2y",
    batch_size: int = 100,
    force_refresh: bool = False,
    sleep_between_batches: float = 1.0,
) -> dict[str, str]:
    """Fetch and cache OHLCV history for symbols, skipping any whose cache
    is already fresh (unless force_refresh). Returns {symbol: status} where
    status is one of "cached" (skipped, already fresh), "updated", "empty"
    (no data returned by yfinance), or "error".
    """
    targets = symbols if force_refresh else [s for s in symbols if not _is_fresh(s)]
    status: dict[str, str] = {s: "cached" for s in symbols if s not in targets}

    for i in range(0, len(targets), batch_size):
        batch = targets[i : i + batch_size]
        try:
            raw = yf.download(
                batch,
                period=period,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as exc:  # yfinance/network errors — skip this batch, keep going
            for s in batch:
                status[s] = f"error: {exc}"
            continue

        is_multi = isinstance(raw.columns, pd.MultiIndex)
        for sym in batch:
            try:
                sym_df = raw[sym] if is_multi else raw
                sym_df = sym_df.dropna(how="all")
                if sym_df.empty:
                    status[sym] = "empty"
                    continue
                sym_df = sym_df[_COLUMNS]
                _save_prices(sym, sym_df)
                status[sym] = "updated"
            except (KeyError, Exception) as exc:
                status[sym] = f"error: {exc}"

        if i + batch_size < len(targets):
            time.sleep(sleep_between_batches)

    return status


def get_price_history(symbol: str, period: str = "2y", force_refresh: bool = False) -> pd.DataFrame:
    """Convenience single-symbol accessor: returns cached data if fresh,
    otherwise fetches and caches it first.
    """
    if not force_refresh and _is_fresh(symbol):
        cached = load_cached_prices(symbol)
        if cached is not None:
            return cached
    refresh_price_cache([symbol], period=period, force_refresh=True)
    return load_cached_prices(symbol) or pd.DataFrame(columns=_COLUMNS)


if __name__ == "__main__":
    result = refresh_price_cache(["AAPL", "MSFT", "NVDA"], period="6mo")
    print(result)
    print(load_cached_prices("AAPL").tail())
