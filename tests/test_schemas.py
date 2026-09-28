"""Round-trip tests (model -> JSON -> model) for every schema, per M2's acceptance check."""

from __future__ import annotations

import json

from cumap.schemas.diagnosis import DiagnosisRecord, WeightedEdgeRef
from cumap.schemas.edges import ConfusableRef, Evidence, ExpertEdge, QuestionLink, Validation
from cumap.schemas.enums import (
    ConfusableKind,
    ConfusableType,
    EdgeLayer,
    EdgeOrigin,
    MentionRole,
    NodeType,
    QuestionLinkRole,
    QuestionLinkSource,
)
from cumap.schemas.labels import (
    Proposition,
    PropositionLabel,
    PropositionTriple,
    SilverAnswerLabel,
)
from cumap.schemas.misconceptions import AssertedEdge, Misconception, MisconceptionEvidence
from cumap.schemas.nodes import Concept, ConceptMention
from cumap.schemas.saf import Answer, Question
from cumap.schemas.student import Alignment, EvidenceSpan, StudentEdge
from cumap.schemas.textbook import Section


def _round_trip(model):
    cls = type(model)
    restored = cls.model_validate(json.loads(model.model_dump_json()))
    assert restored == model
    return restored


def test_section_round_trip():
    section = Section(
        section_id="6.3",
        chapter_num=6,
        chapter_title="Congestion Control",
        section_title="TCP Congestion Control",
        heading_path=["Congestion Control", "TCP Congestion Control"],
        order_index=43,
        source_file="congestion/tcpcc.rst",
        line_start=1,
        line_end=200,
        text="TCP congestion control...",
        emphasized_terms=["self-clocking"],
        word_count=4108,
    )
    _round_trip(section)


def test_question_and_answer_round_trip():
    q = Question(question_id="q_12345678", question="What is TCP?", reference_answer="A protocol.")
    _round_trip(q)
    a = Answer(
        answer_id="a_1234567890",
        question_id="q_12345678",
        split="train",
        provided_answer="TCP is reliable.",
        verification_feedback="Correct",
        score=1.0,
        answer_feedback="Good answer.",
    )
    _round_trip(a)


def test_concept_round_trip():
    concept = Concept(
        concept_id="c_slow_start",
        canonical_name="slow start",
        aliases=["SS"],
        node_type=NodeType.MECHANISM,
        definition="A TCP congestion-control phase.",
        mentions=[ConceptMention(section_id="6.3", role=MentionRole.DEFINED, quote="slow start")],
        validation=Validation(),
    )
    _round_trip(concept)


def test_expert_edge_round_trip():
    edge = ExpertEdge(
        edge_id="E-TCP-014",
        source_id="c_slow_start",
        target_id="c_exponential_cwnd_growth",
        relation="has_property",
        layer=EdgeLayer.SEMANTIC,
        statement="During slow start, cwnd grows exponentially.",
        criticality="core",
        question_links=[
            QuestionLink(
                question_id="q_xxxxxxxx",
                role=QuestionLinkRole.REQUIRED,
                weight=0.25,
                source=QuestionLinkSource.REFERENCE_ANSWER,
            )
        ],
        confusable_with=[
            ConfusableRef(ref_id="E-TCP-015", ref_kind=ConfusableKind.EDGE, type=ConfusableType.SUBSTITUTION)
        ],
        evidence=[Evidence(source="Peterson & Davie 6e", section_id="6.3", quote="cwnd roughly doubles")],
        validation=Validation(),
        origin=EdgeOrigin.TEXTBOOK,
    )
    _round_trip(edge)


def test_evidence_requires_exactly_one_reference():
    import pytest

    with pytest.raises(ValueError, match="exactly one"):
        Evidence(source="x", section_id="6.3", answer_id="a_123", quote="q")
    with pytest.raises(ValueError, match="exactly one"):
        Evidence(source="x", quote="q")


def test_student_edge_round_trip():
    edge = StudentEdge(
        source_id="c_slow_start",
        relation="has_property",
        target_id="c_linear_cwnd_growth",
        response_id="a_1234567890",
        question_id="q_12345678",
        evidence_span=EvidenceSpan(start=0, end=20, text="grows linearly"),
        extraction_confidence=0.9,
        link_confidence=0.8,
        alignment=Alignment(
            expert_edge_id="E-TCP-015",
            match_type="substituted_concept",
            decided_by="rule",
            rationale="target swapped with confusable sibling",
        ),
    )
    _round_trip(edge)


def test_proposition_and_silver_label_round_trip():
    prop = Proposition(
        prop_id="p_1",
        question_id="q_12345678",
        text="cwnd doubles each RTT during slow start",
        triple=PropositionTriple(source="c_slow_start", relation="has_property", target="c_exp_growth", polarity="affirmed"),
        criticality="core",
        weight=0.5,
    )
    _round_trip(prop)

    label = SilverAnswerLabel(
        answer_id="a_1234567890",
        question_id="q_12345678",
        proposition_labels=[PropositionLabel(answer_id="a_1234567890", prop_id="p_1", label="expressed")],
        label_3way="correct",
        run_id="run_1",
    )
    _round_trip(label)


def test_diagnosis_record_round_trip():
    record = DiagnosisRecord(
        answer_id="a_1234567890",
        question_id="q_12345678",
        run_id="run_1",
        matched=[WeightedEdgeRef(edge_id="E-1", criticality="core", weight=0.5)],
        required_coverage=0.75,
        label_3way="incomplete",
    )
    _round_trip(record)


def test_misconception_round_trip():
    m = Misconception(
        misconception_id="M-TCP-phase-swap",
        name="Phase swap",
        description="Confuses slow start with congestion avoidance growth.",
        asserted_edges=[
            AssertedEdge(
                source_id="c_slow_start",
                relation="has_property",
                target_id="c_linear_cwnd_growth",
                polarity="affirmed",
                modality="always",
            )
        ],
        conflicts_with=["E-TCP-014"],
        evidence=[MisconceptionEvidence(answer_id="a_1234567890", feedback_quote="confused the two phases")],
        source="mined_from_feedback",
        validation=Validation(),
    )
    _round_trip(m)
