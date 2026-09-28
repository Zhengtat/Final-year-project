"""DiagnosisRecord (ARCHITECTURE.md §4d) — per-answer diagnosis output. Missing edges
(edges that should be there but aren't) live here, not on StudentEdge, since a missing
edge has no student-side evidence to attach to.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cumap.schemas.chain_links import ChainLinkAlignment
from cumap.schemas.enums import AnswerLabel3Way


class WeightedEdgeRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    criticality: str
    weight: float


class MisconceptionCandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    misconception_id: str
    evidence_strength: float
    supporting_edge_ids: list[str]


class DiagnosisRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    question_id: str
    run_id: str

    matched: list[WeightedEdgeRef] = []
    missing: list[WeightedEdgeRef] = []
    contradicted: list[WeightedEdgeRef] = []
    extra: list[WeightedEdgeRef] = []

    required_coverage: float
    broken_chains: list[str] = []
    upstream_gaps: list[str] = []  # edge_ids
    misconception_candidates: list[MisconceptionCandidateEvidence] = []

    # CR-001 §4.4
    chain_link_results: list[ChainLinkAlignment] = []
    reasoning_errors: list[str] = []  # link_ids (wrong_link_type / reversed_link)
    family_coverage: dict[str, float] = {}  # relation family -> weighted coverage of required edges

    label_3way: AnswerLabel3Way
    saf_label_pred: str | None = None
    score_pred: float | None = None
