"""Alert formatting: turns ranker output (with suggested position sizes
attached) into a human-readable daily alert, per plan.md's Architecture
("Alert") and Alerting section spec — top 3-5 new ideas, each with
ticker, composite score, short rationale (which factors drove it), and
suggested position size.

Pure function over an already-scored/sized DataFrame — no I/O — so it's
easy to test and reusable regardless of what actually delivers the
message (push notification, log, etc).
"""

from __future__ import annotations

import pandas as pd

_FACTOR_LABELS = {
    "fundamental_score": "fundamentals",
    "technical_score": "technical",
    "quant_score": "quant",
}


def _rationale(row: pd.Series) -> str:
    """Names whichever factor group(s) scored highest for this idea, so
    the alert explains *why* a symbol made the list, not just that it did.
    """
    scores = {label: row[col] for col, label in _FACTOR_LABELS.items() if col in row and pd.notna(row[col])}
    if not scores:
        return "insufficient data for rationale"
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    parts = [f"{label} {score:.0f}" for label, score in ranked]
    return f"led by {ranked[0][0]} ({', '.join(parts)})"


def format_idea_line(rank: int, symbol: str, row: pd.Series) -> str:
    size = row.get("suggested_position_size")
    size_str = f"${size:,.0f}" if size is not None and pd.notna(size) else "n/a"
    composite = row.get("composite_score")
    composite_str = f"{composite:.1f}/100" if composite is not None and pd.notna(composite) else "n/a"
    return f"{rank}. {symbol} - composite {composite_str}, suggested size {size_str} ({_rationale(row)})"


def format_alert(ranked_ideas: pd.DataFrame, as_of: pd.Timestamp | None = None) -> str:
    """ranked_ideas: output of satellite.ranker.select_top_ideas with
    suggested_position_size attached via satellite.risk.add_suggested_sizes
    (indexed by symbol, sorted best-first). Returns a plain-text alert
    body. Empty input produces an explicit "nothing cleared the bar"
    message rather than a blank alert, so a quiet day is distinguishable
    from a broken pipeline.
    """
    date_label = as_of.date() if as_of is not None else "today"
    if ranked_ideas.empty:
        return f"Satellite scan for {date_label}: no new ideas cleared the bar."

    lines = [f"Satellite ideas for {date_label} ({len(ranked_ideas)} new):"]
    for i, (symbol, row) in enumerate(ranked_ideas.iterrows(), start=1):
        lines.append(format_idea_line(i, symbol, row))
    if ranked_ideas.attrs.get("below_min_ideas"):
        lines.append("(Fewer than the usual 3-5 ideas cleared the bar today.)")
    return "\n".join(lines)
