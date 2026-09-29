"""M5 task 4 (CR-005 §2, redesigned by §9): candidate concept pairs (Stage A, no LLM,
sentence-level co-occurrence with a configurable window, ranked and capped per
section) -> family choice -> relation choice -> qualifier pass. Family and relation
are two separate LLM calls, so each stage's own accuracy and cost can be measured
independently (ARCHITECTURE.md §6).

CR-005 §9: a pair is classified at most ONCE PER RUN. `PairRegistry` remembers every
pair's resolution (accepted edge, or a terminal rejection -- NO_RELATION included) by
its canonical concept-id pair; a later section that re-proposes an already-resolved
pair records only an extra evidence sentence, with no further LLM calls. This is the
direct fix for the $14.03 IIR-dev overrun (docs/DECISIONS.md), where the same pair was
silently re-billed every time it recurred across a chapter's sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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

DEFAULT_SENTENCE_WINDOW = 0  # 0 = same sentence only
DEFAULT_MAX_PAIRS_PER_SECTION = 30

# CR-005 §9: generic relational cue words/phrases, used only to help *rank* candidate
# pairs -- never to decide a relation. Combines a small curated list of relation-
# indicating verbs/phrases (drawn from the registry's own relation templates) with the
# registry's chain-link connectives (already-curated linguistic cues, ARCHITECTURE.md
# §4e), so this stays registry-driven rather than a second hardcoded relation list.
_GENERIC_CUE_WORDS = {
    "causes",
    "cause",
    "leads to",
    "results in",
    "requires",
    "uses",
    "used by",
    "is a",
    "is a type of",
    "part of",
    "triggers",
    "prevents",
    "increases",
    "decreases",
    "differs from",
    "equivalent to",
    "depends on",
    "consists of",
    "composed of",
    "has property",
    "performs",
    "because",
    "so that",
    "in order to",
}


def _cue_words(registry: RelationRegistry) -> set[str]:
    words = set(_GENERIC_CUE_WORDS)
    for chain_link in registry.chain_link_types.values():
        words.update(c.lower() for c in chain_link.cues)
    return words


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _mentioned_sentence_indices(sentences: list[str], concept: RegisteredConcept) -> list[int]:
    names = [n.lower() for n in {concept.canonical_name, *concept.aliases} if n]
    return [i for i, s in enumerate(sentences) if any(name in s.lower() for name in names)]


def _pair_key(concept_x_id: str, concept_y_id: str) -> frozenset[str]:
    return frozenset((concept_x_id, concept_y_id))


@dataclass
class CandidatePair:
    pair_id: str
    section_id: str
    concept_x_id: str
    concept_y_id: str
    sentence: str  # the earliest co-occurring sentence (or sentence span), evidence context
    cooccurrence_count: int = 1
    cue_score: int = 0


def find_candidate_pairs(
    section_id: str,
    section_text: str,
    concepts: list[RegisteredConcept],
    registry: RelationRegistry,
    *,
    window: int = DEFAULT_SENTENCE_WINDOW,
    max_pairs: int = DEFAULT_MAX_PAIRS_PER_SECTION,
) -> tuple[list[CandidatePair], list[CandidatePair]]:
    """Stage A: rule-based, no LLM call. Two concepts are a candidate pair if they're
    mentioned in the same sentence (window=0) or within `window` sentences of each
    other. Ranked by (has a relational cue word, co-occurrence count, earliest
    position), then capped at `max_pairs`. Returns (kept, overflow) -- `overflow` is
    for logging only and must never be sent for classification (CR-005 §9 item 3).
    """
    sentences = split_sentences(section_text)
    cue_words = _cue_words(registry)
    mentions = {c.concept_id: _mentioned_sentence_indices(sentences, c) for c in concepts}
    mentioned = [c for c in concepts if mentions[c.concept_id]]

    stats: dict[frozenset[str], dict] = {}
    for i in range(len(mentioned)):
        for j in range(i + 1, len(mentioned)):
            cx, cy = mentioned[i], mentioned[j]
            for idx_x in mentions[cx.concept_id]:
                for idx_y in mentions[cy.concept_id]:
                    if abs(idx_x - idx_y) > window:
                        continue
                    key = _pair_key(cx.concept_id, cy.concept_id)
                    entry = stats.setdefault(
                        key,
                        {
                            "concept_x_id": cx.concept_id,
                            "concept_y_id": cy.concept_id,
                            "count": 0,
                            "first_idx": min(idx_x, idx_y),
                            "cue_score": 0,
                        },
                    )
                    entry["count"] += 1
                    entry["first_idx"] = min(entry["first_idx"], idx_x, idx_y)
                    span_start, span_end = sorted((idx_x, idx_y))
                    span_text = " ".join(sentences[span_start : span_end + 1]).lower()
                    if any(cue in span_text for cue in cue_words):
                        entry["cue_score"] = 1

    ranked = sorted(stats.values(), key=lambda e: (-e["cue_score"], -e["count"], e["first_idx"]))
    all_pairs = [
        CandidatePair(
            pair_id=f"RP-{section_id}-{i}",
            section_id=section_id,
            concept_x_id=e["concept_x_id"],
            concept_y_id=e["concept_y_id"],
            sentence=sentences[e["first_idx"]],
            cooccurrence_count=e["count"],
            cue_score=e["cue_score"],
        )
        for i, e in enumerate(ranked)
    ]
    return all_pairs[:max_pairs], all_pairs[max_pairs:]


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
class PairResolution:
    concept_x_id: str
    concept_y_id: str
    resolved: bool = False
    edge: RelationEdgeCandidate | None = None
    reason: str | None = None  # set when resolved without an edge (incl. "family_no_relation")
    evidence_sentences: list[str] = field(default_factory=list)


class PairRegistry:
    """Run-level memory of every candidate pair's classification (CR-005 §9). A pair
    is classified at most once; every later re-occurrence just adds an evidence
    sentence via `add_evidence`, with no LLM call.
    """

    def __init__(self):
        self._pairs: dict[frozenset[str], PairResolution] = {}

    def _entry(self, concept_x_id: str, concept_y_id: str) -> PairResolution:
        key = _pair_key(concept_x_id, concept_y_id)
        return self._pairs.setdefault(
            key, PairResolution(concept_x_id=concept_x_id, concept_y_id=concept_y_id)
        )

    def get(self, concept_x_id: str, concept_y_id: str) -> PairResolution | None:
        return self._pairs.get(_pair_key(concept_x_id, concept_y_id))

    def restore(self, resolutions: list[PairResolution]) -> None:
        """Reinstates previously-saved resolutions as-is (e.g. from a checkpoint)."""
        for resolution in resolutions:
            key = _pair_key(resolution.concept_x_id, resolution.concept_y_id)
            self._pairs[key] = resolution

    def is_resolved(self, concept_x_id: str, concept_y_id: str) -> bool:
        existing = self.get(concept_x_id, concept_y_id)
        return existing is not None and existing.resolved

    def add_evidence(self, concept_x_id: str, concept_y_id: str, sentence: str) -> None:
        entry = self._entry(concept_x_id, concept_y_id)
        if sentence not in entry.evidence_sentences:
            entry.evidence_sentences.append(sentence)

    def resolve(
        self,
        concept_x_id: str,
        concept_y_id: str,
        *,
        edge: RelationEdgeCandidate | None = None,
        reason: str | None = None,
    ) -> None:
        entry = self._entry(concept_x_id, concept_y_id)
        entry.resolved = True
        entry.edge = edge
        entry.reason = reason

    def all(self) -> list[PairResolution]:
        return list(self._pairs.values())


@dataclass
class PairClassification:
    pair: CandidatePair
    edge: RelationEdgeCandidate | None
    # set (and edge is None) when Stage B/C stopped early or an evidence check failed
    reason: str | None = None
    already_resolved: bool = False  # True: reused a prior classification, no LLM call made


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
    """Always makes at least one LLM call (the family step) -- callers wanting the
    run-level dedup must check `PairRegistry.is_resolved` first (see
    `extract_relations_for_section`), not call this directly for a pair that's
    already resolved.
    """
    family_schema = build_family_choice_llm(registry)
    family_rendered = family_prompt.render(
        concept_x=concept_x.canonical_name,
        concept_y=concept_y.canonical_name,
        sentence=pair.sentence,
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
        sentence=pair.sentence,
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

    if not verify_quote(relation_result.output.evidence_quote, pair.sentence):
        return PairClassification(
            pair=pair, edge=None, reason="evidence_quote not found in sentence"
        )

    qualifier_rendered = qualifier_prompt.render(
        concept_x=concept_x.canonical_name,
        concept_y=concept_y.canonical_name,
        relation=relation,
        statement=relation_result.output.statement,
        sentence=pair.sentence,
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
    if not verify_quote(qualifiers.surface_phrase, pair.sentence):
        return PairClassification(
            pair=pair, edge=None, reason="surface_phrase not found in sentence"
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


@dataclass
class SectionRelationResult:
    classifications: list[PairClassification] = field(default_factory=list)
    overflow_pairs: list[CandidatePair] = field(default_factory=list)  # capped out, never billed


def extract_relations_for_section(
    client: LLMClient,
    family_prompt: PromptTemplate,
    relation_prompt: PromptTemplate,
    qualifier_prompt: PromptTemplate,
    registry: RelationRegistry,
    pair_registry: PairRegistry,
    *,
    section_id: str,
    section_text: str,
    concepts: list[RegisteredConcept],
    window: int = DEFAULT_SENTENCE_WINDOW,
    max_pairs: int = DEFAULT_MAX_PAIRS_PER_SECTION,
    fixture_for_pair=None,
) -> SectionRelationResult:
    """Orchestrates Stage A + Stage B/C for one section, honouring `pair_registry`'s
    run-level dedup: an already-resolved pair gets an evidence sentence recorded and
    is returned with `already_resolved=True`, never re-billed.

    `fixture_for_pair`: optional `(pair) -> (family_fixture, relation_fixture,
    qualifier_fixture)` callable, so tests can drive different mock fixtures per pair;
    defaults to "default" for every call when omitted.
    """
    by_id = {c.concept_id: c for c in concepts}
    kept, overflow = find_candidate_pairs(
        section_id, section_text, concepts, registry, window=window, max_pairs=max_pairs
    )

    result = SectionRelationResult(overflow_pairs=overflow)
    for pair in kept:
        if pair_registry.is_resolved(pair.concept_x_id, pair.concept_y_id):
            pair_registry.add_evidence(pair.concept_x_id, pair.concept_y_id, pair.sentence)
            existing = pair_registry.get(pair.concept_x_id, pair.concept_y_id)
            result.classifications.append(
                PairClassification(
                    pair=pair, edge=existing.edge, reason=existing.reason, already_resolved=True
                )
            )
            continue

        family_fixture, relation_fixture, qualifier_fixture = (
            fixture_for_pair(pair) if fixture_for_pair else ("default", "default", "default")
        )
        classification = classify_candidate_pair(
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
        pair_registry.resolve(
            pair.concept_x_id,
            pair.concept_y_id,
            edge=classification.edge,
            reason=classification.reason,
        )
        pair_registry.add_evidence(pair.concept_x_id, pair.concept_y_id, pair.sentence)
        result.classifications.append(classification)

    return result


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
