"""CR-005 §2.7 / §3.3: per-chapter snapshots of the growing expert KG, and the
growth metrics computed from a sequence of them.

Each ChapterSnapshot is a *delta*: the concepts mentioned, edges extracted, and
merges made while processing that one chapter (P&D chapters are processed once,
in book order -- so a concept/edge/merge is written to exactly one chapter's
snapshot, the chapter it was first produced in). "Cumulative" numbers (concepts
seen so far, edges seen so far) are derived at read time by compute_growth_metrics,
not stored per snapshot, so a snapshot only ever needs to know about its own chapter.

Written to data/processed/kg/<run_id>/snapshots/ch<N>/{nodes,edges,merges,
rejected}.jsonl + manifest.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class SnapshotNode:
    concept_id: str
    canonical_name: str
    node_type: str
    first_introduced_chapter: int
    aliases: list[str] = field(default_factory=list)
    mention_section_count: int = 0


@dataclass
class SnapshotEdge:
    edge_id: str
    source_concept_id: str
    relation: str
    target_concept_id: str
    family: str
    source_chapter: int  # chapter where source_concept_id was first introduced
    target_chapter: int  # chapter where target_concept_id was first introduced
    section_id: str


@dataclass
class SnapshotMerge:
    concept_id: str
    alias: str
    section_id: str


@dataclass
class ChapterSnapshot:
    run_id: str
    chapter_num: int
    nodes: list[SnapshotNode] = field(default_factory=list)
    edges: list[SnapshotEdge] = field(default_factory=list)
    merges: list[SnapshotMerge] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    prerequisite_candidate_count: int = 0
    forward_reference_count: int = 0


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def write_snapshot(snapshot: ChapterSnapshot, snapshots_dir: Path) -> Path:
    """`snapshots_dir`: .../data/processed/kg/<run_id>/snapshots/. Writes (and
    returns) the ch<N>/ directory under it.
    """
    ch_dir = snapshots_dir / f"ch{snapshot.chapter_num}"
    ch_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(ch_dir / "nodes.jsonl", [asdict(n) for n in snapshot.nodes])
    _write_jsonl(ch_dir / "edges.jsonl", [asdict(e) for e in snapshot.edges])
    _write_jsonl(ch_dir / "merges.jsonl", [asdict(m) for m in snapshot.merges])
    _write_jsonl(ch_dir / "rejected.jsonl", snapshot.rejected)

    manifest = {
        "run_id": snapshot.run_id,
        "chapter_num": snapshot.chapter_num,
        "node_count": len(snapshot.nodes),
        "edge_count": len(snapshot.edges),
        "merge_count": len(snapshot.merges),
        "rejected_count": len(snapshot.rejected),
        "prerequisite_candidate_count": snapshot.prerequisite_candidate_count,
        "forward_reference_count": snapshot.forward_reference_count,
    }
    (ch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return ch_dir


def load_snapshot(snapshots_dir: Path, chapter_num: int) -> ChapterSnapshot:
    ch_dir = snapshots_dir / f"ch{chapter_num}"
    manifest = json.loads((ch_dir / "manifest.json").read_text())
    return ChapterSnapshot(
        run_id=manifest["run_id"],
        chapter_num=manifest["chapter_num"],
        nodes=[SnapshotNode(**n) for n in _read_jsonl(ch_dir / "nodes.jsonl")],
        edges=[SnapshotEdge(**e) for e in _read_jsonl(ch_dir / "edges.jsonl")],
        merges=[SnapshotMerge(**m) for m in _read_jsonl(ch_dir / "merges.jsonl")],
        rejected=_read_jsonl(ch_dir / "rejected.jsonl"),
        prerequisite_candidate_count=manifest["prerequisite_candidate_count"],
        forward_reference_count=manifest["forward_reference_count"],
    )


@dataclass
class ChapterGrowthMetrics:
    chapter_num: int
    concepts_total: int  # cumulative distinct concepts seen up to and including this chapter
    concepts_new: int  # first introduced in this chapter
    concepts_reused: int  # introduced earlier, mentioned again in this chapter
    merges: int
    edges_total: int  # cumulative distinct edges seen up to and including this chapter
    edges_new: int  # extracted while processing this chapter
    cross_chapter_edges: int  # this chapter's new edges whose endpoints span chapters
    prerequisite_candidates: int
    forward_references: int
    family_share: dict[str, float]  # this chapter's new edges, share by relation family


def compute_growth_metrics(snapshots: list[ChapterSnapshot]) -> list[ChapterGrowthMetrics]:
    ordered = sorted(snapshots, key=lambda s: s.chapter_num)
    metrics: list[ChapterGrowthMetrics] = []
    seen_concept_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    for snap in ordered:
        current_concept_ids = {n.concept_id for n in snap.nodes}
        new_concepts = current_concept_ids - seen_concept_ids
        reused_concepts = current_concept_ids & seen_concept_ids
        seen_concept_ids |= current_concept_ids

        current_edge_ids = {e.edge_id for e in snap.edges}
        seen_edge_ids |= current_edge_ids

        cross_chapter = [e for e in snap.edges if e.source_chapter != e.target_chapter]

        family_counts: dict[str, int] = {}
        for e in snap.edges:
            family_counts[e.family] = family_counts.get(e.family, 0) + 1
        edge_count_this_chapter = len(snap.edges)
        family_share = (
            {f: c / edge_count_this_chapter for f, c in family_counts.items()}
            if edge_count_this_chapter
            else {}
        )

        metrics.append(
            ChapterGrowthMetrics(
                chapter_num=snap.chapter_num,
                concepts_total=len(seen_concept_ids),
                concepts_new=len(new_concepts),
                concepts_reused=len(reused_concepts),
                merges=len(snap.merges),
                edges_total=len(seen_edge_ids),
                edges_new=len(current_edge_ids),
                cross_chapter_edges=len(cross_chapter),
                prerequisite_candidates=snap.prerequisite_candidate_count,
                forward_references=snap.forward_reference_count,
                family_share=family_share,
            )
        )

    return metrics
