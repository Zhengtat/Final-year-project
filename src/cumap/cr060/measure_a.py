"""CR-060 Part A, measured at $0: the head-variant identity rule applied to the saved v5 checkpoints of the first 20 papers (exact, since the
rule runs after relation classification). Objective `IDXR1-P1`; `IDXR1X-P1` / `IDXR1N-P1` beside it (rule 35). No model call.

    uv run python -m cumap.cr060.measure_a [--tag cr055ballp]
    uv run python -m cumap.cr060.measure_a --set rest --tag cr057rest   # CR-061: the other 37 train papers (reference for the page)"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.eval import PRIMARY, pool, prf_d
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr056 import nested as N
from cumap.cr060 import span_identity as SI

OUT = REPO_ROOT / "reports/cr060"
ARMS = ("control", "A-name", "A-all")
VIEWS = {"IDXR1X-P1": False, "IDXR1N-P1": True}


def measure(tag: str, set_name: str = "first") -> dict:
    ad = SciNLPAdapter()
    sym = frozenset(ad.symmetric_relations())
    papers = paper_set(set_name)
    docs, gold = {}, {}
    for s in {s for s, _ in papers}:
        docs[s] = {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        gold[s] = ad.gold(s)
    acc = {a: {"ent": [], "rel": [], **{v: {"ent": [], "rel": []} for v in VIEWS}} for a in ARMS}
    counts = {a: Counter() for a in ARMS}
    examples: dict[str, list] = {a: [] for a in ARMS}
    for s, d in papers:
        cp0 = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
        doc, g = docs[s][d], gold[s][d]
        for a in ARMS:
            if a == "control":
                cp = cp0
            else:
                cp, rec = SI.apply(cp0, doc.text, SI.load_variant(a), symmetric=sym)
                counts[a].update(aliases=len(rec["aliases"]), merges=len(rec["merges"]),
                                 edges_dropped=len(rec["edges_dropped"]))  # fmt: skip
                counts[a].update(Counter("alias_" + x["rule"] for x in rec["aliases"]))
                examples[a] += [f"{m['merged_name']} -> {m['evidence']}" for m in rec["merges"]][:3]
            counts[a]["concepts"] += len(cp["concepts"])
            r = V.sc_score(doc, g, cp, set(sym), PRIMARY)
            acc[a]["ent"].append(r["scores"]["entity_strict"])
            acc[a]["rel"].append(r["scores"]["rel"])
            for view, nested in VIEWS.items():
                vr = N.score(doc, g, cp, set(sym), nested)
                acc[a][view]["ent"].append(vr["entity_strict"])
                acc[a][view]["rel"].append(vr["rel"])
    res = {"tag": tag, "set": set_name, "papers": len(papers), "objective": PRIMARY, "arms": {}}
    for a in ARMS:
        res["arms"][a] = {
            "concept": prf_d(pool(acc[a]["ent"])),
            "relation": prf_d(pool(acc[a]["rel"])),
            "views": {v: {"concept": prf_d(pool(acc[a][v]["ent"])), "relation": prf_d(pool(acc[a][v]["rel"]))} for v in VIEWS},
            "counts": dict(counts[a]),
            "merge_examples": examples[a][:30],
        }  # fmt: skip
    c = res["arms"]["control"]
    for a in ARMS[1:]:
        x = res["arms"][a]
        dr = x["concept"]["recall"] - c["concept"]["recall"]
        df = x["relation"]["f1"] - c["relation"]["f1"]
        x["rule"] = {"concept_recall_delta": round(dr, 4), "relation_f1_delta": round(df, 4),
                     "passes": dr >= 0.01 and df >= -0.005}  # fmt: skip
    return res


def markdown(r: dict) -> str:
    L = [f"# CR-060 Part A: head-variant identity (replay on `{r['tag']}`, {r['papers']} papers, set `{r['set']}`, `{r['objective']}`)", "",
         "| arm | concepts | concept P / R / F1 | relation P / R / F1 | aliases | merges | edges dropped | rule |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for a, x in r["arms"].items():
        cc, rr, n = x["concept"], x["relation"], x["counts"]
        rule = x.get("rule")
        verdict = (
            "—"
            if not rule
            else f"{'PASS' if rule['passes'] else 'fail'} (R {rule['concept_recall_delta']:+.3f}, F1 {rule['relation_f1_delta']:+.3f})"
        )
        L.append(f"| {a} | {n.get('concepts', 0)} | {cc['precision']:.3f} / {cc['recall']:.3f} / {cc['f1']:.3f} | "
                 f"{rr['precision']:.3f} / {rr['recall']:.3f} / {rr['f1']:.3f} | {n.get('aliases', 0)} | {n.get('merges', 0)} | "
                 f"{n.get('edges_dropped', 0)} | {verdict} |")  # fmt: skip
    L += [
        "",
        "Beside it (rule 35):",
        "",
        "| arm | view | concept F1 | relation F1 |",
        "|---|---|---|---|",
    ]
    for a, x in r["arms"].items():
        for v, y in x["views"].items():
            L.append(f"| {a} | {v} | {y['concept']['f1']:.3f} | {y['relation']['f1']:.3f} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="cr055ballp")
    ap.add_argument("--set", default="first", choices=["first", "rest"])
    a = ap.parse_args()
    r = measure(a.tag, a.set)
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "" if a.set == "first" else f"_{a.set}"
    (OUT / f"part_a{suffix}.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    (OUT / f"part_a{suffix}.md").write_text(markdown(r), encoding="utf-8")
    print(markdown(r))


if __name__ == "__main__":
    main()
