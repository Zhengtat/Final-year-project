"""Pre-sleep snapshot view: the nodes of a finished run with the graph context sleep needs. Read-only; the source run is
never modified. Alias provenance classes follow the Research ruling: an alias traceable to a logged merge event is
`legacy_reconstructed`, otherwise `legacy_unrecorded` (origin unknown, never invented)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from cumap.config import REPO_ROOT

KG = REPO_ROOT / "data/processed/kg"


@dataclass
class Node:
    id: str
    name: str
    aliases: list[str]
    type: str
    definition: str | None
    first_section: str
    mentions: list[dict]
    description_history: list[dict]
    chapter: int
    neighbours: set[str] = field(default_factory=set)
    signature: set[tuple[str, str, str]] = field(
        default_factory=set
    )  # (relation, role, other node)
    relations: set[tuple[str, str]] = field(default_factory=set)  # (relation, role)
    alias_class: dict[str, str] = field(default_factory=dict)

    def forms(self) -> list[str]:
        return [self.name, *self.aliases]

    @property
    def one_token(self) -> bool:
        return len(self.name.split()) == 1


@dataclass
class Snapshot:
    run_id: str
    path: Path
    sha256: str
    nodes: dict[str, Node]
    same_concept_pairs: list[tuple[str, str]]
    merges: list[dict]
    chapter_of: dict[str, int]


def load_snapshot(run_id: str, sections) -> Snapshot:
    path = KG / run_id / "checkpoint.json"
    raw = path.read_bytes()
    cp = json.loads(raw)
    chapter_of = {s.section_id: s.chapter_num for s in sections}
    traced = {m["alias"] for m in cp["merges"] if m.get("evidence_quote")}
    nodes: dict[str, Node] = {}
    for c in cp["concepts"]:
        nodes[c["concept_id"]] = Node(
            id=c["concept_id"],
            name=c["canonical_name"],
            aliases=list(c["aliases"]),
            type=c["node_type"],
            definition=c.get("definition"),
            first_section=c["first_introduced"],
            mentions=c["mentions"],
            description_history=c.get("description_history", []),
            chapter=chapter_of.get(c["first_introduced"], -1),
            alias_class={
                a: ("legacy_reconstructed" if a in traced else "legacy_unrecorded")
                for a in c["aliases"]
            },
        )
    nbr: dict[str, set[str]] = defaultdict(set)
    for r in cp["relation_results_v3"]:
        if r["outcome"] != "edge" or r.get("gated_dropped") or r.get("consolidated_into"):
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        src, tgt = (y, x) if r["direction"] == "reversed" else (x, y)
        if src not in nodes or tgt not in nodes or src == tgt:
            continue
        nodes[src].signature.add((r["relation"], "src", tgt))
        nodes[tgt].signature.add((r["relation"], "tgt", src))
        nodes[src].relations.add((r["relation"], "src"))
        nodes[tgt].relations.add((r["relation"], "tgt"))
        nbr[src].add(tgt)
        nbr[tgt].add(src)
    for k, v in nbr.items():
        nodes[k].neighbours = v
    sc = [
        (r["pair"]["concept_x_id"], r["pair"]["concept_y_id"])
        for r in cp["relation_results_v3"]
        if r["outcome"] == "same_concept"
    ]
    return Snapshot(
        run_id, path, hashlib.sha256(raw).hexdigest(), nodes, sc, cp["merges"], chapter_of
    )
