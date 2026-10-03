"""CR-008 §3.5/§8: equivalence is a node property, never an edge (no network, no key)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.checks import retired_relation_errors
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.relations import CandidatePair, concept_vocab
from cumap.expert_kg.relations_v3 import (
    build_relation_choice_v3,
    classify_pair_v3,
    filled_options,
)
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
REG = RelationRegistry.from_yaml(REPO / "configs/relations_v1.3.yaml")
P = {
    "relation_family": load_prompt(REPO / "prompts", "relation_family", "v3"),
    "relation_choice": load_prompt(REPO / "prompts", "relation_choice", "v4"),
    "relation_qualifiers": load_prompt(REPO / "prompts", "relation_qualifiers", "v3"),
}


def test_registry_v13_has_no_equivalent_to_anywhere():
    assert REG.version_label == "1.3"
    assert "equivalent_to" not in REG
    for rel in REG.all_relations():
        assert "equivalent_to" not in rel.conflicts_with
        assert all(m.relation != "equivalent_to" for m in rel.near_misses)
    assert "equivalent_to" not in filled_options(REG, "comparison", "a", "b")


def test_validator_rejects_a_retired_relation_in_any_layer():
    assert retired_relation_errors(["part_of", "equivalent_to"])
    assert not retired_relation_errors(["part_of", "contrasts_with"])


def test_same_concept_is_offered_only_in_the_comparison_family_and_only_when_enabled():
    assert "same_concept" in filled_options(REG, "comparison", "a", "b", same_concept=True)
    assert "same_concept" not in filled_options(REG, "comparison", "a", "b")
    assert "same_concept" not in filled_options(REG, "dependency", "a", "b", same_concept=True)
    ok = {
        "relation": "same_concept",
        "direction": "forward",
        "evidence_quote": "q",
        "statement": "s",
        "comparison_dimension": None,
        "other_description": None,
        "other_suggested_label": None,
    }
    build_relation_choice_v3(REG, "comparison", True).model_validate(ok)
    with pytest.raises(ValidationError):
        build_relation_choice_v3(REG, "comparison").model_validate(ok)


def test_same_concept_creates_no_edge_and_queues_a_merge(tmp_settings, fixtures_dir):
    wire = RegisteredConcept("c_wire", "wire", "Concept", None, "s1")
    air = RegisteredConcept("c_air", "air", "Concept", None, "s1")
    matcher = MentionMatcher(concept_vocab([wire, air]))
    sentence = "A wire (also called air) is a medium."
    res = classify_pair_v3(
        LLMClient(tmp_settings, fixtures_dir=fixtures_dir),
        P["relation_family"],
        P["relation_choice"],
        P["relation_qualifiers"],
        REG,
        CandidatePair("P1", "s1", "c_wire", "c_air", sentence),
        wire,
        air,
        matcher,
        fixtures=("v3_comparison", "v4_same_concept", "v3_acts_on"),
        same_concept=True,
    )
    assert res.outcome == "same_concept" and res.reason == "queued_for_merge"
    assert res.qualifiers == {}  # no edge, so no qualifier step
