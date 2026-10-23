"""CR-012 STOP 4 scoring and report. Reads finished runs and the frozen gold; writes only `reports/cr012/stop4_*`. P&D and SciNLP are reported
separately and never pooled into one number.

    uv run python -m cumap.cr012.stop4_score --tag heldout
    uv run python -m cumap.cr012.stop4_score --tag pilot --pd-sheet <sheet> --pd-sections 1.5 --no-scinlp     # code-path check on development data
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import attribution as A
from cumap.cr012 import bootstrap as B
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.llm.cost import spend_from_log

REPORTS = REPO_ROOT / "reports/cr012"


def no_relation_pairs(cp: dict, unit: str) -> set[frozenset[str]]:
    return {
        frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
        for r in cp["relation_results_v3"]
        if r["pair"]["section_id"] == unit
        and r.get("group", "selected") == "selected"
        and r["outcome"] != "edge"
    }


def provenance(nodes, edges, stats: dict) -> dict:
    n, e = len(nodes), len(edges)
    n_ok = sum(1 for x in nodes if x.mentions)
    e_ok = sum(1 for x in edges if x.evidence_span is not None)
    return {
        "nodes": n, "nodes_with_grounded_span": n_ok, "unsupported_node_rate": (n - n_ok) / n if n else 0.0,
        "edges": e, "edges_with_located_evidence_quote": e_ok, "unsupported_edge_rate": (e - e_ok) / e if e else 0.0,
        "edges_dropped_without_endpoint_node": stats.get("edges_without_endpoint_node", 0),
        "provenance_completeness": (n_ok + e_ok) / (n + e) if n + e else 1.0,
    }  # fmt: skip


def usd(rid: str) -> float:
    return round(spend_from_log(get_settings(), rid), 4)


# ---------------------------------------------------------------- P&D
def score_pd(
    tag: str, sheet: Path, sections: list[str], levels=("E0", "E1", "E2", "E3", "E4")
) -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(sheet, secs, PD.registry())
    assert not problems, problems[:3]
    sym = {r.name for r in PD.registry().all_relations() if r.symmetric}
    out: dict = {"levels": {}}
    for lv in levels:
        per, rows, codes_all = {}, {}, []
        for sid in sections:
            rid = f"cr012_{tag}_{sid.replace('.', '_')}_{lv}"
            f = REPO_ROOT / "data/processed/kg" / rid / "checkpoint.json"
            if not f.exists():
                continue
            cp = PG.load_run(rid)
            if not cp.get("relation_results_v3"):
                continue
            pg = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
            prop = PG.proposed_pairs(cp, sid)
            r = S.score_graph_unit(gold[sid], pg["nodes"], pg["edges"], sym, proposed_pairs=prop)
            traces = A.build_traces(
                gold[sid], pg["nodes"], pg["edges"], prop, no_relation_pairs(cp, sid), sym
            )
            codes = [A.attribute(t) for t in traces]
            codes_all += codes
            per[sid] = r
            rows[sid] = {
                "strict_e2e_edge": r["strict_e2e_edge"].to_dict(),
                "canonical_node": r["canonical_node"].to_dict(),
                "canonical_node_typed": r["canonical_node_typed"].to_dict(),
                "concept_mentions_typed": r["concept_mentions_typed"].to_dict(),
                "identity_pairwise": r["identity"]["pairwise"],
                "identity_bcubed": r["identity"]["bcubed"],
                "pair_recall": r["pair_recall"],
                "relation_conditional": r["relation_conditional"],
                "qualifier_accuracy": r["qualifier_accuracy"],
                "false_merge_nodes": len(r["alignment"]["false_merge_nodes"]),
                "split_concepts": len(r["alignment"]["split_concepts"]),
                "provenance": provenance(pg["nodes"], pg["edges"], pg["stats"]),
                "attribution": A.distribution(codes),
                "graph_stats": pg["stats"],
                "usd": usd(rid),
            }
        if not per:
            continue
        pooled = S.pool_graph_units(per)
        units = {k: v["strict_e2e_edge"] for k, v in per.items()}
        pr = [v["pair_recall"] for v in rows.values()]
        den, hit = (
            sum(p["denominator"] for p in pr),
            sum(p["reached_classification"] or 0 for p in pr),
        )
        rc = Counter()
        for v in rows.values():
            rc.update(v["relation_conditional"])
        out["levels"][lv] = {
            "sections": sorted(per),
            "pooled_strict_e2e": pooled.to_dict(),
            "bootstrap_by_section_95": B.cluster_bootstrap(units, descriptive_label=None),
            "macro_mean_strict_f1": sum(u.f1 for u in units.values()) / len(units),
            "pooled_canonical_node": S.pool_graph_units(per, "canonical_node").to_dict(),
            "pooled_typed_mentions": S.pool_graph_units(per, "concept_mentions_typed").to_dict(),
            "identity_pairwise_f1_macro": sum(v["identity_pairwise"]["f1"] for v in rows.values()) / len(rows),
            "identity_bcubed_f1_macro": sum((v["identity_bcubed"] or {}).get("f1", 0.0) for v in rows.values()) / len(rows),
            "pair_recall_pooled": {"reached": hit, "reachable_denominator": den, "rate": hit / den if den else None,
                                   "missing_endpoint_excluded": sum(p["missing_endpoint_excluded"] for p in pr)},
            "relation_given_correct_endpoints_pooled": dict(rc),
            "attribution_pooled": A.distribution(codes_all),
            "usd": round(sum(v["usd"] for v in rows.values()), 4),
            "per_section": rows,
        }  # fmt: skip
    return out


# ---------------------------------------------------------------- SciNLP
def sc_attribution(doc, gold, pred, cp, sym) -> list[str | None]:
    nodes, edges = pred["nodes"], pred["edges"]
    prop, norel = PG.proposed_pairs(cp, doc.doc_key), no_relation_pairs(cp, doc.doc_key)
    by_span: dict = {}
    for n in nodes:
        for s in n.mentions:
            by_span.setdefault(s, []).append(n.node_id)
    spans = list(by_span)
    by_pair: dict = {}
    for e in edges:
        by_pair.setdefault(frozenset((e.src, e.tgt)), []).append(e)
    codes = []
    for r in gold.relations:
        sts, ns = [], []
        for sp in (r.src_span, r.tgt_span):
            exact = by_span.get(sp, [])
            ns.append(exact)
            sts.append(
                "exact"
                if exact
                else "partial"
                if any(a[0] < sp[1] and sp[0] < a[1] for a in spans)
                else "absent"
            )
        combos = [(a, b) for a in ns[0] for b in ns[1] if a != b]
        proposed = tuple(frozenset(c) in prop for c in combos)
        norel_t = tuple(frozenset(c) in norel for c in combos)
        preds, found_dir = [], False
        for a, b in combos:
            for e in by_pair.get(frozenset((a, b)), []):
                preds.append(e.relation)
                if e.relation == r.relation and (e.src == a or r.relation in sym):
                    found_dir = True
        t = A.EdgeTrace((str(r.src_span), str(r.tgt_span)), (sts[0], sts[1]), (False, False), (False, False), proposed, norel_t,
                        tuple(preds), r.relation, r.relation in sym, r.relation in preds and not found_dir, True, True, True)  # fmt: skip
        codes.append(A.attribute(t))
    return codes


def score_sc(tag: str, split: str, docs: list[str], levels=("E0", "E1", "E3", "E4")) -> dict:
    ad = SciNLPAdapter()
    gold_all = ad.gold(split)
    dmap = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    sym = ad.symmetric_relations()
    out: dict = {"split": split, "levels": {}}
    for lv in levels:
        per, rows, codes_all = {}, {}, []
        for dk in docs:
            rid = f"cr012_scinlp_{tag}_{dk.replace('.', '_').replace('-', '_')}_{lv}"
            f = REPO_ROOT / "data/processed/kg" / rid / "checkpoint.json"
            if not f.exists():
                continue
            cp = json.loads(f.read_text())
            if not cp.get("relation_results_v3"):
                continue
            doc, g = dmap[dk], gold_all[dk]
            pred = SR.predict(doc, cp)
            rels, _ = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
            res = S.score_scinlp_unit(g, S.project_nodes_to_mentions(pred["nodes"]), rels, sym)
            per[dk] = res
            codes = sc_attribution(doc, g, pred, cp, sym)
            codes_all += codes
            reach = [c for c in codes]  # attribution per gold relation
            n_end_ok = sum(1 for c in codes if c not in ("N0", "N1"))
            n_prop = sum(1 for c in codes if c not in ("N0", "N1", "P0"))
            rows[dk] = {
                "scores": {k: v.to_dict() for k, v in res.items()},
                "gold_relations": len(g.relations),
                "pair_recall": {"gold_relations_with_both_endpoints_predicted": n_end_ok, "pair_reached_classification": n_prop,
                                "rate": n_prop / n_end_ok if n_end_ok else None},
                "relation_given_correct_endpoints": {"classified_pairs": n_prop,
                                                     "relation_correct": sum(1 for c in codes if c is None),
                                                     "wrong_relation": codes.count("R1"), "wrong_direction": codes.count("R2"), "no_relation": codes.count("R0")},
                "provenance": provenance(pred["nodes"], pred["edges"], {"edges_without_endpoint_node": pred["stats"]["ungrounded_dropped"]}),
                "prediction_stats": pred["stats"],
                "attribution": A.distribution(codes),
                "usd": usd(rid),
            }  # fmt: skip
            del reach
        if not per:
            continue
        agg = {
            m: S.aggregate_documents(per, m)
            for m in ("entity_strict", "entity_typed", "rel", "rel_plus")
        }
        out["levels"][lv] = {
            "documents": sorted(per),
            "aggregates": agg,
            "headline_relation_micro": agg["rel"]["micro"],
            "CI_status": agg["rel"]["CI_status"],
            "attribution_pooled": A.distribution(codes_all),
            "identity_metrics": "NOT_SUPPORTED",
            "usd": round(sum(v["usd"] for v in rows.values()), 4),
            "per_document": rows,
        }  # fmt: skip
    return out


def md(pd_res: dict | None, sc_res: dict | None, tag: str) -> str:
    L = [
        f"# CR-012 STOP 4 results (`{tag}`)",
        "",
        "P&D-E2E and SciNLP are reported separately; there is no pooled number.",
        "",
    ]
    if pd_res and pd_res["levels"]:
        L += ["## P&D-E2E (canonical graph, section bootstrap)", "",
              "| level | sections | strict E2E P / R / F1 (pooled) | 95% section-bootstrap F1 | pair recall | canon node F1 | typed mention F1 | pairwise id F1 | B-cubed F1 | $ |",
              "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for lv, v in pd_res["levels"].items():
            q, ci = v["pooled_strict_e2e"], v["bootstrap_by_section_95"]
            pr = v["pair_recall_pooled"]
            L.append(f"| {lv} | {len(v['sections'])} | {q['precision']:.3f} / {q['recall']:.3f} / {q['f1']:.3f} | [{ci['ci']['f1'][0]:.3f}, {ci['ci']['f1'][1]:.3f}] ({ci['CI_status']}) | {pr['reached']}/{pr['reachable_denominator']} | {v['pooled_canonical_node']['f1']:.3f} | {v['pooled_typed_mentions']['f1']:.3f} | {v['identity_pairwise_f1_macro']:.3f} | {v['identity_bcubed_f1_macro']:.3f} | {v['usd']} |")  # fmt: skip
        L += ["", "Earliest-failure attribution (pooled over sections; S0/S1 not applicable):", "", "| level | misses | " + " | ".join(A.CODES) + " | recovered |", "|---|---|" + "---|" * (len(A.CODES) + 1)]  # fmt: skip
        for lv, v in pd_res["levels"].items():
            a = v["attribution_pooled"]
            L.append(
                f"| {lv} | {a['misses']} | "
                + " | ".join(str(a["by_code"][c]) for c in A.CODES)
                + f" | {a['recovered']} |"
            )
        L += [
            "",
            "Relation accuracy given correct endpoints (pooled; gold pairs with a predicted edge):",
            "",
        ]
        for lv, v in pd_res["levels"].items():
            c = v["relation_given_correct_endpoints_pooled"]
            L.append(f"- {lv}: {c.get('gold_with_proposed_edge', 0)} pairs, relation correct {c.get('relation_correct', 0)}, direction correct {c.get('direction_correct', 0)}")  # fmt: skip
        L += ["", "Provenance and unsupported rates (E0, pooled over sections):", ""]
        if "E0" in pd_res["levels"]:
            ps = [x["provenance"] for x in pd_res["levels"]["E0"]["per_section"].values()]
            n, e = sum(p["nodes"] for p in ps), sum(p["edges"] for p in ps)
            L.append(f"- unsupported node rate {sum(p['nodes'] - p['nodes_with_grounded_span'] for p in ps) / max(n, 1):.3f}; unsupported edge rate {sum(p['edges'] - p['edges_with_located_evidence_quote'] for p in ps) / max(e, 1):.3f}; provenance completeness {sum(p['provenance_completeness'] * (p['nodes'] + p['edges']) for p in ps) / max(n + e, 1):.3f}")  # fmt: skip
        L.append("")
    if sc_res and sc_res["levels"]:
        L += ["## SciNLP (mention level, 3 test documents, CI_status NOT_EVALUABLE_SMALL_N)", "",
              "| level | relation strict micro P / R / F1 | per-document F1 | macro F1 | min / max doc F1 | entity strict micro F1 | entity typed micro F1 | $ |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for lv, v in sc_res["levels"].items():
            a = v["aggregates"]["rel"]
            m = a["micro"]
            pdf = ", ".join(
                f"{d.split('.')[0][:12]}={x['f1']:.3f}" for d, x in a["per_document"].items()
            )
            L.append(f"| {lv} | {m['precision']:.3f} / {m['recall']:.3f} / {m['f1']:.3f} | {pdf} | {a['macro_mean']['f1']:.3f} | {a['min_document_f1']:.3f} / {a['max_document_f1']:.3f} | {v['aggregates']['entity_strict']['micro']['f1']:.3f} | {v['aggregates']['entity_typed']['micro']['f1']:.3f} | {v['usd']} |")  # fmt: skip
        L += ["", "Mention-level earliest-failure attribution over gold relations (C0 / C1 not applicable: no identity gold):", "", "| level | misses | " + " | ".join(A.CODES) + " | recovered |", "|---|---|" + "---|" * (len(A.CODES) + 1)]  # fmt: skip
        for lv, v in sc_res["levels"].items():
            a = v["attribution_pooled"]
            L.append(
                f"| {lv} | {a['misses']} | "
                + " | ".join(str(a["by_code"][c]) for c in A.CODES)
                + f" | {a['recovered']} |"
            )
        L += ["", "Identity metrics (canonical-node F1, pairwise, B-cubed, E2): NOT_SUPPORTED. No bootstrap over entities or edges; the diagnostic document bootstrap is DESCRIPTIVE_SMALL_N_ONLY and is not reported as a CI.", ""]  # fmt: skip
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="heldout")
    ap.add_argument("--pd-sheet", default="data/gold/pd_e2e_test_blind.csv")
    ap.add_argument("--pd-sections", nargs="*")
    ap.add_argument("--no-scinlp", action="store_true")
    ap.add_argument("--sc-split", default="test")
    ap.add_argument("--sc-docs", nargs="*")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    secs = a.pd_sections or sorted({r["section_id"] for r in PD.load_sections()} & {s for s in __import__("cumap.cr012.stop4", fromlist=["x"]).pd_sections()})  # fmt: skip
    pd_res = score_pd(a.tag, Path(a.pd_sheet), secs)
    sc_res = None
    if not a.no_scinlp:
        docs = a.sc_docs or [d.doc_key for d in SciNLPAdapter().load_documents(a.sc_split)]
        sc_res = score_sc(a.tag, a.sc_split, docs)
    out = a.out or f"stop4_{a.tag}"
    (REPORTS / f"{out}_results.json").write_text(
        json.dumps({"pd": pd_res, "scinlp": sc_res}, indent=1, default=str), encoding="utf-8"
    )
    text = md(pd_res, sc_res, a.tag)
    (REPORTS / f"{out}_results.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
