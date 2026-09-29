"""M5 task 3: canonicalisation against the growing global concept registry. For each
new mention: (1) an exact-string match against an existing concept's name/aliases
auto-merges with no LLM call; (2) otherwise, retrieve the top-5 similar existing
concepts (name+definition embedding) -- above a similarity threshold, the LLM decides
same/broader/narrower/different (a `configs/canonical_overrides.yaml` never_merge/
force_merge list can override or pre-empt this); below threshold, no LLM call is
needed, it's automatically a new concept.

CR-005 §9 follow-up (2026-09-30): three "same" merges from a manual review turned out
wrong (a kind or instance collapsed into its category -- e.g. HDLC into SDLC, the
Internet into "internetworking", CRC into "error-detecting code"). Fixed three ways:
exact-string duplicates no longer need an LLM call at all (removes one source of
LLM-decision noise for the trivial case); canonicalize/v2.md tightens what "same"
means (interchangeable in any sentence -- never a kind/instance/part/version/
predecessor-successor/standardised-variant of the other); and the three flagged pairs
are now hard-blocked via canonical_overrides.yaml regardless of what any prompt
version would say.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from cumap.expert_kg.concepts import ConceptMentionCandidate
from cumap.expert_kg.llm_schemas import CanonicalizeDecisionLLM
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate

DEFAULT_SIMILARITY_THRESHOLD = 0.6


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


@dataclass
class Mention:
    section_id: str
    role: str
    quote: str


@dataclass
class RegisteredConcept:
    concept_id: str
    canonical_name: str
    node_type: str
    definition: str | None
    first_introduced: str
    aliases: list[str] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    embedding: np.ndarray | None = None


@dataclass
class CanonicalizationOutcome:
    decision: str  # same | broader | narrower | different
    concept_id: str
    llm_called: bool
    matched_concept_id: str | None = None  # the existing concept it was compared against, if any
    reason: str | None = None
    auto_merged: bool = False  # exact-string match to an existing name/alias, no LLM call
    overridden: bool = False  # canonical_overrides.yaml forced or blocked this decision


@dataclass
class CanonicalOverrides:
    """configs/canonical_overrides.yaml: name pairs a human has already judged, so no
    prompt version gets another chance to get them wrong. never_merge pre-empts the
    LLM entirely (the candidate is dropped before the prompt is even built);
    force_merge short-circuits straight to a merge, no LLM call.
    """

    never_merge: set[frozenset[str]] = field(default_factory=set)
    force_merge: set[frozenset[str]] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> CanonicalOverrides:
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text()) or {}
        return cls(
            never_merge={
                frozenset((a.lower(), b.lower())) for a, b in raw.get("never_merge") or []
            },
            force_merge={
                frozenset((a.lower(), b.lower())) for a, b in raw.get("force_merge") or []
            },
        )

    def is_never_merge(self, name_a: str, name_b: str) -> bool:
        return frozenset((name_a.lower(), name_b.lower())) in self.never_merge

    def is_force_merge(self, name_a: str, name_b: str) -> bool:
        return frozenset((name_a.lower(), name_b.lower())) in self.force_merge


class ConceptRegistry:
    """The growing global registry canonicalisation reads and writes. Embeddings are
    computed lazily via a caller-supplied embed function so tests don't need a real
    sentence-transformers model.
    """

    def __init__(self, embed_fn):
        self._embed_fn = embed_fn
        self._concepts: dict[str, RegisteredConcept] = {}

    def __len__(self) -> int:
        return len(self._concepts)

    def all(self) -> list[RegisteredConcept]:
        return list(self._concepts.values())

    def get(self, concept_id: str) -> RegisteredConcept:
        return self._concepts[concept_id]

    def restore(self, concepts: list[RegisteredConcept]) -> None:
        """Reinstates previously-saved concepts as-is (e.g. from a checkpoint), unlike
        `add_new`, which mints a fresh id/collision-handling for a *new* mention.
        """
        for concept in concepts:
            self._concepts[concept.concept_id] = concept

    def find_exact_match(self, name: str) -> RegisteredConcept | None:
        """Case-insensitive exact match against an existing concept's canonical_name
        or any alias -- O(n) over the registry, fine at this scale (hundreds, not
        millions, of concepts). Used to auto-merge trivial duplicates with no LLM call.
        """
        name_lower = name.lower()
        for concept in self._concepts.values():
            if name_lower == concept.canonical_name.lower():
                return concept
            if name_lower in {a.lower() for a in concept.aliases}:
                return concept
        return None

    def _text_for_embedding(self, name: str, definition: str | None) -> str:
        return f"{name}. {definition}" if definition else name

    def top_k_similar(
        self, name: str, definition: str | None, k: int = 5
    ) -> list[tuple[RegisteredConcept, float]]:
        if not self._concepts:
            return []
        query = self._embed_fn(self._text_for_embedding(name, definition))
        scored = []
        for concept in self._concepts.values():
            if concept.embedding is None:
                concept.embedding = self._embed_fn(
                    self._text_for_embedding(concept.canonical_name, concept.definition)
                )
            sim = float(
                np.dot(query, concept.embedding)
                / (np.linalg.norm(query) * np.linalg.norm(concept.embedding) + 1e-9)
            )
            scored.append((concept, sim))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def add_new(self, mention: ConceptMentionCandidate) -> RegisteredConcept:
        concept_id = "c_" + slugify(mention.canonical_name)
        base_id, i = concept_id, 2
        while (
            concept_id in self._concepts
        ):  # extremely unlikely name collision with a *different* concept
            concept_id = f"{base_id}_{i}"
            i += 1
        concept = RegisteredConcept(
            concept_id=concept_id,
            canonical_name=mention.canonical_name,
            node_type=mention.node_type,
            definition=mention.definition,
            first_introduced=mention.section_id,
            mentions=[Mention(mention.section_id, mention.role, mention.evidence_quote)],
        )
        self._concepts[concept_id] = concept
        return concept

    def merge_alias(self, concept_id: str, mention: ConceptMentionCandidate) -> None:
        concept = self._concepts[concept_id]
        if (
            mention.canonical_name != concept.canonical_name
            and mention.canonical_name not in concept.aliases
        ):
            concept.aliases.append(mention.canonical_name)
        concept.mentions.append(Mention(mention.section_id, mention.role, mention.evidence_quote))


def canonicalize_mention(
    client: LLMClient,
    prompt_template: PromptTemplate,
    registry: ConceptRegistry,
    mention: ConceptMentionCandidate,
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    k: int = 5,
    fixture_name: str = "default",
    overrides: CanonicalOverrides | None = None,
) -> CanonicalizationOutcome:
    overrides = overrides or CanonicalOverrides()

    # Exact-string duplicate: auto-merge, no LLM call (unless a human has specifically
    # blocked this exact pair via never_merge).
    exact_match = registry.find_exact_match(mention.canonical_name)
    if exact_match is not None and not overrides.is_never_merge(
        mention.canonical_name, exact_match.canonical_name
    ):
        registry.merge_alias(exact_match.concept_id, mention)
        return CanonicalizationOutcome(
            decision="same",
            concept_id=exact_match.concept_id,
            llm_called=False,
            matched_concept_id=exact_match.concept_id,
            auto_merged=True,
        )

    candidates = registry.top_k_similar(mention.canonical_name, mention.definition, k=k)

    for candidate, _sim in candidates:
        if overrides.is_force_merge(mention.canonical_name, candidate.canonical_name):
            registry.merge_alias(candidate.concept_id, mention)
            return CanonicalizationOutcome(
                decision="same",
                concept_id=candidate.concept_id,
                llm_called=False,
                matched_concept_id=candidate.concept_id,
                overridden=True,
            )

    if not candidates or candidates[0][1] < similarity_threshold:
        new_concept = registry.add_new(mention)
        return CanonicalizationOutcome(
            decision="different", concept_id=new_concept.concept_id, llm_called=False
        )

    # never_merge: drop these candidates before the LLM ever sees them, so it can't
    # choose an option a human has already ruled out.
    blocked_any = False
    filtered = []
    for candidate, sim in candidates:
        if overrides.is_never_merge(mention.canonical_name, candidate.canonical_name):
            blocked_any = True
        else:
            filtered.append((candidate, sim))
    candidates = filtered
    if not candidates:
        new_concept = registry.add_new(mention)
        return CanonicalizationOutcome(
            decision="different",
            concept_id=new_concept.concept_id,
            llm_called=False,
            overridden=blocked_any,
        )

    candidates_block = "\n".join(
        f"{i}. {c.canonical_name} ({c.node_type}) — {c.definition or '(no definition)'}"
        for i, (c, _sim) in enumerate(candidates)
    )
    rendered = prompt_template.render(
        new_name=mention.canonical_name,
        new_node_type=mention.node_type,
        new_definition=mention.definition or "(none given)",
        new_evidence=mention.evidence_quote,
        candidates_block=candidates_block,
    )
    result = client.parse(
        task="canonicalize",
        prompt_version=prompt_template.version,
        messages=[{"role": "user", "content": rendered}],
        schema=CanonicalizeDecisionLLM,
        model_tier="strong",
        fixture_name=fixture_name,
    )
    decision = result.output.decision
    idx = result.output.matched_candidate_index
    matched_concept_id = (
        candidates[idx][0].concept_id if idx is not None and 0 <= idx < len(candidates) else None
    )

    if decision == "same" and matched_concept_id:
        registry.merge_alias(matched_concept_id, mention)
        return CanonicalizationOutcome(
            decision="same",
            concept_id=matched_concept_id,
            llm_called=True,
            matched_concept_id=matched_concept_id,
            reason=result.output.reason,
        )

    # broader / narrower / different (or "same" with a missing index, treated as new
    # rather than silently discarding a real mention): all create a new concept node.
    new_concept = registry.add_new(mention)
    return CanonicalizationOutcome(
        decision=decision,
        concept_id=new_concept.concept_id,
        llm_called=True,
        matched_concept_id=matched_concept_id,
        reason=result.output.reason,
    )
