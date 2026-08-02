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

**Phase 1 — Foundations** ✅ done (2026-08-02)
- [x] Universe list fetch/cache.
- [x] Data ingestion layer (price + fundamentals) with local caching.
- [x] Scoring engine skeleton with placeholder weights.
- [x] Backtest harness (data replay + metrics).
- [x] Ranker (top-N selection, diversification filter) — pulled forward
  from Phase 3, since it's cheap plumbing and the backtester needs it too.
- [x] Position sizing / satellite-exposure tracking — pulled forward from
  Phase 3 for the same reason; no live account connection involved.

**Phase 2 — Strategy validation** 🚧 in progress, partially blocked
- [x] Walk-forward backtest mechanism (train/test windowing, weight
  selection on train, out-of-sample evaluation on test).
- [ ] Implement all three factor groups fully — **blocked**: fundamentals
  ingestion code is written (`satellite/data/fundamentals.py`) but
  untested against a live API, since no FMP (or Finnhub) key exists yet.
  Needs the user to sign up and add a key to `.env`.
- [ ] Run walk-forward backtests, tune weights, document results — a
  technical+quant-only walk-forward ran successfully on 99 real S&P 500
  symbols (2026-08-02, see Progress log below) as a mechanism check, but
  this is **not** a strategy validation: no fundamental factor, and the
  aggregate drawdown figure is methodologically shaky (built from
  overlapping 42-day holding periods sampled every ~10 trading days,
  which isn't a valid non-overlapping equity curve). Needs redoing once
  fundamentals are wired in and the metrics harness handles overlapping
  positions properly.
- [ ] Decide go/no-go on live use based on backtest performance.

**Phase 3 — Live daily operation**
- Wire up daily scheduled run.
- Push-notification alert formatting.
- ~~Manual account-value config + position sizing output.~~ done early,
  see Phase 1.

**Phase 4 — Future enhancements (not yet scoped in detail)**
- Stop-loss / exit logic (fixed %, ATR-based, or technical-level — revisit
  once live results exist).
- Swap manual account entry for Alpaca API (account data first, possibly
  semi-automated order placement later, always with confirmation).
- Reassess data budget if free-tier limits become a bottleneck.

## Progress log

**2026-08-02 — Phase 1 foundations built.** Universe fetch/cache
(S&P 500 via Wikipedia + Nasdaq-listed common stock, ~3,588 tickers),
yfinance price ingestion, FMP fundamentals ingestion (code-complete,
unverified live — no API key available), a three-group scoring engine
(fundamental/technical/quant + composite blend), and a backtest replay
engine with hit-rate/drawdown/benchmark metrics. 30 tests. Verified
end-to-end on a real 15-symbol S&P 500 sample, including graceful
degradation to technical+quant-only scoring when fundamentals are
unavailable. Committed as `9a99e3f`.

**2026-08-02 — Ranker, position sizing, walk-forward harness added.**
Built while the user was away for ~1hr with standing permission to work
without asking and to skip anything requiring a security choice (so: no
FMP/Finnhub signup, no `.env` changes). Added `satellite/ranker.py`
(top-N selection, existing-holdings exclusion, concurrent-position cap,
optional sector-diversification filter) and `satellite/risk.py` (manual
account-value position sizing, aggregate satellite-exposure tracking) —
both pulled forward from Phase 3 since they're pure/local and the
backtester benefits from having them too. Added
`satellite/backtest/walkforward.py`: slices rebalance dates into
train/test windows, grid-searches the technical-vs-quant weight balance
on the train window, evaluates out-of-sample on the test window. 14 new
tests (44 total).

Ran a 100-symbol (99 usable) real-data walk-forward backtest, 2024-05
through 2026-03, technical+quant-only (no fundamentals available): 16
windows, 45 test-period observations, mean test return +6.7% vs. SPY's
+2.8% over the same ~42-trading-day holding periods, 67% win rate vs.
benchmark. **Treat this as a plumbing check, not a strategy result** —
see the Phase 2 caveat above (overlapping-period drawdown calc,
missing fundamental factor). Full output saved to a local scratch dir,
not committed (it's a one-off run, not the harness itself).

Also added `satellite/data/fundamentals_finnhub.py`, a Finnhub client
mirroring the FMP fundamentals client's interface — Finnhub's free tier
(60 calls/min) is far less constrained than FMP's (~250/day), so it's a
ready swap-in once the user picks a provider and gets a key. 46 tests
total. Committed as `1fc8b42`, `183ba96`, `0858f9c`.

## Open questions to revisit later

- Exact factor weights — determined empirically via backtesting, not fixed
  up front.
- Whether to add sector/diversification constraints on top of raw score
  ranking.
- Whether daily cadence proves too noisy vs. the weeks-months holding
  period once live — may revisit to weekly.
- Backtest metrics currently treat sequential rebalance-period returns as
  if non-overlapping when building the equity curve / drawdown figure,
  but holding_days (42) is longer than the rebalance step (~10 trading
  days), so positions actually overlap. Needs either non-overlapping
  sampling or a proper portfolio-level simulation before drawdown numbers
  can be trusted for a go/no-go call.
