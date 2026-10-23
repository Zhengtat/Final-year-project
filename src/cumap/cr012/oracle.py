"""CR-012 frozen oracle matrix (CR section 11, amended by Research D2). Each oracle injects information ONLY into the stage it
replaces, and E3 / E4 never expose a gold relation label (nor its direction: endpoint pairs are handed over unordered).

    E0    full workflow, no injection
    E1    gold mention spans + types only (concept extraction replaced); no identity, no relations
    E2    E1 + gold canonical identity clusters (P&D only; SciNLP has no identity gold -> NOT_SUPPORTED)
    E3    gold nodes (+ identity where supported) and every gold endpoint pair forced into relation classification, labels hidden
          (SciNLP: E3-M, mention endpoints)
    E4    correct endpoint pairs given directly; the classifier predicts relation, direction and qualifiers on its own
          (SciNLP: E4-M)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cumap.cr012.types import Span, UnitGold

NOT_SUPPORTED = "NOT_SUPPORTED_NO_IDENTITY_GOLD"
FORBIDDEN_VISIBLE_KEYS = {
    "relation",
    "relations",
    "label",
    "labels",
    "direction",
    "qualifiers",
    "relation_type",
    "rel",
}


class OracleNotSupported(RuntimeError):
    pass


@dataclass(frozen=True)
class InjectedMentions:
    unit: str
    mentions: tuple[tuple[Span, str], ...]  # (span, type)
    clusters: (
        tuple[tuple[str, tuple[Span, ...]], ...] | None
    )  # (cluster id, member spans) - E2 only


@dataclass(frozen=True)
class InjectedPairs:
    unit: str
    pairs: tuple[
        tuple[object, object], ...
    ]  # unordered endpoint pairs (sorted), never a relation label
    level: str  # "concept" (P&D) or "mention" (SciNLP)


def oracle_e1(gold: UnitGold) -> InjectedMentions:
    """Gold concept mentions and types only: no concept id, no cluster, no relation."""
    return InjectedMentions(gold.unit, tuple(sorted((m.span, m.type) for m in gold.mentions)), None)


def oracle_e2(gold: UnitGold, identity_supported: bool) -> InjectedMentions:
    if not identity_supported:
        raise OracleNotSupported(NOT_SUPPORTED)
    groups: dict[str, list[Span]] = {}
    for m in gold.mentions:
        if m.concept_id:
            groups.setdefault(m.concept_id, []).append(m.span)
    return InjectedMentions(
        gold.unit,
        tuple(sorted((m.span, m.type) for m in gold.mentions)),
        tuple((cid, tuple(sorted(spans))) for cid, spans in sorted(groups.items())),
    )


def _endpoint_pairs(gold: UnitGold, level: str) -> tuple[tuple[object, object], ...]:
    pairs = set()
    for r in gold.relations:
        a, b = (r.src_concept, r.tgt_concept) if level == "concept" else (r.src_span, r.tgt_span)
        if a is None or b is None:
            continue
        pairs.add(tuple(sorted((a, b))))  # sorting removes the direction the relation would reveal
    return tuple(sorted(pairs))


def oracle_e3(gold: UnitGold, level: str) -> InjectedPairs:
    """Force every gold endpoint pair into relation classification WITHOUT its relation label or direction."""
    return InjectedPairs(gold.unit, _endpoint_pairs(gold, level), level)


def oracle_e4(gold: UnitGold, level: str) -> InjectedPairs:
    """Correct endpoint pairs only; the gold relation stays hidden until scoring."""
    return InjectedPairs(gold.unit, _endpoint_pairs(gold, level), level)


def visible_payload(obj) -> dict:
    """What a pipeline stage can see. Used by the leakage guard."""
    return {k: v for k, v in obj.__dict__.items()}


def assert_no_label_leak(obj, gold: UnitGold) -> None:
    """Leakage guard: an injected object may not carry relation fields nor any gold relation label string."""
    payload = visible_payload(obj)
    bad_keys = FORBIDDEN_VISIBLE_KEYS & set(payload)
    assert not bad_keys, f"oracle exposes forbidden fields {bad_keys}"
    flat = repr(payload)
    for r in gold.relations:
        assert r.relation not in flat, (
            f"gold relation label {r.relation!r} is visible to the pipeline"
        )


def leakage_scan(
    texts: dict[str, str], surfaces: list[str], min_tokens: int = 2
) -> dict[str, list[str]]:
    """Held-out gold surfaces (multi-token, case-insensitive) found inside development artefacts (prompts, few-shot banks, lexicon,
    cues). Used to evidence that no held-out label entered a prompt or rule; hits are reported, not silently ignored."""
    hits: dict[str, list[str]] = {}
    low = {name: t.lower() for name, t in texts.items()}
    for s in {x.lower().strip() for x in surfaces if len(x.split()) >= min_tokens}:
        pat = re.compile(
            rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])"
        )  # whole-token match, not a substring
        for name, t in low.items():
            if pat.search(t):
                hits.setdefault(name, []).append(s)
    return hits
