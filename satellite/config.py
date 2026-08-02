"""Central config: paths, env vars, and tunable constants.

Placeholder values (cache TTLs, position sizing, factor weights) are
starting guesses per plan.md — the backtester is what actually validates
them before they're trusted live.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / "data_cache"
UNIVERSE_CACHE_DIR = CACHE_DIR / "universe"
PRICE_CACHE_DIR = CACHE_DIR / "prices"
FUNDAMENTALS_CACHE_DIR = CACHE_DIR / "fundamentals"

for _dir in (CACHE_DIR, UNIVERSE_CACHE_DIR, PRICE_CACHE_DIR, FUNDAMENTALS_CACHE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# --- API keys (fundamentals require one of these; price data via yfinance needs none) ---
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# --- Cache freshness ---
UNIVERSE_REFRESH_DAYS = 7
FUNDAMENTALS_REFRESH_DAYS = 7
PRICE_REFRESH_HOURS = 20  # ~daily; price history is pulled once per trading day

# --- Position sizing / risk (plan.md: "Risk & position sizing") ---
MAX_CONCURRENT_POSITIONS = 8
MIN_CONCURRENT_POSITIONS_TARGET = 5
MAX_ALLOCATION_PCT_PER_POSITION = 0.10  # of satellite account value, not total portfolio

# --- Ranker output ---
TOP_N_IDEAS_MIN = 3
TOP_N_IDEAS_MAX = 5

# --- Composite scoring weights (placeholder — see plan.md Scoring methodology;
#     must be validated via backtest before use in a live alert) ---
DEFAULT_FACTOR_WEIGHTS = {
    "fundamental": 0.4,
    "technical": 0.35,
    "quant": 0.25,
}
