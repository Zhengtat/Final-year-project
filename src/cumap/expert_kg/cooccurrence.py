"""CR-064: candidate pairs with an abbreviation-aware sentence splitter and/or one candidate per co-occurrence sentence (profile keys
`sentence_split: plain|abbrev`, `cooccurrence: first|all`, `declined_pass: off|<relation_choice version>`).

`first` + `plain` is today's rule (one earliest sentence per concept pair, plain splitter), so every earlier run is unchanged. Pair budget is
"all" (CR-056), so the selection is the whole pool. Extras (`all`) are the other sentences a pair shares, in any section; one candidate per
(pair, sentence text), the earliest first. No gold and no model call here.
"""

from __future__ import annotations

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.pair_selection import dedupe
from cumap.expert_kg.relations import (
    CandidatePair,
    enumerate_candidates,
    split_sentences,
    split_sentences_abbrev,
)
from cumap.schemas.relations import RelationRegistry

SPLITS = {"plain": split_sentences, "abbrev": split_sentences_abbrev}
COOCCURRENCE = ("first", "all")


def profile_value(key: str, default: str) -> str:
    from cumap.cr012.schema_profile import active_profile

    p = active_profile()
    return str((p.raw.get(key) if p else None) or default)


def resolve(split: str | None = None, cooccurrence: str | None = None) -> tuple[str, str]:
    split = split or profile_value("sentence_split", "plain")
    cooc = cooccurrence or profile_value("cooccurrence", "first")
    if split not in SPLITS or cooc not in COOCCURRENCE:
        raise ValueError(
            f"sentence_split {split!r} / cooccurrence {cooc!r} not in {tuple(SPLITS)} / {COOCCURRENCE}"
        )
    return split, cooc


def _key(p: CandidatePair) -> frozenset[str]:
    return frozenset((p.concept_x_id, p.concept_y_id))


def build_pairs(
    sections: list[tuple[str, str]],
    concepts: list[RegisteredConcept],
    registry: RelationRegistry,
    *,
    split: str,
    cooccurrence: str,
) -> list[CandidatePair]:
    """`sections`: (section_id, text) in book order. Primary pairs first (ranked), then the extra sentences."""
    every = cooccurrence == "all"
    rows = {
        sid: enumerate_candidates(sid, text, concepts, registry, splitter=SPLITS[split], all_sentences=every)
        for sid, text in sections
    }  # fmt: skip
    primary = dedupe({sid: [p for p in ps if "~s" not in p.pair_id] for sid, ps in rows.items()})
    if not every:
        return primary
    seen = {(_key(p), p.sentence) for p in primary}
    out = list(primary)
    for sid, _t in sections:
        for p in rows[sid]:
            if (_key(p), p.sentence) not in seen:
                seen.add((_key(p), p.sentence))
                out.append(p)
    return out
