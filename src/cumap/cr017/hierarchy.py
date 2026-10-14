"""CR-017 Ancestor Hierarchy F1 (scorer only; no model call).

For one P&D-E2E section: gold `is_a` edges between gold concepts -> gold ancestor pairs (descendant, ancestor) by transitive closure; predicted `is_a` edges between predicted nodes ->
mapped to gold concepts through the frozen CR-012 mention-span alignment -> predicted ancestor pairs. Precision / recall / F1 over the two pair sets (CR-017 §6.5).

Frozen semantics (configs/cr017_eval.yaml): relation set {is_a}; per-section closure (concept ids are section-local); pairs are a SET (a split node cannot add duplicates); a wrong canonical concept is
a wrong pair (no lexical credit); a predicted node that maps to no single gold concept (unmatched or false merge) keeps a synthetic id, so every pair involving it is a false positive; a gold
concept with no predicted node loses all its gold pairs (false negatives); cycles are detected and reported, closure uses a visited set so it always terminates, pairs inside a cycle stay in the
prediction and are judged against gold, and self pairs (A, A) are dropped and counted. Gold is read through `UnitGold`; nothing is inferred from predictions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF, PredEdge, PredNode, UnitGold

HIERARCHY_RELATIONS = frozenset({"is_a"})


@dataclass
class Closure:
    pairs: set[tuple[str, str]] = field(default_factory=set)
    cycles: list[tuple[str, ...]] = field(default_factory=list)
    self_pairs_dropped: int = 0
    direct_edges: set[tuple[str, str]] = field(default_factory=set)


def ancestor_closure(edges: set[tuple[str, str]]) -> Closure:
    """Transitive closure of child -> parent edges. Deterministic; terminates on cycles (visited set per start node)."""
    out = Closure()
    children: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        if a == b:
            out.self_pairs_dropped += 1
            continue
        children[a].add(b)
        out.direct_edges.add((a, b))

    def walk(start: str, cur: str, seen: frozenset[str]) -> None:
        for parent in sorted(children.get(cur, ())):
            if parent == start:
                continue
            out.pairs.add((start, parent))
            if parent not in seen:
                walk(start, parent, seen | {parent})

    for start in sorted(children):
        walk(start, start, frozenset({start}))
    out.cycles = find_cycles(out.direct_edges)
    return out


def find_cycles(edges: set[tuple[str, str]]) -> list[tuple[str, ...]]:
    """Each cycle once, as the lexicographically smallest rotation (deterministic)."""
    graph: dict[str, list[str]] = defaultdict(list)
    for a, b in sorted(edges):
        graph[a].append(b)
    found: set[tuple[str, ...]] = set()

    def dfs(start: str, cur: str, path: list[str]) -> None:
        for nxt in graph.get(cur, ()):
            if nxt == start:
                k = min(range(len(path)), key=lambda i: path[i:] + path[:i])
                found.add(tuple(path[k:] + path[:k]))
            elif (
                nxt not in path and nxt > start
            ):  # only extend through nodes larger than the start: each cycle is found from its smallest node
                dfs(start, nxt, [*path, nxt])

    for s in sorted(graph):
        dfs(s, s, [s])
    return sorted(found)


def gold_pairs(gold: UnitGold, relations: frozenset[str] = HIERARCHY_RELATIONS) -> Closure:
    edges = {
        (r.src_concept, r.tgt_concept)
        for r in gold.relations
        if r.relation in relations and r.src_concept and r.tgt_concept
    }
    return ancestor_closure(edges)


def predicted_pairs(
    gold: UnitGold,
    nodes: list[PredNode],
    edges: list[PredEdge],
    relations: frozenset[str] = HIERARCHY_RELATIONS,
) -> tuple[Closure, dict]:
    al = S.align_nodes(nodes, gold.mentions)
    n2c = al["node_to_concept"]

    def ident(node_id: str) -> str:
        return n2c.get(node_id, f"pred:{node_id}")

    unmapped = {e.src for e in edges if e.relation in relations and e.src not in n2c} | {
        e.tgt for e in edges if e.relation in relations and e.tgt not in n2c
    }
    pred_edges = {(ident(e.src), ident(e.tgt)) for e in edges if e.relation in relations}
    return ancestor_closure(pred_edges), {
        "predicted_is_a_edges": sum(1 for e in edges if e.relation in relations),
        "nodes_in_hierarchy_without_a_gold_concept": len(unmapped),
    }


def score_hierarchy_unit(
    gold: UnitGold,
    nodes: list[PredNode],
    edges: list[PredEdge],
    relations: frozenset[str] = HIERARCHY_RELATIONS,
) -> dict:
    g = gold_pairs(gold, relations)
    p, info = predicted_pairs(gold, nodes, edges, relations)
    tp = len(g.pairs & p.pairs)
    prf = PRF(tp, len(p.pairs - g.pairs), len(g.pairs - p.pairs))
    present = {
        c for n in S.align_nodes(nodes, gold.mentions)["node_to_concept"].values() for c in [n]
    }
    direct = PRF(
        len(g.direct_edges & p.direct_edges),
        len(p.direct_edges - g.direct_edges),
        len(g.direct_edges - p.direct_edges),
    )
    gold_concepts_in_pairs = {x for pair in g.pairs for x in pair}
    return {
        "ancestor_hierarchy": prf,
        "gold_ancestor_pairs": len(g.pairs),
        "gold_direct_edges": len(g.direct_edges),
        "predicted_ancestor_pairs": len(p.pairs),
        "gold_pairs_with_an_endpoint_concept_absent_from_prediction": sum(
            1 for a, b in g.pairs if a not in present or b not in present
        ),
        "gold_concepts_in_hierarchy": len(gold_concepts_in_pairs),
        "direct_parent_diagnostic": direct,
        "predicted_cycles": [list(c) for c in p.cycles],
        "gold_cycles": [list(c) for c in g.cycles],
        "self_pairs_dropped": {"gold": g.self_pairs_dropped, "predicted": p.self_pairs_dropped},
        **info,
    }


def pool(units: dict[str, dict]) -> PRF:
    return PRF(
        sum(u["ancestor_hierarchy"].tp for u in units.values()),
        sum(u["ancestor_hierarchy"].fp for u in units.values()),
        sum(u["ancestor_hierarchy"].fn for u in units.values()),
    )
