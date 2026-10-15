"""CR-019 Stage B scoring ($0): SINGLE vs MULTI on SciNLP dev (IDX-P1 primary, IDX-P3, FROZEN, FROZEN-UNPLACED-FP) and on the P&D
development sections (CR-017 five metrics, FROZEN and IDX node positions). Writes reports/cr019/stage_b.{json,md}; reads runs read-only."""

from __future__ import annotations

import json
from collections import Counter

from cumap.cr012 import attribution as A
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import no_relation_pairs, sc_attribution
from cumap.cr017 import headline as HL
from cumap.cr017 import run as R17
from cumap.cr019 import stage_b as B
from cumap.cr019 import variants as V

ARMS = ("SINGLE", "MULTI")


def _rid(arm: str, base: str) -> str:
    return base if arm == "SINGLE" else B.multi_id(base)


def _outcomes(cp: dict) -> dict:
    c = Counter()
    for r in cp["relation_results_v3"]:
        if r.get("group", "selected") != "selected":
            continue
        c[r["outcome"] if r["outcome"] != "rejected" else f"rejected:{r.get('reason')}"] += 1
    return dict(c)


def scinlp() -> dict:
    ad = SciNLPAdapter()
    gold, sym = ad.gold("dev"), ad.symmetric_relations()
    docs = {d.doc_key: d for d in ad.load_documents("dev", paragraph_every=SR.PARAGRAPH_EVERY)}
    out: dict = {}
    for arm in ARMS:
        per = {v: {} for v in V.SC_VARIANTS}
        edges = {v: Counter() for v in V.SC_VARIANTS}
        codes, outc, used = [], Counter(), []
        for d in B.SC_DEV:
            rid = _rid(arm, B.sc_base(d))
            f = PG.run_path(rid) / "checkpoint.json"
            if not f.exists():
                continue
            cp = json.loads(f.read_text())
            if not cp.get("relation_results_v3"):
                continue
            used.append(d)
            outc.update(_outcomes(cp))
            for v in V.SC_VARIANTS:
                r = V.sc_score(docs[d], gold[d], cp, sym, v)
                per[v][d] = r["scores"]
                edges[v].update(
                    {k: n for k, n in r["edges"].items() if k != "unplaced_counted_as_fp"}
                )
                if v == V.PRIMARY:
                    codes += sc_attribution(docs[d], gold[d], r["pred"], cp, sym)
        out[arm] = {
            "documents": used,
            "variants": {
                v: {"strict_relation": S.aggregate_documents(per[v], "rel")["micro"], "concept_f1_entity_strict": S.aggregate_documents(per[v], "entity_strict")["micro"], "edges": dict(edges[v])}
                for v in V.SC_VARIANTS if per[v]
            },
            "attribution_idx_p1": A.distribution(codes),
            "relation_outcomes": dict(outc),
        }  # fmt: skip
    return out


def pd() -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    sheet, _sections = R17.SHEETS["pilot"]
    reg = PD.registry()
    gold, problems = PD.load_gold(R17.ROOT / sheet, secs, reg)
    assert not problems, problems[:2]
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    out: dict = {}
    for arm in ARMS:
        out[arm] = {}
        for pos in ("FROZEN", "IDX"):
            units, outc = {}, Counter()
            for sid in B.PD_DEV:
                rid = _rid(arm, B.pd_base(sid))
                if not (PG.run_path(rid) / "checkpoint.json").exists():
                    continue
                cp = PG.load_run(rid)
                if not cp.get("relation_results_v3"):
                    continue
                outc.update(_outcomes(cp))
                g = (
                    PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
                    if pos == "FROZEN"
                    else V.pd_graph_indexed(cp, sid, secs[sid], PD.sentence_offsets(secs[sid]))
                )
                units[sid] = HL.UnitInput(gold[sid], g["nodes"], g["edges"], PG.proposed_pairs(cp, sid), HL.classifier_from_checkpoint(cp, sid))  # fmt: skip
            if not units:
                continue
            ev = HL.evaluate(units, sym, boot=False)
            codes = []
            for sid, u in units.items():
                cp = PG.load_run(_rid(arm, B.pd_base(sid)))
                codes += [
                    A.attribute(t)
                    for t in A.build_traces(
                        u.gold, u.nodes, u.edges, u.proposed_pairs, no_relation_pairs(cp, sid), sym
                    )
                ]
            out[arm][pos] = {"sections": sorted(units), "headline": ev["headline"], "attribution": A.distribution(codes), "relation_outcomes": dict(outc)}  # fmt: skip
    return out


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def recommend(sc: dict, p: dict) -> dict:
    try:
        d_sc = (
            sc["MULTI"]["variants"][V.PRIMARY]["strict_relation"]["f1"]
            - sc["SINGLE"]["variants"][V.PRIMARY]["strict_relation"]["f1"]
        )
        d_pd = (
            p["MULTI"]["FROZEN"]["headline"]["strict_e2e_edge_f1"]["f1"]
            - p["SINGLE"]["FROZEN"]["headline"]["strict_e2e_edge_f1"]["f1"]
        )
    except KeyError:
        return {"status": "INCOMPLETE"}
    ok = d_sc >= 0.02 and d_pd >= -0.01
    return {"status": "RECOMMEND_MULTI" if ok else "KEEP_SINGLE", "scinlp_dev_idx_p1_f1_delta": d_sc, "pd_dev_strict_f1_delta": d_pd,
            "rule": "MULTI if SciNLP dev IDX-P1 F1 rises >= 0.02 and P&D dev Strict E2E F1 falls by no more than 0.01"}  # fmt: skip


def markdown(r: dict) -> str:
    sc, p, rec, sp = r["scinlp"], r["pd"], r["recommendation"], r["spend"]
    L = ["# CR-019 Stage B — multi-sentence evidence for relation classification", "",
         (f"Pre-registered 2026-10-15 (DECISIONS.md). SINGLE = production relation stage (family v3 / choice v4 / qualifiers v4, first co-occurring sentence); "
         f"MULTI = family v4 / choice v5 / qualifiers v5 on up to {B.K} co-occurring sentences of the same section, on a copy of the SINGLE run (same concepts, same selected pairs). "
         f"Data: SciNLP dev ({len(sc['SINGLE']['documents'])} papers, runs `cr012_scinlp_cr019dev_*_E0`) and P&D development sections {', '.join(B.PD_DEV)} (`cr012_pilot_*_E0`). "
         f"Spend: **${sp['total_usd']:.2f}** of the ${sp['cap_usd']:.0f} cap."), "",
         f"**Recommendation (pre-registered rule): {rec['status']}** — SciNLP dev IDX-P1 F1 Δ {rec.get('scinlp_dev_idx_p1_f1_delta', 0):+.3f}, P&D dev Strict E2E F1 Δ {rec.get('pd_dev_strict_f1_delta', 0):+.3f}.", "",
         "## SciNLP dev (strict relation, mention level)", "", "| arm | variant | edges placed / predicted | P | R | F1 |", "|---|---|---|---|---|---|"]  # fmt: skip
    for arm in ARMS:
        for v, x in sc[arm]["variants"].items():
            rel, e = x["strict_relation"], x["edges"]
            L.append(
                f"| {arm} | `{v}`{' (primary)' if v == V.PRIMARY else ''} | {e.get('placed', 0)} / {e.get('predicted', 0)} | {_f(rel['precision'])} | {_f(rel['recall'])} | **{_f(rel['f1'])}** |"
            )
    L += ["", "Relation-stage outcomes on selected pairs:", ""]
    for arm in ARMS:
        L.append(f"- {arm}: {sc[arm]['relation_outcomes']}")
    L += [
        "",
        "## P&D development sections (CR-017 five metrics)",
        "",
        "| arm | node positions | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 (P / R) |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in ARMS:
        for pos, x in p[arm].items():
            h = x["headline"]
            se = h["strict_e2e_edge_f1"]
            L.append(
                f"| {arm} | `{pos}` | {_f(h['concept_f1']['f1'])} | {_f(h['ancestor_hierarchy_f1'].get('f1'))} | {_f(h['pair_recall']['recall'])} | {_f(h['relation_macro_f1']['f1'])} | {_f(se['f1'])} ({_f(se['precision'])} / {_f(se['recall'])}) |"
            )
    L += ["", "Relation-stage outcomes on selected pairs:", ""]
    for arm in ARMS:
        if "FROZEN" in p[arm]:
            L.append(f"- {arm}: {p[arm]['FROZEN']['relation_outcomes']}")
    L += ["", f"Spend per run: {sp['per_run']}"]
    return "\n".join(L) + "\n"


def main() -> dict:
    r = {"scinlp": scinlp(), "pd": pd(), "spend": B.spend()}
    r["recommendation"] = recommend(r["scinlp"], r["pd"])
    B.OUT.mkdir(parents=True, exist_ok=True)
    (B.OUT / "stage_b.json").write_text(json.dumps(r, indent=1, default=str))
    (B.OUT / "stage_b.md").write_text(markdown(r))
    return {
        "recommendation": r["recommendation"],
        "spend": r["spend"]["total_usd"],
        "report": str(B.OUT / "stage_b.md"),
    }
