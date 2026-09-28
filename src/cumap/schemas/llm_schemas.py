"""Flat LLM-facing schemas for Structured Outputs (CLAUDE.md OpenAI usage rules:
every field required, optional fields typed X | None, no defaults, no extra
properties). These are converted to the richer internal schemas (schemas/edges.py,
schemas/nodes.py, schemas/student.py) by the calling code, never used directly
as the internal representation.

CR-001 §4.5: the v2 schemas below are built *dynamically per registry* via
`pydantic.create_model`, so `relation` is a true enum of "every name the loaded
registry defines, plus 'other'" — Structured Outputs then makes it structurally
impossible for the LLM to invent a relation name. Used by the v2 prompts
(prompts/expert_subgraph/v2.md, prompts/student_graph/v2.md); the v1 prompts above
keep using the plain-str-relation schemas unchanged (CLAUDE.md rule 8: don't edit a
prompt version that has produced saved results).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model


class ConceptSuggestionLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_name: str
    node_type: str
    definition: str
    evidence_quote: str


class EdgeSuggestionLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_concept_name: str  # must match a canonical_name in `concepts`
    relation: str
    target_concept_name: str
    polarity: str
    modality: str
    conditions: list[str]
    statement: str
    criticality: str
    evidence_quote: str
    chain_id: str | None
    chain_position: int | None


class ExpertSubgraphSuggestionLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts: list[ConceptSuggestionLLM]
    edges: list[EdgeSuggestionLLM]


class StudentEdgeSuggestionLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_concept_name: str | None  # None if it doesn't match any known concept
    source_surface: str  # the actual words used in the answer, for unlinked concepts
    relation: str
    target_concept_name: str | None
    target_surface: str
    polarity: str
    modality: str
    conditions: list[str]
    stance: str
    evidence_quote: str  # must be a verified substring of the answer text
    extraction_confidence: float
    link_confidence: float


class StudentGraphSuggestionLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edges: list[StudentEdgeSuggestionLLM]


def _relation_literal(registry) -> type:  # registry: RelationRegistry (avoid import cycle in type hint)
    names = tuple(r.name for r in registry.all_relations()) + ("other",)
    return Literal[*names]


def build_edge_suggestion_v2(registry) -> type[BaseModel]:
    """CR-001 §4.5: EdgeSuggestionLLM + part_type/dimension/surface_phrase + a true
    relation enum (registry names + "other"), built fresh per registry.
    """
    return create_model(
        "EdgeSuggestionLLMv2",
        __config__=ConfigDict(extra="forbid"),
        source_concept_name=(str, ...),
        relation=(_relation_literal(registry), ...),
        target_concept_name=(str, ...),
        polarity=(str, ...),
        modality=(str, ...),
        conditions=(list[str], ...),
        statement=(str, ...),
        criticality=(str, ...),
        evidence_quote=(str, ...),
        chain_id=(str | None, ...),
        chain_position=(int | None, ...),
        part_type=(str | None, ...),
        dimension=(str | None, ...),
        surface_phrase=(str, ...),  # required: LLM-extracted expert edges always have one (§4.1)
    )


def build_expert_subgraph_suggestion_v2(registry) -> type[BaseModel]:
    edge_model = build_edge_suggestion_v2(registry)
    return create_model(
        "ExpertSubgraphSuggestionLLMv2",
        __config__=ConfigDict(extra="forbid"),
        concepts=(list[ConceptSuggestionLLM], ...),
        edges=(list[edge_model], ...),
    )


def build_student_edge_suggestion_v2(registry) -> type[BaseModel]:
    return create_model(
        "StudentEdgeSuggestionLLMv2",
        __config__=ConfigDict(extra="forbid"),
        source_concept_name=(str | None, ...),
        source_surface=(str, ...),
        relation=(_relation_literal(registry), ...),
        target_concept_name=(str | None, ...),
        target_surface=(str, ...),
        polarity=(str, ...),
        modality=(str, ...),
        conditions=(list[str], ...),
        stance=(str, ...),
        evidence_quote=(str, ...),
        extraction_confidence=(float, ...),
        link_confidence=(float, ...),
        part_type=(str | None, ...),
        dimension=(str | None, ...),
        surface_phrase=(str, ...),  # required on every StudentEdge (§4.1)
    )


def build_student_graph_suggestion_v2(registry) -> type[BaseModel]:
    edge_model = build_student_edge_suggestion_v2(registry)
    return create_model(
        "StudentGraphSuggestionLLMv2",
        __config__=ConfigDict(extra="forbid"),
        edges=(list[edge_model], ...),
    )
