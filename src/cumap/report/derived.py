"""Derived layers for the graph view (CR-007 report refresh, $0, from saved edges only).

- inferred: one-hop transitive closure over relations the registry marks `transitive: true`
  (A r B, B r C -> A r C). Never evidence-backed; shown dashed and only when toggled on.
- conflicts: edge pairs between the same two concepts whose relations the registry says conflict.
"""

from __future__ import annotations

from collections import defaultdict

from cumap.report.graph import GEdge
from cumap.schemas.relations import RelationRegistry


def inferred_edges(edges: list[GEdge], registry: RelationRegistry) -> list[dict]:
    transitive = {r.name for r in registry.all_relations() if r.transitive is True}
    direct = {(e.relation, e.source, e.target) for e in edges}
    by_rel: dict[str, list[GEdge]] = defaultdict(list)
    for e in edges:
        if e.relation in transitive and not e.negated:
            by_rel[e.relation].append(e)
    out, seen = [], set()
    for rel, es in sorted(by_rel.items()):
        starts: dict[str, list[GEdge]] = defaultdict(list)
        for e in es:
            starts[e.source].append(e)
        for first in es:
            for second in starts.get(first.target, []):
                key = (rel, first.source, second.target)
                if first.source == second.target or key in direct or key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "relation": rel,
                        "source": first.source,
                        "target": second.target,
                        "via": [first.id, second.id],
                    }
                )
    return out


def conflicting_edge_ids(edges: list[GEdge], registry: RelationRegistry) -> set[str]:
    by_pair: dict[frozenset, list[GEdge]] = defaultdict(list)
    for e in edges:
        by_pair[frozenset((e.source, e.target))].append(e)
    flagged: set[str] = set()
    for es in by_pair.values():
        for i, a in enumerate(es):
            for b in es[i + 1 :]:
                if registry.conflicts(a.relation, b.relation):
                    flagged |= {a.id, b.id}
    return flagged
