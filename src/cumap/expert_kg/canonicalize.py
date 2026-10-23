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
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import yaml

from cumap.expert_kg.alias_rules import split_embedded_acronym
from cumap.expert_kg.canonical_rules import AliasContext
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
    definition: str | None = None  # CR-007 §4.2: kept so a later `refined` mention can be traced
    source: str = "llm"  # "llm" | "propagation" (CR-007 E3)


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
    # CR-007 §4.2: append-only refinements (later `defined` mentions): {section_id, quote, definition}
    description_history: list[dict] = field(default_factory=list)
    # CR-008 §3/§4: pre-merge ids, and per-alias provenance {form, rule_id, section_id, evidence_quote, from_id}
    merged_from: list[str] = field(default_factory=list)
    alias_provenance: list[dict] = field(default_factory=list)


@dataclass
class CanonicalizationOutcome:
    decision: str  # same | broader | narrower | different
    concept_id: str
    llm_called: bool
    matched_concept_id: str | None = None  # the existing concept it was compared against, if any
    reason: str | None = None
    auto_merged: bool = False  # exact-string match to an existing name/alias, no LLM call
    overridden: bool = False  # canonical_overrides.yaml forced or blocked this decision
    # CR-007 §4.3
    review: bool = False  # the LLM said "same" but similarity is below the review band: not merged
    similarity: float | None = None  # similarity to `matched_concept_id`
    related_ids: list[str] = field(default_factory=list)  # different node_type: never `same`
    # CR-008 §3: the deterministic rule that merged it (R0/R1/R2/R3-strong) and its evidence
    rule_id: str | None = None
    evidence_quote: str | None = None
    # CR-035 (`identity_resolver: u1` only): the pre-CR-035 id of a deterministic rule, the registry form that matched in the search, and the
    # registry concepts a weak alias cue ("sometimes called") linked the mention to (review only, never a merge)
    legacy_rule_id: str | None = None
    matched_form: str | None = None
    weak_cue_ids: list[str] = field(default_factory=list)


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

    # ------------------------------------------------------------ CR-035 search (`identity_resolver: u1`)
    @staticmethod
    def gloss_text(form: str, quote: str | None, words: int = 25) -> str:
        """The u1 recipe on both sides of the comparison: "form. gloss", the gloss being the first `words` words of the node's own quote."""
        gloss = " ".join((quote or "").replace('"', "'").split()[:words])
        return f"{form}. {gloss}" if gloss else form

    def _form_vectors(self, concept: RegisteredConcept, words: int) -> list[tuple[str, np.ndarray]]:
        quote = concept.mentions[0].quote if concept.mentions else concept.definition
        cache = concept.__dict__.setdefault("_form_vecs", {})
        out = []
        for form in (concept.canonical_name, *concept.aliases):
            text = self.gloss_text(form, quote, words)
            if text not in cache:  # a merge adds an alias (a new text): the new form is embedded, stale texts are never reused
                cache[text] = self._embed_fn(text)
            out.append((form, cache[text]))
        return out

    def top_k_similar_forms(
        self, name: str, quote: str | None, k: int = 5, words: int = 25
    ) -> list[tuple[RegisteredConcept, float, str]]:
        """(concept, best cosine over its forms, the form that scored best), best first. Same text recipe for the query and every form."""
        if not self._concepts:
            return []
        query = self._embed_fn(self.gloss_text(name, quote, words))
        scored = []
        for concept in self._concepts.values():
            best_sim, best_form = -2.0, concept.canonical_name
            for form, vec in self._form_vectors(concept, words):
                sim = float(np.dot(query, vec) / (np.linalg.norm(query) * np.linalg.norm(vec) + 1e-9))
                if sim > best_sim:
                    best_sim, best_form = sim, form
            scored.append((concept, best_sim, best_form))
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
            mentions=[
                Mention(
                    mention.section_id,
                    mention.role,
                    mention.evidence_quote,
                    mention.definition,
                    mention.source,  # CR-009 STOP 1: add_new used to drop it, relabelling propagation as llm
                )
            ],
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
        concept.mentions.append(
            Mention(
                mention.section_id,
                mention.role,
                mention.evidence_quote,
                mention.definition,
                mention.source,
            )
        )


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
    type_aware: bool = False,
    review_below: float | None = None,
    alias_ctx: AliasContext | None = None,
    identity_resolver: str = "legacy",
    judge_prompt: PromptTemplate | None = None,
    judge_domain: str = "computer networking",
) -> CanonicalizationOutcome:
    """CR-035: `identity_resolver="u1"` searches the registry with `top_k_similar_forms` (name + gloss, every form), logs the U-ids (the old id in
    `legacy_rule_id`) and records weak alias cues; "legacy" is the pre-CR-035 behaviour, byte-identical.
    CR-007 §4.3 (off by default; the CR-007 pipeline turns both on): with `type_aware`, a
    candidate with a different `node_type` is never offered as `same` (it is logged as a `related`
    candidate for the taxonomy layer); with `review_below`, an LLM "same" whose similarity is under
    the band is NOT merged but routed to the review sheet (decision "review", a new concept is
    created, nothing is lost). Exact-string auto-merge and the overrides are unchanged."""
    overrides = overrides or CanonicalOverrides()
    extra_alias: str | None = None
    original_name = mention.canonical_name
    if alias_ctx is not None:  # CR-008 R2: "long form (SF)" -> canonical long form + alias SF
        split = split_embedded_acronym(mention.canonical_name, alias_ctx.cfg)
        if split:
            mention = replace(mention, canonical_name=split[0])
            extra_alias = split[1]
    triples = weak_ids = None
    if identity_resolver == "u1":
        triples = registry.top_k_similar_forms(mention.canonical_name, mention.evidence_quote, k=k)
        weak_ids = (
            _weak_cue_ids(registry, mention, alias_ctx, type_aware) if alias_ctx is not None else []
        )
    outcome = _canonicalize(
        client, prompt_template, registry, mention, similarity_threshold, k, fixture_name,
        overrides, type_aware, review_below, alias_ctx, identity_resolver, triples, judge_prompt, judge_domain,
    )
    if triples is not None:
        outcome.weak_cue_ids = [c for c in (weak_ids or []) if c != outcome.concept_id]
        forms = {c.concept_id: f for c, _s, f in triples}
        outcome.matched_form = forms.get(outcome.matched_concept_id or "")
    if extra_alias:
        if outcome.decision == "same" and outcome.rule_id in (None, "exact"):
            outcome.rule_id, outcome.evidence_quote = "R2", original_name
        concept = registry.get(outcome.concept_id)
        if extra_alias != concept.canonical_name and extra_alias not in concept.aliases:
            concept.aliases.append(extra_alias)
    if identity_resolver == "u1" and outcome.rule_id in _LEGACY_TO_U:
        outcome.legacy_rule_id, outcome.rule_id = outcome.rule_id, _LEGACY_TO_U[outcome.rule_id]
    return outcome


_LEGACY_TO_U = {"R0": "U1", "exact": "U2", "R1": "U2", "R2": "U3", "R3-strong": "U4-strong"}  # = identity.LEGACY_TO_U


def _weak_cue_ids(registry, mention, alias_ctx, type_aware) -> list[str]:
    from cumap.expert_kg.canonical_rules import types_compatible

    out = []
    for c in registry.all():
        if type_aware and not types_compatible(mention.node_type, c.node_type):
            continue
        if any(alias_ctx.weak_hints(mention.canonical_name, f) for f in (c.canonical_name, *c.aliases)):
            out.append(c.concept_id)
    return out


def _canonicalize(
    client, prompt_template, registry, mention, similarity_threshold, k, fixture_name,
    overrides, type_aware, review_below, alias_ctx, identity_resolver="legacy", triples=None,
    judge_prompt=None, judge_domain="computer networking",
) -> CanonicalizationOutcome:
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
            rule_id="exact",
        )

    # CR-008 R0-R3: deterministic rules before any embedding or LLM call
    if alias_ctx is not None:
        found = alias_ctx.find_merge(
            registry.all(), mention.canonical_name, mention.node_type, mention.section_id,
            type_aware=type_aware,
        )
        if found and not overrides.is_never_merge(mention.canonical_name, found[0].canonical_name):
            target, hit = found
            registry.merge_alias(target.concept_id, mention)
            return CanonicalizationOutcome(
                decision="same", concept_id=target.concept_id, llm_called=False,
                matched_concept_id=target.concept_id, auto_merged=True,
                rule_id=hit.rule_id, evidence_quote=hit.evidence_quote,
            )

    if triples is not None:  # CR-035 u1: the search was run by the caller (so the matched form can be logged)
        candidates = [(c, sim) for c, sim, _f in triples]
    else:
        candidates = registry.top_k_similar(mention.canonical_name, mention.definition, k=k)
    if alias_ctx is not None:  # lexicon `different` guard: never offer a listed look-alike to the LLM
        chapter = alias_ctx.chapter_of.get(mention.section_id)
        kept = [
            (c, s) for c, s in candidates
            if not alias_ctx.lexicon.is_different(mention.canonical_name, c.canonical_name, chapter)
        ]
        alias_ctx.stats["candidates_blocked_by_lexicon"] += len(candidates) - len(kept)
        candidates = kept

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
    related_ids: list[str] = []
    if type_aware:
        related_ids = [c.concept_id for c, _ in candidates if c.node_type != mention.node_type]
        candidates = [(c, sim) for c, sim in candidates if c.node_type == mention.node_type]
    if not candidates:
        new_concept = registry.add_new(mention)
        return CanonicalizationOutcome(
            decision="different",
            concept_id=new_concept.concept_id,
            llm_called=False,
            overridden=blocked_any,
            related_ids=related_ids,
        )

    if judge_prompt is not None:  # CR-037 DRAFT: the U5 judge replaces the canonicalize call (identity_resolver u1 + identity_judge v1)
        return _judge_candidates(
            client, judge_prompt, judge_domain, registry, mention, candidates, similarity_threshold, review_below, related_ids, fixture_name,
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

    matched_sim = candidates[idx][1] if idx is not None and 0 <= idx < len(candidates) else None
    if (
        decision == "same"
        and matched_concept_id
        and (review_below is not None and matched_sim is not None and matched_sim < review_below)
    ):
        new_concept = registry.add_new(mention)
        return CanonicalizationOutcome(
            decision="review",
            concept_id=new_concept.concept_id,
            llm_called=True,
            matched_concept_id=matched_concept_id,
            reason=result.output.reason,
            review=True,
            similarity=matched_sim,
            related_ids=related_ids,
        )
    if decision == "same" and matched_concept_id:
        registry.merge_alias(matched_concept_id, mention)
        return CanonicalizationOutcome(
            decision="same",
            concept_id=matched_concept_id,
            llm_called=True,
            matched_concept_id=matched_concept_id,
            reason=result.output.reason,
            similarity=matched_sim,
            related_ids=related_ids,
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


def _judge_candidates(
    client, judge_prompt, domain, registry, mention, candidates, threshold, review_below, related_ids, fixture_name
) -> CanonicalizationOutcome:
    """CR-037 DRAFT (U5 for input B): candidates at or above the offer threshold, best first; the first same / narrower / broader ends the search.
    `new` goes on to the next candidate; `not_a_concept` is only a flag on this path (the node is kept, owner default D-5); a failed evidence quote
    is `no_decision` and also goes on. Nothing matched: a new concept."""
    from cumap.expert_kg.identity_judge import judge_pair

    for cand, sim in candidates:
        if sim < threshold:
            break
        gloss = cand.definition or (cand.mentions[0].quote if cand.mentions else None)
        r = judge_pair(
            client, judge_prompt, domain=domain, surface=mention.canonical_name, target_name=cand.canonical_name,
            target_aliases=cand.aliases, target_type=cand.node_type, target_gloss=gloss, sentence=mention.evidence_quote,
            fixture_name=fixture_name,
        )  # fmt: skip
        if r.decision == "same":
            if review_below is not None and sim < review_below:
                new_concept = registry.add_new(mention)
                return CanonicalizationOutcome(
                    decision="review", concept_id=new_concept.concept_id, llm_called=True, matched_concept_id=cand.concept_id,
                    reason=r.reason, review=True, similarity=sim, related_ids=related_ids, rule_id="U5",
                )  # fmt: skip
            registry.merge_alias(cand.concept_id, mention)
            return CanonicalizationOutcome(
                decision="same", concept_id=cand.concept_id, llm_called=True, matched_concept_id=cand.concept_id,
                reason=r.reason, similarity=sim, related_ids=related_ids, rule_id="U5", evidence_quote=r.evidence_quote,
            )  # fmt: skip
        if r.decision in ("narrower", "broader"):
            new_concept = registry.add_new(mention)
            return CanonicalizationOutcome(
                decision=r.decision, concept_id=new_concept.concept_id, llm_called=True, matched_concept_id=cand.concept_id,
                reason=r.reason, related_ids=related_ids, rule_id="U5",
            )  # fmt: skip
        if r.decision == "not_a_concept":
            new_concept = registry.add_new(mention)
            return CanonicalizationOutcome(
                decision="different", concept_id=new_concept.concept_id, llm_called=True,
                reason="not_a_concept (review flag, node kept): " + r.reason, related_ids=related_ids, rule_id="U5",
            )  # fmt: skip
    new_concept = registry.add_new(mention)
    return CanonicalizationOutcome(decision="different", concept_id=new_concept.concept_id, llm_called=True, related_ids=related_ids)


def write_merge_review_sheet(rows: list[dict], path: Path) -> None:
    """Blind review sheet for merges routed to review (CR-003 sheet rules): the two names, their
    node types and evidence quotes only. No model reason, similarity or decision is shown."""
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "id",
                "section",
                "mention",
                "mention_type",
                "mention_evidence",
                "existing_concept",
                "existing_type",
                "existing_definition",
                "mark (same/different)",
                "note",
            ]
        )
        for i, r in enumerate(rows, 1):
            w.writerow(
                [
                    i,
                    r["section_id"],
                    r["alias"],
                    r["mention_type"],
                    r["quote"],
                    r["candidate_name"],
                    r["candidate_type"],
                    r["candidate_definition"] or "",
                    "",
                    "",
                ]
            )
