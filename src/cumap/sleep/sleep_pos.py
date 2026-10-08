"""CR-011 SLEEP-POS-160 (Research decision 2026-10-09, Option B): a separate, positive-enriched RESIDUAL challenge set. Pairs are
still DIFFERENT canonical nodes in the post-canonicalisation graph. 160 items, 80 development / 80 held-out by candidate family.
Construction is label-blind: ranks come from similarity features and candidate signals only; no SLEEP-240 outcome, no owner
decision and no gold file is read or used as a sampling rule. SLEEP-240 is not changed and its labels are never pooled with these.

Sources follow the Research list. Each source ranks eligible pairs and keeps its top `POOL_TOP`; items are then drawn uniformly
from each source pool up to a quota (rank-based, so there is no similarity threshold to tune)."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass

from cumap.sleep.sleep240 import Item

SEED = 20261010
POOL_TOP = 100
MAX_PAIRS_PER_NODE = 2
SOURCES = (
    "alias_acronym_queue",  # unresolved same_concept queue, acronym / long form, textbook alias statements
    "bridge_high_support",
    "evidence_similarity",
    "definition_similarity",
    "cross_chapter_same_surface",
    "same_type_same_sense",
    "name_similarity",
    "lexical_similarity",
)
QUOTA = {
    "alias_acronym_queue": 12,
    "bridge_high_support": 22,
    "evidence_similarity": 14,
    "definition_similarity": 18,
    "cross_chapter_same_surface": 22,
    "same_type_same_sense": 22,
    "name_similarity": 22,
    "lexical_similarity": 28,
}
assert sum(QUOTA.values()) == 160
ALIAS_SIGNALS = {
    "r2_acronym",
    "r3_strong",
    "r3_weak",
    "lexicon_same",
    "same_concept_queue",
    "r1_key",
}


@dataclass
class Candidate:
    pair: tuple[str, str]
    sources: list[str]


def eligible(pair, flags: dict, excluded: set[tuple[str, str]]) -> bool:
    """Distinct canonical nodes (by construction), CR-008 DIFFERENT excluded, type-incompatible excluded, not in SLEEP-240."""
    return (
        tuple(sorted(pair)) not in excluded
        and not flags["lexicon_different"]
        and not flags["type_incompatible"]
    )


def source_pools(
    pf: dict,
    signals: dict,
    excluded: set[tuple[str, str]],
    bridge_scores: dict[tuple[str, str], float],
    top: int = POOL_TOP,
) -> dict[str, list[tuple[str, str]]]:
    """Per-source candidate pools over eligible pairs. `pf`: pair -> (features, flags). `signals`: pair -> candidate signals."""
    el = {tuple(sorted(p)): (f, fl) for p, (f, fl) in pf.items() if eligible(p, fl, excluded)}

    def topk(score, cond=lambda f, fl: True):
        ranked = sorted(
            ((score(f, fl), p) for p, (f, fl) in el.items() if cond(f, fl)),
            key=lambda t: (-t[0], t[1]),
        )
        return [p for _s, p in ranked[:top]]

    pools = {
        "alias_acronym_queue": sorted(
            p for p in el if signals.get(frozenset(p), set()) & ALIAS_SIGNALS
        ),
        "lexical_similarity": topk(lambda f, fl: max(f["char_ratio"], f["token_jaccard"])),
        "name_similarity": topk(lambda f, fl: f["name_cos"]),
        "definition_similarity": topk(
            lambda f, fl: f["def_cos"], lambda f, fl: not f["def_missing"]
        ),
        "evidence_similarity": topk(lambda f, fl: f["ev_cos"], lambda f, fl: not f["ev_missing"]),
        "cross_chapter_same_surface": topk(
            lambda f, fl: f["name_cos"],
            lambda f, fl: f["cross_chapter"] and (f["same_surface"] or f["head_equal"]),
        ),
        "same_type_same_sense": topk(
            lambda f, fl: (f["name_cos"] + f["ev_cos"]) / 2,
            lambda f, fl: f["type_same"] and not f["ev_missing"],
        ),
    }
    ranked_b = sorted(
        ((s, p) for p, s in bridge_scores.items() if p not in excluded), key=lambda t: (-t[0], t[1])
    )
    pools["bridge_high_support"] = [p for _s, p in ranked_b[:top]]
    return pools


def draw(pools: dict[str, list[tuple[str, str]]], seed: int = SEED) -> tuple[list[Item], dict]:
    """Quota per source, scarcest pool first; a node appears in at most MAX_PAIRS_PER_NODE items; short sources hand their
    remainder to the others (deterministic order). Each pair serves the first source that drew it."""
    rng = random.Random(seed)
    order = sorted(SOURCES, key=lambda s: (len(pools[s]), s))
    chosen: dict[tuple[str, str], str] = {}
    used: Counter = Counter()
    got: Counter = Counter()

    def take(source: str, n: int) -> int:
        cands = [p for p in pools[source] if p not in chosen]
        rng.shuffle(cands)
        k = 0
        for p in cands:
            if k >= n:
                break
            if any(used[x] >= MAX_PAIRS_PER_NODE for x in p):
                continue
            chosen[p] = source
            for x in p:
                used[x] += 1
            k += 1
        got[source] += k
        return k

    for s in order:
        take(s, QUOTA[s])
    short = 160 - len(chosen)
    guard = 0
    while short > 0 and guard < 10:  # hand the shortfall to the other sources, deterministic order
        for s in order:
            if short <= 0:
                break
            short -= take(s, 1)
        guard += 1
    membership = defaultdict(list)
    for s in SOURCES:
        for p in pools[s]:
            membership[p].append(s)
    items = [
        Item(p, s, tuple(membership[p]))
        for p, s in sorted(chosen.items(), key=lambda kv: (kv[1], kv[0]))
    ]
    rep = {
        "pool_sizes": {s: len(pools[s]) for s in SOURCES},
        "quota": QUOTA,
        "drawn_by_source": {s: got[s] for s in SOURCES},
        "total": len(items),
        "shortfall": 160 - len(items),
    }
    return items, rep
