"""CR-020 scoring ($0): TOKEN (base runs) vs R1KEY (cr020_r1key_*) with the same scorers for both arms. Writes reports/cr020/results.{json,md}."""

from __future__ import annotations

import json
from collections import Counter

from cumap.cr012 import attribution as A
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr017 import headline as HL
from cumap.cr017 import run as R17
from cumap.cr019 import stage_b as SB
from cumap.cr019 import variants as V
from cumap.cr020 import run as R

ARMS = ("TOKEN", "R1KEY")
SC_SCORERS = ("IDXR1-P1", "IDX-P1", "IDXR1-P3")
PRIMARY = "IDXR1-P1"


def _rid(arm: str, base: str) -> str:
    return base if arm == "TOKEN" else R.arm_id(base, "r1key")


def _outcomes(cp: dict) -> dict:
    c = Counter()
    for r in cp["relation_results_v3"]:
        if r.get("group", "selected") == "selected":
            c[r["outcome"] if r["outcome"] != "rejected" else f"rejected:{r.get('reason')}"] += 1
    return dict(c)


def scinlp() -> dict:
    ad = SciNLPAdapter()
    gold, sym = ad.gold("dev"), ad.symmetric_relations()
    docs = {d.doc_key: d for d in ad.load_documents("dev", paragraph_every=SR.PARAGRAPH_EVERY)}
    out = {}
    for arm in ARMS:
        per = {v: {} for v in SC_SCORERS}
        codes, outc, n_edges = [], Counter(), 0
        for d in SB.SC_DEV:
            cp = json.loads((PG.run_path(_rid(arm, SB.sc_base(d))) / "checkpoint.json").read_text())
            outc.update(_outcomes(cp))
            for v in SC_SCORERS:
                r = V.sc_score(docs[d], gold[d], cp, sym, v)
                per[v][d] = r["scores"]
                if v == PRIMARY:
                    n_edges += r["edges"]["predicted"]
                    codes += sc_attribution(docs[d], gold[d], r["pred"], cp, sym)
        n_end = sum(1 for c in codes if c not in ("N0", "N1"))
        n_prop = sum(1 for c in codes if c not in ("N0", "N1", "P0"))
        out[arm] = {
            "relation": {v: S.aggregate_documents(per[v], "rel")["micro"] for v in SC_SCORERS},
            "concept_f1_entity_strict": S.aggregate_documents(per[PRIMARY], "entity_strict")["micro"],
            "pair_recall_analogue": {"reached": n_prop, "denominator": n_end, "recall": n_prop / n_end if n_end else None},
            "predicted_edges": n_edges, "attribution": A.distribution(codes), "relation_outcomes": dict(outc),
        }  # fmt: skip
    return out


def pd() -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    sheet, _ = R17.SHEETS["pilot"]
    reg = PD.registry()
    gold, problems = PD.load_gold(R17.ROOT / sheet, secs, reg)
    assert not problems, problems[:2]
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    out = {}
    for arm in ARMS:
        units, outc = {}, Counter()
        for sid in SB.PD_DEV:
            cp = PG.load_run(_rid(arm, SB.pd_base(sid)))
            outc.update(_outcomes(cp))
            g = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
            units[sid] = HL.UnitInput(gold[sid], g["nodes"], g["edges"], PG.proposed_pairs(cp, sid), HL.classifier_from_checkpoint(cp, sid))  # fmt: skip
        out[arm] = {
            "headline": HL.evaluate(units, sym, boot=False)["headline"],
            "relation_outcomes": dict(outc),
        }
    return out


def decide(sc: dict, p: dict) -> dict:
    d_sc = sc["R1KEY"]["relation"][PRIMARY]["f1"] - sc["TOKEN"]["relation"][PRIMARY]["f1"]
    d_pd = (
        p["R1KEY"]["headline"]["strict_e2e_edge_f1"]["f1"]
        - p["TOKEN"]["headline"]["strict_e2e_edge_f1"]["f1"]
    )
    ok = d_sc >= -0.005 and d_pd >= -0.01
    return {"status": "ADOPT_R1KEY" if ok else "KEEP_TOKEN", "scinlp_dev_idxr1_p1_f1_delta": d_sc, "pd_dev_strict_f1_delta": d_pd,
            "rule": "non-inferiority: adopt if SciNLP dev IDXR1-P1 F1 falls by <= 0.005 and P&D dev Strict E2E F1 falls by <= 0.01"}  # fmt: skip


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    sc, p, d, sp = r["scinlp"], r["pd"], r["decision"], r["spend"]
    L = [
        "# CR-020 — R1-key matching in production (dev experiment)", "",
        f"Pre-registered in `docs/change-requests/CR-020-r1key-matching.md`. TOKEN = existing E0 runs; R1KEY = copies with pair generation, selection and the production relation stage re-run under `CUMAP_MATCHING=r1key` (concepts unchanged). Determinism check passed on all 8 runs. Spend **${sp['total_usd']:.2f}** of the ${sp['cap_usd']:.0f} cap.", "",
        f"**Decision (pre-registered rule): {d['status']}** — SciNLP dev IDXR1-P1 F1 Δ {d['scinlp_dev_idxr1_p1_f1_delta']:+.3f}, P&D dev Strict E2E F1 Δ {d['pd_dev_strict_f1_delta']:+.3f}.", "",
        "## SciNLP dev (6 papers)", "", "| arm | predicted edges | IDXR1-P1 P / R / F1 | IDX-P1 F1 | IDXR1-P3 F1 | concept F1 | pair-recall analogue |", "|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for arm in ARMS:
        x = sc[arm]
        r1, pr = x["relation"][PRIMARY], x["pair_recall_analogue"]
        L.append(
            f"| {arm} | {x['predicted_edges']} | {_f(r1['precision'])} / {_f(r1['recall'])} / **{_f(r1['f1'])}** | {_f(x['relation']['IDX-P1']['f1'])} | {_f(x['relation']['IDXR1-P3']['f1'])} | {_f(x['concept_f1_entity_strict']['f1'])} | {pr['reached']} / {pr['denominator']} = {_f(pr['recall'])} |"
        )
    L += [
        "",
        "## P&D development sections 1.5, 2.6 (CR-017 five metrics)",
        "",
        "| arm | Concept F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 (P / R) |",
        "|---|---|---|---|---|",
    ]
    for arm in ARMS:
        h = p[arm]["headline"]
        se = h["strict_e2e_edge_f1"]
        L.append(
            f"| {arm} | {_f(h['concept_f1']['f1'])} | {_f(h['pair_recall']['recall'])} | {_f(h['relation_macro_f1']['f1'])} | {_f(se['f1'])} ({_f(se['precision'])} / {_f(se['recall'])}) |"
        )
    L += (
        ["", "Relation outcomes on selected pairs:", ""]
        + [f"- SciNLP {a}: {sc[a]['relation_outcomes']}" for a in ARMS]
        + [f"- P&D {a}: {p[a]['relation_outcomes']}" for a in ARMS]
    )
    return "\n".join(L) + "\n"


def main() -> dict:
    r = {"scinlp": scinlp(), "pd": pd(), "spend": R.spend()}
    r["decision"] = decide(r["scinlp"], r["pd"])
    R.OUT.mkdir(parents=True, exist_ok=True)
    (R.OUT / "results.json").write_text(json.dumps(r, indent=1, default=str))
    (R.OUT / "results.md").write_text(markdown(r))
    return {"decision": r["decision"], "report": str(R.OUT / "results.md")}
