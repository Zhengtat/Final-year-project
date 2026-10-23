"""CR-015 trace: additive stages, and (when the local A2 development outputs exist) full placement lineage."""

import json
from pathlib import Path

import pytest

from cumap.explain.trace import CR014_STAGES, STAGES, Stage

TRACE = Path("data/processed/cr015/stageA/trace_A2.jsonl")


def test_new_stages_are_additive_and_historical_stage_list_unchanged():
    new = {"boundary_family", "concept_validity", "mention_placement", "adjudication"}
    assert new <= set(Stage.__args__) and new <= set(CR014_STAGES)
    assert not (new & set(STAGES)) and "proposal" not in STAGES
    assert len(STAGES) == 12  # the CR-013 vocabulary


@pytest.mark.skipif(not TRACE.exists(), reason="local CR-015 A2 trace absent")
def test_every_placed_mention_links_to_selector_and_verifier_events():
    ev = [json.loads(x) for x in TRACE.read_text().splitlines() if x]
    ids = {e["event_id"] for e in ev}
    placed = [e for e in ev if e["stage"] == "mention_placement" and e["action"] == "placed"]
    assert placed and all(
        len(e["input_refs"]) >= 1 and all(r in ids for r in e["input_refs"]) for e in placed
    )
    stages = {e["stage"] for e in ev}
    assert {"boundary_family", "concept_validity", "mention_placement"} <= stages
    blocked = [e for e in ev if e["action"] == "suppressed"]
    assert all(e["outcome"] == "blocked" and e["reason_code"] for e in blocked)
    distinct = {(e["section_id"], e["attrs"]["start"], e["attrs"]["end"]) for e in placed}
    out = sum(
        len(json.loads(p.read_text())["spans"])
        for p in Path("data/processed/cr015/stageA").glob("A2_*.json")
    )
    assert len(distinct) == out  # the trace accounts for every placed mention exactly
