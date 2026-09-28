"""Evidence, Validation, QuestionLink, ConfusableRef, ExpertEdge (ARCHITECTURE.md §4b)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from cumap.schemas.enums import (
    ConfusableKind,
    ConfusableType,
    EdgeLayer,
    EdgeOrigin,
    ItemStatus,
    Modality,
    Polarity,
    QuestionLinkRole,
    QuestionLinkSource,
    ValidationStatus,
)


class Evidence(BaseModel):
    """`quote` must be verified as an exact substring (post whitespace-normalisation)
    of the referenced source text — see cumap.gold.validate.verify_quote. CLAUDE.md rule 3.
    """

    model_config = ConfigDict(extra="forbid")

    source: str  # e.g. "Peterson & Davie 6e"
    section_id: str | None = None
    answer_id: str | None = None
    quote: str

    @model_validator(mode="after")
    def _one_reference(self) -> Evidence:
        if (self.section_id is None) == (self.answer_id is None):
            raise ValueError("Evidence needs exactly one of section_id or answer_id")
        return self


class QuestionLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    role: QuestionLinkRole
    weight: float
    source: QuestionLinkSource


class ConfusableRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_id: str
    ref_kind: ConfusableKind
    type: ConfusableType


class Validation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ValidationStatus = ValidationStatus.UNREVIEWED
    reviewer: str | None = None
    date: str | None = None
    note: str | None = None


class ExtractedBy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    prompt_version: str
    run_id: str


PartType = Literal["component", "member", "phase"]


def check_core_qualifier_consistency(relation: str, part_type: str | None, dimension: str | None) -> None:
    """CR-001 §4.1: part_type only on part_of, dimension only on contrasts_with.

    This is a version-independent sanity check (a v0 edge never sets these fields, so it
    trivially passes); it does NOT enforce "part_type is required when relation==part_of"
    — that's a v1-only rule and belongs to the version-aware validator (CR-001 §5,
    cumap.gold.validate), not the schema, so v0 files keep loading unchanged.
    """
    if part_type is not None and relation != "part_of":
        raise ValueError(f"part_type is only valid on relation='part_of', got relation={relation!r}")
    if dimension is not None and relation != "contrasts_with":
        raise ValueError(f"dimension is only valid on relation='contrasts_with', got relation={relation!r}")


class ExpertEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Identity
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    layer: EdgeLayer

    # Truth conditions
    polarity: Polarity = Polarity.AFFIRMED
    modality: Modality = Modality.ALWAYS
    conditions: list[str] = []
    statement: str

    # CR-001 §4.1 core qualifiers (shared shape with StudentEdge). All optional so v0
    # files (which never had these keys) still load unchanged; "part_type required iff
    # part_of" and "surface_phrase required when LLM-extracted" are v1-only rules
    # enforced by cumap.gold.validate, not here.
    part_type: PartType | None = None
    dimension: str | None = None
    surface_phrase: str | None = None
    relation_family: str | None = None  # derived from the registry; not user-set
    registry_version: int | None = None  # stamped by code that writes the edge; None = v0

    # Diagnostic weight
    criticality: str  # "core" | "supporting" | "peripheral" (see enums.Criticality)
    question_links: list[QuestionLink] = []
    learning_objective_ids: list[str] = []
    cognitive_level: str | None = None
    chain_id: str | None = None
    chain_position: int | None = None
    depends_on_edges: list[str] = []
    introduced_in: str | None = None  # section_id

    # Misconception hooks
    confusable_with: list[ConfusableRef] = []
    contradicted_by_misconceptions: list[str] = []
    diagnostic_power: float | None = None

    # Provenance & trust
    evidence: list[Evidence]
    extracted_by: ExtractedBy | None = None
    confidence: float = 1.0
    validation: Validation
    status: ItemStatus = ItemStatus.CANDIDATE
    version: int = 1
    superseded_by: str | None = None
    origin: EdgeOrigin

    @model_validator(mode="after")
    def _qualifier_consistency(self) -> ExpertEdge:
        check_core_qualifier_consistency(self.relation, self.part_type, self.dimension)
        return self
