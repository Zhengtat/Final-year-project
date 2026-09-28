"""StudentEdge, Alignment (ARCHITECTURE.md §4c). Shares core fields with ExpertEdge."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cumap.schemas.enums import DecidedBy, MatchType, Modality, Polarity, Stance, Verdict


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int
    end: int
    text: str


class Alignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expert_edge_id: str | None
    match_type: MatchType
    decided_by: DecidedBy
    rationale: str


class MisconceptionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    misconception_id: str
    evidence_strength: float


class StudentEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Core fields (shared with ExpertEdge)
    source_id: str  # concept_id or "unlinked:<surface>"
    relation: str
    target_id: str
    polarity: Polarity = Polarity.AFFIRMED
    modality: Modality = Modality.ALWAYS
    conditions: list[str] = []

    # Identity / aggregation
    response_id: str  # == answer_id
    student_id: str | None = None  # always None for SAF
    question_id: str

    # Evidence
    evidence_span: EvidenceSpan
    stance: Stance = Stance.ASSERTED
    extraction_confidence: float
    link_confidence: float

    # Diagnosis
    alignment: Alignment | None = None
    match_type: MatchType | None = None
    verdict: Verdict | None = None
    misconception_candidates: list[MisconceptionCandidate] = []
