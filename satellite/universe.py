"""Universe construction: S&P 500 + Nasdaq-listed common stocks.

Sourced from static/periodic listings (not a paid reference-data API) and
cached locally, per plan.md. Refresh cadence is weekly at most — index and
listing changes are infrequent.

NOTE (2026-08-03): the on-disk cache (_CACHE_FILE) is gitignored, so it
doesn't exist in the cloud routine's fresh-checkout environment — every
cloud run has to hit Wikipedia/Nasdaq live. The first live run hit a 403
from Wikipedia (cloud sandbox's outbound proxy, not a code bug — the
same fetch works fine locally). Since build_universe() can't cache its
way out of a cold start, it now falls back to _SNAPSHOT_PATH, a small
CSV checked into the repo (unlike the cache dir), whenever a live fetch
fails for any reason. The snapshot goes stale as constituents change
(rare) — refresh it with `python -m satellite.universe --refresh-snapshot`
from an environment where the live fetch works.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from satellite.config import UNIVERSE_CACHE_DIR, UNIVERSE_REFRESH_DAYS

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"

_CACHE_FILE = UNIVERSE_CACHE_DIR / "universe.parquet"
_SNAPSHOT_PATH = Path(__file__).resolve().parent / "universe_snapshot.csv"

# Heuristic exclusion of non-common-stock listings (warrants, rights, units,
# preferreds, test issues) since the Nasdaq symbol directory mixes these in
# with ordinary common stock under one flat file.
_EXCLUDE_NAME_KEYWORDS = (
    "Warrant",
    "Right",
    " Unit",
    "Preferred",
    "Depositary",
    "Notes",
)


@dataclass(frozen=True)
class UniverseEntry:
    symbol: str
    name: str
    source: str  # "sp500" or "nasdaq"


def _fetch_sp500() -> pd.DataFrame:
    resp = requests.get(_SP500_URL, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    table = pd.read_html(StringIO(resp.text))[0]
    df = table[["Symbol", "Security"]].rename(columns={"Symbol": "symbol", "Security": "name"})
    df["symbol"] = df["symbol"].str.replace(".", "-", regex=False).str.strip()
    df["source"] = "sp500"
    return df


def _fetch_nasdaq_listed() -> pd.DataFrame:
    resp = requests.get(_NASDAQ_LISTED_URL, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    # Last line is a footer ("File Creation Time: ...") — drop it.
    lines = resp.text.strip().splitlines()
    body = "\n".join(lines[:-1]) if lines and lines[-1].startswith("File Creation Time") else "\n".join(lines)
    df = pd.read_csv(StringIO(body), sep="|")

    df = df[(df["Test Issue"] == "N") & (df["ETF"] == "N")]
    name_mask = ~df["Security Name"].str.contains("|".join(_EXCLUDE_NAME_KEYWORDS), case=False, na=False)
    df = df[name_mask]

    out = df[["Symbol", "Security Name"]].rename(columns={"Symbol": "symbol", "Security Name": "name"})
    out["symbol"] = out["symbol"].str.strip()
    out["source"] = "nasdaq"
    return out


def _cache_is_fresh() -> bool:
    if not _CACHE_FILE.exists():
        return False
    age_days = (time.time() - _CACHE_FILE.stat().st_mtime) / 86400
    return age_days < UNIVERSE_REFRESH_DAYS


def _load_snapshot(source: str) -> pd.DataFrame:
    """Bundled fallback slice of the last known-good universe, checked
    into the repo. Used when the live fetch fails (e.g. the cloud
    routine's outbound proxy gets a 403 from Wikipedia/Nasdaq)."""
    if not _SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"{_SNAPSHOT_PATH} is missing and the live {source} fetch failed — no data available"
        )
    snapshot = pd.read_csv(_SNAPSHOT_PATH, dtype=str)
    return snapshot[snapshot["source"] == source].reset_index(drop=True)


def _fetch_sp500_resilient() -> pd.DataFrame:
    try:
        return _fetch_sp500()
    except Exception as exc:
        print(f"WARNING: live S&P 500 fetch failed ({exc!r}); falling back to bundled snapshot")
        return _load_snapshot("sp500")


def _fetch_nasdaq_resilient() -> pd.DataFrame:
    try:
        return _fetch_nasdaq_listed()
    except Exception as exc:
        print(f"WARNING: live Nasdaq-listed fetch failed ({exc!r}); falling back to bundled snapshot")
        return _load_snapshot("nasdaq")


def build_universe(force_refresh: bool = False) -> pd.DataFrame:
    """Return the combined S&P 500 + Nasdaq-listed universe as a DataFrame
    with columns [symbol, name, source], deduped by symbol (sp500 wins on
    overlap). Uses a local parquet cache refreshed at most every
    UNIVERSE_REFRESH_DAYS days. Falls back to a bundled snapshot per
    source if a live fetch fails (see module docstring).
    """
    if not force_refresh and _cache_is_fresh():
        return pd.read_parquet(_CACHE_FILE)

    sp500 = _fetch_sp500_resilient()
    nasdaq = _fetch_nasdaq_resilient()

    combined = pd.concat([sp500, nasdaq], ignore_index=True)
    combined = combined.drop_duplicates(subset="symbol", keep="first")
    combined = combined.sort_values("symbol").reset_index(drop=True)

    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(_CACHE_FILE, index=False)
    except OSError:
        pass  # read-only or unavailable filesystem (e.g. some sandboxes) -- caching is best-effort
    return combined


def _refresh_snapshot() -> None:
    """Regenerate the bundled fallback snapshot from a live fetch. Run
    this occasionally from an environment where the live fetch works
    (i.e. not the cloud routine) to keep the fallback from going stale.
    """
    sp500 = _fetch_sp500()
    nasdaq = _fetch_nasdaq_listed()
    combined = pd.concat([sp500, nasdaq], ignore_index=True)
    combined = combined.drop_duplicates(subset="symbol", keep="first")
    combined = combined.sort_values("symbol").reset_index(drop=True)
    combined.to_csv(_SNAPSHOT_PATH, index=False)
    print(f"Wrote {len(combined)} rows to {_SNAPSHOT_PATH}")


def load_universe_symbols(force_refresh: bool = False) -> list[str]:
    return build_universe(force_refresh=force_refresh)["symbol"].tolist()


if __name__ == "__main__":
    if "--refresh-snapshot" in sys.argv:
        _refresh_snapshot()
    else:
        df = build_universe()
        print(f"Universe size: {len(df)}")
        print(df["source"].value_counts())
        print(df.head(10))
