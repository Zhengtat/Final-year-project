"""CR-005 §2 task 5 tests: defined -> used later prerequisite candidates, and
forward references (used before defined), computed from a concept's own mention
history plus book-order section IDs. Rule-based, no LLM call.
"""

from __future__ import annotations

from cumap.expert_kg.canonicalize import Mention, RegisteredConcept
from cumap.expert_kg.prerequisites import find_forward_references, find_prerequisite_candidates

SECTION_ORDER = ["ch1_s1", "ch1_s2", "ch2_s1"]


def _concept(concept_id, mentions) -> RegisteredConcept:
    return RegisteredConcept(
        concept_id=concept_id,
        canonical_name=concept_id,
        node_type="Mechanism",
        definition=None,
        first_introduced=mentions[0].section_id,
        mentions=mentions,
    )


def test_find_prerequisite_candidates_defined_then_used_later():
    concept = _concept(
        "c_cwnd",
        [Mention("ch1_s1", "defined", "q1"), Mention("ch2_s1", "used", "q2")],
    )
    candidates = find_prerequisite_candidates([concept], SECTION_ORDER)
    assert len(candidates) == 1
    assert candidates[0].concept_id == "c_cwnd"
    assert candidates[0].defined_section_id == "ch1_s1"
    assert candidates[0].used_section_id == "ch2_s1"


def test_find_prerequisite_candidates_dedupes_repeated_use_in_same_section():
    concept = _concept(
        "c_cwnd",
        [
            Mention("ch1_s1", "defined", "q1"),
            Mention("ch2_s1", "used", "q2"),
            Mention("ch2_s1", "used", "q3"),  # used twice in the same later section
        ],
    )
    candidates = find_prerequisite_candidates([concept], SECTION_ORDER)
    assert len(candidates) == 1


def test_find_prerequisite_candidates_ignores_mentioned_role():
    concept = _concept(
        "c_cwnd",
        [Mention("ch1_s1", "defined", "q1"), Mention("ch2_s1", "mentioned", "q2")],
    )
    assert find_prerequisite_candidates([concept], SECTION_ORDER) == []


def test_find_prerequisite_candidates_no_candidate_when_never_defined():
    concept = _concept("c_cwnd", [Mention("ch1_s1", "used", "q1")])
    assert find_prerequisite_candidates([concept], SECTION_ORDER) == []


def test_find_forward_references_used_before_defined():
    concept = _concept(
        "c_slow_start",
        [Mention("ch1_s1", "used", "q1"), Mention("ch1_s2", "defined", "q2")],
    )
    refs = find_forward_references([concept], SECTION_ORDER)
    assert len(refs) == 1
    assert refs[0].concept_id == "c_slow_start"
    assert refs[0].used_section_id == "ch1_s1"
    assert refs[0].defined_section_id == "ch1_s2"


def test_find_forward_references_none_when_defined_first():
    concept = _concept(
        "c_cwnd",
        [Mention("ch1_s1", "defined", "q1"), Mention("ch2_s1", "used", "q2")],
    )
    assert find_forward_references([concept], SECTION_ORDER) == []
