"""CR-015 frozen scorer: synthetic fixtures plus a regression against the committed CR-014 held-out numbers (skipped when the local run data is absent)."""

import json
from pathlib import Path

import pytest

from cumap.cr015.scoring import GoldMention, placement_views, score_mentions

TEXT = "A TCP congestion control algorithm limits the congestion window."


def g(a: str, nested=False):
    i = TEXT.index(a)
    return GoldMention("s", i, i + len(a), "C", nested)


def test_longest_match_suppresses_nested_but_nested_aware_keeps_it():
    surf = {"s": ["TCP congestion control", "congestion control", "congestion window"]}
    v = placement_views(surf, {"s": TEXT})
    assert len(v["longest_match"]["s"]) == 2 and len(v["nested_aware_all"]["s"]) == 3
    gold = [
        g("TCP congestion control"),
        g("congestion control", nested=True),
        g("congestion window"),
    ]
    lm = score_mentions(v["longest_match"], gold, {"s": TEXT})
    na = score_mentions(v["nested_aware_all"], gold, {"s": TEXT})
    assert lm["mention_span_exact"]["recall"] == pytest.approx(2 / 3)
    assert na["mention_span_exact"]["recall"] == 1.0
    assert lm["nested_gold_recall"]["recall"] == 0.0 and na["nested_gold_recall"]["recall"] == 1.0
    assert na["predicted_nested"]["n"] == 2  # the outer and inner spans


def test_over_long_and_under_long_false_positives_are_counted():
    gold = [g("congestion control")]
    pred = {
        "s": [(TEXT.index("TCP"), TEXT.index("algorithm") + len("algorithm"))]
    }  # contains the gold span
    r = score_mentions(pred, gold, {"s": TEXT})
    assert r["over_long_fp"] == 1 and r["under_long_fp"] == 0
    pred2 = {"s": [(TEXT.index("control"), TEXT.index("control") + 7)]}  # inside the gold span
    r2 = score_mentions(pred2, gold, {"s": TEXT})
    assert r2["under_long_fp"] == 1 and r2["over_long_fp"] == 0


def test_distinct_surface_view():
    gold = [g("congestion window")]
    r = score_mentions(
        {"s": [(TEXT.index("congestion window"), TEXT.index("congestion window") + 17)]},
        gold,
        {"s": TEXT},
    )
    assert r["distinct_surface"]["f1"] == 1.0


HELD = Path("data/processed/cr014/heldout/V3_4.2.json")


@pytest.mark.skipif(
    not (HELD.exists() and Path("data/gold/pd_concept_test_blind.csv").exists()),
    reason="local CR-014 held-out data absent",
)
def test_reproduces_the_committed_cr014_numbers():
    from cumap.cr014.heldout_run import section_row
    from cumap.cr014.pilot_score import load_gold

    secs = ["4.2", "5.3", "6.1", "6.4", "7.2", "8.3", "8.4", "8.5"]
    texts = {s: section_row(s)["text"] for s in secs}
    gold = load_gold(
        Path("data/gold/pd_concept_test_blind.csv"),
        Path("data/interim/checks/cr014/pd_concept_test_sentences.csv"),
    )
    surf = {
        s: sorted(
            json.loads(Path(f"data/processed/cr014/heldout/V3_{s}.json").read_text())["outcome"][
                "accepted"
            ]
        )
        for s in secs
    }
    v = placement_views(surf, texts)
    lm = score_mentions(v["longest_match"], gold, texts)["mention_span_exact"]
    na = score_mentions(v["nested_aware_all"], gold, texts)["mention_span_exact"]
    ref = json.loads(Path("reports/cr014/heldout_results.json").read_text())
    assert lm["precision"] == pytest.approx(
        ref["arms"]["V3"]["mention_span_exact"]["precision"], abs=1e-9
    )
    assert lm["recall"] == pytest.approx(
        ref["arms"]["V3"]["mention_span_exact"]["recall"], abs=1e-9
    )
    assert na["f1"] == pytest.approx(
        ref["nested_allowed"]["V3"]["mention_span_exact"]["f1"], abs=1e-9
    )
