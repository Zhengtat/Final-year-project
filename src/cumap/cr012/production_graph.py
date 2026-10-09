"""CR-012: convert a finished production run (checkpoint) into per-section `PredNode` / `PredEdge` objects for scoring. Mention spans are the
production's own longest-match occurrences (`expert_kg/mentions.py`, rule 17) of a node's canonical name and aliases, kept only in sections
where the node has at least one generator mention; edge evidence spans are the position of the accepted edge's quote in the section text.
This reads the run and never changes it."""

from __future__ import annotations

import json
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012.types import PredEdge, PredNode
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.relations import concept_vocab


def load_run(run_id: str) -> dict:
    return json.loads((REPO_ROOT / "data/processed/kg/" / run_id / "checkpoint.json").read_text())


def graph_for_sections(cp: dict, sections: dict[str, str]) -> dict[str, dict]:
    """-> {section_id: {"nodes": [PredNode], "edges": [PredEdge], "stats": {...}}}."""
    from cumap.expert_kg.pipeline import _concept_from_dict

    concepts = [_concept_from_dict(c) for c in cp["concepts"]]
    matcher = MentionMatcher(concept_vocab(concepts))
    by_id = {c["concept_id"]: c for c in cp["concepts"]}
    out: dict[str, dict] = {}
    for sid, text in sections.items():
        found: dict[str, list[tuple[int, int]]] = {}
        for m in matcher.find(text):
            found.setdefault(m.concept_id, []).append((m.start, m.end))
        has_mention = {
            c["concept_id"]
            for c in cp["concepts"]
            if any(x["section_id"] == sid for x in c["mentions"])
        }
        nodes = [
            PredNode(
                cid,
                sid,
                by_id[cid]["node_type"],
                by_id[cid]["canonical_name"],
                tuple(sorted(set(spans))),
            )
            for cid, spans in sorted(found.items())
            if cid in has_mention
        ]
        node_ids = {n.node_id for n in nodes}
        edges, ungrounded = [], 0
        for r in cp["relation_results_v3"]:
            if (
                r["outcome"] != "edge"
                or r.get("gated_dropped")
                or r.get("consolidated_into")
                or r["pair"]["section_id"] != sid
            ):
                continue
            x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
            src, tgt = (y, x) if r["direction"] == "reversed" else (x, y)
            if src not in node_ids or tgt not in node_ids:
                ungrounded += 1
                continue
            q = r.get("evidence_quote") or ""
            i = text.find(q) if q else -1
            span = (i, i + len(q)) if i >= 0 else None
            edges.append(PredEdge(sid, src, tgt, r["relation"], span))
        out[sid] = {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "edges_without_endpoint_node": ungrounded,
            },
        }
    return out


def proposed_pairs(cp: dict, section_id: str) -> set[frozenset[str]]:
    """Pairs sent to relation classification for a section (every result of the run, whatever its outcome)."""
    return {
        frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
        for r in cp["relation_results_v3"]
        if r["pair"]["section_id"] == section_id
    }


def run_path(run_id: str) -> Path:
    return REPO_ROOT / "data/processed/kg" / run_id
