"""Concept node schema (ARCHITECTURE.md §3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cumap.schemas.edges import ExtractedBy, Validation
from cumap.schemas.enums import ConceptStatus, MentionRole, NodeType


class ConceptMention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    role: MentionRole
    quote: str


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str
    canonical_name: str
    aliases: list[str] = []
    node_type: NodeType
    definition: str | None = None
    first_introduced: str | None = None  # section_id
    mentions: list[ConceptMention] = []
    status: ConceptStatus = ConceptStatus.CANDIDATE
    merged_into: str | None = None  # concept_id
    confidence: float = 1.0
    extracted_by: ExtractedBy | None = None
    validation: Validation
    version: int = 1
