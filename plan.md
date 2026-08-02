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
- [x] Implement all three factor groups fully — both FMP and Finnhub keys
  are live in `.env` and verified against real data (2026-08-02). Fixed a
  real Finnhub/FMP unit mismatch (market cap millions-vs-absolute,
  percent-vs-decimal ROE/margins) that would have silently corrupted
  cross-sectional scoring if a symbol's data came from a different
  provider than its peers. Full composite pipeline (fundamental +
  technical + quant) validated end-to-end on 110 real S&P 500 symbols —
  fundamental_score populated for 109/110. **Caveat:** this wires
  fundamentals into *live/current-day* scoring only. Point-in-time
  historical fundamentals for backtesting remain infeasible — FMP's free
  tier returns 402 (payment required) on the historical/quarterly ratios
  endpoint (confirmed live 2026-08-02), so the walk-forward backtest
  below is still technical+quant only, same as before.
- [x] Fixed the overlapping-holding-period drawdown bug flagged below:
  added `satellite/backtest/portfolio.py` (`daily_portfolio_returns`),
  which marks every open position to market daily and equal-weights
  whatever cohorts are open that day, instead of chaining full 42-day
  holding-period returns as if they were sequential, non-overlapping
  events (they aren't — holding_days=42 vs. a ~10-trading-day rebalance
  step means ~4 cohorts are open at once).
- [x] Reran the walk-forward backtest (technical+quant only, 109 real
  symbols, 5 windows, 100 test-period trades, 2026-08-02) with the fixed
  methodology — see Progress log for the honest numbers, including a
  materially worse drawdown than the old (buggy) calculation implied.
- [ ] Decide go/no-go on live use based on backtest performance — **open,
  and it's the user's call**: the corrected max drawdown (-31.46% vs.
  SPY's -8.88% over the same test window) is a meaningfully different
  risk picture than anything reported before the methodology fix, and
  this is still technical+quant only (no fundamental factor validated
  in backtest, per the caveat above).

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

**2026-08-02 (later same day) — Fundamentals unblocked, drawdown methodology
fixed, walk-forward rerun.** User provided a Finnhub API key; FMP key was
already in `.env` from earlier the same day. Both verified live against 5
real symbols (MSFT, JPM, XOM, JNJ, KO) — field names and value ranges
check out. Found and fixed a real bug in `fundamentals_finnhub.py`: it
returned market cap in millions and ROE/margins as percentages while FMP
uses absolute dollars and decimal fractions — both modules claim the same
interface, so a symbol sourced from the "wrong" provider relative to its
peers would have silently ranked as if its ROE were ~100x everyone
else's under `score_fundamentals`' cross-sectional percentile ranking.
Also fixed `fundamentals.py`'s ROE/FCF-yield extraction to check
`key_metrics_ttm` before `ratios_ttm` (verified live: `ratios_ttm` doesn't
reliably carry those fields). Confirmed `roic`/`earnings_yield` don't
exist anywhere in Finnhub's free `metric=all` response (133 keys checked
for MSFT) — hardcoded `None` there rather than a dead lookup.

Validated the full three-factor composite pipeline end-to-end on 110 real
S&P 500 symbols using cached prices + live Finnhub fundamentals:
`fundamental_score` populated for 109/110, `technical_score` for 110/110,
`composite_score` for all 110 — this is the "Implement all three factor
groups fully" roadmap item, done for live/current-day scoring. Tried to
extend this to backtesting (point-in-time historical fundamentals) but
FMP's free tier returns 402 on the historical/quarterly ratios endpoint —
confirmed infeasible on free tier, not just a rate-limit issue.

Fixed the overlapping-holding-period drawdown bug logged in the prior
session's Progress log entry: added `satellite/backtest/portfolio.py`
(`daily_portfolio_returns` + `benchmark_daily_returns`), which builds a
proper daily mark-to-market equity curve across overlapping rebalance
cohorts instead of chaining full 42-day holding-period returns as if
sequential. Reran the walk-forward backtest (technical+quant only, 109
real symbols, 5 windows, 100 test-period trades, test period 2025-09
through 2026-05): overall test avg return +15.33% per idea, 65.88% hit
rate, 76.47% win rate vs. SPY per rebalance period. With the corrected
equity curve: **strategy total return +50.53%, max drawdown -31.46%**
vs. **SPY buy-and-hold total return +13.49%, max drawdown -8.88%** over
the same window. This drawdown is materially worse than anything implied
by the old (buggy) methodology — a real data point for the still-open
go/no-go decision, not something to gloss over. 46 -> 51 tests (added
`test_portfolio.py`, updated `test_fundamentals_finnhub.py`'s fixtures to
match confirmed live units). Committed as `90d15aa`, `e676b01`, `7b219f5`.

## Open questions to revisit later

- Exact factor weights — determined empirically via backtesting, not fixed
  up front.
- Whether to add sector/diversification constraints on top of raw score
  ranking.
- Whether daily cadence proves too noisy vs. the weeks-months holding
  period once live — may revisit to weekly.
- ~~Backtest metrics currently treat sequential rebalance-period returns
  as if non-overlapping...~~ fixed 2026-08-02, see
  `satellite/backtest/portfolio.py` and the Phase 2 checklist above.
- Point-in-time historical fundamentals for backtesting: confirmed
  2026-08-02 that FMP's free tier blocks the historical/quarterly ratios
  endpoint outright (402), not just rate-limits it. If fundamentals ever
  need to be backtested, that likely means either a paid FMP tier or
  finding a different historical-fundamentals source — not a "wait for a
  bigger free-tier budget" problem.
