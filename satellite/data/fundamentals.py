"""Fundamentals ingestion via Financial Modeling Prep (FMP), cached to disk.

Free-tier FMP is capped at ~250 calls/day (as of 2026). This module makes
3 calls per symbol (profile, ratios-ttm, key-metrics-ttm), so a full
universe refresh (thousands of symbols) cannot happen in one day on the
free tier — callers should budget/throttle via `max_symbols` and rely on
the on-disk cache (FUNDAMENTALS_REFRESH_DAYS) to spread refreshes out.

NOTE: field names verified live 2026-08-02 against a real FMP key (5
symbols across sectors: MSFT, JPM, XOM, JNJ, KO) — all fields populated
with sane values. `extract_factor_inputs` still reads defensively with
multiple candidate key names and returns None for anything missing, in
case free-tier field coverage varies by symbol.
"""

from __future__ import annotations

import json
import time

import requests

from satellite.config import FMP_API_KEY, FUNDAMENTALS_CACHE_DIR, FUNDAMENTALS_REFRESH_DAYS

_BASE_URL = "https://financialmodelingprep.com/stable"
_ENDPOINTS = {
    "profile": "profile",
    "ratios_ttm": "ratios-ttm",
    "key_metrics_ttm": "key-metrics-ttm",
}

FMP_DAILY_CALL_BUDGET = 250
CALLS_PER_SYMBOL = len(_ENDPOINTS)


class FmpNotConfigured(RuntimeError):
    pass


def _cache_path(symbol: str):
    return FUNDAMENTALS_CACHE_DIR / f"{symbol}.json"


def _is_fresh(symbol: str) -> bool:
    path = _cache_path(symbol)
    if not path.exists():
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days < FUNDAMENTALS_REFRESH_DAYS


def load_cached_fundamentals(symbol: str) -> dict | None:
    path = _cache_path(symbol)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _fmp_get(endpoint_key: str, symbol: str) -> list | dict | None:
    if not FMP_API_KEY:
        raise FmpNotConfigured("FMP_API_KEY is not set in .env — fundamentals data unavailable")
    url = f"{_BASE_URL}/{_ENDPOINTS[endpoint_key]}"
    resp = requests.get(url, params={"symbol": symbol, "apikey": FMP_API_KEY}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data


def fetch_fundamentals_raw(symbol: str) -> dict:
    """Fetch profile + TTM ratios + TTM key metrics for one symbol and
    combine into a single flat dict (each source's first list item, since
    FMP returns a one-element list for *-ttm/profile-by-symbol calls).
    Raises FmpNotConfigured if no API key is set.
    """
    combined: dict = {"symbol": symbol}
    for key in _ENDPOINTS:
        data = _fmp_get(key, symbol)
        record = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        combined[key] = record
    return combined


def _save_fundamentals(symbol: str, raw: dict) -> None:
    _cache_path(symbol).parent.mkdir(parents=True, exist_ok=True)
    _cache_path(symbol).write_text(json.dumps(raw))


def refresh_fundamentals_cache(
    symbols: list[str], max_symbols: int | None = None, force_refresh: bool = False
) -> dict[str, str]:
    """Refresh fundamentals cache for symbols whose cache is stale/missing,
    up to max_symbols (to respect the free-tier daily call budget). Returns
    {symbol: status}: "cached" (skipped), "updated", or "error: ...".
    """
    targets = symbols if force_refresh else [s for s in symbols if not _is_fresh(s)]
    if max_symbols is not None:
        targets = targets[:max_symbols]
    status: dict[str, str] = {s: "cached" for s in symbols if s not in targets}

    for symbol in targets:
        try:
            raw = fetch_fundamentals_raw(symbol)
            _save_fundamentals(symbol, raw)
            status[symbol] = "updated"
        except Exception as exc:
            status[symbol] = f"error: {exc}"

    return status


def extract_factor_inputs(raw: dict) -> dict:
    """Normalize a raw FMP record into the flat set of fields the scoring
    engine consumes. Missing fields come back as None rather than raising,
    since free-tier coverage/field availability can vary by symbol.
    """
    profile = raw.get("profile", {}) or {}
    ratios = raw.get("ratios_ttm", {}) or {}
    metrics = raw.get("key_metrics_ttm", {}) or {}

    def first(d: dict, *keys):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    def first_of(*dict_key_pairs):
        """Like first(), but searches across multiple (dict, key) sources
        in order — needed because FMP splits fields across ratios_ttm and
        key_metrics_ttm inconsistently (e.g. ROE and FCF yield live in
        key_metrics_ttm, not ratios_ttm). Checks `is not None`, not
        truthiness, so a legitimate 0.0 isn't skipped.
        """
        for d, key in dict_key_pairs:
            if key in d and d[key] is not None:
                return d[key]
        return None

    return {
        "symbol": raw.get("symbol"),
        "market_cap": first(profile, "marketCap", "mktCap"),
        "sector": first(profile, "sector"),
        "industry": first(profile, "industry"),
        "pe_ratio": first(ratios, "priceToEarningsRatioTTM", "peRatioTTM"),
        "pb_ratio": first(ratios, "priceToBookRatioTTM", "pbRatioTTM"),
        "fcf_yield": first_of((metrics, "freeCashFlowYieldTTM"), (ratios, "freeCashFlowYieldTTM")),
        "roe": first_of((metrics, "returnOnEquityTTM"), (ratios, "returnOnEquityTTM")),
        "gross_margin": first(ratios, "grossProfitMarginTTM"),
        "net_margin": first(ratios, "netProfitMarginTTM"),
        "debt_to_equity": first(ratios, "debtToEquityRatioTTM", "debtEquityRatioTTM"),
        "roic": first(metrics, "returnOnInvestedCapitalTTM", "roicTTM"),
        "earnings_yield": first(metrics, "earningsYieldTTM"),
    }


def get_fundamentals(symbol: str) -> dict | None:
    """Cached-first fundamentals accessor. Returns extracted factor inputs,
    or None if nothing is cached and FMP isn't configured / the fetch fails.
    """
    raw = load_cached_fundamentals(symbol)
    if raw is None:
        try:
            raw = fetch_fundamentals_raw(symbol)
            _save_fundamentals(symbol, raw)
        except Exception:
            return None
    return extract_factor_inputs(raw)


if __name__ == "__main__":
    if not FMP_API_KEY:
        print("FMP_API_KEY not set — add it to .env to test live fundamentals fetch.")
    else:
        result = refresh_fundamentals_cache(["AAPL"], max_symbols=1)
        print(result)
        print(get_fundamentals("AAPL"))
