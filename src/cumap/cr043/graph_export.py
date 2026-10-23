"""CR-043: export each paper's expert graph with every edge marked against the SciNLP gold ($0, no model call, read-only).

    uv run python -m cumap.cr043.graph_export [--tag cr043base]     # writes reports/cr043/graphs_<tag>.json

Per paper: concept nodes (name, type, aliases, number of placed mentions, whether a mention exactly matches a gold mention),
predicted edges (relation, direction, evidence quote, status), and the gold relations no predicted edge matches (with their
earliest-failure code). Edge status under `IDXR1-P1` (the headline grounding): `correct` = one of the edge's mention-level
placements equals a gold relation; `not_in_gold` = placed, but the gold does not mark it (SciNLP annotates selectively, so
some of these may be true); `unplaced` = the edge could not be placed on mention spans in its own evidence sentence."""

from __future__ import annotations

import argparse
import json

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import TAG, run_id

OUT = REPO_ROOT / "reports" / "cr043"
VARIANT = "IDXR1-P1"


def span_text(doc, sp) -> str:
    return " ".join(doc.tokens[sp[0] : sp[1]])


def sentence_text(doc, sp) -> str:
    import bisect

    i = bisect.bisect_right(doc.sentence_ends, sp[0])
    start = doc.sentence_ends[i - 1] if i else 0
    return " ".join(doc.tokens[start : doc.sentence_ends[i]])


def paper_graph(doc, gold, cp: dict, sym: set[str]) -> dict:
    r = V.sc_score(doc, gold, cp, sym, VARIANT)
    pred = r["pred"]
    nodes, edges = pred["nodes"], pred["edges"]
    by_id = {c["concept_id"]: c for c in cp["concepts"]}
    gold_spans = {m.span for m in gold.mentions}
    gold_keys = {S._rel_key(g.src_span, g.tgt_span, g.relation, sym): g for g in gold.relations}
    matched: set = set()
    out_edges = []
    for e in edges:
        rels, _ = S.project_edges_to_mentions(nodes, [e])
        hit = [k for s, t, rel, *_ in rels if (k := S._rel_key(s, t, rel, sym)) in gold_keys]
        matched.update(hit)
        out_edges.append(
            {
                "source": e.src,
                "target": e.tgt,
                "relation": e.relation,
                "status": "correct" if hit else "not_in_gold",
                "evidence": sentence_text(doc, e.evidence_span) if e.evidence_span else "",
            }
        )
    placed = {(e["source"], e["target"], e["relation"]) for e in out_edges}
    for row in cp["relation_results_v3"]:
        if row["outcome"] != "edge" or row.get("group", "selected") != "selected":
            continue
        if (row.get("qualifiers") or {}).get("polarity") == "negated":
            continue
        p = row["pair"]
        s, t = (
            (p["concept_y_id"], p["concept_x_id"])
            if row.get("direction") == "reversed"
            else (p["concept_x_id"], p["concept_y_id"])
        )
        if (s, t, row["relation"]) not in placed:
            out_edges.append(
                {
                    "source": s,
                    "target": t,
                    "relation": row["relation"],
                    "status": "unplaced",
                    "evidence": row.get("evidence_quote") or "",
                }
            )
    codes = sc_attribution(doc, gold, pred, cp, sym)
    missed = [
        {
            "source": span_text(doc, g.src_span),
            "relation": g.relation,
            "target": span_text(doc, g.tgt_span),
            "code": c or "recovered",
            "sentence": sentence_text(doc, g.src_span),
        }
        for g, c in zip(gold.relations, codes, strict=True)
        if S._rel_key(g.src_span, g.tgt_span, g.relation, sym) not in matched
    ]
    used = {e["source"] for e in out_edges} | {e["target"] for e in out_edges}
    out_nodes = []
    for n in nodes:
        c = by_id.get(n.node_id, {})
        out_nodes.append(
            {
                "id": n.node_id,
                "name": n.name,
                "type": n.type,
                "aliases": c.get("aliases") or [],
                "mentions": len(n.mentions),
                "in_gold": any(m in gold_spans for m in n.mentions),
                "linked": n.node_id in used,
            }
        )
    for nid in used - {n["id"] for n in out_nodes}:  # an edge endpoint without a placed mention
        c = by_id.get(nid, {})
        out_nodes.append(
            {
                "id": nid,
                "name": c.get("canonical_name", nid),
                "type": c.get("node_type", "?"),
                "aliases": c.get("aliases") or [],
                "mentions": 0,
                "in_gold": False,
                "linked": True,
            }
        )
    rel = r["scores"]["rel"]
    return {
        "nodes": out_nodes,
        "edges": out_edges,
        "missed_gold": missed,
        "summary": {
            "concepts": len(out_nodes),
            "edges": len(out_edges),
            "gold_relations": len(gold.relations),
            "correct_edges": sum(e["status"] == "correct" for e in out_edges),
            "strict_f1": rel.f1,
            "strict_p": rel.precision,
            "strict_r": rel.recall,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=TAG)
    a = ap.parse_args()
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    out = {"tag": a.tag, "variant": VARIANT, "papers": {}}
    cache: dict = {}
    for split, d in first_set():
        f = PG.run_path(run_id(d, a.tag)) / "checkpoint.json"
        if not f.exists():
            continue
        cp = json.loads(f.read_text())
        if cp.get("stage") != "snapshots":
            continue  # still running
        if split not in cache:
            cache[split] = (
                ad.gold(split),
                {
                    x.doc_key: x
                    for x in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)
                },
            )
        gold, docs = cache[split]
        out["papers"][d] = {"split": split, **paper_graph(docs[d], gold[d], cp, sym)}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"graphs_{a.tag}.json"
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(p, len(out["papers"]), "papers")


if __name__ == "__main__":
    main()
