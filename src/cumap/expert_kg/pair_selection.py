"""CR-007 §5.3 (owner-approved change): global, coverage-aware pair selection.

CR-005 classified only the first 30 cue-ranked pairs of each section, which left 508 of 736 concepts
without any classified pair although 660 appear in some candidate pair. This replaces the
per-section cap with a global pair budget:

  phase 0  a small per-section minimum (the best-cue pairs of every section);
  phase 0b ANCHOR PAIRS (CR-009 §6.3): each new concept paired with the node it was anchored to (the cue sentence is
           the evidence sentence); they go FIRST in the coverage phase. The anchor TYPE only sets this priority and is
           never shown to the relation generator or verifier;
  phase 1  COVERAGE: every `defined` / `used` concept gets its best-cue pair first; a pair that covers
           two uncovered concepts beats one that covers a single concept. Mentioned-only concepts are
           NOT covered in this phase;
  phase 2  FILL: the remaining budget goes to the highest-cue, highest-count pairs (this is where
           mentioned-only concepts can be covered, by cue score).

A random sample of unselected candidate pairs is returned for classification, to estimate how many
real relations the selection leaves out ("estimated missed-relation rate", Wilson CI).
Deterministic (fixed seed, sorted tie-breaks).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from cumap.expert_kg.relations import CandidatePair

CORE_ROLES = {"defined", "used"}


def pair_key(p: CandidatePair) -> frozenset[str]:
    return frozenset((p.concept_x_id, p.concept_y_id))


def _rank(p: CandidatePair) -> tuple:
    return (-p.cue_score, -p.cooccurrence_count, p.pair_id)


@dataclass
class Selection:
    selected: list[CandidatePair]
    unselected_sample: list[CandidatePair]
    stats: dict = field(default_factory=dict)


def dedupe(per_section: dict[str, list[CandidatePair]]) -> list[CandidatePair]:
    """Run-level dedup: one entry per concept pair, keeping its best-ranked occurrence."""
    best: dict[frozenset[str], CandidatePair] = {}
    for sid in sorted(per_section):
        for p in per_section[sid]:
            k = pair_key(p)
            if k not in best or _rank(p) < _rank(best[k]):
                best[k] = p
    return sorted(best.values(), key=_rank)


def select_pairs(
    per_section: dict[str, list[CandidatePair]],
    concept_role: dict[str, str],
    *,
    budget: int,
    min_per_section: int = 8,
    sample_unselected: int = 50,
    seed: int = 42,
    anchors: list[dict] | None = None,
) -> Selection:
    """`concept_role`: concept id -> strongest role (defined > used > mentioned). `anchors`: CR-009 anchor records
    {concept_id, anchor_id, section_id, cue, anchored_edge_count?} in book order (pairs go first in coverage)."""
    pool = dedupe(per_section)
    by_section: dict[str, list[CandidatePair]] = {}
    for p in pool:
        by_section.setdefault(p.section_id, []).append(p)
    chosen: dict[frozenset[str], CandidatePair] = {}
    covered: set[str] = set()

    def take(p: CandidatePair) -> None:
        if pair_key(p) not in chosen and len(chosen) < budget:
            chosen[pair_key(p)] = p
            covered.update((p.concept_x_id, p.concept_y_id))

    for sid in sorted(by_section):  # phase 0
        for p in sorted(by_section[sid], key=_rank)[:min_per_section]:
            take(p)
    phase0 = len(chosen)

    by_key = {pair_key(p): p for p in pool}
    for i, a in enumerate(anchors or []):  # phase 0b: anchor pairs, in book order
        x, y = a["concept_id"], a["anchor_id"]
        if x == y or frozenset((x, y)) in chosen:
            continue
        cand = by_key.get(frozenset((x, y)))
        sent = a["cue"] if a.get("both_in_cue") else (cand.sentence if cand else None)
        if (
            sent is None
        ):  # the pair is not co-mentioned anywhere: there is no evidence sentence to classify
            continue
        base = cand or CandidatePair(f"AP-{i}", a["section_id"], x, y, sent)
        take(
            CandidatePair(
                base.pair_id, base.section_id, x, y, sent, base.cooccurrence_count, base.cue_score
            )
        )
    phase0b = len(chosen) - phase0

    core = {c for c, r in concept_role.items() if r in CORE_ROLES}
    cand_of: dict[str, list[CandidatePair]] = {}
    for p in pool:
        for c in (p.concept_x_id, p.concept_y_id):
            if c in core:
                cand_of.setdefault(c, []).append(p)
    uncovered = sorted((c for c in cand_of if c not in covered), key=lambda c: (len(cand_of[c]), c))
    for c in (
        uncovered
    ):  # phase 1: rarest concepts first, best pair (prefer covering two new core concepts)
        if c in covered or len(chosen) >= budget:
            continue
        options = [p for p in cand_of[c] if pair_key(p) not in chosen]
        if not options:
            continue
        gain = lambda p: sum(
            1 for x in (p.concept_x_id, p.concept_y_id) if x in core and x not in covered
        )
        take(min(options, key=lambda p: (-gain(p), *_rank(p))))
    phase1 = len(chosen) - phase0 - phase0b

    for p in pool:  # phase 2: fill by cue score (mentioned-only concepts are covered only here)
        if len(chosen) >= budget:
            break
        take(p)
    selected = sorted(chosen.values(), key=_rank)
    rest = [p for p in pool if pair_key(p) not in chosen]
    sample = random.Random(seed).sample(rest, min(sample_unselected, len(rest)))
    linked_candidates = {c for p in pool for c in (p.concept_x_id, p.concept_y_id)}
    stats = {
        "unique_candidate_pairs": len(pool),
        "selected": len(selected),
        "phase0_min_per_section": phase0,
        "phase1_coverage": phase1,
        "phase0b_anchor_pairs": phase0b,
        "phase2_fill": len(selected) - phase0 - phase0b - phase1,
        "concepts_in_any_candidate": len(linked_candidates),
        "concepts_covered": len(covered),
        "core_concepts_with_candidates": len(cand_of),
        "core_concepts_covered": sum(1 for c in cand_of if c in covered),
    }
    return Selection(selected, sample, stats)
