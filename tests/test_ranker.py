import pandas as pd

from satellite.ranker import select_top_ideas


def _scored_df(n=10, sectors=None):
    idx = [f"T{i}" for i in range(n)]
    data = {"composite_score": [100 - i for i in range(n)]}
    if sectors:
        data["sector"] = sectors
    return pd.DataFrame(data, index=idx)


def test_select_top_ideas_caps_at_top_n_max():
    df = _scored_df(20)
    picked = select_top_ideas(df, top_n_max=5, max_concurrent_positions=8)
    assert len(picked) == 5
    assert list(picked.index) == ["T0", "T1", "T2", "T3", "T4"]
    assert list(picked["rank"]) == [1, 2, 3, 4, 5]


def test_select_top_ideas_excludes_existing_holdings():
    df = _scored_df(5)
    picked = select_top_ideas(df, existing_holdings={"T0", "T1"}, top_n_max=5, max_concurrent_positions=8)
    assert "T0" not in picked.index
    assert "T1" not in picked.index
    assert list(picked.index) == ["T2", "T3", "T4"]


def test_select_top_ideas_respects_open_slots_under_max_concurrent():
    df = _scored_df(10)
    # 6 held already, cap is 8 -> only 2 open slots
    held = {f"H{i}" for i in range(6)}
    picked = select_top_ideas(df, existing_holdings=held, top_n_max=5, max_concurrent_positions=8)
    assert len(picked) == 2


def test_select_top_ideas_no_open_slots_returns_empty():
    df = _scored_df(10)
    held = {f"H{i}" for i in range(8)}
    picked = select_top_ideas(df, existing_holdings=held, max_concurrent_positions=8)
    assert picked.empty


def test_select_top_ideas_drops_nan_scores():
    df = _scored_df(5)
    df.loc["T0", "composite_score"] = None
    picked = select_top_ideas(df, top_n_max=5, max_concurrent_positions=8)
    assert "T0" not in picked.index


def test_select_top_ideas_sector_cap_enforced():
    df = _scored_df(6, sectors=["Tech", "Tech", "Tech", "Health", "Health", "Energy"])
    picked = select_top_ideas(df, top_n_max=5, max_concurrent_positions=8, sector_col="sector", max_per_sector=1)
    assert picked["sector"].value_counts().max() == 1
    assert len(picked) == 3  # one per sector present
