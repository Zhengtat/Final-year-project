"""CR-011 §8 pair features. Everything is computed from the pre-sleep snapshot (or, for a historical label whose strings are
not nodes, from the strings alone with explicit missing-indicators). The CR-008 lexicon `different` veto and the type veto are
NOT model features: they run before any scorer. `concept_score` is not stored on checkpoint nodes, so it is absent (reported)."""

from __future__ import annotations

import difflib
import math
from dataclasses import dataclass

import numpy as np

from cumap.expert_kg.alias_rules import r1_key
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.sleep.candidates import evidence_text, tokens
from cumap.sleep.snapshot import Node
from cumap.sleep.typecompat import TypeMap

UNKNOWN_TYPE = "?"
FEATURES = [
    "name_cos",
    "def_cos",
    "def_missing",
    "ev_cos",
    "ev_missing",
    "char_ratio",
    "token_jaccard",
    "r1_equal",
    "head_equal",
    "containment",
    "r2_acronym",
    "r3_strong",
    "r3_weak",
    "type_unknown",
    "type_same",
    "type_compatible",
    "either_generic",
    "neighbour_jaccard",
    "signature_jaccard",
    "graph_missing",
    "cross_chapter",
    "chapter_gap",
    "mentions_min_log",
    "mentions_max_log",
    "both_defined",
    "one_token_any",
    "one_token_both",
    "same_surface",
    "erst_linked",
]
GROUPS = {
    "lexical": ["char_ratio", "token_jaccard", "r1_equal", "head_equal", "containment"],
    "embedding": ["name_cos", "def_cos", "def_missing", "ev_cos", "ev_missing"],
    "alias": ["r2_acronym", "r3_strong", "r3_weak"],
    "type": ["type_unknown", "type_same", "type_compatible", "either_generic"],
    "graph": ["neighbour_jaccard", "signature_jaccard", "graph_missing"],
    "chapter_recurrence": [
        "cross_chapter",
        "chapter_gap",
        "mentions_min_log",
        "mentions_max_log",
        "both_defined",
    ],
    "one_token": ["one_token_any", "one_token_both", "same_surface"],
    "erst_context": ["erst_linked"],
}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


@dataclass
class Vecs:
    """Embeddings for one node: name, definition (or None), evidence."""

    name: np.ndarray
    definition: np.ndarray | None
    evidence: np.ndarray | None


def node_vecs(node: Node, lookup) -> Vecs:
    return lookup(node)


def pair_features(
    a: Node,
    b: Node,
    va: Vecs,
    vb: Vecs,
    ctx: AliasContext,
    types: TypeMap,
    erst_linked: set[frozenset[str]],
) -> dict[str, float]:
    cfg = ctx.cfg
    ta, tb = tokens(a.name), tokens(b.name)
    la, lb = a.name.split(), b.name.split()
    known = a.type != UNKNOWN_TYPE and b.type != UNKNOWN_TYPE
    rule = {"R2": 0.0, "R3-strong": 0.0}
    for x in a.forms():
        for y in b.forms():
            hit = ctx.pair_rule(x, y, None, a_type=a.type, b_type=b.type, type_aware=False)
            if hit and hit.rule_id in rule:
                rule[hit.rule_id] = 1.0
    ka, kb = r1_key(a.name, cfg), r1_key(b.name, cfg)
    weak = float(bool(ctx.weak_hints(a.name, b.name)))
    graph_missing = float(not a.neighbours or not b.neighbours)
    ca, cb = a.chapter, b.chapter
    f = {
        "name_cos": float(va.name @ vb.name),
        "def_cos": float(va.definition @ vb.definition)
        if va.definition is not None and vb.definition is not None
        else 0.0,
        "def_missing": float(va.definition is None or vb.definition is None),
        "ev_cos": float(va.evidence @ vb.evidence)
        if va.evidence is not None and vb.evidence is not None
        else 0.0,
        "ev_missing": float(va.evidence is None or vb.evidence is None),
        "char_ratio": difflib.SequenceMatcher(None, a.name.casefold(), b.name.casefold()).ratio(),
        "token_jaccard": jaccard(set(ta), set(tb)),
        "r1_equal": float(bool(ka) and ka == kb),
        "head_equal": float(bool(la) and bool(lb) and tokens(la[-1]) == tokens(lb[-1])),
        "containment": float(bool(ta) and bool(tb) and (ta < tb or tb < ta)),
        "r2_acronym": rule["R2"],
        "r3_strong": rule["R3-strong"],
        "r3_weak": weak,
        "type_unknown": float(not known),
        "type_same": float(known and a.type == b.type),
        "type_compatible": float(known and types.compatible(a.type, b.type)),
        "either_generic": float(types.generic in (a.type, b.type)),
        "neighbour_jaccard": jaccard(a.neighbours, b.neighbours),
        "signature_jaccard": jaccard(a.relations, b.relations),
        "graph_missing": graph_missing,
        "cross_chapter": float(ca != cb and ca > 0 and cb > 0),
        "chapter_gap": float(abs(ca - cb)) if ca > 0 and cb > 0 else 0.0,
        "mentions_min_log": math.log1p(min(len(a.mentions), len(b.mentions))),
        "mentions_max_log": math.log1p(max(len(a.mentions), len(b.mentions))),
        "both_defined": float(bool(a.definition) and bool(b.definition)),
        "one_token_any": float(len(la) == 1 or len(lb) == 1),
        "one_token_both": float(len(la) == 1 and len(lb) == 1),
        "same_surface": float(
            a.name.casefold() == b.name.casefold()
            or a.name.casefold() in {x.casefold() for x in b.aliases}
            or b.name.casefold() in {x.casefold() for x in a.aliases}
        ),
        "erst_linked": float(frozenset((a.id, b.id)) in erst_linked),
    }
    assert set(f) == set(FEATURES)
    return f


def matrix(rows: list[dict[str, float]], cols: list[str] | None = None) -> np.ndarray:
    cols = cols or FEATURES
    return np.array([[r[c] for c in cols] for r in rows], dtype=float)


def evidence_for(node: Node) -> str:
    return evidence_text(node)
