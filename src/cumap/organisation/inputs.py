"""Read-only inputs for `kg organise`: the content snapshots (nodes, typed edges, first
chapters) plus, for the `spread` and background-guard components, each concept's per-section
roles from the run checkpoint. Nothing here writes anything (CR-006 §1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cumap.expert_kg.snapshots import load_snapshot
from cumap.organisation.config import OrgConfig
from cumap.schemas.relations import RelationRegistry


@dataclass
class OrgConcept:
    concept_id: str
    name: str
    node_type: str
    first_chapter: int


@dataclass
class OrgEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    family: str
    section_id: str
    chapter: int  # chapter in which the edge (and both endpoints) exist
    weight: float  # registry diagnostic_prior of the family x edge confidence (1.0 if absent)


@dataclass
class OrgInputs:
    concepts: dict[str, OrgConcept]
    edges: list[OrgEdge]
    section_chapter: dict[str, int]
    section_order: dict[str, int]
    mentions: dict[str, list[tuple[str, str]]]  # concept_id -> [(section_id, role)]
    chapters: list[int]
    run_id: str = ""
    meta: dict = field(default_factory=dict)


def load_inputs(
    run_dir: Path,
    sections_jsonl: Path,
    registry: RelationRegistry,
    cfg: OrgConfig,
    *,
    through_chapter: int | None = None,
) -> OrgInputs:
    snap_root = run_dir / "snapshots"
    chapters = sorted(int(p.name[2:]) for p in snap_root.glob("ch*") if p.is_dir())
    if through_chapter is not None:
        chapters = [c for c in chapters if c <= through_chapter]
    snaps = [load_snapshot(snap_root, c) for c in chapters]

    layers = set(cfg.graph.layers) | (
        {"prerequisite"} if cfg.graph.include_prerequisite_layer else set()
    )
    rel_layer = {r.name: r.layer for r in registry.all_relations()}
    prior = {name: f.diagnostic_prior for name, f in registry.families.items()}

    concepts: dict[str, OrgConcept] = {}
    for snap in snaps:
        for n in snap.nodes:
            concepts.setdefault(
                n.concept_id,
                OrgConcept(n.concept_id, n.canonical_name, n.node_type, n.first_introduced_chapter),
            )

    section_chapter: dict[str, int] = {}
    section_order: dict[str, int] = {}
    with sections_jsonl.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("chapter_num") in chapters:
                section_chapter[row["section_id"]] = row["chapter_num"]
                section_order[row["section_id"]] = row["order_index"]

    edges: list[OrgEdge] = []
    seen: set[str] = set()
    for snap in snaps:
        for e in snap.edges:
            if e.edge_id in seen or rel_layer.get(e.relation) not in layers:
                continue
            seen.add(e.edge_id)
            ch = max(
                section_chapter.get(e.section_id, snap.chapter_num),
                concepts[e.source_concept_id].first_chapter,
                concepts[e.target_concept_id].first_chapter,
            )
            edges.append(
                OrgEdge(
                    e.edge_id,
                    e.source_concept_id,
                    e.target_concept_id,
                    e.relation,
                    e.family,
                    e.section_id,
                    ch,
                    float(prior.get(e.family, 1.0)) * 1.0,
                )
            )

    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    mentions = {
        c["concept_id"]: [(m["section_id"], m["role"]) for m in c["mentions"]]
        for c in checkpoint["concepts"]
        if c["concept_id"] in concepts
    }
    return OrgInputs(
        concepts, edges, section_chapter, section_order, mentions, chapters, run_id=run_dir.name
    )
