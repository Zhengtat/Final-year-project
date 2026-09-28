"""Flat LLM-facing schemas for Structured Outputs (CLAUDE.md OpenAI usage rules:
every field required, optional fields typed X | None, no defaults, no extra
properties). These are converted to the richer internal schemas (schemas/edges.py,
schemas/nodes.py, schemas/student.py) by the calling code, never used directly
as the internal representation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
