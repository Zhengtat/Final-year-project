"""CR-008 item 2 regression fixtures: the 4 edges the old per-pair `corrects_intuition` flag fired on.
Two are real warnings the cues must RECALL (MTU, Central Offices); two must be REJECTED by structuring
(study advice, the piggybacking scope note). The structuring answers in tests/fixtures/llm/
misconception_structuring/regress_*.json are the real model's answers recorded on 2026-10-02 (no network)."""

from pathlib import Path

import pytest

from cumap.expert_kg.misconception import Candidate, run_stage, scan_cues
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
REG = RelationRegistry.from_yaml(REPO / "configs/relations_v1.3.yaml")
PROMPT = load_prompt(REPO / "prompts", "misconception_structuring", "v2")

MTU = (
    "The central idea here is that every network type has a maximum transmission unit (MTU), which is the "
    "largest IP datagram that it can carry in a frame.\\ [#]_ Note that this value is smaller than the "
    "largest packet size on that network because the IP datagram needs to fit in the payload of the "
    "link-layer frame."
)
CENTRAL_OFFICES = (
    "These edge sites are commonly called Central Offices in the Telco world and Head Ends in the cable "
    "world, but despite their names implying “centralized” and “root of the hierarchy” these sites are at "
    "the very edge of the ISP’s network; the ISP-side of the last-mile that directly connects to customers."
)
ADVICE = (
    "While it is tempting to settle\xa0for just understanding the way it’s done today, it is important to "
    "recognize the underlying concepts because networks are constantly changing as technology evolves and "
    "new applications are invented."
)
PIGGY = (
    "Note that this particular implementation does not support piggybacking ACKs on data frames."
)


def _recalled(sentence: str) -> list[str]:
    cands = scan_cues([("s1", sentence)], lexicon=None)  # text cues only, no lexicon coincidence
    return sorted({f for c in cands for f in c.families})


@pytest.mark.parametrize("sentence", [MTU, CENTRAL_OFFICES], ids=["mtu", "central_offices"])
def test_the_two_real_warnings_are_recalled_by_the_text_cues(sentence):
    assert "contrast" in _recalled(sentence)


def test_the_new_contrast_cues_are_narrow():
    # a plain remark with "Note that" is NOT a candidate; the cue needs a negation/contrast near it
    assert (
        _recalled("Note that the packets are transmitted beginning with the leftmost field.") == []
    )


def _structure(tmp_settings, fixtures_dir, sentence, fixture):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    cand = Candidate("s1", sentence, sentence, ["regression"])
    state = {"concepts": [], "relation_results_v3": []}
    return run_stage(
        client, PROMPT, REG, state, [("s1", sentence)], None, limit=0, extra=[cand], fixture=fixture
    )


@pytest.mark.parametrize(
    ("sentence", "fixture"),
    [(ADVICE, "regress_advice"), (PIGGY, "regress_piggy")],
    ids=["study_advice", "piggyback_scope_note"],
)
def test_the_two_non_warnings_are_rejected_by_structuring(
    tmp_settings, fixtures_dir, sentence, fixture
):
    layer = _structure(tmp_settings, fixtures_dir, sentence, fixture)
    assert (
        layer["items"] == [] and layer["needs_correct_edge"] == [] and layer["needs_review"] == []
    )
    assert len(layer["not_warning"]) == 1  # dismissed, with the real model's recorded reason
