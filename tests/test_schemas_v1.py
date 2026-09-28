"""CR-001 §4 acceptance tests: core edge qualifiers, ChainLink, extended match types,
DiagnosisRecord additions, and the dynamic v2 LLM-facing schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cumap.schemas.chain_links import ChainLink, ChainLinkAlignment, verdict_for_chain_link_match
from cumap.schemas.diagnosis import DiagnosisRecord
from cumap.schemas.edges import Evidence, ExpertEdge, Validation
from cumap.schemas.enums import ChainLinkMatchType, ChainLinkType, Verdict
from cumap.schemas.llm_schemas import (
    build_edge_suggestion_v2,
    build_expert_subgraph_suggestion_v2,
    build_student_edge_suggestion_v2,
)
from cumap.schemas.relations import RelationRegistry
from cumap.schemas.student import EvidenceSpan, StudentEdge

V1_PATH = Path(__file__).parents[1] / "configs" / "relations_v1.yaml"


@pytest.fixture(scope="module")
def registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(V1_PATH)


def _round_trip(model):
    cls = type(model)
    restored = cls.model_validate(json.loads(model.model_dump_json()))
    assert restored == model
    return restored


# ---------------------------------------------------------------------------
# Core edge qualifiers (§4.1)
# ---------------------------------------------------------------------------


def test_expert_edge_accepts_new_qualifiers():
    edge = ExpertEdge(
        edge_id="E-1",
        source_id="c_ext_header",
        target_id="c_ipv6_packet",
        relation="part_of",
        layer="taxonomy",
        statement="An extension header is a component of an IPv6 packet.",
        criticality="core",
        part_type="component",
        surface_phrase="is part of",
        relation_family="classification_structure",
        registry_version=1,
        evidence=[Evidence(source="P&D 6e", section_id="4.2", quote="extension header")],
        validation=Validation(),
        origin="textbook",
    )
    _round_trip(edge)


def test_v0_shaped_expert_edge_dict_still_loads():
    """No part_type/dimension/surface_phrase/relation_family/registry_version keys at all."""
    v0_dict = {
        "edge_id": "E-OLD",
        "source_id": "c_a",
        "target_id": "c_b",
        "relation": "is_a",
        "layer": "taxonomy",
        "statement": "A is a kind of B.",
        "criticality": "core",
        "evidence": [{"source": "P&D 6e", "section_id": "1.1", "quote": "A is a kind of B"}],
        "validation": {},
        "origin": "textbook",
    }
    edge = ExpertEdge.model_validate(v0_dict)
    assert edge.part_type is None
    assert edge.registry_version is None


def test_part_type_rejected_on_non_part_of_relation():
    with pytest.raises(ValidationError, match="part_type is only valid on relation='part_of'"):
        ExpertEdge(
            edge_id="E-2",
            source_id="c_a",
            target_id="c_b",
            relation="causes",
            layer="semantic",
            statement="x",
            criticality="core",
            part_type="component",
            evidence=[Evidence(source="s", section_id="1.1", quote="x")],
            validation=Validation(),
            origin="textbook",
        )


def test_dimension_rejected_on_non_contrasts_with_relation():
    with pytest.raises(ValidationError, match="dimension is only valid on relation='contrasts_with'"):
        ExpertEdge(
            edge_id="E-3",
            source_id="c_a",
            target_id="c_b",
            relation="causes",
            layer="semantic",
            statement="x",
            criticality="core",
            dimension="growth rate",
            evidence=[Evidence(source="s", section_id="1.1", quote="x")],
            validation=Validation(),
            origin="textbook",
        )


def test_student_edge_accepts_new_qualifiers_and_validates_consistency():
    edge = StudentEdge(
        source_id="c_slow_start",
        relation="contrasts_with",
        target_id="c_congestion_avoidance",
        dimension="cwnd growth rate",
        surface_phrase="is different from",
        response_id="a_1",
        question_id="q_1",
        evidence_span=EvidenceSpan(start=0, end=10, text="different"),
        extraction_confidence=0.9,
        link_confidence=0.9,
    )
    _round_trip(edge)

    with pytest.raises(ValidationError):
        StudentEdge(
            source_id="c_a",
            relation="causes",
            target_id="c_b",
            part_type="component",  # invalid: causes is not part_of
            response_id="a_1",
            question_id="q_1",
            evidence_span=EvidenceSpan(start=0, end=1, text="x"),
            extraction_confidence=0.9,
            link_confidence=0.9,
        )


# ---------------------------------------------------------------------------
# ChainLink / ChainLinkAlignment (§4.2-4.3)
# ---------------------------------------------------------------------------


def test_chain_link_round_trip():
    link = ChainLink(
        link_id="CL-1",
        from_edge_id="E-TCP-014",
        to_edge_id="E-TCP-013",
        type=ChainLinkType.CAUSE,
        statement="cwnd is reset to 1 MSS because a timeout signals severe congestion",
        surface_phrase="because",
        evidence=[Evidence(source="P&D 6e", section_id="6.3", quote="because")],
        origin="textbook",
        question_ids=["q_582d0a1c"],
        validation=Validation(status="accepted"),
    )
    _round_trip(link)


def test_chain_link_alignment_round_trip_and_verdict_mapping():
    alignment = ChainLinkAlignment(
        expert_link_id="CL-1",
        student_from_edge_id="SE-1",
        student_to_edge_id="SE-2",
        match_type=ChainLinkMatchType.WRONG_LINK_TYPE,
        verdict=verdict_for_chain_link_match(ChainLinkMatchType.WRONG_LINK_TYPE),
        rationale="student used 'sequence' where the textbook says 'cause'",
    )
    _round_trip(alignment)
    assert alignment.verdict == Verdict.CONTRADICTORY


@pytest.mark.parametrize(
    "match_type,expected_verdict",
    [
        (ChainLinkMatchType.EXACT, Verdict.CORRECT),
        (ChainLinkMatchType.WRONG_LINK_TYPE, Verdict.CONTRADICTORY),
        (ChainLinkMatchType.REVERSED_LINK, Verdict.CONTRADICTORY),
        (ChainLinkMatchType.MISSING_LINK, Verdict.INACCURATE),
        (ChainLinkMatchType.UNSUPPORTED_LINK, Verdict.INACCURATE),
    ],
)
def test_verdict_for_every_chain_link_match_type(match_type, expected_verdict):
    assert verdict_for_chain_link_match(match_type) == expected_verdict


# ---------------------------------------------------------------------------
# DiagnosisRecord additions (§4.4)
# ---------------------------------------------------------------------------


def test_diagnosis_record_chain_link_fields_round_trip():
    record = DiagnosisRecord(
        answer_id="a_1",
        question_id="q_1",
        run_id="run_1",
        required_coverage=0.5,
        label_3way="incomplete",
        chain_link_results=[
            ChainLinkAlignment(
                expert_link_id="CL-1",
                student_from_edge_id=None,
                student_to_edge_id=None,
                match_type="missing_link",
                verdict="inaccurate",
                rationale="not stated",
            )
        ],
        reasoning_errors=["CL-1"],
        family_coverage={"mechanism_process": 0.6, "cause_effect": 0.3},
    )
    _round_trip(record)


# ---------------------------------------------------------------------------
# v2 LLM-facing schemas: relation is a true enum of registry names + "other" (§4.5)
# ---------------------------------------------------------------------------


def test_edge_suggestion_v2_accepts_registry_relation(registry):
    schema = build_edge_suggestion_v2(registry)
    instance = schema(
        source_concept_name="A",
        relation="causes",
        target_concept_name="B",
        polarity="affirmed",
        modality="always",
        conditions=[],
        statement="A causes B",
        criticality="core",
        evidence_quote="quote",
        chain_id=None,
        chain_position=None,
        part_type=None,
        dimension=None,
        surface_phrase="causes",
    )
    assert instance.relation == "causes"


def test_edge_suggestion_v2_accepts_other_sentinel(registry):
    schema = build_edge_suggestion_v2(registry)
    instance = schema(
        source_concept_name="A",
        relation="other",
        target_concept_name="B",
        polarity="affirmed",
        modality="always",
        conditions=[],
        statement="A relates to B somehow",
        criticality="peripheral",
        evidence_quote="quote",
        chain_id=None,
        chain_position=None,
        part_type=None,
        dimension=None,
        surface_phrase="relates to",
    )
    assert instance.relation == "other"


def test_edge_suggestion_v2_rejects_hallucinated_relation_name(registry):
    schema = build_edge_suggestion_v2(registry)
    with pytest.raises(ValidationError):
        schema(
            source_concept_name="A",
            relation="not_a_real_relation",
            target_concept_name="B",
            polarity="affirmed",
            modality="always",
            conditions=[],
            statement="x",
            criticality="core",
            evidence_quote="quote",
            chain_id=None,
            chain_position=None,
            part_type=None,
            dimension=None,
            surface_phrase="x",
        )


def test_expert_subgraph_suggestion_v2_nests_the_v2_edge_schema(registry):
    schema = build_expert_subgraph_suggestion_v2(registry)
    instance = schema(
        concepts=[],
        edges=[
            {
                "source_concept_name": "A",
                "relation": "causes",
                "target_concept_name": "B",
                "polarity": "affirmed",
                "modality": "always",
                "conditions": [],
                "statement": "A causes B",
                "criticality": "core",
                "evidence_quote": "quote",
                "chain_id": None,
                "chain_position": None,
                "part_type": None,
                "dimension": None,
                "surface_phrase": "causes",
            }
        ],
    )
    assert instance.edges[0].relation == "causes"


def test_student_edge_suggestion_v2_relation_enum(registry):
    schema = build_student_edge_suggestion_v2(registry)
    with pytest.raises(ValidationError):
        schema(
            source_concept_name=None,
            source_surface="x",
            relation="not_a_real_relation",
            target_concept_name=None,
            target_surface="y",
            polarity="affirmed",
            modality="always",
            conditions=[],
            stance="asserted",
            evidence_quote="x causes y",
            extraction_confidence=0.5,
            link_confidence=0.0,
            part_type=None,
            dimension=None,
            surface_phrase="causes",
        )
