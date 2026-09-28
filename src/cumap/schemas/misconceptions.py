"""Misconception (M8, ARCHITECTURE.md §3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cumap.schemas.edges import Validation
from cumap.schemas.enums import MisconceptionSource


class AssertedEdge(BaseModel):
    """The wrong triple a misconception implies; same core fields as an edge."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    relation: str
    target_id: str
    polarity: str
    modality: str
    conditions: list[str] = []


class MisconceptionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    feedback_quote: str


class Misconception(BaseModel):
    model_config = ConfigDict(extra="forbid")

    misconception_id: str
    name: str
    description: str
    asserted_edges: list[AssertedEdge]
    conflicts_with: list[str]  # expert edge_ids
    evidence: list[MisconceptionEvidence]
    source: MisconceptionSource
    validation: Validation
