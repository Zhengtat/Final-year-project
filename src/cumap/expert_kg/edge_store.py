"""CR-036 edge store and registry record for `assembly: v2` ($0, no model call; `assembly: legacy | v2`, default legacy).

The checks the old "verify and assemble" stage did move to where an edge is written: the store is built from the classification results of the
SELECTED group, in order, by pure functions:

* directed edges, keyed (source, relation, target), with the original pair id kept for traceability (selection, de-duplication, CR-013 joins);
* direction from node types: when the model's orientation is type-invalid and the reverse is valid, the valid one is stored and the change is flagged
  `direction_set_by_types` (both valid: the model's answer stands; neither: the edge was rejected at classification, as before);
* symmetric relations normalised to sorted ids; identical edges merged with every quote kept (`quotes`);
* several relations on one pair are all kept (edge identity is pair + relation + direction);
* a registry `conflicts_with` pair in the same direction is flagged on both edges, neither dropped;
* measurement-sample results (group other than `selected`) go to a separate list and never reach the edge store.

Nothing is rejected here except a relation the loaded registry does not have, which is logged and skipped (the registry version is checked at load,
see `check_registry_record`)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT
from cumap.schemas.relations import EdgeRef, RelationRegistry

MODES = ("legacy", "v2")


def resolve_assembly(mode: str | None = None) -> str:
    """The explicit argument wins; else `configs/relation_policy.yaml` (`assembly`, default legacy). Quote the value in YAML."""
    if mode is None:
        p = REPO_ROOT / "configs/relation_policy.yaml"
        mode = (
            (yaml.safe_load(p.read_text()) or {}).get("assembly", "legacy")
            if p.exists()
            else "legacy"
        )
    if mode not in MODES:
        raise ValueError(f"assembly must be one of {MODES}, got {mode!r}")
    return mode


def registry_record(registry: RelationRegistry, path: Path | None = None) -> dict:
    path = path or getattr(registry, "source_path", None)
    return {
        "version": registry.version_label,
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None,
        "file": str(Path(path).relative_to(REPO_ROOT))
        if path and Path(path).is_relative_to(REPO_ROOT)
        else None,
    }


def check_registry_record(
    stats: dict, registry: RelationRegistry, path: Path | None = None
) -> None:
    """Loading a stored run for `v2` assembly refuses a registry other than the one it was classified with."""
    rec = (stats or {}).get("registry")
    if not rec:
        raise ValueError("this run records no registry version; assemble it with assembly=legacy")
    now = registry_record(registry, path)
    if rec["version"] != now["version"] or (
        rec.get("sha256") and now["sha256"] and rec["sha256"] != now["sha256"]
    ):
        raise ValueError(
            f"registry mismatch: the run was classified with {rec['version']} ({rec.get('sha256')}), loaded {now['version']} ({now['sha256']})"
        )


@dataclass
class StoredEdge:
    edge_id: str
    pair_id: str
    source_id: str
    target_id: str
    relation: str
    family: str
    section_id: str
    quotes: list[str] = field(default_factory=list)
    pair_ids: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    direction_model: str = "forward"


@dataclass
class EdgeStore:
    edges: list[StoredEdge] = field(default_factory=list)
    measurement: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            k: ([asdict(e) for e in v] if k == "edges" else v) for k, v in self.__dict__.items()
        }


def type_valid(
    registry: RelationRegistry, src: str, rel: str, tgt: str, types: dict[str, str]
) -> bool:
    return not registry.check_types(EdgeRef(source_id=src, relation=rel, target_id=tgt), types)


def build_edge_store(
    results: list[dict], concept_types: dict[str, str], registry: RelationRegistry
) -> EdgeStore:
    store = EdgeStore()
    by_key: dict[tuple[str, str, str], StoredEdge] = {}
    used_ids: set[str] = set()
    for r in results:
        pair = r.get("pair") or {}
        if r.get("group", "selected") != "selected":  # the unselected sample: measurement only
            store.measurement.append(
                {
                    "pair_id": pair.get("pair_id"),
                    "outcome": r.get("outcome"),
                    "relation": r.get("relation"),
                }
            )
            continue
        if (
            r.get("outcome") != "edge"
            or r.get("self_pair")
            or r.get("consolidated_into")
            or r.get("snapshot_secondary")
        ):
            continue
        rel = r["relation"]
        if rel not in registry:
            store.log.append(
                {"pair_id": pair["pair_id"], "event": "relation_not_in_registry", "relation": rel}
            )
            continue
        x, y = pair["concept_x_id"], pair["concept_y_id"]
        src, tgt = (y, x) if r.get("direction") == "reversed" else (x, y)
        flags: list[str] = []
        if registry.get(rel).symmetric:
            n = registry.normalise(EdgeRef(source_id=src, relation=rel, target_id=tgt))
            src, tgt = n.source_id, n.target_id
        elif not type_valid(registry, src, rel, tgt, concept_types) and type_valid(
            registry, tgt, rel, src, concept_types
        ):
            store.log.append(
                {
                    "pair_id": pair["pair_id"],
                    "event": "direction_set_by_types",
                    "model_direction": r.get("direction"),
                    "relation": rel,
                }
            )
            src, tgt = tgt, src
            flags.append("direction_set_by_types")
        quote = r.get("evidence_quote") or ""
        key = (src, rel, tgt)
        if key in by_key:  # an identical edge: merged, every quote kept
            e = by_key[key]
            if quote and quote not in e.quotes:
                e.quotes.append(quote)
            e.pair_ids.append(pair["pair_id"])
            e.flags += [f for f in flags if f not in e.flags]
            store.log.append(
                {"pair_id": pair["pair_id"], "event": "merged_into", "edge_id": e.edge_id}
            )
            continue
        eid = pair["pair_id"]
        if eid in used_ids:  # a second relation on the same pair
            eid = f"{pair['pair_id']}~{rel}"
            n = 2
            while eid in used_ids:
                eid, n = f"{pair['pair_id']}~{rel}~{n}", n + 1
        used_ids.add(eid)
        e = StoredEdge(eid, pair["pair_id"], src, tgt, rel, r.get("family") or "", pair.get("section_id") or "", [quote] if quote else [], [pair["pair_id"]], flags, r.get("direction") or "forward")  # fmt: skip
        by_key[key] = e
        store.edges.append(e)
    for i, a in enumerate(
        store.edges
    ):  # registry conflicts in the same direction: flag both, drop neither
        for b in store.edges[i + 1 :]:
            if (
                (a.source_id, a.target_id) == (b.source_id, b.target_id)
                and a.relation != b.relation
                and registry.conflicts(a.relation, b.relation)
            ):
                a.flags.append(f"conflict:{b.relation}")
                b.flags.append(f"conflict:{a.relation}")
                store.conflicts.append({"source_id": a.source_id, "target_id": a.target_id, "relations": [a.relation, b.relation], "edge_ids": [a.edge_id, b.edge_id]})  # fmt: skip
    return store


def recoverable_domain_range(
    results: list[dict], concept_types: dict[str, str], registry: RelationRegistry
) -> dict:
    """$0: of the classification-time `domain_range` rejections, how many have the OTHER orientation type-valid (what `v2` would store instead)."""
    rejected = [
        r for r in results if r.get("reason") == "domain_range" and r.get("relation") in registry
    ]
    rec = []
    for r in rejected:
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        src, tgt = (y, x) if r.get("direction") == "reversed" else (x, y)
        if not registry.get(r["relation"]).symmetric and type_valid(
            registry, tgt, r["relation"], src, concept_types
        ):
            rec.append(
                {
                    "pair_id": r["pair"]["pair_id"],
                    "relation": r["relation"],
                    "model_direction": r.get("direction"),
                }
            )
    return {
        "domain_range_rejections": len(rejected),
        "recoverable_by_direction_from_types": len(rec),
        "examples": rec[:10],
    }


def find_existing_result(
    results: list[dict], src: str, rel: str, tgt: str, registry: RelationRegistry | None = None
) -> dict | None:
    """CR-036 misconception stage: the selected edge result already stored for (src, rel, tgt) on this pair, if any (a symmetric relation matches in
    either direction; a directed one only in the proposed direction). Such a pair is not classified again."""
    for r in results:
        if (
            r.get("group", "selected") != "selected"
            or r.get("outcome") != "edge"
            or r.get("relation") != rel
        ):
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        s, t = (y, x) if r.get("direction") == "reversed" else (x, y)
        sym = registry.get(rel).symmetric if registry is not None and rel in registry else False
        if (s, t) == (src, tgt) or (sym and (t, s) == (src, tgt)):
            return r
    return None
