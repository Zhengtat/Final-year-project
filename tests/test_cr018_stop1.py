"""CR-018 STOP 1: the Track A substrate replays from saved artefacts with no model call (skipped when the saved CR-015 outputs are absent)."""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path("data/processed/cr015/stageA/A2_4.2.json").exists(),
    reason="saved CR-015 outputs absent",
)


def test_saved_a2_spans_equal_family_grounded_replay_and_cr015_scores():
    from cumap.cr018.stop1_replay import main

    r = main()
    assert r["a2_spans_equal_family_grounded_replay"] is True
    a2 = r["scores"]["A2_saved"]
    assert (a2["P"], a2["R"], a2["F1"]) == (0.665, 0.785, 0.72)
    assert r["scores"]["A2_replayed"] == a2
    u0 = r["scores"]["U0"]
    assert (u0["P"], u0["R"], u0["F1"]) == (0.764, 0.513, 0.614)
    assert (
        r["scores"]["BA1_selector_only"]["over_long_fp"] > a2["over_long_fp"]
    )  # no verifier: more over-long FPs
    ref = json.loads(Path("reports/cr015/stage_ab_results.json").read_text())["arms"]["A2"][
        "mention"
    ]
    assert round(ref["precision"], 3) == a2["P"] and round(ref["recall"], 3) == a2["R"]
