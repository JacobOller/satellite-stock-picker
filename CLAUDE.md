# CLAUDE.md

This file gives working conventions for Claude Code sessions in this repo.
See `plan.md` for the full project plan and roadmap.

## What this project is

A decision-support tool for a satellite investing account (~20% of the
user's total portfolio). It scans US large/mid-cap stocks (S&P 500 +
Nasdaq), scores them with a blended fundamental/technical/quant model, and
sends a daily push alert with the top 3-5 new ideas plus a suggested
position size. Holding period is weeks-months.

## How this project is built

This is a deliberate experiment in hands-off AI coding: the user wants
Claude to write and operate essentially all of the code, staying out of
the implementation loop as much as possible. Default to building the next
roadmap item using judgment and `plan.md` as the spec, rather than waiting
for step-by-step direction. Still stop and ask when a decision is genuinely
the user's to make — scope changes, or anything in the hard constraints
below.

### Permissions mode

This project's `.claude/settings.json` sets `permissions.defaultMode` to
`bypassPermissions` (project-scoped only — not user-wide), so Claude runs
here with tool-call approval prompts turned off, in support of the
hands-off goal above.

- This takes effect on a fresh session/restart (the settings watcher only
  picks up `.claude/` if it existed when the session started), and the
  first time bypass mode actually activates it shows a one-time warning
  dialog that must be accepted.
- Anthropic's own guidance is that bypass mode is intended for isolated
  environments (container/VM, no internet) because it removes safety
  prompts and gives no protection against prompt injection. This project
  needs live internet access (market data APIs), so that guidance doesn't
  fully apply here — the user made this trade-off knowingly, since no real
  money or sensitive credentials are at stake in the code itself.
- This does **not** loosen the hard constraints below. Bypass mode means
  Claude isn't asked to approve routine file/shell operations — it does
  not mean the project's own safety rules (no auto-trading, no live broker
  writes, no committed secrets) are up for reinterpretation.
- To change or turn this off: edit `.claude/settings.json` in this repo
  (or delete it to fall back to normal prompting).

## Hard constraints — do not violate

- **Never place trades automatically.** This tool only surfaces ideas and
  suggested position sizes; the user always decides and executes manually
  (currently in Fidelity). Do not add order-execution code without explicit
  user request and confirmation at the time.
- **No stop-loss/exit logic in v1.** This is intentionally deferred to
  phase 4 (see `plan.md`). Don't add it opportunistically.
- **Account data is manually entered.** There is no live brokerage
  connection yet. Don't wire up Alpaca (or any broker) API calls unless the
  user asks — it's planned but not started.
- **Never commit API keys/secrets.** Fundamentals API keys (FMP/Finnhub)
  and any future broker keys go in a `.env` file, which must be gitignored.

## Tech stack & conventions

- Python 3.11+.
- Dependencies in `requirements.txt`; use a venv (`.venv/`, gitignored).
- Prefer small, testable, pure functions for the scoring engine — it must
  run identically inside the backtester and the live daily scan. Avoid
  putting scoring logic only inside notebooks or one-off scripts.
- Cache external data (price history, fundamentals, universe lists) to
  disk (parquet/SQLite) rather than re-fetching on every run — free-tier
  API rate limits are a real constraint here.
- Data sources: `yfinance` for price/technicals (free, no key); Financial
  Modeling Prep or Finnhub free tier for fundamentals (needs an API key in
  `.env`).

## Current state

No code has been written yet — this repo currently contains only `plan.md`
and this file. Build order follows the phases in `plan.md`: universe +
data ingestion + scoring skeleton + backtest harness first, before any live
daily run or alerting is wired up.

## Before trusting a strategy change live

Any change to factor weights or scoring logic should be run through the
backtester first (walk-forward, not single in-sample fit) and compared
against a simple benchmark (e.g. SPY buy-and-hold) before it affects the
live daily alert.
