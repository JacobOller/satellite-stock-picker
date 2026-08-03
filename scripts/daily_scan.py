"""Entry point for the locally-scheduled daily scan (Windows Task
Scheduler -> headless `claude -p` invocation, see plan.md Phase 3).

Prints the formatted alert to stdout; the invoking Claude Code session
reads that output and sends a push notification (see the scheduled
task's prompt). Not meant to be wired to any other trigger -- this is a
thin, easily-editable entry point specifically for that one scheduled
task, kept out of satellite/ since it's a script, not library code.

Runs locally, so it has access to .env (both FMP_API_KEY and
FINNHUB_API_KEY) and the on-disk data_cache/ -- unlike the abandoned
cloud routine, this uses the full fundamentals-included scan.
"""

from satellite.scan import run_scan
from satellite.universe import build_universe

# Update these by hand as the account changes -- there's no live
# brokerage connection (CLAUDE.md hard constraint), so this is manual.
ACCOUNT_VALUE = 250.0
EXISTING_HOLDINGS: set[str] = set()


def main() -> None:
    universe_df = build_universe()
    symbols = sorted(universe_df[universe_df["source"] == "sp500"]["symbol"].tolist())
    _, alert_text = run_scan(symbols, ACCOUNT_VALUE, existing_holdings=EXISTING_HOLDINGS)
    print(alert_text)


if __name__ == "__main__":
    main()
