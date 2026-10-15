"""CR-019 O2: grounding-consistent evaluation variants. Reuses the frozen CR-012 / CR-017 scorers unchanged; only their inputs change.

Variants (pre-registered in DECISIONS.md 2026-10-15, before any test-split rescoring):
  FROZEN               frozen CR-012 inputs (recorded-window spans; unplaced edges silently excluded). Must reproduce the frozen numbers.
  FROZEN-UNPLACED-FP   frozen inputs; every predicted edge that cannot be placed counts as one false positive.
  IDX-P1   (primary)   recorded spans + occurrence index; edge placed in its own evidence sentence; unplaced edges count as FP.
  IDX-P3               recorded spans + occurrence index; edge placed at the nearest endpoint pair of every sentence where both endpoints occur; unplaced FP.
The P&D scorer already counts every edge, so P&D has FROZEN and IDX only."""

from __future__ import annotations

import bisect
from itertools import product

from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF, PredEdge, PredNode, Span
from cumap.cr019.occurrences import build_index, spans_by_node

PRIMARY = "IDX-P1"
SC_VARIANTS = ("FROZEN", "FROZEN-UNPLACED-FP", "IDX-P1", "IDX-P3")


def _edge_rows(cp: dict, unit: str | None = None) -> list[dict]:
    out = []
    for r in cp["relation_results_v3"]:
        if (
            r["outcome"] != "edge"
            or r.get("group", "selected") != "selected"
            or r.get("gated_dropped")
            or r.get("consolidated_into")
        ):
            continue
        if unit is not None and r["pair"]["section_id"] != unit:
            continue
        out.append(r)
    return out


def _endpoints(r: dict) -> tuple[str, str]:
    x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
    return (y, x) if r["direction"] == "reversed" else (x, y)


def _locate_quote(text: str, q: str, a_spans: list[Span], b_spans: list[Span]) -> Span | None:
    """Character span of the quote occurrence that contains both endpoints; the first occurrence when none does (CR-012 behaviour)."""
    if not q:
        return None
    hits, i = [], text.find(q)
    while i >= 0:
        hits.append((i, i + len(q)))
        i = text.find(q, i + 1)
    if not hits:
        return None
    for a, b in hits:
        if any(a <= s and e <= b for s, e in a_spans) and any(
            a <= s and e <= b for s, e in b_spans
        ):
            return a, b
    return hits[0]


# ---------------------------------------------------------------- SciNLP (mention level, token spans)
def sc_sentences(doc) -> list[Span]:
    out, start = [], 0
    for end in doc.sentence_ends:
        out.append((doc.token_offsets[start][0], doc.token_offsets[end - 1][1]))
        start = end
    return out


def sc_predict_indexed(doc, cp: dict) -> dict:
    """Same contract as `scinlp_run.predict`, with node spans = recorded-window spans ∪ occurrence index."""
    by_id = {c["concept_id"]: c for c in cp["concepts"]}
    rec, _ = PG.grounded_spans(cp["concepts"], doc.text, doc.doc_key)
    occ, istats = build_index(cp["concepts"], doc.text, doc.doc_key, sc_sentences(doc))
    idx = spans_by_node(occ)
    chars = {
        cid: sorted(set(rec.get(cid, [])) | set(idx.get(cid, []))) for cid in set(rec) | set(idx)
    }
    found, off = {}, 0
    for cid, cs in chars.items():
        for a, b in cs:
            sp = doc.chars_to_span(a, b)
            if sp is None:
                off += 1
                continue
            found.setdefault(cid, set()).add(sp)
    nodes = [PredNode(cid, doc.doc_key, by_id[cid]["node_type"], by_id[cid]["canonical_name"], tuple(sorted(sp))) for cid, sp in sorted(found.items())]  # fmt: skip
    ids = {n.node_id for n in nodes}
    edges, unplaced = [], 0
    for r in _edge_rows(cp):
        if (r.get("qualifiers") or {}).get("polarity") == "negated":
            continue
        src, tgt = _endpoints(r)
        loc = _locate_quote(
            doc.text, r.get("evidence_quote") or "", chars.get(src, []), chars.get(tgt, [])
        )
        ev = SR.char_to_token(doc, *loc) if loc else None
        if src not in ids or tgt not in ids or ev is None:
            unplaced += 1
            continue
        edges.append(PredEdge(doc.doc_key, src, tgt, r["relation"], ev))
    return {"nodes": nodes, "edges": edges, "occurrences": occ, "stats": {"nodes": len(nodes), "edges": len(edges), "edges_without_node_or_quote": unplaced, "mentions_off_token_boundary": off, **dict(istats)}}  # fmt: skip


def project_p3(doc, nodes: list[PredNode], edges: list[PredEdge]) -> tuple[list, int]:
    """Rule P3: for every sentence where both endpoints occur, the nearest endpoint pair carries the edge."""
    by_id = {n.node_id: n for n in nodes}
    ends = doc.sentence_ends
    sid = lambda t: bisect.bisect_right(ends, t)
    out, unplaced = [], 0
    for e in edges:
        s, t = by_id[e.src], by_id[e.tgt]
        placed = False
        for k in {sid(m[0]) for m in s.mentions} & {sid(m[0]) for m in t.mentions}:
            pairs = [
                (abs(a[0] - b[0]), a, b)
                for a, b in product(s.mentions, t.mentions)
                if a != b and sid(a[0]) == k and sid(b[0]) == k
            ]
            if pairs:
                _, a, b = min(pairs)
                out.append((a, b, e.relation, s.type, t.type))
                placed = True
        unplaced += not placed
    return out, unplaced


def sc_score(doc, gold, cp: dict, sym: set[str], variant: str) -> dict:
    """-> {"scores": score_scinlp_unit output with unplaced edges added as FP where the variant says so, "edges": accounting}."""
    if variant.startswith("FROZEN"):
        pred = SR.predict(doc, cp)
        dropped_before = pred["stats"]["ungrounded_dropped"]
        rels, unplaced = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
    else:
        pred = sc_predict_indexed(doc, cp)
        dropped_before = pred["stats"]["edges_without_node_or_quote"]
        rels, unplaced = (
            S.project_edges_to_mentions
            if variant == "IDX-P1"
            else lambda n, e: project_p3(doc, n, e)
        )(pred["nodes"], pred["edges"])
    res = S.score_scinlp_unit(gold, S.project_nodes_to_mentions(pred["nodes"]), rels, sym)
    n_unplaced = unplaced + dropped_before
    if variant != "FROZEN":
        r = res["rel"]
        res["rel"] = PRF(r.tp, r.fp + n_unplaced, r.fn)
    total = len(
        [r for r in _edge_rows(cp) if (r.get("qualifiers") or {}).get("polarity") != "negated"]
    )
    return {
        "scores": res,
        "pred": pred,
        "edges": {
            "predicted": total,
            "placed": total - n_unplaced,
            "unplaced": n_unplaced,
            "unplaced_counted_as_fp": variant != "FROZEN",
        },
    }


def n0_split(doc, gold, codes: list[str | None], occ) -> dict:
    """Frozen N0 codes split by whether a node owns the endpoint's occurrence (`N0-unrecorded`) or no node has that surface (`N0-absent`)."""
    owned = set()
    for o in occ:
        sp = doc.chars_to_span(o.start, o.end)
        if sp is not None:
            owned.add(sp)
    out = {"N0-absent": 0, "N0-unrecorded": 0}
    for r, c in zip(gold.relations, codes, strict=True):
        if c != "N0":
            continue
        out["N0-unrecorded" if r.src_span in owned and r.tgt_span in owned else "N0-absent"] += 1
    return out


# ---------------------------------------------------------------- P&D (canonical graph, character spans)
def pd_graph_indexed(cp: dict, sid: str, text: str, sentences: list[Span]) -> dict:
    base = PG.graph_for_sections(cp, {sid: text})[sid]
    occ, istats = build_index(cp["concepts"], text, sid, sentences)
    idx = spans_by_node(occ)
    nodes = [PredNode(n.node_id, n.unit, n.type, n.name, tuple(sorted(set(n.mentions) | set(idx.get(n.node_id, []))))) for n in base["nodes"]]  # fmt: skip
    spans = {n.node_id: list(n.mentions) for n in nodes}
    edges, node_ids = [], set(spans)
    for r in _edge_rows(cp, sid):  # same filter and order as production_graph.graph_for_sections
        src, tgt = _endpoints(r)
        if src not in node_ids or tgt not in node_ids:
            continue
        edges.append(
            PredEdge(
                sid,
                src,
                tgt,
                r["relation"],
                _locate_quote(
                    text, r.get("evidence_quote") or "", spans.get(src, []), spans.get(tgt, [])
                ),
            )
        )
    return {"nodes": nodes, "edges": edges, "occurrences": occ, "stats": {**base["stats"], **{f"index_{k}": v for k, v in istats.items()}}}  # fmt: skip
