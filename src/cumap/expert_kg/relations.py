"""M5 task 4 (CR-005 §2): candidate concept pairs (Stage A, no LLM) -> family choice
(Stage B step 1) -> relation choice (Stage B step 2) -> qualifier pass. Family and
relation are two separate LLM calls, per the CR-005 build order, so each stage's own
accuracy and cost can be measured independently (ARCHITECTURE.md §6).
"""

from __future__ import annotations

from dataclasses import dataclass

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.llm_schemas import (
    NO_RELATION,
    OTHER,
    QualifiersLLM,
    build_family_choice_llm,
    build_relation_choice_llm,
)
from cumap.gold.validate import verify_quote
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate
from cumap.schemas.relations import RelationRegistry


def _family_options_block(registry: RelationRegistry) -> str:
    lines = [
        f"- {f.name}: {f.label} — {f.grounding}"
        for f in registry.families.values()
        if f.name != "pedagogical"
    ]
    lines.append("- no_relation: nothing meaningful is stated between these two concepts here")
    lines.append("- other: a real relation is stated, but it doesn't fit any family above")
    return "\n".join(lines)


def _relation_options_block(registry: RelationRegistry, family: str) -> str:
    lines = []
    for rel in registry.all_relations():
        if rel.family != family:
            continue
        near_misses = "; ".join(
            f'not {nm.relation} ("{nm.example}" — {nm.why})' for nm in rel.near_misses
        )
        line = f'- {rel.name}: {rel.definition} e.g. "{rel.template}"'
        if near_misses:
            line += f" [{near_misses}]"
        lines.append(line)
    lines.append("- other: none of the above fit, even though the pair is in this family")
    return "\n".join(lines)


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _mentions_concept(paragraph_lower: str, concept: RegisteredConcept) -> bool:
    names = {concept.canonical_name, *concept.aliases}
    return any(name and name.lower() in paragraph_lower for name in names)


@dataclass
class CandidatePair:
    pair_id: str
    section_id: str
    concept_x_id: str
    concept_y_id: str
    paragraph: str


def find_candidate_pairs(
    section_id: str, section_text: str, concepts: list[RegisteredConcept]
) -> list[CandidatePair]:
    """Stage A: rule-based, no LLM call. Two concepts are a candidate pair if both are
    mentioned (by canonical name or alias) in the same paragraph of the section. A pair
    is only proposed once per section, at its first co-occurring paragraph.
    """
    pairs: list[CandidatePair] = []
    seen: set[tuple[str, str]] = set()
    for p_index, paragraph in enumerate(split_paragraphs(section_text)):
        paragraph_lower = paragraph.lower()
        mentioned = [c for c in concepts if _mentions_concept(paragraph_lower, c)]
        for i in range(len(mentioned)):
            for j in range(i + 1, len(mentioned)):
                cx, cy = mentioned[i], mentioned[j]
                key = tuple(sorted((cx.concept_id, cy.concept_id)))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append(
                    CandidatePair(
                        pair_id=f"RP-{section_id}-{p_index}-{len(pairs)}",
                        section_id=section_id,
                        concept_x_id=cx.concept_id,
                        concept_y_id=cy.concept_id,
                        paragraph=paragraph,
                    )
                )
    return pairs


@dataclass
class RelationEdgeCandidate:
    pair: CandidatePair
    family: str
    relation: str
    direction: str
    statement: str
    evidence_quote: str
    qualifiers: QualifiersLLM


@dataclass
class PairClassification:
    pair: CandidatePair
    edge: RelationEdgeCandidate | None
    # set (and edge is None) when Stage B/C stopped early or an evidence check failed
    reason: str | None = None


def classify_candidate_pair(
    client: LLMClient,
    family_prompt: PromptTemplate,
    relation_prompt: PromptTemplate,
    qualifier_prompt: PromptTemplate,
    registry: RelationRegistry,
    pair: CandidatePair,
    concept_x: RegisteredConcept,
    concept_y: RegisteredConcept,
    *,
    family_fixture: str = "default",
    relation_fixture: str = "default",
    qualifier_fixture: str = "default",
) -> PairClassification:
    family_schema = build_family_choice_llm(registry)
    family_rendered = family_prompt.render(
        concept_x=concept_x.canonical_name,
        concept_y=concept_y.canonical_name,
        paragraph=pair.paragraph,
        family_options=_family_options_block(registry),
    )
    family_result = client.parse(
        task="relation_family",
        prompt_version=family_prompt.version,
        messages=[{"role": "user", "content": family_rendered}],
        schema=family_schema,
        model_tier="strong",
        fixture_name=family_fixture,
    )
    family = family_result.output.family
    if family in (NO_RELATION, OTHER):
        return PairClassification(pair=pair, edge=None, reason=f"family_{family}")

    relation_schema = build_relation_choice_llm(registry, family)
    relation_rendered = relation_prompt.render(
        concept_x=concept_x.canonical_name,
        concept_y=concept_y.canonical_name,
        family=family,
        paragraph=pair.paragraph,
        relation_options=_relation_options_block(registry, family),
    )
    relation_result = client.parse(
        task="relation_choice",
        prompt_version=relation_prompt.version,
        messages=[{"role": "user", "content": relation_rendered}],
        schema=relation_schema,
        model_tier="strong",
        fixture_name=relation_fixture,
    )
    relation = relation_result.output.relation
    if relation == OTHER:
        return PairClassification(pair=pair, edge=None, reason="relation_other")

    if not verify_quote(relation_result.output.evidence_quote, pair.paragraph):
        return PairClassification(
            pair=pair, edge=None, reason="evidence_quote not found in paragraph"
        )

    qualifier_rendered = qualifier_prompt.render(
        concept_x=concept_x.canonical_name,
        concept_y=concept_y.canonical_name,
        relation=relation,
        statement=relation_result.output.statement,
        paragraph=pair.paragraph,
    )
    qualifier_result = client.parse(
        task="relation_qualifiers",
        prompt_version=qualifier_prompt.version,
        messages=[{"role": "user", "content": qualifier_rendered}],
        schema=QualifiersLLM,
        model_tier="strong",
        fixture_name=qualifier_fixture,
    )
    qualifiers = qualifier_result.output
    if not verify_quote(qualifiers.surface_phrase, pair.paragraph):
        return PairClassification(
            pair=pair, edge=None, reason="surface_phrase not found in paragraph"
        )

    edge = RelationEdgeCandidate(
        pair=pair,
        family=family,
        relation=relation,
        direction=relation_result.output.direction,
        statement=relation_result.output.statement,
        evidence_quote=relation_result.output.evidence_quote,
        qualifiers=qualifiers,
    )
    return PairClassification(pair=pair, edge=edge)


def extract_relations_for_section(
    client: LLMClient,
    family_prompt: PromptTemplate,
    relation_prompt: PromptTemplate,
    qualifier_prompt: PromptTemplate,
    registry: RelationRegistry,
    *,
    section_id: str,
    section_text: str,
    concepts: list[RegisteredConcept],
    fixture_for_pair=None,
) -> list[PairClassification]:
    """Orchestrates Stage A + Stage B/C over every candidate pair in a section.

    `fixture_for_pair`: optional `(pair) -> (family_fixture, relation_fixture,
    qualifier_fixture)` callable, so tests/calibration runs can drive different mock
    fixtures per pair; defaults to "default" for every call when omitted.
    """
    by_id = {c.concept_id: c for c in concepts}
    pairs = find_candidate_pairs(section_id, section_text, concepts)
    results = []
    for pair in pairs:
        family_fixture, relation_fixture, qualifier_fixture = (
            fixture_for_pair(pair) if fixture_for_pair else ("default", "default", "default")
        )
        results.append(
            classify_candidate_pair(
                client,
                family_prompt,
                relation_prompt,
                qualifier_prompt,
                registry,
                pair,
                by_id[pair.concept_x_id],
                by_id[pair.concept_y_id],
                family_fixture=family_fixture,
                relation_fixture=relation_fixture,
                qualifier_fixture=qualifier_fixture,
            )
        )
    return results
