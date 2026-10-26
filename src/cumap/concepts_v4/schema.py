"""CR-009 §3.6: the generator's flat LLM schemas (every field required, optionals `X | None`, no defaults,
no extra properties) and the anchor/role vocabularies. Internal models stay plain dicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model

NODE_TYPES = (
    "Protocol",
    "Mechanism",
    "Component",
    "DataUnit",
    "Parameter",
    "Property",
    "Event",
    "State",
    "Layer",
    "Identifier",
    "Concept",
)
ANCHOR_TYPES = (
    "kind_of",
    "instance_of",
    "part_of",
    "property_of",
    "performed_by",
    "acts_on",
    "uses",
    "used_for",
    "requires",
    "causes",
    "compared_with",
    "other",
)
NOT_MENTION_REASONS = ("different_sense", "generic_use", "inside_longer_term")
HINT_REASONS = (*NOT_MENTION_REASONS, "not_a_concept", "not_related_here")
NodeType = Literal[*NODE_TYPES]
AnchorType = Literal[*ANCHOR_TYPES]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExistingMentionLLM(_Strict):
    node_id: str
    surface: str
    node_type: NodeType
    role: Literal["used", "mentioned", "refined", "defined"]
    evidence: str
    para: str


class NotMentionLLM(_Strict):
    node_id: str
    reason: Literal[*NOT_MENTION_REASONS]


class AnchorLLM(_Strict):
    node_id: str
    anchor_type: AnchorType
    cue: str


class NewConceptLLM(_Strict):
    name: str
    aliases: list[str]
    node_type: NodeType
    role: Literal["defined", "used", "mentioned"]
    evidence: str
    para: str
    extraction_origin: Literal["anchored", "independent"]
    anchors: list[AnchorLLM]
    independence_check: str | None
    found_via_anchor: bool


class HintResponseLLM(_Strict):
    hint_id: str
    decision: Literal["added", "rejected"]
    reason: str


class ConceptGeneratorV4LLM(_Strict):
    existing_mentions: list[ExistingMentionLLM]
    not_mentions: list[NotMentionLLM]
    new_concepts: list[NewConceptLLM]
    hint_responses: list[HintResponseLLM]


class BackfillLLM(_Strict):
    """CR-009 §3.7: the mention-check call: no new concepts, never iterated."""

    existing_mentions: list[ExistingMentionLLM]
    hint_responses: list[HintResponseLLM]


@dataclass(frozen=True)
class GeneratorSchemas:
    """The generator / backfill output schemas for one node-type set. The default set is the networking one (this module's classes);
    a benchmark-local schema (CR-012) supplies its own node types and nothing else changes."""

    generator: type[BaseModel]
    backfill: type[BaseModel]
    fill_type: str | None = None  # CR-059: type-free schemas; the runner gives every item this internal type after parsing


DEFAULT_SCHEMAS = GeneratorSchemas(ConceptGeneratorV4LLM, BackfillLLM)

# ---------------------------------------------------------------- CR-059: type-free generator schemas (no node_type field)
UNTYPED = "Concept"  # the generic type every downstream rule already treats as "no type" (domain/range skip, identity same_or_generic)


class ExistingMentionUntypedLLM(_Strict):
    node_id: str
    surface: str
    role: Literal["used", "mentioned", "refined", "defined"]
    evidence: str
    para: str


class NewConceptUntypedLLM(_Strict):
    name: str
    aliases: list[str]
    role: Literal["defined", "used", "mentioned"]
    evidence: str
    para: str
    extraction_origin: Literal["anchored", "independent"]
    anchors: list[AnchorLLM]
    independence_check: str | None
    found_via_anchor: bool


class ConceptGeneratorUntypedLLM(_Strict):
    existing_mentions: list[ExistingMentionUntypedLLM]
    not_mentions: list[NotMentionLLM]
    new_concepts: list[NewConceptUntypedLLM]
    hint_responses: list[HintResponseLLM]


class BackfillUntypedLLM(_Strict):
    existing_mentions: list[ExistingMentionUntypedLLM]
    hint_responses: list[HintResponseLLM]


UNTYPED_SCHEMAS = GeneratorSchemas(ConceptGeneratorUntypedLLM, BackfillUntypedLLM, fill_type=UNTYPED)


def fill_types(out: dict, fill_type: str | None) -> dict:
    """Give every generator item the internal type when the schema has no node_type field (CR-059); otherwise unchanged."""
    if fill_type:
        for k in ("existing_mentions", "new_concepts"):
            for it in out.get(k) or []:
                it.setdefault("node_type", fill_type)
    return out


def make_schemas(node_types: tuple[str, ...] | list[str] | None) -> GeneratorSchemas:
    """None = the networking types; an empty list = type-free (CR-059); otherwise a benchmark's own types (CR-012)."""
    if node_types is None or tuple(node_types) == NODE_TYPES:
        return DEFAULT_SCHEMAS
    if not node_types:
        return UNTYPED_SCHEMAS
    nt = Literal[tuple(node_types)]  # type: ignore[valid-type]
    existing = create_model("ExistingMentionLLM", __base__=ExistingMentionLLM, node_type=(nt, ...))
    new = create_model("NewConceptLLM", __base__=NewConceptLLM, node_type=(nt, ...))
    gen = create_model(
        "ConceptGeneratorV4LLM_" + "_".join(node_types),
        __base__=_Strict,
        existing_mentions=(list[existing], ...),  # type: ignore[valid-type]
        not_mentions=(list[NotMentionLLM], ...),
        new_concepts=(list[new], ...),  # type: ignore[valid-type]
        hint_responses=(list[HintResponseLLM], ...),
    )
    back = create_model(
        "BackfillLLM_" + "_".join(node_types),
        __base__=_Strict,
        existing_mentions=(list[existing], ...),  # type: ignore[valid-type]
        hint_responses=(list[HintResponseLLM], ...),
    )
    return GeneratorSchemas(gen, back)
