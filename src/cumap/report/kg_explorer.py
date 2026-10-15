"""Read-only KG explorer: one self-contained offline HTML (`reports/kg_explorer/index.html`) with two modes, the P&D production Expert KG
(`slice3_c2`, Chapters 1-3, with the CR-006 organisation `org_b6ebb5bc`) and the retained CR-012 SciNLP held-out E0 graphs.

No model call, no rerun, no write outside `reports/kg_explorer/`. SciNLP edges are marked as matching a gold relation using the frozen CR-012
scorer's own functions (`project_edges_to_mentions`, `_rel_key`) on the retained checkpoints; scoring is not altered.

    uv run python -m cumap.report.kg_explorer
"""

from __future__ import annotations

import base64
import gzip
import json
import math
from collections import Counter
from pathlib import Path

import networkx as nx

from cumap.config import REPO_ROOT

NA = "NOT_AVAILABLE_IN_RETAINED_OUTPUT"
KG = REPO_ROOT / "data/processed/kg"
PD_RUN, ORG = "slice3_c2", "org_b6ebb5bc"
OUT = REPO_ROOT / "reports/kg_explorer/index.html"


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def norm(pos: dict) -> dict:
    if not pos:
        return {}
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    s = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 2
    return {k: ((p[0] - cx) / s, (p[1] - cy) / s) for k, p in pos.items()}


def force_layout(ids: list[str], edges: list[tuple[str, str]], seed: int = 42) -> dict:
    g = nx.Graph()
    g.add_nodes_from(ids)
    g.add_edges_from(edges)
    k = 1.6 / math.sqrt(max(len(ids), 1))
    return norm(
        {n: tuple(p) for n, p in nx.spring_layout(g, k=k, iterations=200, seed=seed).items()}
    )


def relation_defs(path: str) -> dict:
    import yaml

    y = yaml.safe_load((REPO_ROOT / path).read_text())
    return {
        r["name"]: {"definition": r.get("definition", NA), "template": r.get("template", NA), "family": r.get("family", NA),
                    "symmetric": bool(r.get("symmetric")), "domain": r.get("domain_types", []), "range": r.get("range_types", [])}
        for r in y["relations"]
    }  # fmt: skip


# ------------------------------------------------------------------ P&D production graph
def build_pd() -> dict:
    base = KG / PD_RUN
    cp = json.loads((base / "checkpoint.json").read_text())
    concepts = {c["concept_id"]: c for c in cp["concepts"]}
    results = {r["pair"]["pair_id"]: r for r in cp["relation_results_v3"] if r["outcome"] == "edge"}
    nodes, edges = {}, {}
    for ch in (1, 2, 3):
        for n in jl(base / f"snapshots/ch{ch}/nodes.jsonl"):
            nodes[n["concept_id"]] = n
        for e in jl(base / f"snapshots/ch{ch}/edges.jsonl"):
            e["_snapshot_chapter"] = ch
            edges[e["edge_id"]] = e
    org = {}
    for ch in (1, 2, 3):
        for r in jl(base / f"organisation/{ORG}/ch{ch}/org_nodes.jsonl"):
            org.setdefault(r["concept_id"], {})[ch] = r
    linked = {x for e in edges.values() for x in (e["source_concept_id"], e["target_concept_id"])}
    ids = sorted(nodes)
    lay = force_layout(
        sorted(linked & set(ids)),
        [(e["source_concept_id"], e["target_concept_id"]) for e in edges.values()],
    )
    out_nodes = []
    for cid in ids:
        n, c, o3 = nodes[cid], concepts.get(cid, {}), org.get(cid, {}).get(3, {})
        ms = c.get("mentions", [])
        secs = sorted({m["section_id"] for m in ms})
        a, r = math.radians(o3.get("angle_deg", 0.0)), o3.get("radius", 1.0)
        fx, fy = lay.get(cid, (None, None)) if cid in lay else (None, None)
        if fx is None:  # unlinked nodes sit on an outer ring in the force view
            fx, fy = 1.25 * math.cos(a), 1.25 * math.sin(a)
        out_nodes.append({
            "id": cid, "name": n["canonical_name"], "type": n["node_type"], "aliases": n.get("aliases", []),
            "ch": n["first_introduced_chapter"], "first_section": c.get("first_introduced", NA), "sections": secs, "n_mentions": len(ms),
            "quotes": [{"sec": m["section_id"], "role": m["role"], "q": m["quote"]} for m in ms[:4]],
            "definition": c.get("definition") or NA,
            "alias_provenance": [str(x) for x in c.get("alias_provenance", [])[:4]] or NA,
            "merged_from": c.get("merged_from", []),
            "linked": cid in linked,
            "ring": o3.get("ring", NA), "importance": o3.get("importance_adj"), "comm": o3.get("community_id_coarse", NA), "comm_fine": o3.get("community_id_fine", NA),
            "ring_by_chapter": {str(k): v["ring"] for k, v in sorted(org.get(cid, {}).items())},
            "fx": fx, "fy": fy, "rx": r * math.cos(a), "ry": r * math.sin(a),
        })  # fmt: skip
    out_edges = []
    for eid, e in sorted(edges.items()):
        r = results.get(eid, {})
        sec = e.get("section_id", NA)
        out_edges.append({
            "id": eid, "s": e["source_concept_id"], "t": e["target_concept_id"], "rel": e["relation"], "family": e["family"],
            "ch": e["_snapshot_chapter"], "section": sec,
            "statement": r.get("statement", NA), "quote": r.get("evidence_quote", NA), "sentence": r.get("pair", {}).get("sentence", NA),
            "qual": r.get("qualifiers", NA), "grounding": r.get("grounding", NA), "family_reason": r.get("family_reason", NA),
            "hashes": r.get("prompt_hashes", NA), "selection_group": r.get("group", NA), "confidence": NA,
            "model_direction": r.get("direction", NA),
        })  # fmt: skip
    rel_counts = Counter(e["rel"] for e in out_edges)
    manifest = json.loads((base / f"organisation/{ORG}/manifest.json").read_text())
    return {
        "title": "P&D Expert KG — production/development graph (Peterson & Davie, Chapters 1–3)",
        "run_id": PD_RUN, "snapshot_path": f"data/processed/kg/{PD_RUN}/snapshots/ch1..ch3 (per-chapter additions; union shown)",
        "organisation_path": f"data/processed/kg/{PD_RUN}/organisation/{ORG}/ch3/org_nodes.jsonl",
        "stats": {"canonical_nodes": len(out_nodes), "accepted_edges": len(out_edges), "nodes_with_edges": len(linked), "unlinked_nodes": len(out_nodes) - len(linked),
                  "aliases": sum(len(n["aliases"]) for n in out_nodes), "relation_counts": dict(rel_counts.most_common()),
                  "ring_counts": dict(Counter(n["ring"] for n in out_nodes)), "chapters": [1, 2, 3],
                  "organisation": {"org_id": ORG, "label_source": manifest["label_source"], "modularity_fine": manifest["chapters"]["3"]["modularity_fine"]}},
        "defs": relation_defs("configs/relations_v1.3.yaml"), "nodes": out_nodes, "edges": out_edges,
    }  # fmt: skip


# ------------------------------------------------------------------ SciNLP held-out E0 graphs (retained checkpoints)
def build_scinlp() -> dict:
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012 import scoring as S
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr012.stop4_score import sc_attribution
    from cumap.cr019 import variants as V19

    res = json.loads((REPO_ROOT / "reports/cr012/stop4_heldout_results.json").read_text())[
        "scinlp"
    ]["levels"]["E0"]
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    gold_all = ad.gold("test")
    c19_path = REPO_ROOT / "reports/cr019/stage_a.json"
    c19 = json.loads(c19_path.read_text())["stage_a"]["scinlp"] if c19_path.exists() else None
    docs = []
    for doc in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY):
        rid = f"cr012_scinlp_heldout_{doc.doc_key.replace('.', '_').replace('-', '_')}_E0"
        path = KG / rid / "checkpoint.json"
        cp = json.loads(path.read_text())
        pred = SR.predict(doc, cp)
        # CR-019 occurrence index (labelled; the frozen view is unchanged)
        ipred = V19.sc_predict_indexed(doc, cp)
        g = gold_all[doc.doc_key]
        gold_spans = {m.span for m in g.mentions}
        gold_typed = {(m.span, m.type) for m in g.mentions}
        gold_type = {m.span: m.type for m in g.mentions}
        gold_keys = {S._rel_key(r.src_span, r.tgt_span, r.relation, sym) for r in g.relations}
        starts = [0, *doc.sentence_ends[:-1]]

        def sent_idx(tok: int, starts=starts) -> int:
            return max(j for j, s0 in enumerate(starts) if s0 <= tok)

        def sentence_of(tok: int, doc=doc, starts=starts) -> str:
            i = sent_idx(tok)
            return " ".join(doc.tokens[starts[i] : doc.sentence_ends[i]])

        results = [
            r
            for r in cp["relation_results_v3"]
            if r["outcome"] == "edge" and r.get("group", "selected") == "selected"
        ]
        by_pair: dict = {}
        for r in results:
            by_pair.setdefault(
                frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"])), []
            ).append(r)
        nodes, span_node = [], {}
        for n in pred["nodes"]:
            surf = [" ".join(doc.tokens[a:b]) for a, b in n.mentions]
            nodes.append({
                "id": n.node_id, "name": surf[0] if surf else n.name, "canonical_name": n.name, "type": n.type, "surfaces": sorted(set(surf))[:6], "n_spans": len(n.mentions),
                "spans": [list(s0) for s0 in n.mentions[:6]], "sentence": sentence_of(n.mentions[0][0]) if n.mentions else NA, "ghost": False,
                "gold_entity_match": any(s0 in gold_spans for s0 in n.mentions), "gold_entity_typed_match": any((s0, n.type) in gold_typed for s0 in n.mentions),
            })  # fmt: skip
            for s0 in n.mentions:
                span_node.setdefault(s0, n.node_id)
        frozen_ids = {n.node_id for n in pred["nodes"]}
        index_node = {
            s0: n.node_id
            for n in ipred["nodes"]
            if n.node_id in frozen_ids
            for s0 in n.mentions
            if s0 not in span_node
        }
        iedge = {(e.src, e.tgt, e.relation): e for e in ipred["edges"]}
        edges, matched_keys = [], set()
        for i, e in enumerate(pred["edges"]):
            proj, _ = S.project_edges_to_mentions(pred["nodes"], [e])
            keys = [S._rel_key(a, b, rel, sym) for a, b, rel, _st, _tt in proj]
            match = any(k in gold_keys for k in keys)
            ie = iedge.get((e.src, e.tgt, e.relation))
            iproj = S.project_edges_to_mentions(ipred["nodes"], [ie])[0] if ie else []
            match19 = any(S._rel_key(a, b, rel, sym) in gold_keys for a, b, rel, _st, _tt in iproj)
            matched_keys |= {k for k in keys if k in gold_keys}
            cands = [
                r for r in by_pair.get(frozenset((e.src, e.tgt)), []) if r["relation"] == e.relation
            ]
            r = cands[0] if cands else {}
            edges.append({
                "id": f"{doc.doc_key}-e{i}", "kind": "pred", "s": e.src, "t": e.tgt, "rel": e.relation, "statement": r.get("statement", NA), "quote": r.get("evidence_quote", NA),
                "sentence": r.get("pair", {}).get("sentence", NA), "qual": r.get("qualifiers", NA), "model_direction": r.get("direction", NA),
                "matches_gold": match, "grounded": bool(proj), "matches_gold_cr019": match19, "placed_cr019": bool(iproj), "confidence": NA, "family_reason": r.get("family_reason", NA),
                "grounding": r.get("grounding", NA), "hashes": r.get("prompt_hashes", NA),
            })  # fmt: skip
        # gold relations: matched / missed with the earliest-failure code (frozen attribution)
        codes = sc_attribution(doc, g, pred, cp, sym)
        ghosts: dict = {}
        gold_rels, miss_i = [], 0
        for r, code in zip(g.relations, codes, strict=True):
            matched = S._rel_key(r.src_span, r.tgt_span, r.relation, sym) in matched_keys
            item = {
                "src": list(r.src_span), "tgt": list(r.tgt_span), "src_text": " ".join(doc.tokens[r.src_span[0] : r.src_span[1]]),
                "tgt_text": " ".join(doc.tokens[r.tgt_span[0] : r.tgt_span[1]]), "rel": r.relation, "matched": matched,
                "code": "MATCHED" if matched else (code or "NODE_LEVEL_ONLY"), "sentence": sentence_of(r.src_span[0]),
            }  # fmt: skip
            gold_rels.append(item)
            if matched:
                continue
            ends, by_index = [], False
            for sp in (r.src_span, r.tgt_span):
                if sp in span_node:
                    ends.append(span_node[sp])
                # CR-019: the occurrence belongs to a predicted node, so no grey duplicate is drawn
                elif sp in index_node:
                    ends.append(index_node[sp])
                    by_index = True
                else:
                    gid = f"ghost-{sp[0]}-{sp[1]}"
                    ghosts.setdefault(gid, {
                        "id": gid, "name": " ".join(doc.tokens[sp[0] : sp[1]]), "canonical_name": NA, "type": gold_type.get(sp, NA), "surfaces": [" ".join(doc.tokens[sp[0] : sp[1]])],
                        "n_spans": 1, "spans": [list(sp)], "sentence": sentence_of(sp[0]), "ghost": True, "gold_entity_match": True, "gold_entity_typed_match": True,
                    })  # fmt: skip
                    ends.append(gid)
            edges.append({
                "id": f"{doc.doc_key}-g{miss_i}", "kind": "gold_missed", "s": ends[0], "t": ends[1], "rel": r.relation, "statement": NA, "quote": NA,
                "sentence": item["sentence"], "qual": NA, "model_direction": NA, "matches_gold": False, "grounded": True, "confidence": NA, "code": item["code"], "attached_by_index": by_index,
            })  # fmt: skip
            miss_i += 1
        nodes += list(ghosts.values())
        nid = {n["id"] for n in nodes}
        assert all(e["s"] in nid and e["t"] in nid for e in edges)
        lay = force_layout([n["id"] for n in nodes], [(e["s"], e["t"]) for e in edges], seed=7)
        for n in nodes:
            n["fx"], n["fy"] = lay[n["id"]]
        sc = res["per_document"][doc.doc_key]["scores"]
        att = res["per_document"][doc.doc_key]["attribution"]
        docs.append({
            "doc_id": doc.doc_key, "retained_prediction_path": f"data/processed/kg/{rid}/checkpoint.json",
            "predicted_nodes": len(pred["nodes"]), "predicted_entity_mentions": sum(len(n.mentions) for n in pred["nodes"]), "predicted_edges": len(pred["edges"]),
            "gold_entities": len(g.mentions), "gold_relations": len(g.relations), "e0_strict_relation_f1": sc["rel"]["f1"],
            "e0_relation_tp_fp_fn": [sc["rel"]["tp"], sc["rel"]["fp"], sc["rel"]["fn"]], "e0_relation_prf": [sc["rel"]["precision"], sc["rel"]["recall"], sc["rel"]["f1"]],
            "e0_entity_strict_f1": sc["entity_strict"]["f1"], "e0_entity_prf": [sc["entity_strict"]["precision"], sc["entity_strict"]["recall"], sc["entity_strict"]["f1"]],
            "edges_matching_gold": sum(1 for e in edges if e["kind"] == "pred" and e["matches_gold"]), "attribution": att["by_code"], "recovered_by_attribution": att["recovered"],
            "tokens": doc.tokens, "sentence_ends": doc.sentence_ends,
            "pred_spans": [[a, b, n.node_id] for n in pred["nodes"] for a, b in n.mentions],
            "gold_spans": [[m.span[0], m.span[1], m.type] for m in g.mentions], "gold_rels": gold_rels,
            "nodes": nodes, "edges": edges,
            "cr019": ({"variant": V19.PRIMARY, "rel_prf": [c19[V19.PRIMARY]["strict_relation_per_document"][doc.doc_key][k] for k in ("precision", "recall", "f1")],
                       "edges_matching": sum(1 for e in edges if e.get("matches_gold_cr019")), "edges_not_scored_frozen": sum(1 for e in edges if e["kind"] == "pred" and not e["grounded"])} if c19 else None),
        })  # fmt: skip
    micro = res["aggregates"]["rel"]["micro"]
    return {
        "docs": docs,
        "defs": relation_defs("configs/relations_scinlp.yaml"),
        "headline": {
            "relation_f1": micro["f1"],
            "precision": micro["precision"],
            "recall": micro["recall"],
            "ci_status": res["CI_status"],
        },
        "cr019": (
            {
                "variant": V19.PRIMARY,
                **{
                    k: c19[V19.PRIMARY]["strict_relation"][k] for k in ("precision", "recall", "f1")
                },
            }
            if c19
            else None
        ),
    }


def build(out: Path | None = None) -> Path:
    data = {
        "pd": build_pd(), "sci": build_scinlp(),
        "pd_heldout": {"e0_strict_f1": 0.053, "sections": ["4.4", "4.5", "5.4", "6.3", "7.1", "8.2", "9.3"]},
        "na": NA,
    }  # fmt: skip
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    html = (Path(__file__).with_name("kg_explorer.html")).read_text(encoding="utf-8")
    html = html.replace(
        "/*__TRACE_JS__*/",
        (Path(__file__).with_name("kg_explorer_trace.js")).read_text(encoding="utf-8"),
    )
    trace_b64 = ""
    try:  # CR-013: the derived trace of the production run, gzip + base64 (decoded lazily in the browser)
        from cumap.explain.viewer_adapter import build_trace_payload

        payload = build_trace_payload()
        if payload:
            trace_b64 = base64.b64encode(
                gzip.compress(
                    json.dumps(
                        payload, separators=(",", ":"), ensure_ascii=False, default=list
                    ).encode("utf-8"),
                    9,
                    mtime=0,
                )
            ).decode()
    except FileNotFoundError:
        trace_b64 = ""
    html = html.replace("/*__TRACE_B64__*/", trace_b64)
    html = html.replace(
        "/*__EVAL_JS__*/",
        (Path(__file__).with_name("kg_explorer_eval.js")).read_text(encoding="utf-8"),
    )
    eval_b64 = ""
    try:  # CR-013 STOP 4: the evaluation overlay has its OWN payload; it is never mixed into the production trace
        from cumap.explain.eval_adapter import build_eval_payload

        eval_b64 = base64.b64encode(
            gzip.compress(
                json.dumps(build_eval_payload(), separators=(",", ":"), ensure_ascii=False).encode(
                    "utf-8"
                ),
                9,
                mtime=0,
            )
        ).decode()
    except FileNotFoundError:
        eval_b64 = ""
    html = html.replace("/*__EVAL_B64__*/", eval_b64)
    score_b64 = ""
    try:  # CR-017 STOP 5: the scorecard has its OWN payload, rendered from reports/cr017/*.json (nothing recomputed)
        from cumap.cr017.scorecard import build_scorecard

        score_b64 = base64.b64encode(
            gzip.compress(
                json.dumps(build_scorecard(), separators=(",", ":"), ensure_ascii=False).encode(
                    "utf-8"
                ),
                9,
                mtime=0,
            )
        ).decode()
    except FileNotFoundError:
        score_b64 = ""
    html = html.replace("/*__SCORECARD_B64__*/", score_b64)
    target.write_text(
        html.replace(
            "/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        ),
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    p = build()
    d = json.loads(
        p.read_text(encoding="utf-8")
        .split("const DATA = ")[1]
        .split(";\n")[0]
        .replace("<\\/", "</")
    )
    print(
        "wrote",
        p,
        "pd",
        d["pd"]["stats"]["canonical_nodes"],
        d["pd"]["stats"]["accepted_edges"],
        [(x["doc_id"], x["predicted_nodes"], x["predicted_edges"]) for x in d["sci"]["docs"]],
    )
