"""Relation registry: loads configs/relations_v{0,1}.yaml and implements the diagnostic
logic that reads it (normalisation, reversal/conflict/compatibility checks, domain/range
type checks, cycle detection). See ARCHITECTURE.md §4a.

CR-001 (2026-09-28) added v1: families, templates, near-misses, qualifiers and the
functions that use them (family_of, choice_set, can_chain, required_qualifiers). The
v1-only fields on RelationType are optional so v0 files (which don't have them) still
load and behave exactly as before; v1-only registry functions raise a clear error if
called against a v0 file instead of silently returning nonsense.
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


class NearMiss(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: str
    example: str
    why: str


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
    transitive: bool | Literal["within_same_part_type"]
    inverse_of: str | None
    conflicts_with: list[str]
    compatible_with: dict[str, Literal["full", "partial"]]

    # v1 additions (CR-001 §3) — optional so v0 relations (which lack them) still load.
    family: str | None = None
    status: str | None = None
    template: str | None = None
    near_misses: list[NearMiss] = []


class FamilyDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    diagnostic_prior: float
    grounding: str


class QualifierDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[str] | None = None
    type: str | None = None
    applies_to: Literal["all"] | list[str]
    required: bool | str  # bool, or a descriptive string like "recommended" / a per-context note
    note: str | None = None


class ChainLinkTypeDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    template: str
    cues: list[str]


class Choice(NamedTuple):
    """One option in a family-first multiple-choice relation-verification prompt
    (CR-001 §3 choice_set; used by M5/M6's relation-extraction verification step).
    """

    kind: Literal["relation", "no_relation", "other"]
    relation: str | None
    reversed: bool
    text: str


class RelationRegistry:
    def __init__(
        self,
        relations: list[RelationType],
        node_types: list[str],
        *,
        version: int = 0,
        supersedes: int | None = None,
        families: list[FamilyDef] | None = None,
        qualifiers: dict[str, QualifierDef] | None = None,
        chain_link_types: list[ChainLinkTypeDef] | None = None,
    ):
        self._by_name: dict[str, RelationType] = {r.name: r for r in relations}
        self.node_types = node_types
        self.version = version
        self.supersedes = supersedes
        self.families: dict[str, FamilyDef] = {f.name: f for f in (families or [])}
        self.qualifiers: dict[str, QualifierDef] = qualifiers or {}
        self.chain_link_types: dict[str, ChainLinkTypeDef] = {c.name: c for c in (chain_link_types or [])}
        self._inverse_to_forward: dict[str, str] = {
            r.inverse_of: r.name for r in relations if r.inverse_of
        }

    @classmethod
    def from_yaml(cls, path: Path) -> RelationRegistry:
        raw = yaml.safe_load(path.read_text())
        relations = [RelationType(**r) for r in raw["relations"]]
        return cls(
            relations,
            raw["node_types"],
            version=raw.get("version", 0),
            supersedes=raw.get("supersedes"),
            families=[FamilyDef(**f) for f in raw.get("families", [])],
            qualifiers={k: QualifierDef(**v) for k, v in raw.get("qualifiers", {}).items()},
            chain_link_types=[ChainLinkTypeDef(**c) for c in raw.get("chain_link_types", [])],
        )

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def all_relations(self) -> list[RelationType]:
        return list(self._by_name.values())

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

    # ------------------------------------------------------------------
    # v1-only (CR-001 §3): require `family`/`template` to be set, i.e. a v1 registry.
    # ------------------------------------------------------------------

    def _require_v1_field(self, rel: RelationType, field: str) -> str:
        value = getattr(rel, field)
        if value is None:
            raise ValueError(
                f"Relation {rel.name!r} has no {field!r} — this looks like a v0 registry "
                f"(loaded version={self.version}); v1-only registry functions need relations_v1.yaml."
            )
        return value

    def family_of(self, relation: str) -> str:
        rel = self.get(relation)
        return self._require_v1_field(rel, "family")

    def same_family(self, relation_a: str, relation_b: str) -> bool:
        return self.family_of(relation_a) == self.family_of(relation_b)

    def template_for(self, relation: str, x: str, y: str, reverse: bool = False) -> str:
        rel = self.get(relation)
        template = self._require_v1_field(rel, "template")
        if reverse:
            if not rel.directional:
                raise ValueError(f"reverse=True is only valid for directional relations; {relation!r} is not directional")
            x, y = y, x
        return template.format(X=x, Y=y)

    def choice_set(self, x: str, y: str, families: list[str] | None = None) -> list[Choice]:
        """Multiple-choice options for verifying the relation between concepts named
        `x` and `y`: every registry relation's filled template (plus reversed form for
        directional relations), restricted to `families` if given, plus NO_RELATION
        and OTHER — always both offered (CR-001 §3, following QA4RE / Sainz et al. 2021).
        """
        choices: list[Choice] = []
        for rel in self.all_relations():
            if rel.family is None:
                continue  # v0-only relation with no template to fill; skip rather than error
            if families is not None and rel.family not in families:
                continue
            choices.append(Choice(kind="relation", relation=rel.name, reversed=False, text=self.template_for(rel.name, x, y)))
            if rel.directional:
                choices.append(Choice(kind="relation", relation=rel.name, reversed=True, text=self.template_for(rel.name, x, y, reverse=True)))
        choices.append(Choice(kind="no_relation", relation=None, reversed=False, text="No relation is stated between these."))
        choices.append(Choice(kind="other", relation=None, reversed=False, text="Other (not in this list) — give the phrase."))
        return choices

    def can_chain(
        self,
        edge_a: EdgeRef,
        edge_b: EdgeRef,
        *,
        part_type_a: str | None = None,
        part_type_b: str | None = None,
    ) -> bool:
        """Transitive inference: can edge_a and edge_b be chained (edge_a.target ==
        edge_b.source) into a single implied edge_a.source -> edge_b.target?

        For `part_of`, only within the same `part_type` (Winston/Chaffin/Herrmann 1987 —
        transitivity fails across part-whole types, e.g. component + member does not chain).
        """
        if edge_a.target_id != edge_b.source_id:
            return False
        forward_a, _ = self._to_forward_name(edge_a.relation)
        forward_b, _ = self._to_forward_name(edge_b.relation)
        if forward_a != forward_b:
            return False

        rel = self._by_name[forward_a]
        if rel.transitive is False:
            return False
        if rel.transitive == "within_same_part_type":
            return part_type_a is not None and part_type_a == part_type_b
        return True  # transitive is True: unconditional

    def required_qualifiers(self, relation: str) -> set[str]:
        """Qualifier names that are unconditionally required for `relation` — i.e.
        `applies_to` is "all" or includes this relation, AND `required` is the literal
        bool True (a descriptive string like "student edges: yes; expert: ..." means
        conditionally required and is deliberately left out of this simple set).
        """
        forward_name, _ = self._to_forward_name(relation)
        required = set()
        for qname, qdef in self.qualifiers.items():
            applies = qdef.applies_to == "all" or forward_name in qdef.applies_to
            if applies and qdef.required is True:
                required.add(qname)
        return required
