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
- [x] Found and fixed a second, more fundamental backtest bug while
  investigating the drawdown: `run_backtest` picked the naive top-N by
  score at every rebalance date with **no memory of what was already
  held**. Since holding_days (42) spans ~4 rebalance steps, the same
  top-scoring symbol got picked repeatedly — the first "fixed-drawdown"
  rerun below resolved to only 17 distinct symbols across 100 trades
  (CIEN picked 18/20 times, COHR 17/20), concentrating the simulated
  portfolio in 2-3 volatile names instead of the diversified book
  `satellite/ranker.py`'s `select_top_ideas` enforces live
  (existing-holdings exclusion + `MAX_CONCURRENT_POSITIONS` cap).
  `run_backtest` now tracks open positions with bar-accurate exit dates
  and applies the same rules — see `satellite/backtest/engine.py`.
- [x] Reran the walk-forward backtest (technical+quant only, 109 real
  symbols, 5 windows, 2026-08-02) with **both** fixes (daily-portfolio
  drawdown + position tracking) — see Progress log for the numbers.
  Note the position-tracking fix means far fewer trades resolve per
  window (the account-level concurrent-position cap fills up fast), so
  even 109 candidate symbols only produced 40 test-period trades.
- [x] Extended price history from 2y to 10y (yfinance, no key needed) and
  reran the walk-forward backtest for real statistical power: 120
  test-period trades across 30 rebalance periods spanning ~2.5 years
  (2024-02 through 2026-07), vs. 40 trades / 9 periods / ~8 months
  before. See Progress log for the current best numbers.
- [ ] Decide go/no-go on live use based on backtest performance — **open,
  and it's the user's call**: current best numbers (technical+quant
  only, corrected methodology, 2.5y test window) show strategy total
  return +195.45% vs. SPY's +55.76%, max drawdown -31.44% vs. SPY's
  -18.76%. The strategy beats the benchmark on both return and (now that
  the sample covers more regimes) the risk gap is smaller than the
  short-window estimate suggested — but a -31% drawdown on a satellite
  account is still a real number to sit with before trusting this live.

**Phase 3 — Live daily operation** ✅ activated 2026-08-03
- [x] Alert formatting: `satellite/alert.py` (`format_alert`) — pure
  function, top 3-5 ideas with ticker, composite score, short rationale
  (which factor group led), suggested position size. Fully tested.
- [x] Scan orchestration: `satellite/scan.py` (`run_scan`,
  `collect_universe_scores`) wires universe -> data ingestion -> scoring
  -> ranker -> sizing -> formatted alert, using Finnhub for fundamentals
  (higher free-tier budget than FMP). Added a `use_fundamentals` flag for
  environments without a fundamentals API key.
- [x] **Go/no-go decision made 2026-08-03: user approved activating live
  alerts.** Account value $250 (fresh, small, to be grown over time), no
  existing holdings.
- [x] Wire up daily scheduled run — went through two different
  mechanisms before landing on one that actually works:
  - **Cloud routine (abandoned):** pushed the repo to
    `github.com/JacobOller/satellite-stock-picker` (private) and created
    a `RemoteTrigger` cloud routine. Dead end: the cloud sandbox's
    outbound network is broadly restricted and blocked BOTH
    Wikipedia/Nasdaq (fixed via a bundled `satellite/universe_snapshot.csv`
    fallback, see below) AND Yahoo Finance itself (yfinance is this
    project's only price source — no workaround exists for that one).
    Also: no way to hand a cloud routine the FMP/Finnhub API keys
    securely (no secrets field in the routine config). Routine
    `trig_01R3YUnNuDRMvcw69YhJ7HVP` is disabled, not deleted.
  - **Local Windows Task Scheduler (active):** task
    `SatelliteStockPickerDailyScan` runs weekdays at 8:15am ET, invoking
    `claude.exe -p "..." --permission-mode bypassPermissions` (via a
    `powershell.exe` wrapper that redirects output to
    `daily_scan_task.log`) in this project directory. This has full
    access to local `.env` (both API keys) and `data_cache/`, so it uses
    the fuller fundamentals-included scan (`scripts/daily_scan.py`,
    account_value/existing_holdings hardcoded there — update by hand as
    the account changes). Two setup bugs found and fixed: (1)
    `New-ScheduledTaskSettingsSet` defaults to
    `DisallowStartIfOnBatteries=$true`, which silently left the task
    stuck in "Queued" — fixed by passing `-AllowStartIfOnBatteries
    -DontStopIfGoingOnBatteries`. (2) The first working run showed
    "push notification was sent but not delivered to mobile (Remote
    Control inactive)" — desktop notifications should still work; phone
    push needs the user to separately enable Remote Control pairing,
    which isn't something settable via CLI/API.
- [x] Fixed a related bug found via the cloud routine's first failure:
  `build_universe()` had no fallback if the live Wikipedia/Nasdaq fetch
  failed (crashes the whole scan). Added `satellite/universe_snapshot.csv`
  (checked into git, unlike the gitignored on-disk cache) as a
  per-source fallback. Regenerate via `python -m satellite.universe
  --refresh-snapshot`.
- [x] Fixed a real test-hygiene bug found while debugging the above: two
  `tests/test_universe.py` tests called `build_universe(force_refresh=
  True)` with mocked fetchers, and `build_universe()` unconditionally
  persists its result to the real on-disk cache — so running `pytest`
  had been silently corrupting the local universe cache with mock data.
  Fixed by monkeypatching `_CACHE_FILE` to a tmp path in both tests.
- [x] Hardened `collect_universe_scores` (scan.py): if every fundamentals
  fetch fails/returns nothing for any reason, `fundamental_df` now still
  gets the right column shape instead of a columnless empty frame that
  crashes `score_fundamentals` with a raw `KeyError`.
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
equity curve: strategy total return +50.53%, max drawdown -31.46% vs.
SPY buy-and-hold total return +13.49%, max drawdown -8.88% over the same
window. **Superseded by the next entry below — these numbers still had a
second bug baked in.** 46 -> 51 tests (added `test_portfolio.py`, updated
`test_fundamentals_finnhub.py`'s fixtures to match confirmed live units).
Committed as `90d15aa`, `e676b01`, `7b219f5`.

**2026-08-02 (evening) — Second backtest bug found: no open-position
tracking.** While investigating what was driving the -31.46% drawdown
above, found that `run_backtest` picked the naive top-N by score at every
rebalance date with no memory of what was already held. Since
holding_days (42) spans ~4 rebalance steps, the same top-scoring symbol
got picked over and over: the 100 trades behind the number above resolved
to only **17 distinct symbols**, with CIEN picked 18/20 times and COHR
17/20 — the simulated portfolio was concentrated in 2-3 volatile momentum
names instead of the diversified 5-8-position book
`satellite/ranker.py`'s `select_top_ideas` actually enforces live. Fixed
`run_backtest` to track open positions (bar-accurate exit dates via new
`position_exit_date`) and apply the same existing-holdings-exclusion +
`MAX_CONCURRENT_POSITIONS` cap the live path uses. Added regression tests
for both new behaviors. Committed as `3b58f6a`.

Reran the walk-forward backtest with **both** fixes in place (same 109
symbols, 5 windows): only 40 test-period trades resolved this time (the
account-level position cap fills up fast, so more candidate symbols
mostly changes *which* 8 names are held, not how many trades happen).
Overall test avg return +12.40% per idea, 62.16% hit rate. Corrected
equity curve: **strategy total return +39.87%, max drawdown -28.27%**
vs. **SPY total return +13.49%, max drawdown -8.88%** — still a
meaningfully worse risk profile than the benchmark, though a bit less
extreme than the concentrated-position number above. This is the current
best estimate; go/no-go is still the user's call (see Phase 2 checklist).
Realized mid-investigation that expanding the candidate universe (more
tickers) won't meaningfully improve statistical power here, since
`MAX_CONCURRENT_POSITIONS=8` is a fixed account-design constraint
regardless of universe size — a **longer historical backtest window**
(more independent market regimes) would be the actual lever, not a wider
symbol list.

**2026-08-02 (evening, continued) — Extended history to 10y, reran for
real statistical power.** Refetched all 111 cached symbols (incl. SPY)
via yfinance with `period="10y"` instead of the original `"2y"` (2016-08
through 2026-07, ~2,514 bars each, no API key needed — this is pure
price data via yfinance). Reran the same walk-forward config: **15
windows, 120 test-period trades, 30 rebalance periods, test window
2024-02 through 2026-07 (~2.5 years)** — a much better-powered sample
than the 40-trade/9-period/~8-month estimate above. Overall test avg
return +8.15% per idea, 65% hit rate, return range -44.16% to +71.35%.
Corrected equity curve: **strategy total return +195.45%, max drawdown
-31.44%** vs. **SPY buy-and-hold total return +55.76%, max drawdown
-18.76%** — 66.67% win rate vs. benchmark per rebalance period, mean
excess return +4.6pp/period. Notably, the *relative* drawdown gap
(1.7x SPY's) is smaller than the short-window estimate implied (3.2x) —
the earlier comparison was skewed by SPY happening to have an unusually
calm max drawdown in that particular 8-month slice. This is the current
best estimate for the technical+quant-only strategy; fundamentals still
aren't backtestable (FMP free-tier wall, confirmed earlier this session).
Go/no-go remains the user's call. 55 tests, no new ones needed for this
step (data refresh + rerun only, no code changes).

**2026-08-02 (evening, continued) — Phase 3 mechanism built.** Added
`satellite/alert.py` (pure `format_alert`/`format_idea_line`, 5 new
tests) and `satellite/scan.py` (I/O orchestration: refreshes
prices/fundamentals, scores, ranks, sizes, formats — untested by design,
same pattern as `prices.py`/`fundamentals*.py`). `python -m
satellite.scan <account_value>` runs a manual dry run over whatever's
already cached; verified against 110 real symbols, correctly producing 5
ranked ideas with rationale and position sizing. This is groundwork
only — **not** wired to a scheduler or push notification, since the
Phase 2 go/no-go decision is still open and CLAUDE.md is explicit that
turning on a live daily alert isn't something to default into. 60 tests
total. Committed as `48d095b`.

**2026-08-02 (evening, continued) — Refactored run_backtest to reuse
ranker.select_top_ideas; ran a full-S&P-500 robustness check.** Found
`run_backtest`'s position-picking logic (added earlier this session)
reimplemented `satellite.ranker.select_top_ideas`'s exclusion/cap rules
independently instead of calling it — against CLAUDE.md's principle that
scoring must run identically in the backtester and live scan. Refactored
`run_backtest` to build a `composite_score` DataFrame each rebalance and
call `select_top_ideas` directly; verified byte-identical output on the
109-symbol run before/after (pure simplification). Committed as
`5fe6886`.

Fetched 10y price history for the full 503-symbol S&P 500 (yfinance, no
key needed, all succeeded) to check whether the 109-symbol subset's
result holds up over a bigger candidate pool. First attempt at a full
walk-forward (weight-grid search per window) was killed after 25+
minutes — too slow at 500-symbol scale (the grid search recomputes
technical indicators for every symbol once per weight candidate). Instead
ran a single-fixed-weight (0.7 technical / 0.3 quant, no train/test
split) backtest over the full 500-symbol universe and full ~9.5-year
history as a **robustness sanity check, not a walk-forward validation**:
373 trades, 162 distinct symbols, avg return +8.53% per idea, 65.22% hit
rate — both numbers landing within a point of the 109-symbol walk-forward
result (+8.15%, 65%), a reassuring cross-check that the smaller sample
wasn't a fluke of which symbols happened to be cached. Total return over
the full window: strategy +4859.50% vs. SPY +254.91%; max drawdown
-35.73% vs. SPY's own -33.72%. **Do not read the total-return figure at
face value** — it's a single a-priori weight over 10 years including the
NVDA/SMCI/PLTR/TSLA/AMD AI-and-semiconductor supercycle (the most-picked
symbols list confirms this), not an out-of-sample validated result.
The more informative takeaway: over this much longer window, SPY's own
drawdown is close to the strategy's, unlike the short recent test windows
above where SPY looked unusually calm — the relative-drawdown gap used
for a go/no-go call is highly sensitive to which historical slice you
look at, and that sensitivity is itself worth weighing, not just any one
number. Also confirmed one script bug in the process (not shipped code):
building "rebalance dates" from the shortest cached symbol's index breaks
when the universe includes very recently listed constituents (HONA/FDXF,
<50 bars) — fixed by anchoring to SPY's full index instead.

**2026-08-02 (evening, continued) — Tested wiring RSI/MACD into the
technical score; reverted, it hurt performance.** User asked what
metrics drive stock selection, which surfaced that `raw_technical_metrics`
computes `rsi14`/`macd_hist` but `score_technicals` never reads them —
despite plan.md's own spec listing "momentum (RSI/MACD)" and the
function's docstring implying they were used. Tried wiring them into the
momentum component (ranked same-direction as price momentum, matching
the system's buy-strength design rather than treating high RSI as
contrarian). Backtested before/after on the full S&P 500 (identical
fixed 0.7 technical / 0.3 quant weight, otherwise unchanged): avg return
per idea +8.53% -> +4.09%, hit rate 65.22% -> 58.42%, max drawdown
-35.73% -> -43.23%. A clear regression, not noise. Reverted per
CLAUDE.md's "run scoring changes through the backtester before trusting
them" rule, and documented the finding directly in
`score_technicals`' docstring so it isn't silently re-added later without
re-testing. Committed as `d8baa15`. 61 tests.

**2026-08-03 — Go/no-go decision made; live alerts activated.** User
reviewed the backtest results and approved activating live alerts,
account value $250 (fresh, small, to grow over time), no existing
holdings. This took two failed infrastructure attempts before landing on
a working setup — see the Phase 3 checklist above for full detail.
Summary: pushed the repo to a new private GitHub repo and tried a cloud
routine first (per the original plan), but the cloud sandbox's network
policy blocked Yahoo Finance itself (yfinance is the only price source
this project has), which is unfixable — no snapshot/fallback works for
*live* daily prices the way it did for the mostly-static S&P 500 list.
Pivoted to a local Windows Task Scheduler job instead (weekdays 8:15am
ET, headless `claude -p` in this directory), which has full access to
local `.env`/`data_cache/` and works. Along the way, fixed: (1) no
fallback when `build_universe()`'s live fetch fails (added a bundled
snapshot CSV), (2) a real test-hygiene bug where `test_universe.py` was
silently corrupting the real local universe cache with mock data via an
unpatched `_CACHE_FILE`, (3) `collect_universe_scores` crashing instead
of degrading gracefully when fundamentals come back completely empty,
(4) `New-ScheduledTaskSettingsSet`'s battery-power default silently
stalling the task in "Queued" forever. First fully-successful run found
5 ideas, top pick PANW (composite 98.9/100); push notification fired
(desktop confirmed working; mobile push needs the user to separately
enable Remote Control pairing — not something settable via CLI/API).
63 tests. Committed as `5f5ade0` (plus earlier commits this session);
Task Scheduler job and cloud routine are not tracked in git (external
infra), documented here instead.

## Open questions to revisit later

- Exact factor weights — determined empirically via backtesting, not fixed
  up front.
- Whether to add sector/diversification constraints on top of raw score
  ranking.
- Whether daily cadence proves too noisy vs. the weeks-months holding
  period once live — may revisit to weekly.
- Walk-forward performance at full-universe scale: `run_walk_forward`'s
  weight-grid search recomputes technical indicators for every symbol
  once per weight candidate per date (5x redundant work), which was fine
  at 109 symbols but too slow at 500 (killed after 25+ min). If a real
  walk-forward validation across the full S&P 500 is ever needed, worth
  caching raw_technical_metrics per (symbol, date) once and reusing it
  across weight candidates, rather than the current per-call recompute.
- ~~Backtest metrics currently treat sequential rebalance-period returns
  as if non-overlapping...~~ fixed 2026-08-02, see
  `satellite/backtest/portfolio.py` and the Phase 2 checklist above.
- Point-in-time historical fundamentals for backtesting: confirmed
  2026-08-02 that FMP's free tier blocks the historical/quarterly ratios
  endpoint outright (402), not just rate-limits it. If fundamentals ever
  need to be backtested, that likely means either a paid FMP tier or
  finding a different historical-fundamentals source — not a "wait for a
  bigger free-tier budget" problem.
- ~~Backtest statistical power: current walk-forward only covers ~8
  months...~~ addressed 2026-08-02: extended cached price history to 10y,
  walk-forward now covers 2.5 years / 120 trades / 30 periods. Could still
  go further (full 3,588-symbol universe, not just the 111-symbol
  leftover sample) if the go/no-go call ends up close.
