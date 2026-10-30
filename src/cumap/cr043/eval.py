"""CR-043 SciNLP scorecard ($0, no model call): every objective for one set of per-paper runs, from the frozen scorers.

    uv run python -m cumap.cr043.eval [--tag cr043base]      # writes reports/cr043/<tag>.{json,md}

Headline: strict relation F1 under `IDXR1-P1` (the occurrence index with R1-key matching; the runs use R1-key matching).
Beside it: `FROZEN` (frozen CR-012 grounding, unplaced edges excluded) and `IDXR1-P3` (lenient upper reading), concept F1
(entity strict), the pair-recall analogue, relation macro F1 (CR-022 A3), hierarchy (CR-022 A1 / A2, H2 labels), fact F1
(CR-033 `FACT-C1-SURF-R1`) and earliest-failure codes. "Pair not proposed" (P0) is split by whether the two gold mention spans
share a sentence: a same-sentence pair was in the candidate pool and the budget or ranking left it out; a cross-sentence pair
can never be a candidate (pairs are same-sentence only). Train / dev papers only; the test split is never read here (rule 9)."""

from __future__ import annotations

import argparse
import bisect
import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr012.types import PRF
from cumap.cr019 import variants as V
from cumap.cr022 import scoring as C
from cumap.cr025.report import usage
from cumap.cr032 import scinlp_t1 as ST
from cumap.cr033 import fact_f1 as F
from cumap.cr043.papers import paper_set
from cumap.cr043.run import TAG, run_id
from cumap.expert_kg.alias_rules import AliasConfig

OUT = REPO_ROOT / "reports" / "cr043"
PRIMARY = "IDXR1-P1"  # strict: the adoption metric and the secondary reported number (CR-063)
HEADLINE = "IDXR1OV-P1"  # CR-063 (owner, 2026-10-30): overlap matching is the headline reported number; strict beside it
VARIANTS = ("FROZEN", PRIMARY, "IDXR1-P3")
REPORTED = (HEADLINE, *VARIANTS)
H2 = C.HIER_SETS["H2 {subclassOf, subtaskOf}"]


def pool(xs: list[PRF]) -> PRF:
    return PRF(sum(x.tp for x in xs), sum(x.fp for x in xs), sum(x.fn for x in xs))


def prf_d(x: PRF) -> dict:
    return {
        "tp": x.tp,
        "fp": x.fp,
        "fn": x.fn,
        "precision": x.precision,
        "recall": x.recall,
        "f1": x.f1,
        "f2": f_beta(x, 2.0),  # CR-062: the concept headline (beta fixed at 2); F1 beside it
    }


def f_beta(x: PRF, beta: float) -> float:
    b2 = beta * beta
    d = (1 + b2) * x.tp + b2 * x.fn + x.fp
    return (1 + b2) * x.tp / d if d else 0.0


def c3(x: dict) -> str:
    """Concept cell: P / R / **F2** (F1 ...); F2 from the counts when an older scorecard has none."""
    f2 = x.get("f2", f_beta(PRF(x["tp"], x["fp"], x["fn"]), 2.0))
    return f"{x['precision']:.3f} / {x['recall']:.3f} / **{f2:.3f}** (F1 {x['f1']:.3f}; tp {x['tp']}, fp {x['fp']}, fn {x['fn']})"


def sentence_of(doc, span) -> int:
    return bisect.bisect_right(doc.sentence_ends, span[0])


def p0_split(doc, gold, codes: list[str | None]) -> Counter:
    out: Counter = Counter()
    for r, c in zip(gold.relations, codes, strict=True):
        if c == "P0":
            same = sentence_of(doc, r.src_span) == sentence_of(doc, r.tgt_span)
            out["P0_same_sentence" if same else "P0_cross_sentence"] += 1
    return out


def score(papers: list[tuple[str, str]], tag: str) -> dict:
    ad = SciNLPAdapter()
    sym, acfg = ad.symmetric_relations(), AliasConfig.load()
    gold = {s: ad.gold(s) for s in {s for s, _ in papers}}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in gold
    }
    present = [
        (s, d) for s, d in papers if (PG.run_path(run_id(d, tag)) / "checkpoint.json").exists()
    ]
    res: dict = {
        "tag": tag,
        "papers": [d for _, d in present],
        "missing": [d for s, d in papers if (s, d) not in present],
    }
    ent = {v: [] for v in REPORTED}
    rel = {v: [] for v in REPORTED}
    by_split = {v: {"dev": [], "train": []} for v in REPORTED}
    codes_all: Counter = Counter()
    p0: Counter = Counter()
    a1, a2, rows, facts = [], [], [], {}
    graph: Counter = Counter()
    per_paper = {}
    views: dict = {}
    for s, d in present:
        cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
        doc, g = docs[s][d], gold[s][d]
        stats = cp.get("selection_stats") or {}
        graph["concepts"] += len(cp["concepts"])
        graph["candidate_pairs"] += stats.get("unique_candidate_pairs") or 0
        graph["selected_pairs"] += len(cp["selected_pairs"])
        graph["edges"] += sum(
            1
            for r in cp["relation_results_v3"]
            if r["outcome"] == "edge" and r.get("group", "selected") == "selected"
        )
        graph["gold_relations"] += len(g.relations)
        graph["budget_saturated_papers"] += int(
            len(cp["selected_pairs"]) < (stats.get("unique_candidate_pairs") or 0)
        )
        for v in VARIANTS:
            r = V.sc_score(doc, g, cp, sym, v)
            ent[v].append(r["scores"]["entity_strict"])
            rel[v].append(r["scores"]["rel"])
            by_split[v][s].append(r["scores"]["rel"])
            if v == PRIMARY:
                codes = sc_attribution(doc, g, r["pred"], cp, sym)
                codes_all.update(c or "recovered" for c in codes)
                p0.update(p0_split(doc, g, codes))
                per_paper[d] = {"split": s, "f1": r["scores"]["rel"].f1, "tp": r["scores"]["rel"].tp,
                                "gold": len(g.relations), "edges_predicted": r["edges"]["predicted"]}  # fmt: skip
        from cumap.cr063 import tolerant as T  # CR-063: the overlap headline

        ov = T.score(doc, g, cp, sym, "overlap")["scores"]
        ent[HEADLINE].append(ov["entity_strict"])
        rel[HEADLINE].append(ov["rel"])
        by_split[HEADLINE][s].append(ov["rel"])
        from cumap.cr056 import (
            nested as N,  # CR-057: recall-first views, reported beside IDXR1-P1 (rule 35)
        )

        for view, nested in (("IDXR1X-P1", False), ("IDXR1N-P1", True)):
            vr = N.score(doc, g, cp, sym, nested)
            views.setdefault(view, {"ent": [], "rel": []})
            views[view]["ent"].append(vr["entity_strict"])
            views[view]["rel"].append(vr["rel"])
        p = C.place(doc, cp, PRIMARY)
        a1.append(C.direct_relation_prf(g, p, sym, PRIMARY, H2))
        a2.append(C.surface_hierarchy(doc, g, p, PRIMARY, H2)["prf"])
        rows += C.relation_rows(doc, g, p, sym)
        ident, _ = ST.r1_identity(doc, acfg)
        facts[d] = F.fact_score(g, p.rels, sum(p.unplaced_by_label.values()), PRIMARY, ident, sym)
    n_end = sum(n for c, n in codes_all.items() if c not in ("N0", "N1"))
    n_prop = sum(n for c, n in codes_all.items() if c not in ("N0", "N1", "P0"))
    m = C.pooled_macro(rows)
    fp = F.pool(facts) if facts else None
    res |= {
        "graph": dict(graph),
        "variants": {
            v: {
                "concept_entity_strict": prf_d(pool(ent[v])),
                "relation_strict": prf_d(pool(rel[v])),
                "relation_strict_dev": prf_d(pool(by_split[v]["dev"])),
                "relation_strict_train": prf_d(pool(by_split[v]["train"])),
            }
            for v in REPORTED
        },
        "pair_recall_analogue": {
            "reached": n_prop,
            "endpoints_present": n_end,
            "rate": n_prop / n_end if n_end else None,
        },
        "relation_macro_f1": {
            "macro_f1": m["macro_f1"],
            "classes": m["classes_in_macro"],
            "population": m["population"],
        },
        "hierarchy_direct_H2": prf_d(pool(a1)),
        "hierarchy_surface_ancestor_H2": prf_d(pool(a2)),
        "fact_f1_surf_r1": {**fp, "prf": prf_d(fp["prf"])} if fp else None,
        "recall_views": {
            k: {
                "concept_entity_strict": prf_d(pool(x["ent"])),
                "relation_strict": prf_d(pool(x["rel"])),
            }
            for k, x in views.items()
        },
        "earliest_failure": dict(sorted(codes_all.items())),
        "p0_split": dict(p0),
        "per_paper": per_paper,
        "usage": usage([run_id(d, tag) for _, d in present]),
    }
    return res


def f3(x: dict) -> str:
    return f"{x['precision']:.3f} / {x['recall']:.3f} / **{x['f1']:.3f}** (tp {x['tp']}, fp {x['fp']}, fn {x['fn']})"


def markdown(r: dict) -> str:
    g, v = r["graph"], r["variants"]
    L = [
        f"# CR-043 SciNLP scorecard: `{r['tag']}` ({len(r['papers'])} papers, set `{r.get('paper_set', 'first')}`)",
        "",
        "Generated by `cumap.cr043.eval` ($0, no model call). Frozen scorers; every number names its grounding (rule 35). Test split not used (rule 9).",
        "",
        (
            f"Graphs: {g.get('concepts', 0)} concepts, {g.get('candidate_pairs', 0)} candidate pairs, {g.get('selected_pairs', 0)} classified, "
            f"{g.get('edges', 0)} edges; {g.get('gold_relations', 0)} gold relations; budget left pairs out in {g.get('budget_saturated_papers', 0)} papers. "
            f"Spend ${r['usage']['usd']:.3f} ({r['usage']['calls']} non-cached calls)."
        ),
        "",
        "## Relation P / R / F1 and concept P / R / F2: headline overlap `IDXR1OV-P1`, strict `IDXR1-P1` beside (CR-063)",
        "",
        (
            "Overlap: a predicted mention that shares a token with a gold mention counts as it (one-to-one, closest first; relation endpoints the same). "
            "Strict `IDXR1-P1` (exact spans) is the secondary number and the adoption metric."
        ),
        "",
        "| grounding | all papers | dev papers | train papers | concept P / R / F2 (F1 beside) |",
        "|---|---|---|---|---|",
    ]
    for k, x in v.items():
        L.append(
            f"| `{k}` | {f3(x['relation_strict'])} | {f3(x['relation_strict_dev'])} | {f3(x['relation_strict_train'])} | {c3(x['concept_entity_strict'])} |"
        )
    if r.get("recall_views"):
        L += [
            "",
            "## Recall-first views (reported beside `IDXR1-P1`, rule 35)",
            "",
            (
                '`IDXR1X-P1` adds the CR-052 span rules (absorb a trailing generic head noun and a following "( ACRONYM )"); `IDXR1N-P1` also places, inside every placed mention, '
                "every other node name it contains and the mention minus a trailing generic head (CR-056 / CR-057). Both add mentions, so precision can fall."
            ),
            "",
            "| view | concept P / R / F1 | relation P / R / F1 |",
            "|---|---|---|",
            *[
                f"| `{k}` | {c3(x['concept_entity_strict'])} | {f3(x['relation_strict'])} |"
                for k, x in r["recall_views"].items()
            ],
        ]
    pr, mf = r["pair_recall_analogue"], r["relation_macro_f1"]
    L += [
        "",
        "## Other objectives (`IDXR1-P1`)",
        "",
        "| objective | value |",
        "|---|---|",
        f"| Pair recall (analogue) | {pr['reached']} / {pr['endpoints_present']} = **{(pr['rate'] or 0):.3f}** |",
        f"| Relation macro F1 (A3) | **{(mf['macro_f1'] or 0):.3f}** ({mf['classes']} classes, {mf['population']} relations) |",
        f"| Hierarchy, direct H2 (A1) | {f3(r['hierarchy_direct_H2'])} |",
        f"| Hierarchy, surface ancestor H2 (A2, identity from strings) | {f3(r['hierarchy_surface_ancestor_H2'])} |",
    ]
    if r["fact_f1_surf_r1"]:
        L.append(
            f"| Fact F1 (`FACT-C1-SURF-R1`, identity from strings) | {f3(r['fact_f1_surf_r1']['prf'])} |"
        )
    ef = r["earliest_failure"]
    total = sum(ef.values())
    L += [
        "",
        f"## Where the {total} gold relations are lost (earliest failure, `IDXR1-P1`)",
        "",
        "| code | meaning | count | share |",
        "|---|---|---|---|",
    ]
    meaning = {"N0": "concept not found", "N1": "wrong or incomplete span", "C0": "concept split", "C1": "false merge",
               "P0": "pair never classified", "R0": "classifier said no relation", "R1": "wrong relation", "R2": "wrong direction",
               "R3": "qualifier / type", "E0": "evidence invalid", "recovered": "pipeline right (strict match may still differ)"}  # fmt: skip
    for c, n in ef.items():
        L.append(f"| {c} | {meaning.get(c, c)} | {n} | {n / total:.1%} |")
    p0 = r["p0_split"]
    L += [
        "",
        (
            f"P0 split: same sentence (in the candidate pool, left out by budget or ranking) **{p0.get('P0_same_sentence', 0)}**; "
            f"cross-sentence (can never be a candidate) **{p0.get('P0_cross_sentence', 0)}**."
        ),
        "",
        "## Per paper (`IDXR1-P1`)",
        "",
        "| paper | split | strict F1 | TP | gold relations | predicted edges |",
        "|---|---|---|---|---|---|",
    ]
    for d, x in r["per_paper"].items():
        L.append(
            f"| {d} | {x['split']} | {x['f1']:.3f} | {x['tp']} | {x['gold']} | {x['edges_predicted']} |"
        )
    if r["missing"]:
        L += ["", f"Not run yet: {', '.join(r['missing'])}."]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=TAG)
    ap.add_argument(
        "--set", default="first", choices=["first", "rest", "all"]
    )  # CR-057: "rest" = the 37 unseen train papers
    a = ap.parse_args()
    r = score(paper_set(a.set), a.tag)
    r["paper_set"] = a.set
    name = a.tag if a.set == "first" else f"{a.tag}_{a.set}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
    (OUT / f"{name}.md").write_text(markdown(r), encoding="utf-8")
    print(markdown(r)[:1500])


if __name__ == "__main__":
    main()
