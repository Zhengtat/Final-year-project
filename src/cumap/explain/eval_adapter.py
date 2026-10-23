"""CR-013 STOP 4 evaluation overlay data. This is the ONLY explain module that reads evaluation material (the frozen CR-012 SciNLP / P&D held-out gold, the retained E0 predictions
and the frozen attribution functions). It consumes frozen outputs; it never runs a model, never regenerates predictions and never reinterprets gold. Every per-gold-relation
earliest-failure code is the frozen `cumap.cr012.attribution.attribute` applied to the facts of that relation, and the pooled counts are checked to equal the frozen
`reports/cr012/stop4_heldout_results.json` (a mismatch raises). The overlay is stored in its own payload (`eval-gz`), never in the production trace.

    uv run python -m cumap.explain.eval_adapter          # prints the consistency check"""

from __future__ import annotations

import functools
import json
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import attribution as A
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import no_relation_pairs
from cumap.explain.why_not_eval import EVAL_TEXT

KG = REPO_ROOT / "data/processed/kg"
FROZEN = REPO_ROOT / "reports/cr012/stop4_heldout_results.json"
PD_GOLD = REPO_ROOT / "data/gold/pd_e2e_test_blind.csv"
CODES = ("N0", "N1", "C0", "C1", "P0", "R0", "R1", "R2", "R3", "E0")
DECISIVE = {
    "N0": 0,
    "N1": 0,
    "C1": 2,
    "C0": 3,
    "P0": 4,
    "R0": 5,
    "R1": 6,
    "R2": 7,
    "R3": 8,
    "E0": 9,
}
CHECKS = [
    ("ep_src", "Source endpoint extracted with the gold span?"), ("ep_tgt", "Target endpoint extracted with the gold span?"), ("merge", "An endpoint node is a false merge?"), ("split", "An endpoint concept is split over several nodes?"),
    ("pair", "The endpoint pair was sent to relation classification?"), ("classified", "What the classifier decided for the pair"), ("relation", "The gold relation is among the predicted relations?"),
    ("direction", "Direction matches the gold?"), ("types", "Endpoint types and qualifiers acceptable?"), ("evidence", "Evidence valid?"),
]  # fmt: skip
NOTICE = "Failure codes describe where a benchmark gold object was lost in the frozen CR-012 run. They are observations, not decision rules for the production pipeline."


def checks_from_trace(t: A.EdgeTrace) -> list[list[str]]:
    st = {"exact": "yes", "partial": "partial span", "absent": "no"}
    proposed = any(t.pairs_proposed)
    if not t.pairs_proposed:
        classified = "n/a (no node pair)"
    elif not proposed:
        classified = "n/a (pair not sent)"
    elif t.predicted_relations:
        classified = "relation proposed"
    else:
        classified = "no relation"
    return [
        ["ep_src", st[t.span_status[0]]], ["ep_tgt", st[t.span_status[1]]], ["merge", "yes" if any(t.false_merge) else "no"], ["split", "yes" if any(t.split) else "no"],
        ["pair", "yes" if proposed else ("no" if t.pairs_proposed or any(s != "absent" for s in t.span_status) else "n/a")], ["classified", classified],
        ["relation", "yes" if t.gold_relation in t.predicted_relations and not t.reversed_only else "no"], ["direction", "wrong" if (t.reversed_only and not t.symmetric) else "ok"],
        ["types", "ok" if t.types_ok and t.qualifiers_ok else "failed"], ["evidence", "valid" if t.evidence_valid else "invalid"],
    ]  # fmt: skip


def _sentence(text: str, offs: list, sid_: str) -> str | None:
    n = int(sid_[1:]) if sid_[1:].isdigit() else 0
    return text[offs[n - 1][0] : offs[n - 1][1]] if 0 < n <= len(offs) else None


def frozen() -> dict:
    return json.loads(FROZEN.read_text())


def sc_traces(doc, gold, pred, cp, sym):
    """The mention-level traces of `stop4_score.sc_attribution` (same logic), returned with the facts instead of only the codes."""
    nodes, edges = pred["nodes"], pred["edges"]
    prop, norel = PG.proposed_pairs(cp, doc.doc_key), no_relation_pairs(cp, doc.doc_key)
    by_span: dict = {}
    for n in nodes:
        for s in n.mentions:
            by_span.setdefault(s, []).append(n.node_id)
    spans = list(by_span)
    name = {n.node_id: n.name for n in nodes}
    by_pair: dict = {}
    for e in edges:
        by_pair.setdefault(frozenset((e.src, e.tgt)), []).append(e)
    out = []
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
        t = A.EdgeTrace((str(r.src_span), str(r.tgt_span)), (sts[0], sts[1]), (False, False), (False, False), proposed, norel_t, tuple(preds), r.relation, r.relation in sym, r.relation in preds and not found_dir, True, True, True)  # fmt: skip
        out.append((t, [name[x] for x in ns[0] + ns[1]], sorted(set(preds))))
    return out


def build_scinlp() -> dict:
    fz = frozen()["scinlp"]["levels"]
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    gold_all = ad.gold("test")
    units, pooled = [], Counter()
    recovered_total = 0
    for doc in ad.load_documents("test", paragraph_every=SR.PARAGRAPH_EVERY):
        rid = f"cr012_scinlp_heldout_{doc.doc_key.replace('.', '_').replace('-', '_')}_E0"
        cp = json.loads((KG / rid / "checkpoint.json").read_text())
        pred = SR.predict(doc, cp)
        g = gold_all[doc.doc_key]
        traces = sc_traces(doc, g, pred, cp, sym)
        matched_keys = set()
        for e in pred["edges"]:
            proj, _ = S.project_edges_to_mentions(pred["nodes"], [e])
            matched_keys |= {S._rel_key(a, b, rel, sym) for a, b, rel, _s, _t in proj}
        starts = [0, *doc.sentence_ends[:-1]]
        rels, miss_i, counts = [], 0, Counter()
        for i, (r, (t, node_names, preds)) in enumerate(zip(g.relations, traces, strict=True)):
            code = A.attribute(t)
            strict = S._rel_key(r.src_span, r.tgt_span, r.relation, sym) in matched_keys
            si = max(j for j, s0 in enumerate(starts) if s0 <= r.src_span[0])
            item = {
                "i": i, "unit": doc.doc_key, "src": " ".join(doc.tokens[r.src_span[0] : r.src_span[1]]), "tgt": " ".join(doc.tokens[r.tgt_span[0] : r.tgt_span[1]]), "rel": r.relation, "sym": r.relation in sym,
                "sentence": " ".join(doc.tokens[starts[si] : doc.sentence_ends[si]]), "strict": strict, "code": code, "checks": checks_from_trace(t), "pred_rels": preds, "end_nodes": node_names[:6],
                "graph_edge": None,
            }  # fmt: skip
            if not strict:
                item["graph_edge"] = f"{doc.doc_key}-g{miss_i}"
                miss_i += 1
            rels.append(item)
            counts[code or "recovered"] += 1
        pooled.update(counts)
        res = fz["E0"]["per_document"][doc.doc_key]
        assert {k: v for k, v in res["attribution"]["by_code"].items()} == {
            c: counts.get(c, 0) for c in CODES
        }, doc.doc_key
        assert res["attribution"]["recovered"] == counts.get("recovered", 0), doc.doc_key
        recovered_total += counts.get("recovered", 0)
        stats = cp["selection_stats"]
        units.append({
            "id": doc.doc_key, "title": doc.doc_key.replace(".grobid", ""), "gold_n": len(g.relations), "counts": {c: counts.get(c, 0) for c in CODES}, "recovered": counts.get("recovered", 0),
            "f1": res["scores"]["rel"]["f1"], "prf": [res["scores"]["rel"]["precision"], res["scores"]["rel"]["recall"], res["scores"]["rel"]["f1"]],
            "tp_fp_fn": [res["scores"]["rel"]["tp"], res["scores"]["rel"]["fp"], res["scores"]["rel"]["fn"]],
            "selection": {"eligible_pool": stats["unique_candidate_pairs"], "selected": stats["selected"], "budget": stats["budget"]}, "relations": rels,
        })  # fmt: skip
    pf = fz["E0"]["attribution_pooled"]
    assert {c: pooled.get(c, 0) for c in CODES} == pf["by_code"] and recovered_total == pf[
        "recovered"
    ], "overlay counts differ from the frozen CR-012 results"
    micro = fz["E0"]["aggregates"]["rel"]
    return {
        "id": "scinlp", "label": "SciNLP held-out (3 test documents), E0", "unit_word": "document", "units": units,
        "headline": {"f1": micro["micro"]["f1"], "precision": micro["micro"]["precision"], "recall": micro["micro"]["recall"], "ci_status": micro["CI_status"], "metric": "strict relation F1 (mention level)"},
        "ladder": {lv.replace("E3", "E3-M").replace("E4", "E4-M"): v["aggregates"]["rel"]["micro"]["f1"] for lv, v in fz.items()},
        "not_applicable": ["C0", "C1"], "not_applicable_note": "SciNLP has no identity gold, so C0 / C1 are not applicable.", "frozen_attribution": pf,
    }  # fmt: skip


def build_pd() -> dict:
    fz = frozen()["pd"]["levels"]
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(PD_GOLD, secs, PD.registry())
    assert not problems
    sym = {r.name for r in PD.registry().all_relations() if r.symmetric}
    units, pooled, recovered_total = [], Counter(), 0
    for sid in sorted(gold, key=lambda x: [int(p) for p in x.split(".")]):
        g, text = gold[sid], secs[sid]
        rid = f"cr012_heldout_{sid.replace('.', '_')}_E0"
        cp = PG.load_run(rid)
        pg = PG.graph_for_sections(cp, {sid: text})[sid]
        prop = PG.proposed_pairs(cp, sid)
        traces = A.build_traces(g, pg["nodes"], pg["edges"], prop, no_relation_pairs(cp, sid), sym)
        al = S.align_nodes(pg["nodes"], g.mentions)
        node_name = {n.node_id: n.name for n in pg["nodes"]}
        cname = {c.concept_id: c.name for c in g.concepts}
        offs = PD.sentence_offsets(text)
        sent = functools.partial(_sentence, text, offs)
        rels_in = [r for r in g.relations if r.src_concept and r.tgt_concept]
        assert len(rels_in) == len(traces)
        rels, counts = [], Counter()
        for i, (r, t) in enumerate(zip(rels_in, traces, strict=True)):
            code = A.attribute(t)
            end_nodes = [
                node_name[x]
                for c in (r.src_concept, r.tgt_concept)
                for x in al["concept_to_nodes"].get(c, [])
            ]
            sentences = [x for x in (sent(e) for e in r.evidence) if x]
            rels.append({
                "i": i, "unit": sid, "src": cname[r.src_concept], "tgt": cname[r.tgt_concept], "rel": r.relation, "sym": r.relation in sym, "sentence": " ".join(sentences[:2]) if sentences else None, "strict": code is None,
                "code": code, "checks": checks_from_trace(t), "pred_rels": sorted(set(t.predicted_relations)), "end_nodes": end_nodes[:6], "graph_edge": None, "qualifiers": [list(q) for q in r.qualifiers],
            })  # fmt: skip
            counts[code or "recovered"] += 1
        pooled.update(counts)
        res = fz["E0"]["per_section"][sid]
        assert {c: counts.get(c, 0) for c in CODES} == res["attribution"]["by_code"] and counts.get(
            "recovered", 0
        ) == res["attribution"]["recovered"], sid
        recovered_total += counts.get("recovered", 0)
        stats = cp["selection_stats"]
        q = res["strict_e2e_edge"]
        units.append({
            "id": sid, "title": sid, "gold_n": len(rels), "counts": {c: counts.get(c, 0) for c in CODES}, "recovered": counts.get("recovered", 0), "f1": q["f1"], "prf": [q["precision"], q["recall"], q["f1"]], "tp_fp_fn": [q["tp"], q["fp"], q["fn"]],
            "selection": {"eligible_pool": stats["unique_candidate_pairs"], "selected": stats["selected"], "budget": stats["budget"]}, "relations": rels,
        })  # fmt: skip
    pf = fz["E0"]["attribution_pooled"]
    assert {c: pooled.get(c, 0) for c in CODES} == pf["by_code"] and recovered_total == pf[
        "recovered"
    ], "overlay counts differ from the frozen CR-012 results"
    q = fz["E0"]["pooled_strict_e2e"]
    ci = fz["E0"]["bootstrap_by_section_95"]
    return {
        "id": "pd", "label": "P&D held-out (7 sections, not the Chapters 1-3 graph), E0", "unit_word": "section", "units": units,
        "headline": {"f1": q["f1"], "precision": q["precision"], "recall": q["recall"], "ci_status": "DESCRIPTIVE_SMALL_N (" + ci["CI_status"] + ")", "ci": ci["ci"]["f1"], "metric": "STRICT_E2E_EDGE (canonical graph)"},
        "ladder": {lv: v["pooled_strict_e2e"]["f1"] for lv, v in fz.items()}, "not_applicable": [], "not_applicable_note": "", "frozen_attribution": pf,
    }  # fmt: skip


def build_eval_payload() -> dict:
    return {
        "meta": {
            "scope": "evaluation", "notice": NOTICE, "frozen_tag": "cr012-stop4-complete", "frozen_commit": "4697acb", "cr011": "NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION", "s0_s1": "S0 / S1 not applicable: CR-011 adopted no transformation",
            "oracle_note": "Oracle levels E1-E4 are conditional diagnostics (gold information injected at one stage), not an additive decomposition.", "single_annotator": "P&D held-out gold has a single human annotator.",
        },
        "codes": {c: EVAL_TEXT[c] for c in CODES}, "code_order": list(CODES), "decisive": DECISIVE, "checks": CHECKS,
        "datasets": {"scinlp": build_scinlp(), "pd": build_pd()},
    }  # fmt: skip


if __name__ == "__main__":
    p = build_eval_payload()
    for k, d in p["datasets"].items():
        tot = Counter()
        for u in d["units"]:
            tot.update(u["counts"])
        print(
            k,
            "gold relations",
            sum(u["gold_n"] for u in d["units"]),
            dict(tot),
            "recovered",
            sum(u["recovered"] for u in d["units"]),
            "== frozen:",
            d["frozen_attribution"]["by_code"] == dict(tot),
        )
    _ = Path
