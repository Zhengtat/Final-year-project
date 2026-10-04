"""CR-007 §5: relation classification for registry v1.1 with relation prompts v3.

Two LLM steps + a qualifier pass, all strong tier through LLMClient:
  family step  -> each family shown with a gloss and its relation names; stated OR denied relations go
                  to their family, lists/co-mentions to NO_RELATION;
  relation step-> the registry templates FILLED with the two concepts' names, in both directions for
                  directional relations (QA4RE-faithful), plus no_relation and other; OTHER must carry
                  other_description and other_suggested_label; contrasts_with / trades_off_with must
                  carry a comparison_dimension grounded in the sentence, else the pair is NO_RELATION
                  (owner decision at STOP 1: 4 of 7 spot-check failures were lists read as contrasts);
  qualifiers   -> polarity records a denial; action_type for acts_on; corrects_intuition / intuition.
Checks after the LLM: evidence quote is a substring of the sentence, both endpoints are grounded as
longest-match mentions (in the quote by default), domain/range from the registry, surface phrase.
The exact prompt text of every call is in data/logs/llm_prompts.jsonl (by input hash).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, create_model, model_validator

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.llm_schemas import NO_RELATION, OTHER, build_family_choice_llm
from cumap.expert_kg.mentions import MentionMatcher, default_lemma, tokenize
from cumap.expert_kg.relations import CandidatePair
from cumap.gold.validate import verify_quote
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate
from cumap.schemas.relations import EdgeRef, RelationRegistry

# CR-007 (2026-10-01): the generic fallback type never blocks an edge (owner decision at STOP 4);
# specific wrong types still do. check_types skips endpoints whose type is not supplied.
GENERIC_TYPE = "Concept"
SAME_CONCEPT = "same_concept"  # CR-008 §3.5: a choice, never an edge
DIMENSION_RELATIONS = {"contrasts_with", "trades_off_with"}
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "between",
    "that",
    "this",
    "than",
    "its",
    "their",
    "are",
    "was",
}


# ------------------------------------------------------------------ prompt blocks
def family_options_v3(registry: RelationRegistry) -> str:
    lines = []
    for f in registry.families.values():
        if f.name == "pedagogical":
            continue
        rels = ", ".join(r.name for r in registry.all_relations() if r.family == f.name)
        lines.append(f"- {f.name}: {f.gloss or f.label} (relations: {rels})")
    lines.append("- no_relation: nothing meaningful is stated between these two concepts here")
    lines.append("- other: a real relation is stated, but it does not fit any family above")
    return "\n".join(lines)


def filled_options(
    registry: RelationRegistry, family: str, x: str, y: str, same_concept: bool = False
) -> str:
    """Registry templates filled with the actual names, both directions for directional relations."""
    lines = []
    for rel in registry.all_relations():
        if rel.family != family:
            continue
        lines.append(f"- {rel.name}: {rel.definition}")
        lines.append(f'    forward  (X first): "{registry.template_for(rel.name, x, y)}"')
        if rel.directional:
            lines.append(
                f'    reversed (Y first): "{registry.template_for(rel.name, x, y, reverse=True)}"'
            )
        for nm in rel.near_misses:
            lines.append(f'    not {nm.relation}: "{nm.example}" ({nm.why})')
    if same_concept and family == "comparison":  # CR-008 §3.5: equivalence is a node property
        lines.append(
            f"- {SAME_CONCEPT}: {x} and {y} are two names for the same thing (no relation is "
            "drawn; the pair is queued to be merged into one node)"
        )
    lines.append(
        "- no_relation: X and Y are only listed together or co-mentioned; no relation is stated between them"
    )
    lines.append("- other: the sentence relates X and Y, but none of the relations above fits")
    return "\n".join(lines)


# ------------------------------------------------------------------ schemas
def build_relation_choice_v3(
    registry: RelationRegistry, family: str, same_concept: bool = False
) -> type[BaseModel]:
    extra = (SAME_CONCEPT,) if same_concept and family == "comparison" else ()
    names = (
        tuple(r.name for r in registry.all_relations() if r.family == family)
        + extra
        + (NO_RELATION, OTHER)
    )

    def _other_needs_text(self):
        if self.relation == OTHER and not (self.other_description and self.other_suggested_label):
            raise ValueError(
                "relation 'other' requires other_description and other_suggested_label"
            )
        return self

    return create_model(
        "RelationChoiceV3LLM",
        __config__=ConfigDict(extra="forbid"),
        __validators__={"_other_needs_text": model_validator(mode="after")(_other_needs_text)},
        relation=(Literal[*names], ...),
        direction=(Literal["forward", "reversed"], ...),
        evidence_quote=(str, ...),
        statement=(str, ...),
        comparison_dimension=(str | None, ...),
        other_description=(str | None, ...),
        other_suggested_label=(str | None, ...),
    )


def build_qualifiers_v3(registry: RelationRegistry, intuition: bool = True) -> type[BaseModel]:
    """`intuition=False` is the v4 schema: no corrects_intuition / intuition (CR-008 item 2)."""
    extra = {"corrects_intuition": (bool, ...), "intuition": (str | None, ...)} if intuition else {}
    action_values = tuple(registry.qualifiers["action_type"].values or ["other"])
    return create_model(
        "QualifiersV3LLM" if intuition else "QualifiersV4LLM",
        __config__=ConfigDict(extra="forbid"),
        polarity=(Literal["affirmed", "negated"], ...),
        modality=(Literal["necessary", "always", "typically", "possible", "never"], ...),
        conditions=(list[str], ...),
        part_type=(Literal["component", "member", "phase"] | None, ...),
        dimension=(str | None, ...),
        action_type=(Literal[*action_values] | None, ...),
        surface_phrase=(str, ...),
        **extra,
    )


# ------------------------------------------------------------------ checks
def dimension_grounded(dimension: str | None, sentence: str) -> bool:
    """A comparison dimension must be named in the evidence sentence: verbatim, or every content
    word of it (lemmatised) occurs in the sentence."""
    if not dimension or not dimension.strip():
        return False
    if dimension.lower().strip() in sentence.lower():
        return True
    words = {t for _, _, t in tokenize(dimension) if len(t) > 2 and t not in _STOP}
    have = {default_lemma(t) for _, _, t in tokenize(sentence)}
    return bool(words) and words <= have


def _contained(short: str, longer: str) -> bool:
    a, b = tokenize(short), tokenize(longer)
    ta, tb = [t for _, _, t in a], [t for _, _, t in b]
    return (
        bool(ta)
        and len(ta) < len(tb)
        and any(tb[i : i + len(ta)] == ta for i in range(len(tb) - len(ta) + 1))
    )


def endpoint_grounding(
    text: str, matcher: MentionMatcher, cid_x: str, cid_y: str
) -> tuple[bool, bool]:
    """Is each endpoint a longest-match mention inside `text`? ('bit' inside 'bit rate' does not
    ground the concept 'bit'.)"""
    found = {m.concept_id for m in matcher.find(text)}
    return cid_x in found, cid_y in found


# ------------------------------------------------------------------ classification
@dataclass
class V3Result:
    pair: CandidatePair
    outcome: str  # edge | no_relation | other | rejected | same_concept (CR-008: no edge)
    reason: str | None = None
    family: str | None = None
    relation: str | None = None
    direction: str | None = None
    statement: str | None = None
    evidence_quote: str | None = None
    qualifiers: dict = field(default_factory=dict)
    comparison_dimension: str | None = None
    other_description: str | None = None
    other_suggested_label: str | None = None
    family_reason: str | None = None
    grounding: dict = field(default_factory=dict)
    type_errors: list[str] = field(default_factory=list)
    prompt_hashes: dict = field(default_factory=dict)  # step -> input hash of the logged prompt

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "pair"}
        d["pair"] = self.pair.__dict__
        return d


def classify_pair_v3(
    client: LLMClient,
    family_prompt: PromptTemplate,
    relation_prompt: PromptTemplate,
    qualifier_prompt: PromptTemplate,
    registry: RelationRegistry,
    pair: CandidatePair,
    cx: RegisteredConcept,
    cy: RegisteredConcept,
    matcher: MentionMatcher,
    *,
    grounding_scope: str = "quote",  # "quote" (CR-007 §5.3) | "sentence"
    same_concept: bool = False,  # CR-008: offer the `same_concept` outcome (relation_choice v4)
    model_tier: str = "strong",
    containment_grounding: bool = False,
    fixtures: tuple[str, str, str] = ("default", "default", "default"),
) -> V3Result:
    x, y = cx.canonical_name, cy.canonical_name
    res = V3Result(pair=pair, outcome="rejected")

    fam = client.parse(
        task="relation_family",
        prompt_version=family_prompt.version,
        messages=[
            {
                "role": "user",
                "content": family_prompt.render(
                    concept_x=x,
                    concept_y=y,
                    sentence=pair.sentence,
                    family_options=family_options_v3(registry),
                ),
            }
        ],
        schema=build_family_choice_llm(registry),
        model_tier=model_tier,
        fixture_name=fixtures[0],
    )
    res.prompt_hashes["family"] = fam.input_hash
    res.family, res.family_reason = fam.output.family, fam.output.reason
    if res.family == NO_RELATION:
        res.outcome, res.reason = "no_relation", "family_no_relation"
        return res
    if res.family == OTHER:
        res.outcome, res.reason = "other", "family_other"
        res.other_description = fam.output.reason
        return res

    schema = build_relation_choice_v3(registry, res.family, same_concept)
    try:
        rel = client.parse(
            task="relation_choice",
            prompt_version=relation_prompt.version,
            messages=[
                {
                    "role": "user",
                    "content": relation_prompt.render(
                        concept_x=x,
                        concept_y=y,
                        family=res.family,
                        sentence=pair.sentence,
                        relation_options=filled_options(registry, res.family, x, y, same_concept),
                    ),
                }
            ],
            schema=schema,
            model_tier=model_tier,
            fixture_name=fixtures[1],
        )
    except ValidationError as e:  # e.g. OTHER without its description fields
        res.reason = f"schema_invalid: {e.errors()[0]['msg']}"
        return res
    res.prompt_hashes["choice"] = rel.input_hash
    o = rel.output
    res.relation, res.direction, res.statement = o.relation, o.direction, o.statement
    res.evidence_quote, res.comparison_dimension = o.evidence_quote, o.comparison_dimension
    if o.relation == NO_RELATION:
        res.outcome, res.reason = "no_relation", "relation_no_relation"
        return res
    if o.relation == SAME_CONCEPT:  # no edge: the pair becomes a canonicalisation merge candidate
        if not verify_quote(o.evidence_quote, pair.sentence):
            res.reason = "evidence_quote_not_in_sentence"
            return res
        res.outcome, res.reason = "same_concept", "queued_for_merge"
        return res
    if o.relation == OTHER:
        res.outcome, res.reason = "other", "relation_other"
        res.other_description, res.other_suggested_label = (
            o.other_description,
            o.other_suggested_label,
        )
        return res

    if o.relation in DIMENSION_RELATIONS and not dimension_grounded(
        o.comparison_dimension, pair.sentence
    ):
        res.outcome, res.reason = "no_relation", "comparison_no_grounded_dimension"
        return res
    if not verify_quote(o.evidence_quote, pair.sentence):
        res.reason = "evidence_quote_not_in_sentence"
        return res
    text = o.evidence_quote if grounding_scope == "quote" else pair.sentence
    gx, gy = endpoint_grounding(text, matcher, cx.concept_id, cy.concept_id)
    sx, sy = endpoint_grounding(pair.sentence, matcher, cx.concept_id, cy.concept_id)
    res.grounding = {
        "quote_x": endpoint_grounding(o.evidence_quote, matcher, cx.concept_id, cy.concept_id)[0],
        "quote_y": endpoint_grounding(o.evidence_quote, matcher, cx.concept_id, cy.concept_id)[1],
        "sentence_x": sx,
        "sentence_y": sy,
    }
    if containment_grounding and gx != gy:
        # CR-009: an ANCHOR pair whose shorter name sits inside the longer term ("frame" in "control frame") grounds
        # through the longer term; the rule exists to stop a granularity error, not a kind_of between those two.
        short, longer = (cy, cx) if gx else (cx, cy)
        if _contained(short.canonical_name, longer.canonical_name):
            gx = gy = True
    if not (gx and gy):
        res.reason = "endpoint_not_grounded"
        return res
    src, tgt = (cy, cx) if o.direction == "reversed" else (cx, cy)
    res.type_errors = registry.check_types(
        EdgeRef(source_id=src.concept_id, relation=o.relation, target_id=tgt.concept_id),
        {c.concept_id: c.node_type for c in (cx, cy) if c.node_type != GENERIC_TYPE},
    )
    if res.type_errors:
        res.reason = "domain_range"
        return res

    q = client.parse(
        task="relation_qualifiers",
        prompt_version=qualifier_prompt.version,
        messages=[
            {
                "role": "user",
                "content": qualifier_prompt.render(
                    concept_x=x,
                    concept_y=y,
                    relation=o.relation,
                    statement=o.statement,
                    sentence=pair.sentence,
                ),
            }
        ],
        schema=build_qualifiers_v3(registry, intuition=qualifier_prompt.version == "v3"),
        model_tier=model_tier,
        fixture_name=fixtures[2],
    )
    res.prompt_hashes["qualifiers"] = q.input_hash
    res.qualifiers = q.output.model_dump()
    if not verify_quote(q.output.surface_phrase, pair.sentence):
        res.reason = "surface_phrase_not_in_sentence"
        return res
    if o.relation == "acts_on" and not q.output.action_type:
        res.reason = "acts_on_without_action_type"
        return res
    res.outcome, res.reason = "edge", None
    return res
