# Satellite Stock-Picker — Plan

## Meta: how this project gets built

This is explicitly a side-project experiment in hands-off AI coding: the
user wants **Claude to write and operate all of the code**, with the user
staying out of the implementation loop as much as possible, to see how far
a "fully Claude-coded" project can go. Implications for future sessions:

- Default to just building the next roadmap item rather than waiting for
  detailed direction — use judgment and this plan as the spec.
- Still pause and ask when a decision is genuinely the user's to make
  (e.g. changing scope, spending real money, connecting a live brokerage
  account) — see the hard constraints in `CLAUDE.md`.
- The one line that can never move: **no real money moves without the
  user explicitly doing it themselves.** Hands-off applies to the code,
  not to trade execution.

## Goal

A decision-support tool for a satellite investing account (~20% of total
portfolio). It scans a defined stock universe, scores candidates using a
blended fundamental + technical + quant approach, and alerts on the best
new ideas. It never places trades on its own.

## Non-goals (v1)

- No automated order execution.
- No stop-loss / exit logic (flagged as phase 4, see Roadmap).
- No live brokerage account connection (manual account-value entry for now).

## Architecture

```
[Universe list] -> [Data ingestion] -> [Scoring engine] -> [Ranker] -> [Alert]
                                              |
                                        [Backtester] (offline, validates scoring)
```

- **Universe list**: S&P 500 + Nasdaq constituents. Sourced from a
  periodically-refreshed static list (e.g. Wikipedia S&P 500 table + Nasdaq
  listed-securities file), cached locally to avoid re-fetching every run.
- **Data ingestion**: pulls price history + fundamentals per ticker, caches
  to disk (parquet/SQLite) to stay within free-tier rate limits.
- **Scoring engine**: computes a composite score per ticker from three
  factor groups (see below). Pure functions, easy to unit test and to run
  identically in backtest and live modes.
- **Ranker**: sorts scored universe, applies any universe/diversification
  filters, takes the top N.
- **Alert**: formats the top 3-5 new ideas into a push notification.
- **Backtester**: replays the scoring engine over historical data to
  validate/tune factor weights before trusting live signals.

## Data sources

| Need | Source | Notes |
|---|---|---|
| Price history / technicals | `yfinance` (free) | No API key; watch for rate limiting on full-universe pulls |
| Fundamentals | Financial Modeling Prep or Finnhub (free tier) | Requires a free API key; a few hundred calls/day — fine at daily/weekly cadence with caching |
| Universe constituents | Static S&P 500 / Nasdaq listing sources | Refresh weekly at most; index changes are infrequent |

Start free. Revisit paid data (Polygon.io, IEX Cloud) only if data quality
or rate limits become an actual blocker.

## Scoring methodology

Composite score = weighted blend of three factor groups:

1. **Fundamental** — valuation (P/E, P/B, FCF yield), earnings quality/growth,
   profitability (margins, ROE).
2. **Technical** — trend (moving averages), momentum (RSI/MACD), relative
   strength vs. sector/benchmark.
3. **Quant/factor** — cross-sectional ranking of the above (value, momentum,
   quality, size) relative to the rest of the universe, so scores are
   comparable across sectors.

Initial factor weights are a starting guess; **the backtester is what
actually tunes/validates these weights** before they're trusted live.

## Risk & position sizing

- Account value entered manually (Fidelity account, no API available).
- Small-account profile: cap at 5-8 concurrent satellite positions.
- Suggested position size per idea = account value × max allocation %
  (tighter concentration than a diversified core, but capped to avoid
  over-concentration in any single name).
- Tool tracks total satellite exposure so you can see aggregate risk across
  open ideas, not just per-trade.
- No stop-loss/exit rules in v1 — entries are flagged, exits are manual
  until phase 4.

## Backtesting plan

- Historical price + fundamentals data, walk-forward validation (train
  weights on one period, test on a later out-of-sample period) rather than
  a single in-sample fit.
- Metrics: hit rate, average return per idea, holding-period return
  distribution, max drawdown, comparison against a simple benchmark
  (e.g. SPY buy-and-hold over the same period).
- Backtest must run before any weight change is trusted in the live scan.

## Runtime & scheduling

- Daily scheduled run via Claude Code's `schedule` skill (cloud agent,
  no local infra to maintain).
- Timed for premarket / before-open so ideas are actionable same-day.

## Alerting

- Push notification (Claude Code native), not email/Slack — zero extra
  setup.
- Content per alert: top 3-5 new ideas, each with ticker, composite score,
  short rationale (which factors drove it), and suggested position size
  given current account value.

## Roadmap

**Phase 1 — Foundations**
- Universe list fetch/cache.
- Data ingestion layer (price + fundamentals) with local caching.
- Scoring engine skeleton with placeholder weights.
- Backtest harness (data replay + metrics).

**Phase 2 — Strategy validation**
- Implement all three factor groups fully.
- Run walk-forward backtests, tune weights, document results.
- Decide go/no-go on live use based on backtest performance.

**Phase 3 — Live daily operation**
- Wire up daily scheduled run.
- Push-notification alert formatting.
- Manual account-value config + position sizing output.

**Phase 4 — Future enhancements (not yet scoped in detail)**
- Stop-loss / exit logic (fixed %, ATR-based, or technical-level — revisit
  once live results exist).
- Swap manual account entry for Alpaca API (account data first, possibly
  semi-automated order placement later, always with confirmation).
- Reassess data budget if free-tier limits become a bottleneck.

## Open questions to revisit later

- Exact factor weights — determined empirically via backtesting, not fixed
  up front.
- Whether to add sector/diversification constraints on top of raw score
  ranking.
- Whether daily cadence proves too noisy vs. the weeks-months holding
  period once live — may revisit to weekly.
