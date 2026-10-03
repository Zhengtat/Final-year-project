"""M5 task 7: structural checks over the accumulated graph -- domain/range type
errors and cycles among transitive relations. Evidence-substring checks already
happen per-item at extraction time (concepts.py rejects bad concept quotes,
relations.py rejects bad relation/qualifier quotes); this module is the final
structural pass over the *accepted* edge set, reusing RelationRegistry's own
check_types/find_cycles (schemas/relations.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cumap.expert_kg.relations import RelationEdgeCandidate
from cumap.schemas.relations import EdgeRef, RelationRegistry


@dataclass
class StructuralCheckResult:
    domain_range_errors: list[str] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)


def to_edge_ref(edge: RelationEdgeCandidate) -> EdgeRef:
    if edge.direction == "reversed":
        source, target = edge.pair.concept_y_id, edge.pair.concept_x_id
    else:
        source, target = edge.pair.concept_x_id, edge.pair.concept_y_id
    return EdgeRef(source_id=source, relation=edge.relation, target_id=target)


def check_structure(
    edges: list[RelationEdgeCandidate],
    concept_types: dict[str, str],
    registry: RelationRegistry,
) -> StructuralCheckResult:
    edge_refs = [to_edge_ref(e) for e in edges]

    domain_range_errors: list[str] = []
    for ref in edge_refs:
        domain_range_errors.extend(registry.check_types(ref, concept_types))

    cycles: list[list[str]] = []
    transitive_relations = {r.name for r in registry.all_relations() if r.transitive}
    for relation in transitive_relations:
        cycles.extend(registry.find_cycles(edge_refs, relation))

    return StructuralCheckResult(domain_range_errors=domain_range_errors, cycles=cycles)


RETIRED_RELATIONS = {
    "equivalent_to": "equivalence is a node property (aliases), never an edge (CR-008, registry v1.3)"
}


def retired_relation_errors(relations: list[str]) -> list[str]:
    """CR-008 §3.5: an edge with a retired relation is invalid in every layer."""
    return [f"{r!r} is retired: {RETIRED_RELATIONS[r]}" for r in relations if r in RETIRED_RELATIONS]
