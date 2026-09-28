"""Flat LLM-facing schemas for the M5 expert-KG pipeline (CR-005 §2 / CR-001 §6's
4-stage relation method). Same Structured Outputs rules as schemas/llm_schemas.py:
every field required, optionals typed X | None, no defaults, no extra properties.
Built dynamically per RelationRegistry where the field is a registry choice (node
types, families, relations within a family), so a hallucinated value is structurally
impossible, not just prompt-discouraged.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model

from cumap.schemas.relations import RelationRegistry

NO_RELATION = "no_relation"
OTHER = "other"


def _node_type_literal(registry: RelationRegistry) -> type:
    return Literal[*registry.node_types]


def build_concept_mention_llm(registry: RelationRegistry) -> type[BaseModel]:
    return create_model(
        "ConceptMentionLLM",
        __config__=ConfigDict(extra="forbid"),
        canonical_name=(str, ...),
        node_type=(_node_type_literal(registry), ...),
        role=(Literal["defined", "used", "mentioned"], ...),
        definition=(str | None, ...),  # only when role == "defined"
        evidence_quote=(str, ...),
    )


def build_concept_extraction_llm(registry: RelationRegistry) -> type[BaseModel]:
    mention_model = build_concept_mention_llm(registry)
    return create_model(
        "ConceptExtractionLLM",
        __config__=ConfigDict(extra="forbid"),
        concepts=(list[mention_model], ...),
    )


class CanonicalizeDecisionLLM(BaseModel):
    """Not registry-dependent -- candidate_index refers to the top-5 list the caller
    included in the prompt, not a registry field."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["same", "broader", "narrower", "different"]
    matched_candidate_index: int | None  # index into the top-5 candidates shown; null iff "different"
    reason: str


def _family_literal(registry: RelationRegistry) -> type:
    names = tuple(registry.families.keys()) + (NO_RELATION, OTHER)
    return Literal[*names]


def build_family_choice_llm(registry: RelationRegistry) -> type[BaseModel]:
    """CR-005 relation Stage B, step 1 of 2: pick a family (or no_relation/other) for a
    candidate concept pair, before picking the specific relation within it.
    """
    return create_model(
        "FamilyChoiceLLM",
        __config__=ConfigDict(extra="forbid"),
        family=(_family_literal(registry), ...),
        reason=(str, ...),
    )


def build_relation_choice_llm(registry: RelationRegistry, family: str) -> type[BaseModel]:
    """CR-005 relation Stage B, step 2 of 2: given a chosen family, pick the specific
    relation (or "other"), plus direction for directional relations.
    """
    names = tuple(r.name for r in registry.all_relations() if r.family == family) + (OTHER,)
    return create_model(
        "RelationChoiceLLM",
        __config__=ConfigDict(extra="forbid"),
        relation=(Literal[*names], ...),
        direction=(Literal["forward", "reversed"], ...),  # ignored for non-directional/other
        evidence_quote=(str, ...),
        statement=(str, ...),
    )


class QualifiersLLM(BaseModel):
    """CR-001's separate qualifier pass, reused here for the M5 pipeline. Not
    registry-dependent beyond the part_type literal (fixed by CR-001, not per-registry).
    """

    model_config = ConfigDict(extra="forbid")

    polarity: Literal["affirmed", "negated"]
    modality: Literal["necessary", "always", "typically", "possible", "never"]
    conditions: list[str]
    part_type: Literal["component", "member", "phase"] | None
    dimension: str | None
    surface_phrase: str
