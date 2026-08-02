"""Ranker: turns composite-scored universe into a bounded list of new
ideas, per plan.md's Architecture ("Ranker: sorts scored universe, applies
any universe/diversification filters, takes the top N") and Risk &
position sizing section (concurrent-position cap).

Pure function over a DataFrame — no I/O — so it's identically usable live
and in the backtester.
"""

from __future__ import annotations

import pandas as pd

from satellite.config import (
    MAX_CONCURRENT_POSITIONS,
    TOP_N_IDEAS_MAX,
    TOP_N_IDEAS_MIN,
)


def select_top_ideas(
    scored_df: pd.DataFrame,
    existing_holdings: set[str] | None = None,
    top_n_min: int = TOP_N_IDEAS_MIN,
    top_n_max: int = TOP_N_IDEAS_MAX,
    max_concurrent_positions: int = MAX_CONCURRENT_POSITIONS,
    sector_col: str | None = None,
    max_per_sector: int | None = None,
) -> pd.DataFrame:
    """scored_df must be indexed by symbol with a composite_score column
    (as produced by satellite.scoring.composite.compute_composite_scores).

    Filters out symbols already held, caps the result at however many
    slots remain under max_concurrent_positions, then takes the top
    `top_n_max` scored candidates (fewer if slots or candidates run out).
    Never returns more than top_n_max rows even with plenty of open slots
    — top_n_min/top_n_max bound the *alert size*, not the position cap.

    If sector_col + max_per_sector are given, enforces a per-sector cap
    while walking the ranked list (plan.md's open question on
    diversification constraints — off by default since that's still
    undecided; pass max_per_sector to opt in).
    """
    candidates = scored_df.dropna(subset=["composite_score"]).copy()
    if existing_holdings:
        candidates = candidates[~candidates.index.isin(existing_holdings)]
    candidates = candidates.sort_values("composite_score", ascending=False)

    open_slots = max_concurrent_positions - len(existing_holdings or [])
    if open_slots <= 0:
        return candidates.iloc[0:0]

    take_n = min(top_n_max, open_slots)

    if sector_col and max_per_sector:
        sector_counts: dict[str, int] = {}
        picked_idx = []
        for symbol, row in candidates.iterrows():
            if len(picked_idx) >= take_n:
                break
            sector = row.get(sector_col)
            count = sector_counts.get(sector, 0)
            if sector is not None and count >= max_per_sector:
                continue
            picked_idx.append(symbol)
            sector_counts[sector] = count + 1
        picked = candidates.loc[picked_idx]
    else:
        picked = candidates.head(take_n)

    picked = picked.copy()
    picked["rank"] = range(1, len(picked) + 1)
    if len(picked) < top_n_min:
        picked.attrs["below_min_ideas"] = True
    return picked
