"""Risk & position sizing, per plan.md's "Risk & position sizing" section.

Account value and current holdings are manually entered (no live
brokerage connection — see CLAUDE.md hard constraints), so everything
here is pure computation over user-supplied numbers. No stop-loss/exit
logic — that's explicitly phase 4 (CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from satellite.config import (
    MAX_ALLOCATION_PCT_PER_POSITION,
    MAX_CONCURRENT_POSITIONS,
)


@dataclass(frozen=True)
class Position:
    symbol: str
    market_value: float  # current $ value of the holding, manually entered


def suggested_position_size(
    account_value: float, max_allocation_pct: float = MAX_ALLOCATION_PCT_PER_POSITION
) -> float:
    """Dollar size for a single new idea: account_value * max allocation %.
    Uniform per-idea sizing per plan.md — not adjusted for existing
    holdings (use satellite_exposure() separately to see aggregate risk).
    """
    return account_value * max_allocation_pct


def satellite_exposure(positions: list[Position], account_value: float) -> dict:
    """Aggregate risk across all currently open satellite positions."""
    total_value = sum(p.market_value for p in positions)
    return {
        "position_count": len(positions),
        "total_value": total_value,
        "pct_of_account": (total_value / account_value) if account_value else None,
        "open_slots": max(MAX_CONCURRENT_POSITIONS - len(positions), 0),
    }


def add_suggested_sizes(
    ranked_ideas: pd.DataFrame,
    account_value: float,
    max_allocation_pct: float = MAX_ALLOCATION_PCT_PER_POSITION,
) -> pd.DataFrame:
    """Attach a suggested_position_size column (and its % of account) to a
    ranker output DataFrame, given the current manually-entered account
    value.
    """
    out = ranked_ideas.copy()
    out["suggested_position_size"] = suggested_position_size(account_value, max_allocation_pct)
    out["suggested_position_pct"] = max_allocation_pct
    return out
