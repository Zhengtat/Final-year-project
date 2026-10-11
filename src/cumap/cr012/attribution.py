"""CR-012 earliest-failure attribution (CR section 10). Each gold edge that the final graph misses gets exactly ONE primary earliest
causal failure. Order (earlier stages win; downstream consequences are never double counted):

    N0 endpoint concept not extracted          N1 endpoint extracted with a wrong / incomplete span
    C1 endpoint node is a false merge          C0 endpoint concept split into several nodes and that split lost the pair
    P0 both nodes exist but no pair proposed   R0 pair proposed, classifier chose NO_RELATION
    R1 wrong relation                          R2 wrong direction
    R3 qualifier / endpoint-type failure       E0 evidence / provenance invalid
    S0 / S1 sleep damage / non-repair: NOT_APPLICABLE (CR-011 adopted no transformation)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from cumap.cr012.scoring import align_nodes
from cumap.cr012.types import PredEdge, PredNode, Span, UnitGold

CODES = ("N0", "N1", "C0", "C1", "P0", "R0", "R1", "R2", "R3", "E0")
NOT_APPLICABLE = ("S0", "S1")


@dataclass(frozen=True)
class EdgeTrace:
    """Everything needed to attribute one gold edge."""

    endpoints: tuple[str, str]
    span_status: tuple[str, str]  # per endpoint: exact | partial | absent
    false_merge: tuple[bool, bool]
    split: tuple[bool, bool]
    pairs_proposed: tuple[bool, ...]  # for every node-pair combination of the endpoints' nodes
    no_relation: tuple[
        bool, ...
    ]  # classifier said NO_RELATION for the combination (only meaningful where proposed)
    predicted_relations: tuple[str, ...]  # relations predicted over the combinations
    gold_relation: str
    symmetric: bool
    reversed_only: bool  # the gold relation was predicted only in the opposite direction
    types_ok: bool
    qualifiers_ok: bool
    evidence_valid: bool


def attribute(t: EdgeTrace) -> str | None:
    """Primary earliest failure code, or None when the gold edge is in the final graph."""
    for st in t.span_status:
        if st == "absent":
            return "N0"
    if "partial" in t.span_status:
        return "N1"
    if any(t.false_merge):
        return "C1"
    found = t.gold_relation in t.predicted_relations and not t.reversed_only
    if any(t.split) and not found and not all(t.pairs_proposed):
        return "C0"
    if not any(t.pairs_proposed):
        return "P0"
    if (
        all(nr for p, nr in zip(t.pairs_proposed, t.no_relation, strict=True) if p)
        and not t.predicted_relations
    ):
        return "R0"
    if t.gold_relation not in t.predicted_relations:
        return "R1"
    if t.reversed_only and not t.symmetric:
        return "R2"
    if not t.types_ok or not t.qualifiers_ok:
        return "R3"
    if not t.evidence_valid:
        return "E0"
    return None


def build_traces(
    gold: UnitGold,
    nodes: list[PredNode],
    edges: list[PredEdge],
    proposed_pairs: set[frozenset[str]],
    no_relation_pairs: set[frozenset[str]],
    symmetric: set[str],
    evidence_valid: dict[tuple, bool] | None = None,
) -> list[EdgeTrace]:
    al = align_nodes(nodes, gold.mentions)
    c_nodes = al["concept_to_nodes"]
    n2c = al["node_to_concept"]
    gold_spans_by_c: dict[str, list[Span]] = {}
    for m in gold.mentions:
        if m.concept_id:
            gold_spans_by_c.setdefault(m.concept_id, []).append(m.span)
    pred_spans = [s for n in nodes for s in n.mentions]
    fm_nodes = set(al["false_merge_nodes"])
    node_by = {n.node_id: n for n in nodes}
    c_type = {c.concept_id: c.type for c in gold.concepts}
    pred_by_pair: dict[frozenset[str], list[PredEdge]] = {}
    for e in edges:
        pred_by_pair.setdefault(frozenset((e.src, e.tgt)), []).append(e)

    def status(cid: str) -> str:
        spans = gold_spans_by_c.get(cid, [])
        if any(s in pred_spans for s in spans):
            return "exact"
        overlap = any(a[0] < s[1] and s[0] < a[1] for s in spans for a in pred_spans)
        return "partial" if overlap else "absent"

    out = []
    for r in gold.relations:
        if not (r.src_concept and r.tgt_concept):
            continue
        s_nodes, t_nodes = c_nodes.get(r.src_concept, []), c_nodes.get(r.tgt_concept, [])
        sts = (status(r.src_concept), status(r.tgt_concept))
        if not s_nodes:
            sts = (sts[0] if sts[0] != "exact" else "absent", sts[1])
        # a node that exists only as a false merge hides the concept from the 1:1 map: detect through span hits
        fm = tuple(
            any(
                n.node_id in fm_nodes
                and any(sp in gold_spans_by_c.get(cid, []) for sp in n.mentions)
                for n in nodes
            )
            for cid in (r.src_concept, r.tgt_concept)
        )
        combos = [(a, b) for a in s_nodes for b in t_nodes] or []
        proposed = tuple(frozenset((a, b)) in proposed_pairs for a, b in combos)
        norel = tuple(frozenset((a, b)) in no_relation_pairs for a, b in combos)
        preds, rev_only, found_dir = [], False, False
        for a, b in combos:
            for e in pred_by_pair.get(frozenset((a, b)), []):
                preds.append(e.relation)
                if e.relation == r.relation and (
                    n2c.get(e.src) == r.src_concept or r.relation in symmetric
                ):
                    found_dir = True
        rev_only = r.relation in preds and not found_dir
        types_ok = all(
            node_by[n].type == c_type.get(cid)
            for cid, ns in ((r.src_concept, s_nodes), (r.tgt_concept, t_nodes))
            for n in ns[:1]
        )
        key = (r.src_concept, r.tgt_concept, r.relation)
        out.append(
            EdgeTrace(
                (r.src_concept, r.tgt_concept), sts, fm, (len(s_nodes) > 1, len(t_nodes) > 1), proposed, norel, tuple(preds),
                r.relation, r.relation in symmetric, rev_only, types_ok, True, (evidence_valid or {}).get(key, True),
            )
        )  # fmt: skip
    return out


def distribution(codes: list[str | None]) -> dict:
    c = Counter(x for x in codes if x)
    n_miss = sum(c.values())
    return {
        "misses": n_miss,
        "recovered": sum(1 for x in codes if x is None),
        "by_code": {k: c.get(k, 0) for k in CODES},
        "not_applicable": list(NOT_APPLICABLE),
    }
