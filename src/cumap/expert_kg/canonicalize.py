"""M5 task 3: canonicalisation against the growing global concept registry. For each
new mention, retrieve the top-5 similar existing concepts (name+definition embedding);
above a similarity threshold, the LLM decides same/broader/narrower/different. Below
threshold, no LLM call is needed — it's automatically a new concept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

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
) -> CanonicalizationOutcome:
    candidates = registry.top_k_similar(mention.canonical_name, mention.definition, k=k)
    if not candidates or candidates[0][1] < similarity_threshold:
        new_concept = registry.add_new(mention)
        return CanonicalizationOutcome(
            decision="different", concept_id=new_concept.concept_id, llm_called=False
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
