"""Fundamentals ingestion via Finnhub — alternative to FMP
(satellite/data/fundamentals.py), per plan.md's Data sources table.

Finnhub's free tier is far less constrained than FMP's (60 calls/min vs.
~250/day total), so this is worth having ready even though FMP was built
first. Same interface shape as fundamentals.py (fetch_fundamentals_raw,
refresh_fundamentals_cache, get_fundamentals, extract_factor_inputs) so
either module can back the scoring engine without touching callers.

NOTE: verified live 2026-08-02 against a real Finnhub key (5 symbols
across sectors). roic and earnings_yield are not present anywhere in the
free-tier metric=all response (confirmed by inspecting all 133 keys for
MSFT) — they will always be None here, unlike FMP which provides both.
"""

from __future__ import annotations

import json
import time

import requests

from satellite.config import FINNHUB_API_KEY, FUNDAMENTALS_CACHE_DIR, FUNDAMENTALS_REFRESH_DAYS

_BASE_URL = "https://finnhub.io/api/v1"
_CACHE_DIR = FUNDAMENTALS_CACHE_DIR / "finnhub"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

CALLS_PER_SYMBOL = 2  # profile2 + metric


class FinnhubNotConfigured(RuntimeError):
    pass


def _cache_path(symbol: str):
    return _CACHE_DIR / f"{symbol}.json"


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


def _finnhub_get(path: str, params: dict) -> dict:
    if not FINNHUB_API_KEY:
        raise FinnhubNotConfigured("FINNHUB_API_KEY is not set in .env — fundamentals data unavailable")
    resp = requests.get(f"{_BASE_URL}/{path}", params={**params, "token": FINNHUB_API_KEY}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_fundamentals_raw(symbol: str) -> dict:
    profile = _finnhub_get("stock/profile2", {"symbol": symbol})
    basic_financials = _finnhub_get("stock/metric", {"symbol": symbol, "metric": "all"})
    return {"symbol": symbol, "profile": profile, "metric": basic_financials.get("metric", {})}


def _save_fundamentals(symbol: str, raw: dict) -> None:
    _cache_path(symbol).write_text(json.dumps(raw))


def refresh_fundamentals_cache(
    symbols: list[str], max_symbols: int | None = None, force_refresh: bool = False
) -> dict[str, str]:
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
    """Normalize a raw Finnhub record to the same flat field set FMP's
    extract_factor_inputs produces, so scoring code is provider-agnostic.
    """
    profile = raw.get("profile", {}) or {}
    metric = raw.get("metric", {}) or {}

    def first(d: dict, *keys):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    def pct_to_fraction(value):
        """Finnhub reports ROE/margins as percentages (33.2 = 33.2%);
        FMP reports them as decimal fractions (0.332). Normalize to FMP's
        convention so the two providers are truly interchangeable inputs
        to score_fundamentals' cross-sectional percentile ranking —
        otherwise a symbol sourced from the "wrong" provider would rank
        as if its ROE were 100x everyone else's.
        """
        return value / 100 if value is not None else None

    market_cap_millions = first(profile, "marketCapitalization")

    return {
        "symbol": raw.get("symbol"),
        "market_cap": market_cap_millions * 1_000_000 if market_cap_millions is not None else None,
        "sector": first(profile, "finnhubIndustry"),
        "industry": first(profile, "finnhubIndustry"),
        "pe_ratio": first(metric, "peTTM", "peExclExtraTTM", "peBasicExclExtraTTM", "peNormalizedAnnual"),
        "pb_ratio": first(metric, "pbAnnual", "pbQuarterly", "pb"),
        "fcf_yield": None,  # not directly provided by Finnhub's free basic-financials set
        "roe": pct_to_fraction(first(metric, "roeTTM", "roeRfy", "roeAnnual")),
        "gross_margin": pct_to_fraction(first(metric, "grossMarginTTM", "grossMarginAnnual")),
        "net_margin": pct_to_fraction(first(metric, "netProfitMarginTTM", "netMarginTTM", "netProfitMarginAnnual")),
        "debt_to_equity": first(metric, "totalDebt/totalEquityAnnual", "totalDebt/totalEquityQuarterly"),
        "roic": None,  # not present in Finnhub's free metric=all response (checked live 2026-08-02)
        "earnings_yield": None,  # not present in Finnhub's free metric=all response (checked live 2026-08-02)
    }


def get_fundamentals(symbol: str) -> dict | None:
    raw = load_cached_fundamentals(symbol)
    if raw is None:
        try:
            raw = fetch_fundamentals_raw(symbol)
            _save_fundamentals(symbol, raw)
        except Exception:
            return None
    return extract_factor_inputs(raw)


if __name__ == "__main__":
    if not FINNHUB_API_KEY:
        print("FINNHUB_API_KEY not set — add it to .env to test live fundamentals fetch.")
    else:
        result = refresh_fundamentals_cache(["AAPL"], max_symbols=1)
        print(result)
        print(get_fundamentals("AAPL"))
