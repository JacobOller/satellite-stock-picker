import pandas as pd

from satellite.alert import format_alert, format_idea_line


def _row(fundamental=None, technical=None, quant=None, composite=80.0, size=1000.0):
    return pd.Series(
        {
            "fundamental_score": fundamental,
            "technical_score": technical,
            "quant_score": quant,
            "composite_score": composite,
            "suggested_position_size": size,
        }
    )


def test_format_idea_line_includes_ticker_score_size_and_rationale():
    row = _row(fundamental=60.0, technical=90.0, quant=70.0, composite=75.3, size=1234.0)
    line = format_idea_line(1, "ACME", row)
    assert line.startswith("1. ACME")
    assert "75.3/100" in line
    assert "$1,234" in line
    assert "led by technical" in line


def test_format_idea_line_handles_missing_factor_scores():
    row = _row(fundamental=None, technical=88.0, quant=None, composite=88.0, size=500.0)
    line = format_idea_line(1, "ACME", row)
    assert "led by technical" in line
    assert "fundamentals" not in line


def test_format_alert_lists_all_ideas_in_order():
    df = pd.DataFrame(
        {
            "fundamental_score": [70.0, 60.0],
            "technical_score": [80.0, 90.0],
            "quant_score": [75.0, 65.0],
            "composite_score": [78.0, 71.0],
            "suggested_position_size": [1000.0, 900.0],
        },
        index=["AAA", "BBB"],
    )
    text = format_alert(df, as_of=pd.Timestamp("2026-08-02"))
    assert "2026-08-02" in text
    assert "2 new" in text
    lines = text.splitlines()
    assert lines[1].startswith("1. AAA")
    assert lines[2].startswith("2. BBB")


def test_format_alert_empty_produces_explicit_no_ideas_message():
    text = format_alert(pd.DataFrame(), as_of=pd.Timestamp("2026-08-02"))
    assert "no new ideas" in text.lower()
    assert "2026-08-02" in text


def test_format_alert_notes_when_below_min_ideas():
    df = pd.DataFrame(
        {
            "fundamental_score": [70.0],
            "technical_score": [80.0],
            "quant_score": [75.0],
            "composite_score": [78.0],
            "suggested_position_size": [1000.0],
        },
        index=["AAA"],
    )
    df.attrs["below_min_ideas"] = True
    text = format_alert(df)
    assert "fewer than the usual" in text.lower()
