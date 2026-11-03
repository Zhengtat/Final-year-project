"""CR-022 Part A scorers for SciNLP ($0, no model call; frozen CR-012 / CR-017 / CR-019 code reused unchanged, only its inputs are filtered).

A1 HIER-DIRECT      strict mention-level edge P/R/F1 restricted to a hierarchy label set (the frozen strict scorer; no identity is inferred).
A2 HIER-ANC-SURF    ancestor hierarchy P/R/F1 over SURFACE pseudo-nodes (one per distinct case-folded, whitespace-normalised surface per document).
                    It infers identity from strings, so it is a labelled variant, never a headline (CR-012 ruling D2).
A3 REL-MACRO-SCINLP relation macro F1 over the SciNLP labels (`cr017.headline.macro_from_rows`), on gold relations whose two endpoint spans are
                    both predicted mentions; the prediction is the relation of the projected edge at that unordered endpoint pair.

Unplaced predicted edges (rule 35): in every variant except FROZEN each one counts as one false positive in the label set it carries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.scinlp_oracle import surface_key
from cumap.cr012.types import PRF, Span, UnitGold
from cumap.cr017 import headline as HL
from cumap.cr017.hierarchy import ancestor_closure
from cumap.cr019 import variants as V

HIER_SETS: dict[str, frozenset[str]] = {
    "H2 {subclassOf, subtaskOf}": frozenset({"subclassOf", "subtaskOf"}),
    "H1 {subclassOf}": frozenset({"subclassOf"}),
}
VARIANT_NOTE = {
    "FROZEN": "frozen CR-012 grounding; unplaced edges excluded (as in the frozen number)",
    "FROZEN-UNPLACED-FP": "frozen grounding; each unplaced edge counts as a false positive",
    "IDX-P1": "CR-019 occurrence index, own-evidence-sentence placement (primary); unplaced = FP",
    "IDXR1-P1": "as IDX-P1 with CR-020 R1-key matching (the mode the CR-021 rebuild ran under); unplaced = FP",
}


@dataclass
class Placed:
    """Predicted relations of one run on one document under one variant."""

    rels: list[
        tuple[Span, Span, str, str, str]
    ]  # (src_span, tgt_span, relation, src_type, tgt_type)
    mentions: list[tuple[Span, str]]
    unplaced_by_label: Counter


def _projector(doc, variant: str):
    if variant.startswith("FROZEN") or variant.endswith("-P1"):
        return S.project_edges_to_mentions
    return lambda n, e: V.project_p3(doc, n, e)


def place(doc, cp: dict, variant: str) -> Placed:
    """Same prediction and projection as `cr019.variants.sc_score`, plus the unplaced edges counted per relation label."""
    if variant.startswith("FROZEN"):
        pred = SR.predict(doc, cp)
    else:
        pred = V.sc_predict_indexed(doc, cp, "r1key" if variant.startswith("IDXR1") else "token")
    proj = _projector(doc, variant)
    rels, _ = proj(pred["nodes"], pred["edges"])
    placed_labels: Counter = Counter()
    for e in pred["edges"]:
        if proj(pred["nodes"], [e])[0]:
            placed_labels[e.relation] += 1
    total = Counter(
        r["relation"]
        for r in V._edge_rows(cp)
        if (r.get("qualifiers") or {}).get("polarity") != "negated"
    )
    unplaced = total - placed_labels
    if sum(placed_labels.values()) + sum(unplaced.values()) != sum(
        total.values()
    ):  # pragma: no cover
        raise AssertionError("placed + unplaced does not add up to the predicted edges")
    return Placed(rels, S.project_nodes_to_mentions(pred["nodes"]), unplaced)


# ---------------------------------------------------------------- A1
def filter_gold(gold: UnitGold, labels: frozenset[str] | None) -> UnitGold:
    if labels is None:
        return gold
    return UnitGold(
        unit=gold.unit,
        mentions=gold.mentions,
        relations=[r for r in gold.relations if r.relation in labels],
    )


def direct_relation_prf(
    gold: UnitGold, p: Placed, sym: set[str], variant: str, labels: frozenset[str] | None
) -> PRF:
    """Strict edge PRF on `labels` (all labels when None). With labels=None and the matching variant it equals `cr019.variants.sc_score`'s `rel`."""
    keep = (lambda r: True) if labels is None else (lambda r: r[2] in labels)
    res = S.score_scinlp_unit(
        filter_gold(gold, labels), p.mentions, [r for r in p.rels if keep(r)], sym
    )["rel"]
    if variant == "FROZEN":
        return res
    extra = sum(n for lab, n in p.unplaced_by_label.items() if labels is None or lab in labels)
    return PRF(res.tp, res.fp + extra, res.fn)


def hierarchy_direction_prf(gold: UnitGold, p: Placed, variant: str, labels: frozenset[str]) -> PRF:
    """A1-DIR (CR-064, owner): hierarchy F1 over the hierarchy relations only, scored on the directed (child, parent) span pair.
    The labels in `labels` are one class: a predicted subtaskOf on a gold subclassOf pair with the same direction is a hit; the
    reversed direction is a miss (one FP, one FN). Gold relations outside `labels` are not scored; unplaced predicted hierarchy
    edges are FPs (rule 35) except under FROZEN."""
    g = {(r.src_span, r.tgt_span) for r in gold.relations if r.relation in labels}
    pr = {(r[0], r[1]) for r in p.rels if r[2] in labels}
    extra = (
        0
        if variant == "FROZEN"
        else sum(n for lab, n in p.unplaced_by_label.items() if lab in labels)
    )
    return PRF(len(g & pr), len(pr - g) + extra, len(g - pr))


# ---------------------------------------------------------------- A2
def _surf(doc, sp: Span) -> str:
    a, b = doc.span_to_chars(sp)
    return surface_key(doc.text[a:b])


def surface_hierarchy(doc, gold: UnitGold, p: Placed, variant: str, labels: frozenset[str]) -> dict:
    """Ancestor closure on surface pseudo-nodes for gold and prediction (CR-017 cycle policy: detect, report, closure with a visited set,
    cycle pairs stay in the prediction, self pairs dropped and counted)."""
    surfaces = {_surf(doc, m.span) for m in gold.mentions}
    g_edges, g_same = set(), 0
    for r in gold.relations:
        if r.relation not in labels:
            continue
        a, b = _surf(doc, r.src_span), _surf(doc, r.tgt_span)
        if a == b:
            g_same += 1
        g_edges.add((a, b))
    p_edges = {(_surf(doc, r[0]), _surf(doc, r[1])) for r in p.rels if r[2] in labels}
    gc, pc = ancestor_closure(g_edges), ancestor_closure(p_edges)
    gp, pp = set(gc.pairs), set(pc.pairs)
    n_unplaced = 0
    if (
        variant != "FROZEN"
    ):  # rule 35: an edge that cannot be placed is a false positive (an unmatchable synthetic pair)
        n_unplaced = sum(n for lab, n in p.unplaced_by_label.items() if lab in labels)
        pp |= {(f"unplaced:{i}", f"unplaced:{i}:parent") for i in range(n_unplaced)}
    prf = PRF(len(gp & pp), len(pp - gp), len(gp - pp))
    return {
        "prf": prf,
        "gold_direct_edges": len(gc.direct_edges),
        "gold_closure_pairs": len(gp),
        "gold_pairs_added_by_closure": len(gp) - len(gc.direct_edges),
        "pred_direct_edges": len(pc.direct_edges),
        "pred_closure_pairs": len(set(pc.pairs)),
        "gold_mentions": len(gold.mentions),
        "gold_surface_nodes": len(surfaces),
        "gold_surface_collisions": len(gold.mentions) - len(surfaces),
        "gold_cycles": [list(c) for c in gc.cycles],
        "pred_cycles": [list(c) for c in pc.cycles],
        "gold_self_relations": g_same,
        "unplaced_counted_as_fp": n_unplaced,
    }


# ---------------------------------------------------------------- A3
def relation_rows(doc, gold: UnitGold, p: Placed, sym: set[str]) -> list[dict]:
    """One row per distinct gold relation whose two endpoint spans are predicted mentions."""
    placed_spans = {s for s, _t in p.mentions}
    by_pair: dict[frozenset, list[tuple[Span, Span, str]]] = {}
    for s, t, rel, _st, _tt in p.rels:
        by_pair.setdefault(frozenset((s, t)), []).append((s, t, rel))
    seen, rows = set(), []
    for r in gold.relations:
        k = S._rel_key(r.src_span, r.tgt_span, r.relation, sym)
        if k in seen:
            continue
        seen.add(k)
        if r.src_span not in placed_spans or r.tgt_span not in placed_spans:
            continue
        hits = by_pair.get(frozenset((r.src_span, r.tgt_span)), [])
        exact = [h for h in hits if h[2] == r.relation]
        pick = exact[0] if exact else (hits[0] if hits else None)
        if pick is None:
            rows.append(
                {
                    "gold": r.relation,
                    "pred": HL.NO_PREDICTION,
                    "outcome": "no_edge_at_pair",
                    "direction_ok": None,
                }
            )
            continue
        ok = None
        if pick[2] == r.relation:
            ok = r.relation in sym or (pick[0], pick[1]) == (r.src_span, r.tgt_span)
        rows.append({"gold": r.relation, "pred": pick[2], "outcome": "edge", "direction_ok": ok})
    return rows


def pooled_macro(rows: list[dict]) -> dict:
    return HL.macro_from_rows(rows)
