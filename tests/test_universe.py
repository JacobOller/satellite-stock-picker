from unittest.mock import patch

import pandas as pd

from satellite import universe


def test_build_universe_falls_back_to_snapshot_when_live_fetch_fails():
    # Regression test for the 2026-08-03 cloud routine failure: Wikipedia/
    # Nasdaq fetches can fail (403 from an outbound proxy, network issues,
    # etc.) in environments without a warm on-disk cache (e.g. the cloud
    # routine's fresh checkout). build_universe() must still return usable
    # data via the bundled snapshot rather than raising.
    with patch.object(universe, "_fetch_sp500", side_effect=RuntimeError("simulated 403")):
        with patch.object(universe, "_fetch_nasdaq_listed", side_effect=RuntimeError("simulated 403")):
            df = universe.build_universe(force_refresh=True)

    assert not df.empty
    assert set(df.columns) >= {"symbol", "name", "source"}
    assert (df["source"] == "sp500").sum() > 400  # roughly the real S&P 500 size


def test_build_universe_uses_live_fetch_when_only_one_source_fails():
    fake_sp500 = pd.DataFrame({"symbol": ["ZZZ"], "name": ["Fake Live Co"], "source": ["sp500"]})
    with patch.object(universe, "_fetch_sp500", return_value=fake_sp500):
        with patch.object(universe, "_fetch_nasdaq_listed", side_effect=RuntimeError("simulated 403")):
            df = universe.build_universe(force_refresh=True)

    assert "ZZZ" in set(df.loc[df["source"] == "sp500", "symbol"])  # came from the live fetch, not the snapshot
    assert (df["source"] == "nasdaq").sum() > 1000  # snapshot fallback still populated it
