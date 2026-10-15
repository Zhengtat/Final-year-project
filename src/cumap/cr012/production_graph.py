"""CR-012: convert a finished production run (checkpoint) into per-section `PredNode` / `PredEdge` objects for scoring.

Mention spans are EVIDENCE-GROUNDED (rule 24 and the SciNLP ruling): a node's spans are the occurrences of the node's own names and aliases that lie inside
the evidence windows of the mentions the pipeline recorded for that node (the located quotes). Matching is per node, so two senses that share a surface
form ("bandwidth" of a link vs of a frequency band) are resolved by where each node's evidence is, not by one global string table; overlaps across nodes
are then settled longest-first, as in the production longest-match rule (rule 17). Edge evidence spans are the position of the accepted edge's quote.
This reads the run and never changes it.

An earlier version matched every string occurrence in the section with one global vocabulary. That made a shared surface look like a false merge and
removed 10 of 39 gold edges from the pair-recall denominators of the pilot oracle runs; it is superseded (reports/cr012/invalid_runs.md)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012.types import PredEdge, PredNode, Span
from cumap.expert_kg.mentions import MentionMatcher


def load_run(run_id: str) -> dict:
    return json.loads((REPO_ROOT / "data/processed/kg/" / run_id / "checkpoint.json").read_text())


def _windows(quotes: set[str], text: str) -> list[Span]:
    """Located occurrences of the recorded evidence quotes, merged."""
    raw: list[Span] = []
    for q in quotes:
        if not q:
            continue
        i = text.find(q)
        while i >= 0:
            raw.append((i, i + len(q)))
            i = text.find(q, i + len(q))
    raw.sort()
    merged: list[Span] = []
    for a, b in raw:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def grounded_spans(
    concepts: list[dict], text: str, sid: str
) -> tuple[dict[str, list[Span]], Counter]:
    """-> ({node_id: [char spans]}, stats). Per-node matching inside the node's evidence windows; overlaps settled longest-first across nodes."""
    stats: Counter = Counter()
    cands: list[tuple[int, int, str]] = []
    for c in concepts:
        quotes = {m["quote"] for m in c["mentions"] if m["section_id"] == sid}
        if not quotes:
            continue
        wins = _windows(quotes, text)
        if not wins:
            stats["nodes_with_no_locatable_evidence_quote"] += 1
            continue
        forms = [c["canonical_name"], *c.get("aliases", [])]
        matcher = MentionMatcher(
            {f.lower(): c["concept_id"] for f in forms if f}, mode="token"
        )  # frozen CR-012 scorer
        for a, b in wins:
            for m in matcher.find(text[a:b]):
                cands.append((a + m.start, a + m.end, c["concept_id"]))
    cands.sort(key=lambda t: (-(t[1] - t[0]), t[0], t[2]))
    taken: list[tuple[int, int, str]] = []
    for a, b, cid in cands:
        if any(a < tb and ta < b and tc != cid for ta, tb, tc in taken):
            stats["span_dropped_overlaps_a_longer_span_of_another_node"] += 1
            continue
        taken.append((a, b, cid))
    out: dict[str, list[Span]] = {}
    for a, b, cid in taken:
        out.setdefault(cid, []).append((a, b))
    return {k: sorted(set(v)) for k, v in out.items()}, stats


def graph_for_sections(cp: dict, sections: dict[str, str]) -> dict[str, dict]:
    """-> {section_id: {"nodes": [PredNode], "edges": [PredEdge], "stats": {...}}}."""
    by_id = {c["concept_id"]: c for c in cp["concepts"]}
    out: dict[str, dict] = {}
    for sid, text in sections.items():
        spans, gstats = grounded_spans(cp["concepts"], text, sid)
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
                tuple(spans.get(cid, ())),
            )
            for cid in sorted(has_mention)
        ]
        node_ids = {n.node_id for n in nodes}
        edges, ungrounded = [], 0
        for r in cp["relation_results_v3"]:
            if (
                r["outcome"] != "edge"
                or r.get("group", "selected")
                != "selected"  # the 50-pair unselected sample is measurement only, never part of the graph
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
                "nodes_without_grounded_span": sum(1 for n in nodes if not n.mentions),
                "edges": len(edges),
                "edges_without_endpoint_node": ungrounded,
                **dict(gstats),
            },
        }
    return out


def proposed_pairs(cp: dict, section_id: str) -> set[frozenset[str]]:
    """Pairs the production run chose to send to relation classification for a section (the measurement sample is not a choice of the
    pipeline and is excluded)."""
    return {
        frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
        for r in cp["relation_results_v3"]
        if r["pair"]["section_id"] == section_id and r.get("group", "selected") == "selected"
    }


def run_path(run_id: str) -> Path:
    return REPO_ROOT / "data/processed/kg" / run_id
