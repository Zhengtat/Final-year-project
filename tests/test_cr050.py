"""CR-050: the fresh identity sheet is blind and written outside data/gold (no network, no key)."""

from cumap.cr050 import sheet as SH


def test_sheet_is_a_draft_outside_gold_and_blind():
    assert "data/interim/suggestions" in str(SH.OUT) and "data/gold" not in str(SH.OUT)
    cols = [c for c in SH.COLUMNS if c != "rule_promotes"]
    assert not any(
        w in c.lower() for c in cols for w in ("decision", "reason", "adjudicat", "confidence")
    )
    assert [c for c in cols if c.startswith("MARK_")] == [
        "MARK_distinct_concept (yes/no)",
        "MARK_same_as_target (yes/no)",
        "MARK_note",
    ]


def test_sources_never_include_a_scinlp_test_run():
    assert all("heldout" not in rid for _, rid in SH.sources())
