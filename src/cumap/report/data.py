"""Assembles everything the demo report shows from saved artefacts (no LLM, no network):
the P&D run checkpoint + snapshots, the frozen IIR eval runs, and the owner's review files.
Nothing here reads or writes the human-owned gold directory -- review files live in
data/interim/review/.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from cumap.eval.stats import wilson_ci
from cumap.expert_kg.snapshots import ChapterSnapshot, load_snapshot
from cumap.report.graph import GEdge, GNode
from cumap.schemas.relations import RelationRegistry


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _mark_column(row: dict) -> str:
    return next(k for k in row if k.lower().startswith("mark"))


def ci_dict(successes: int, n: int, confidence: float = 0.95) -> dict:
    w = wilson_ci(successes, n, confidence=confidence)
    return {"successes": successes, "n": n, "point": w.point_estimate, "low": w.low, "high": w.high}


def summarise_merge_marks(rows: list[dict]) -> dict:
    """Owner check of the non-trivial 'same' merges: mark is ok / wrong."""
    marks = [r[_mark_column(r)].strip().lower() for r in rows]
    ok = sum(1 for m in marks if m == "ok")
    return {
        "ci": ci_dict(ok, len(marks)),
        "wrong": [
            {"alias": r["alias_merged"], "into": r["merged_into"], "note": r.get("note", "")}
            for r, m in zip(rows, marks, strict=True)
            if m != "ok"
        ],
    }


def normalise_edge_mark(mark: str) -> str:
    m = mark.strip().lower()
    if m in {"ok", "correct"}:
        return "correct"
    if m.startswith("wrong-dir"):  # includes the owner's 'wrong-directon' typo
        return "wrong_direction"
    return "incorrect"


def summarise_spotcheck(sheet: list[dict], key: list[dict]) -> dict:
    """Strict precision counts only 'correct'; lenient also counts wrong-direction (the
    relation was right, the arrow wasn't). Per-family counts use the key file."""
    fam = {int(k["id"]): k["family"] for k in key}
    marks = {int(r["id"]): normalise_edge_mark(r[_mark_column(r)]) for r in sheet}
    n = len(marks)
    counts = Counter(marks.values())
    by_family: dict[str, Counter] = defaultdict(Counter)
    for i, m in marks.items():
        by_family[fam.get(i, "?")][m] += 1
    return {
        "n": n,
        "counts": dict(counts),
        "strict": ci_dict(counts["correct"], n),
        "lenient": ci_dict(counts["correct"] + counts["wrong_direction"], n),
        "by_family": {f: dict(c) for f, c in sorted(by_family.items())},
    }


@dataclass
class GrowthData:
    nodes: list[GNode]
    edges: list[GEdge]
    edge_details: dict[str, dict]
    chapters: list[int]
    snapshots: list[ChapterSnapshot]
    key_concepts: list[dict]  # name + per-section role grid
    section_labels: list[dict]  # ordered sections: id, chapter, label
    steps: list[dict]  # one per section, book order: caption + what the time bar reveals


def _section_order(sections: list[dict]) -> list[dict]:
    return sorted(sections, key=lambda r: r["order_index"])


def build_growth(
    checkpoint: dict, snapshots: list[ChapterSnapshot], sections: list[dict], *, key_n: int
) -> GrowthData:
    order = {s["section_id"]: i for i, s in enumerate(_section_order(sections))}
    ordered_secs = [
        s for s in _section_order(sections) if s["section_id"] in checkpoint["mentions_by_section"]
    ]
    sec_idx = {s["section_id"]: i for i, s in enumerate(ordered_secs)}
    concepts = {c["concept_id"]: c for c in checkpoint["concepts"]}

    # prerequisite candidate = defined in section D, used in some later section
    prereq: set[str] = set()
    for cid, c in concepts.items():
        defined = [
            order[m["section_id"]]
            for m in c["mentions"]
            if m["role"] == "defined" and m["section_id"] in order
        ]
        used = [
            order[m["section_id"]]
            for m in c["mentions"]
            if m["role"] == "used" and m["section_id"] in order
        ]
        if defined and any(u > min(defined) for u in used):
            prereq.add(cid)

    first_sec = {
        cid: min(sec_idx[m["section_id"]] for m in c["mentions"] if m["section_id"] in sec_idx)
        for cid, c in concepts.items()
        if any(m["section_id"] in sec_idx for m in c["mentions"])
    }
    node_by_id: dict = {}
    for snap in sorted(snapshots, key=lambda s: s.chapter_num):
        for n in snap.nodes:
            node_by_id.setdefault(n.concept_id, n)
    edges: list[GEdge] = []
    details: dict[str, dict] = {}
    pair_edges = {
        d["edge"]["pair"]["pair_id"]: d["edge"]
        for d in checkpoint["pair_registry"]
        if d.get("edge")
    }
    seen: set[str] = set()
    for snap in sorted(snapshots, key=lambda s: s.chapter_num):
        for e in snap.edges:
            if e.edge_id in seen:
                continue
            seen.add(e.edge_id)
            raw = pair_edges[e.edge_id]
            negated = raw["qualifiers"]["polarity"] == "negated"
            edges.append(
                GEdge(
                    id=e.edge_id,
                    source=e.source_concept_id,
                    target=e.target_concept_id,
                    relation=e.relation,
                    family=e.family,
                    negated=negated,
                    chapter=snap.chapter_num,
                    cross=e.source_chapter != e.target_chapter,
                    section=sec_idx[e.section_id],
                )
            )
            details[e.edge_id] = {
                "source": concepts[e.source_concept_id]["canonical_name"],
                "target": concepts[e.target_concept_id]["canonical_name"],
                "relation": e.relation,
                "family": e.family,
                "section": e.section_id,
                "sentence": raw["pair"]["sentence"],
                "statement": raw["statement"],
                "quote": raw["evidence_quote"],
                "polarity": raw["qualifiers"]["polarity"],
                "modality": raw["qualifiers"]["modality"],
                "chapter": snap.chapter_num,
                "source_chapter": e.source_chapter,
                "target_chapter": e.target_chapter,
            }

    degree: Counter = Counter()
    for e in edges:
        degree[e.source] += 1
        degree[e.target] += 1
    ranked = sorted(
        node_by_id.values(),
        key=lambda n: (-degree[n.concept_id], -n.mention_section_count, n.canonical_name),
    )
    rank = {n.concept_id: i for i, n in enumerate(ranked)}
    nodes = [
        GNode(
            id=n.concept_id,
            label=n.canonical_name,
            chapter=n.first_introduced_chapter,
            size=n.mention_section_count,
            aliases=list(n.aliases),
            prereq=n.concept_id in prereq,
            section=first_sec[n.concept_id],
            rank=rank[n.concept_id],
        )
        for n in ranked
    ]

    section_labels = [
        {
            "id": s["section_id"],
            "chapter": s["chapter_num"],
            "label": s["section_id"]
            if s["section_id"][0].isdigit() and "." in s["section_id"]
            else s.get("section_title", s["section_id"]),
        }
        for s in _section_order(sections)
        if s["section_id"] in checkpoint["mentions_by_section"]
    ]
    key_ids = sorted(
        concepts,
        key=lambda cid: (
            -len({m["section_id"] for m in concepts[cid]["mentions"]}),
            concepts[cid]["canonical_name"],
        ),
    )[:key_n]
    key_concepts = []
    for cid in key_ids:
        by_section: dict[str, str] = {}
        rank_role = {"defined": 3, "refined": 3, "used": 2, "mentioned": 1}  # CR-007: refined shows as defined
        for m in concepts[cid]["mentions"]:
            if rank_role[m["role"]] > rank_role.get(by_section.get(m["section_id"], ""), 0):
                by_section[m["section_id"]] = m["role"]
        key_concepts.append(
            {
                "name": concepts[cid]["canonical_name"],
                "roles": by_section,
                "aliases": len(concepts[cid]["aliases"]),
            }
        )
    steps = []
    merges_by_sec = Counter(
        sec_idx[m["section_id"]] for m in checkpoint["merges"] if m["section_id"] in sec_idx
    )
    for i, sec in enumerate(ordered_secs):
        sid = sec["section_id"]
        title = sec.get("section_title", "")
        steps.append(
            {
                "caption": f"{sid} {title}".strip()
                if sid[0].isdigit() and "." in sid
                else title or sid,
                "chapter": sec["chapter_num"],
                "mentioned": sorted(
                    cid
                    for cid, c in concepts.items()
                    if any(m["section_id"] == sid for m in c["mentions"])
                ),
                "merges": merges_by_sec.get(i, 0),
            }
        )
    return GrowthData(
        steps=steps,
        nodes=nodes,
        edges=edges,
        edge_details=details,
        chapters=sorted(s.chapter_num for s in snapshots),
        snapshots=snapshots,
        key_concepts=key_concepts,
        section_labels=section_labels,
    )


def worked_examples(
    checkpoint: dict, registry: RelationRegistry, growth: GrowthData, *, n: int = 3
) -> list[dict]:
    """Three sections with the most families among their accepted edges (ties: more edges,
    then section id); one representative edge each, families kept distinct where possible.
    Each carries the exact option lists the model saw in the two classification steps."""
    by_section: dict[str, list[GEdge]] = defaultdict(list)
    for e in growth.edges:
        by_section[growth.edge_details[e.id]["section"]].append(e)
    ranked = sorted(
        by_section, key=lambda s: (-len({e.family for e in by_section[s]}), -len(by_section[s]), s)
    )[:n]
    concepts = {c["concept_id"]: c["canonical_name"] for c in checkpoint["concepts"]}
    pair_edges = {
        d["edge"]["pair"]["pair_id"]: d for d in checkpoint["pair_registry"] if d.get("edge")
    }
    used_families: set[str] = set()
    out = []
    for sid in ranked:
        cands = sorted(by_section[sid], key=lambda e: e.id)
        edge = next((e for e in cands if e.family not in used_families), cands[0])
        used_families.add(edge.family)
        res = pair_edges[edge.id]
        raw = res["edge"]
        x, y = concepts[res["concept_x_id"]], concepts[res["concept_y_id"]]
        family_options = [
            {"name": f.name, "label": f.label, "chosen": f.name == edge.family}
            for f in registry.families.values()
            if f.name != "pedagogical"
        ] + [
            {"name": "no_relation", "label": "nothing meaningful is stated", "chosen": False},
            {"name": "other", "label": "a relation that fits no family", "chosen": False},
        ]
        relation_options = []
        for rel in registry.all_relations():
            if rel.family != edge.family:
                continue
            relation_options.append(
                {
                    "text": registry.template_for(rel.name, x, y),
                    "relation": rel.name,
                    "reversed": False,
                    "chosen": rel.name == edge.relation and raw["direction"] != "reversed",
                }
            )
            if rel.directional:
                relation_options.append(
                    {
                        "text": registry.template_for(rel.name, x, y, reverse=True),
                        "relation": rel.name,
                        "reversed": True,
                        "chosen": rel.name == edge.relation and raw["direction"] == "reversed",
                    }
                )
        out.append(
            {
                "section": sid,
                "edge_id": edge.id,
                "x": x,
                "y": y,
                "sentence": raw["pair"]["sentence"],
                "cooccurrence": raw["pair"]["cooccurrence_count"],
                "cue_score": raw["pair"]["cue_score"],
                "family": edge.family,
                "relation": edge.relation,
                "direction": raw["direction"],
                "statement": raw["statement"],
                "quote": raw["evidence_quote"],
                "qualifiers": raw["qualifiers"],
                "family_options": family_options,
                "relation_options": relation_options
                + [
                    {
                        "text": "other: none of the above fit",
                        "relation": "other",
                        "reversed": False,
                        "chosen": False,
                    }
                ],
                "source": concepts[edge.source],
                "target": concepts[edge.target],
            }
        )
    return out


def edge_counts(growth: GrowthData) -> tuple[Counter, Counter]:
    fam = Counter(e.family for e in growth.edges)
    rel = Counter((e.family, e.relation) for e in growth.edges)
    return fam, rel


def load_snapshots(run_dir: Path) -> list[ChapterSnapshot]:
    chapters = sorted(int(p.name[2:]) for p in (run_dir / "snapshots").glob("ch*") if p.is_dir())
    return [load_snapshot(run_dir / "snapshots", c) for c in chapters]
