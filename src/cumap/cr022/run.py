"""CR-022 Part A ($0, no model call). Reads frozen/rebuilt SciNLP runs and the SciNLP gold; writes only reports/cr022/.

    uv run python -m cumap.cr022.run

Determinism gate first (the scorer must reproduce the frozen SciNLP figures exactly), source-run hashes before and after, then A1-A3 for every
run set x grounding variant, always beside the frozen / CR-019 figure and naming its variant (rule 35)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PRF
from cumap.cr019 import run as R19
from cumap.cr019 import stage_b as SB
from cumap.cr019 import variants as V
from cumap.cr022 import scoring as C

OUT = REPO_ROOT / "reports/cr022"
RELEASE = "SciNLP-repo-e78342be"
FROZEN_012 = REPO_ROOT / "reports/cr012/stop4_heldout_results.json"
STAGE_A = REPO_ROOT / "reports/cr019/stage_a.json"
TOKEN_VARIANTS = ("FROZEN", "FROZEN-UNPLACED-FP", "IDX-P1")
R1_VARIANTS = (*TOKEN_VARIANTS, "IDXR1-P1")


def slug(d: str) -> str:
    return d.replace(".", "_").replace("-", "_")


SETS = [
    ("test", "frozen CR-012 STOP 4 (token matching)", lambda d: f"cr012_scinlp_heldout_{slug(d)}_E0", R19.SC_DOCS, TOKEN_VARIANTS),
    ("test", "CR-021 rebuild `cr021test` (r1key matching)", lambda d: f"cr012_scinlp_cr021test_{slug(d)}_E0", R19.SC_DOCS, R1_VARIANTS),
    ("dev", "CR-019 dev runs `cr019dev` (token matching)", SB.sc_base, SB.SC_DEV, TOKEN_VARIANTS),
    ("dev", "CR-021 dev rebuild `cr021dev` (r1key matching)", lambda d: f"cr012_scinlp_cr021dev_{slug(d)}_E0", SB.SC_DEV, R1_VARIANTS),
]  # fmt: skip


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source_files() -> list[Path]:
    fs = [FROZEN_012, STAGE_A]
    for split, _label, rid, docs, _v in SETS:
        fs += [PG.run_path(rid(d)) / "checkpoint.json" for d in docs]
    return [f for f in fs if f.exists()]


def prf_d(x: PRF) -> dict:
    return {
        "tp": x.tp,
        "fp": x.fp,
        "fn": x.fn,
        "precision": x.precision,
        "recall": x.recall,
        "f1": x.f1,
    }


def pool(prfs: list[PRF]) -> PRF:
    return PRF(sum(x.tp for x in prfs), sum(x.fp for x in prfs), sum(x.fn for x in prfs))


def score_set(split: str, rid, docs: list[str], variants: tuple[str, ...], ad, sym) -> dict:
    gold = ad.gold(split)
    dmap = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    out: dict = {
        "documents": [d for d in docs if (PG.run_path(rid(d)) / "checkpoint.json").exists()],
        "variants": {},
    }
    for v in variants:
        rel_docs, a1, a2, rows = [], {h: [] for h in C.HIER_SETS}, {h: [] for h in C.HIER_SETS}, []
        a2stats: dict[str, Counter] = {h: Counter() for h in C.HIER_SETS}
        cycles: dict[str, list] = {h: [] for h in C.HIER_SETS}
        gold_hier = {h: 0 for h in C.HIER_SETS}
        for d in out["documents"]:
            cp = json.loads((PG.run_path(rid(d)) / "checkpoint.json").read_text())
            doc, g = dmap[d], gold[d]
            p = C.place(doc, cp, v)
            rel_docs.append(C.direct_relation_prf(g, p, sym, v, None))
            for h, labs in C.HIER_SETS.items():
                a1[h].append(C.direct_relation_prf(g, p, sym, v, labs))
                gold_hier[h] += sum(1 for r in g.relations if r.relation in labs)
                x = C.surface_hierarchy(doc, g, p, v, labs)
                a2[h].append(x["prf"])
                a2stats[h].update({k: x[k] for k in ("gold_direct_edges", "gold_closure_pairs", "gold_pairs_added_by_closure", "pred_direct_edges", "pred_closure_pairs", "gold_mentions", "gold_surface_nodes", "gold_surface_collisions", "gold_self_relations", "unplaced_counted_as_fp")})  # fmt: skip
                cycles[h] += (
                    [{"doc": d, "gold": x["gold_cycles"], "pred": x["pred_cycles"]}]
                    if (x["gold_cycles"] or x["pred_cycles"])
                    else []
                )
            rows += C.relation_rows(doc, g, p, sym)
        macro = C.pooled_macro(rows)
        out["variants"][v] = {
            "relation_all_labels": prf_d(pool(rel_docs)),
            "A1_HIER_DIRECT": {
                h: {**prf_d(pool(a1[h])), "gold_relations_in_set": gold_hier[h]}
                for h in C.HIER_SETS
            },
            "A2_HIER_ANC_SURF": {
                h: {**prf_d(pool(a2[h])), **dict(a2stats[h]), "cycles": cycles[h]}
                for h in C.HIER_SETS
            },
            "A3_REL_MACRO_SCINLP": macro,
        }
    return out


# ---------------------------------------------------------------- determinism gate
def gate(ad, sym) -> dict:
    split, _label, rid, docs, _ = SETS[0]
    gold = ad.gold(split)
    dmap = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}
    per_doc_equal, mine, theirs = True, {}, {}
    for v in ("FROZEN", "FROZEN-UNPLACED-FP", "IDX-P1"):
        a, b = [], []
        for d in docs:
            cp = PG.load_run(rid(d))
            r = V.sc_score(dmap[d], gold[d], cp, sym, v)["scores"]["rel"]
            m = C.direct_relation_prf(gold[d], C.place(dmap[d], cp, v), sym, v, None)
            per_doc_equal &= (r.tp, r.fp, r.fn) == (m.tp, m.fp, m.fn)
            a.append(m)
            b.append(r)
        mine[v], theirs[v] = pool(a), pool(b)
    fz = json.loads(FROZEN_012.read_text())["scinlp"]["levels"]["E0"]["aggregates"]
    sa = json.loads(STAGE_A.read_text())["stage_a"]["scinlp"]
    r9 = (
        R19.stage_a_scinlp()
    )  # the CR-019 function itself, for concept F1 and the pair-recall analogue
    checks = {
        "A1_all_labels_equals_cr019_per_document_for_all_three_variants": per_doc_equal,
        "frozen_strict_relation_micro_equals_cr012_json": (mine["FROZEN"].tp, mine["FROZEN"].fp, mine["FROZEN"].fn) == (fz["rel"]["micro"]["tp"], fz["rel"]["micro"]["fp"], fz["rel"]["micro"]["fn"]) and abs(mine["FROZEN"].f1 - fz["rel"]["micro"]["f1"]) < 1e-12,
        "idx_p1_micro_equals_cr019_stage_a_json": (mine["IDX-P1"].tp, mine["IDX-P1"].fp, mine["IDX-P1"].fn) == tuple(sa["IDX-P1"]["strict_relation"][k] for k in ("tp", "fp", "fn")),
        "frozen_concept_f1_0.352": round(r9["FROZEN"]["concept_f1_entity_strict"]["f1"], 3) == 0.352 == round(fz["entity_strict"]["micro"]["f1"], 3),
        "frozen_pair_recall_0.545": round(r9["FROZEN"]["pair_recall_analogue"]["recall"], 3) == 0.545,
        "frozen_strict_edge_f1_0.050": round(mine["FROZEN"].f1, 3) == 0.050,
        "idx_p1_f1_0.195": round(mine["IDX-P1"].f1, 3) == 0.195,
    }  # fmt: skip
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "figures": {v: prf_d(x) for v, x in mine.items()},
    }


# ---------------------------------------------------------------- report
def f(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def triple(d: dict) -> str:
    return f"{f(d['precision'])} / {f(d['recall'])} / **{f(d['f1'])}** (tp {d['tp']}, fp {d['fp']}, fn {d['fn']})"


def markdown(r: dict) -> str:
    L = [
        "# CR-022 Part A: SciNLP hierarchy and relation scoring ($0, no model call)",
        "",
        "Written for: the project owner and Research. Part A only (Part B is not approved and was not run).",
        "",
        f"Dataset release `{RELEASE}`. Scorer: frozen CR-012 strict mention-level scorer (`cumap.cr012.scoring.score_scinlp_unit`), CR-017 `ancestor_closure` and `macro_from_rows`, CR-019 occurrence index; new code in `src/cumap/cr022/`. Every figure names its grounding variant; none replaces a frozen number.",
        "",
        "Grounding variants: " + "; ".join(f"`{k}` = {v}" for k, v in C.VARIANT_NOTE.items()) + ".",
        "",
        "## Determinism gate",
        "",
        "| check | result |",
        "|---|---|",
        *[f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in r["gate"]["checks"].items()],
        "",
        f"**Gate: {'PASSED' if r['gate']['passed'] else 'FAILED, no variant is reported'}.** Source hashes identical before and after: **{r['hashes_unchanged']}** ({r['n_hashed']} files).",
        "",
    ]
    if not r["gate"]["passed"]:
        return "\n".join(L)
    L += [
        "Hierarchy label sets (owner decision at STOP 1, both shown): `H2 {subclassOf, subtaskOf}` is the spec default; `H1 {subclassOf}` only. `partOf` is excluded from both, as CR-017 uses `{is_a}` only.",
        "",
        "Reading note: the frozen SciNLP strict relation number is mention level and the occurrence index changes only which mentions a node owns; no number here is an official SciNLP score.",
        "",
    ]
    for split in ("test", "dev"):
        for s in r["sets"].values():
            if s["split"] != split:
                continue
            L += [
                f"## {split.upper()} · {s['label']}",
                "",
                f"Documents ({len(s['documents'])}): {', '.join(s['documents'])}.",
                "",
            ]
            vs = s["variants"]
            L += [
                "### Frozen / CR-019 reference: strict relation P / R / F1, all labels",
                "",
                "| variant | P / R / F1 |",
                "|---|---|",
            ]
            L += [f"| `{v}` | {triple(x['relation_all_labels'])} |" for v, x in vs.items()]
            for h in C.HIER_SETS:
                L += [
                    "",
                    f"### A1 HIER-DIRECT, {h}: direct hierarchy edge P / R / F1 (gold relations in set: {next(iter(vs.values()))['A1_HIER_DIRECT'][h]['gold_relations_in_set']})",
                    "",
                    "| variant | P / R / F1 |",
                    "|---|---|",
                ]
                L += [f"| `{v}` | {triple(x['A1_HIER_DIRECT'][h])} |" for v, x in vs.items()]
                L += [
                    "",
                    f"### A2 HIER-ANC-SURF, {h}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)",
                    "",
                    "| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |",
                    "|---|---|---|---|---|---|",
                ]
                for v, x in vs.items():
                    a = x["A2_HIER_ANC_SURF"][h]
                    L.append(
                        f"| `{v}` | {triple(a)} | {a['gold_direct_edges']} -> {a['gold_closure_pairs']} (+{a['gold_pairs_added_by_closure']}) | {a['pred_direct_edges']} -> {a['pred_closure_pairs']} | {a['gold_mentions']} -> {a['gold_surface_nodes']} (collisions {a['gold_surface_collisions']}) | {a['unplaced_counted_as_fp']} |"
                    )
                cyc = [c for x in vs.values() for c in x["A2_HIER_ANC_SURF"][h]["cycles"]]
                L += ["", "Cycles detected: " + (json.dumps(cyc[:4]) if cyc else "none") + "."]
            L += [
                "",
                "### A3 REL-MACRO-SCINLP: relation macro F1 (gold relations whose two endpoints are predicted mentions)",
                "",
                "| variant | macro F1 | classes in macro | population | micro F1 | direction accuracy given correct label | no edge at pair |",
                "|---|---|---|---|---|---|---|",
            ]
            for v, x in vs.items():
                m = x["A3_REL_MACRO_SCINLP"]
                L.append(
                    f"| `{v}` | **{f(m['macro_f1'])}** | {m['classes_in_macro']} | {m['population']} | {f(m['micro']['f1'])} | {f(m['direction_accuracy_given_correct_label'])} | {m['no_prediction_by_outcome'].get('no_edge_at_pair', 0)} |"
                )
            pv = "IDX-P1" if "IDX-P1" in vs else next(iter(vs))
            L += [
                "",
                f"Per-class support (variant `{pv}`; `low` = support of 3 or fewer):",
                "",
                "| label | support | tp | fp | fn | P | R | F1 | low |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            for c, v in vs[pv]["A3_REL_MACRO_SCINLP"]["classes"].items():
                L.append(
                    f"| {c} | {v['support']} | {v['tp']} | {v['fp']} | {v['fn']} | {f(v['precision'])} | {f(v['recall'])} | {f(v['f1'])} | {'low' if v['low_support'] else ''} |"
                )
            L.append("")
    L += [
        "## Limits",
        "",
        "- E1, E3-M and E4-M runs (named in the spec) are not rescored tonight: their prediction path differs from E0 and was not wired; only E0 runs are covered.",
        "- A3 cannot tell a pair that never reached the classifier from one the classifier answered `no_relation` (the SciNLP run records no per-gold-pair classifier outcome at mention level): both are `no_edge_at_pair` and count as a false negative for the gold class.",
        "- A2 closes the hierarchy on case-folded surface strings: two different concepts with one surface collapse (collisions are counted above), and one concept written two ways stays two nodes.",
        "- Dev has 6 and test 3 documents; per-class F1 on classes with support of 3 or fewer is unstable (flagged). No confidence interval is attempted (`NOT_EVALUABLE_SMALL_N`).",
        "- The CR-021 rebuild runs mix the setting change with run-to-run variation (CR-021 report); they are shown beside, never pooled with, the frozen runs.",
    ]
    return "\n".join(L) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = {str(p): sha(p) for p in source_files()}
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    g = gate(ad, sym)
    res: dict = {"release": RELEASE, "gate": g, "sets": {}}
    if g["passed"]:
        for split, label, rid, docs, variants in SETS:
            res["sets"][f"{split}:{label}"] = {
                "split": split,
                "label": label,
                **score_set(split, rid, docs, variants, ad, sym),
            }
    after = {str(p): sha(p) for p in source_files()}
    res["hashes_unchanged"] = before == after
    res["n_hashed"] = len(before)
    (OUT / "part_a.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (OUT / "part_a.md").write_text(markdown(res), encoding="utf-8")
    print("gate", g["passed"], g["checks"], "hashes unchanged", res["hashes_unchanged"])


if __name__ == "__main__":
    main()
