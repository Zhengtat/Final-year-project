"""CR-005 §2 task 7 tests: structural checks (domain/range, cycles) over the
accepted relation-edge set. Evidence-substring checks are covered by
test_expert_kg_concepts.py / test_expert_kg_relations.py (they happen at
extraction time, not here).
"""

from __future__ import annotations

from pathlib import Path

from cumap.expert_kg.checks import check_structure
from cumap.expert_kg.llm_schemas import QualifiersLLM
from cumap.expert_kg.relations import CandidatePair, RelationEdgeCandidate
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]


def _registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(REPO_ROOT / "configs" / "relations_v1.yaml")


def _qualifiers() -> QualifiersLLM:
    return QualifiersLLM(
        polarity="affirmed",
        modality="always",
        conditions=[],
        part_type=None,
        dimension=None,
        surface_phrase="uses",
    )


def _edge(
    concept_x_id, relation, concept_y_id, *, direction="forward", pair_id="RP-1"
) -> RelationEdgeCandidate:
    pair = CandidatePair(
        pair_id=pair_id,
        section_id="s1",
        concept_x_id=concept_x_id,
        concept_y_id=concept_y_id,
        sentence="p",
    )
    registry = _registry()
    family = registry.family_of(relation)
    return RelationEdgeCandidate(
        pair=pair,
        family=family,
        relation=relation,
        direction=direction,
        statement="s",
        evidence_quote="q",
        qualifiers=_qualifiers(),
    )


def test_check_structure_flags_domain_range_violation():
    registry = _registry()
    # "performs" requires domain_types [Protocol, Component, Mechanism]; a DataUnit
    # source is a violation.
    edge = _edge("c_packet", "performs", "c_fast_retransmit")
    concept_types = {"c_packet": "DataUnit", "c_fast_retransmit": "Event"}

    result = check_structure([edge], concept_types, registry)
    assert len(result.domain_range_errors) == 1
    assert "c_packet" in result.domain_range_errors[0]


def test_check_structure_passes_when_types_match():
    registry = _registry()
    edge = _edge("c_bridge", "performs", "c_backward_learning")
    concept_types = {"c_bridge": "Component", "c_backward_learning": "Mechanism"}

    result = check_structure([edge], concept_types, registry)
    assert result.domain_range_errors == []


def test_check_structure_detects_is_a_cycle():
    registry = _registry()
    edges = [
        _edge("c_a", "is_a", "c_b", pair_id="RP-1"),
        _edge("c_b", "is_a", "c_c", pair_id="RP-2"),
        _edge("c_c", "is_a", "c_a", pair_id="RP-3"),
    ]
    concept_types = {"c_a": "Concept", "c_b": "Concept", "c_c": "Concept"}

    result = check_structure(edges, concept_types, registry)
    assert len(result.cycles) >= 1


def test_check_structure_reversed_direction_swaps_endpoints():
    registry = _registry()
    # "performs" is directional; "reversed" means the stated direction is
    # concept_y -> concept_x, so the violation should be on concept_y, not concept_x.
    edge = _edge("c_fast_retransmit", "performs", "c_packet", direction="reversed")
    concept_types = {"c_fast_retransmit": "Event", "c_packet": "DataUnit"}

    result = check_structure([edge], concept_types, registry)
    assert len(result.domain_range_errors) == 1
    assert "c_packet" in result.domain_range_errors[0]
