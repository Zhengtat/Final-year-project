"""Relation registry: loads configs/relations_v0.yaml and implements the diagnostic
logic that reads it (normalisation, reversal/conflict/compatibility checks, domain/range
type checks, cycle detection). See ARCHITECTURE.md §4a.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, NamedTuple

import yaml
from pydantic import BaseModel, ConfigDict


class EdgeRef(NamedTuple):
    """The minimal (source, relation, target) triple the registry operates on.

    ExpertEdge and StudentEdge (schemas/edges.py, schemas/student.py) carry this same
    triple as their core fields; registry functions take this narrower type so they
    don't need to import those richer, higher-level schemas.
    """

    source_id: str
    relation: str
    target_id: str


class RelationType(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    layer: str
    definition: str
    examples: list[str]
    domain_types: list[str]
    range_types: list[str]
    directional: bool
    symmetric: bool
    transitive: bool
    inverse_of: str | None
    conflicts_with: list[str]
    compatible_with: dict[str, Literal["full", "partial"]]


class RelationRegistry:
    def __init__(self, relations: list[RelationType], node_types: list[str]):
        self._by_name: dict[str, RelationType] = {r.name: r for r in relations}
        self.node_types = node_types
        self._inverse_to_forward: dict[str, str] = {
            r.inverse_of: r.name for r in relations if r.inverse_of
        }

    @classmethod
    def from_yaml(cls, path: Path) -> RelationRegistry:
        raw = yaml.safe_load(path.read_text())
        relations = [RelationType(**r) for r in raw["relations"]]
        return cls(relations, raw["node_types"])

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def get(self, name: str) -> RelationType:
        forward_name, _ = self._to_forward_name(name)
        try:
            return self._by_name[forward_name]
        except KeyError:
            raise KeyError(f"Unknown relation {name!r} (not a registry name or inverse_of)") from None

    def _to_forward_name(self, name: str) -> tuple[str, bool]:
        """Returns (forward_relation_name, was_inverse)."""
        if name in self._by_name:
            return name, False
        if name in self._inverse_to_forward:
            return self._inverse_to_forward[name], True
        raise KeyError(f"Unknown relation {name!r}")

    def normalise(self, edge: EdgeRef) -> EdgeRef:
        """Canonical form: an inverse-named edge is rewritten to its forward relation
        with endpoints swapped; a symmetric relation's endpoints are sorted so that
        "A rel B" and "B rel A" normalise to the same edge.
        """
        forward_name, was_inverse = self._to_forward_name(edge.relation)
        source, target = edge.source_id, edge.target_id
        if was_inverse:
            source, target = target, source

        rel = self._by_name[forward_name]
        if rel.symmetric and source > target:
            source, target = target, source

        return EdgeRef(source_id=source, relation=forward_name, target_id=target)

    def is_reversal(self, a: EdgeRef, b: EdgeRef) -> bool:
        """True iff `a` and `b` are the same *directional* relation with swapped endpoints.

        Symmetric relations are never a reversal (there's nothing to reverse): normalising
        both edges puts a symmetric relation's endpoints in the same canonical order, so a
        same-relation, swapped-endpoint pair collapses to equal, not "reversed".
        """
        na, nb = self.normalise(a), self.normalise(b)
        if na.relation != nb.relation:
            return False
        if na == nb:
            return False
        rel = self._by_name[na.relation]
        if not rel.directional:
            return False
        return na.source_id == nb.target_id and na.target_id == nb.source_id

    def conflicts(self, relation_a: str, relation_b: str) -> bool:
        a, _ = self._to_forward_name(relation_a)
        b, _ = self._to_forward_name(relation_b)
        return b in self._by_name[a].conflicts_with or a in self._by_name[b].conflicts_with

    def compatible(self, relation_a: str, relation_b: str) -> Literal["full", "partial"] | None:
        a, _ = self._to_forward_name(relation_a)
        b, _ = self._to_forward_name(relation_b)
        if a == b:
            return "full"
        return self._by_name[a].compatible_with.get(b) or self._by_name[b].compatible_with.get(a)

    def check_types(self, edge: EdgeRef, concept_types: dict[str, str]) -> list[str]:
        """Domain/range violations, given a concept_id -> node_type lookup. "Any" matches
        every type. Concepts missing from `concept_types` are not flagged (unknown, not wrong).
        """
        rel = self.get(edge.relation)
        errors = []
        source_type = concept_types.get(edge.source_id)
        target_type = concept_types.get(edge.target_id)
        if source_type is not None and "Any" not in rel.domain_types and source_type not in rel.domain_types:
            errors.append(
                f"{edge.source_id} has type {source_type!r}, not in domain_types {rel.domain_types} of {rel.name!r}"
            )
        if target_type is not None and "Any" not in rel.range_types and target_type not in rel.range_types:
            errors.append(
                f"{edge.target_id} has type {target_type!r}, not in range_types {rel.range_types} of {rel.name!r}"
            )
        return errors

    def find_cycles(self, edges: list[EdgeRef], relation: str) -> list[list[str]]:
        """Detects cycles among edges of a single (transitive) relation, e.g. is_a."""
        forward_name, _ = self._to_forward_name(relation)
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            if self._to_forward_name(edge.relation)[0] != forward_name:
                continue
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)

        cycles: list[list[str]] = []
        visited: set[str] = set()

        def dfs(node: str, path: list[str], on_path: set[str]) -> None:
            if node in on_path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            for neighbour in adjacency.get(node, []):
                dfs(neighbour, path + [node], on_path | {node})

        for start in adjacency:
            dfs(start, [], set())

        return cycles
