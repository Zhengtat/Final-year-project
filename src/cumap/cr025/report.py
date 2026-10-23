"""CR-025 report ($0, reads retained runs and the llm call log): three one-model arms on the SciNLP dev split, scored with the same scorers.

    uv run python -m cumap.cr025.report
Beside the arms, two reference rows from earlier runs are shown and labelled (mixed-tier CR-021 dev rebuild, CR-019 dev runs). Descriptive only:
6 papers, one run per arm, no sampling parameters, run-to-run variation is not separated."""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PRF
from cumap.cr019 import stage_b as SB
from cumap.cr019 import variants as V
from cumap.cr022 import scoring as C
from cumap.cr025.run import ARMS, PRICE, run_id

OUT = REPO_ROOT / "reports/cr025"
LOG = REPO_ROOT / "data/logs/llm_calls.jsonl"
H2 = C.HIER_SETS["H2 {subclassOf, subtaskOf}"]
VARIANTS = ("FROZEN", "IDX-P1", "IDXR1-P1")


def slug(d: str) -> str:
    return d.replace(".", "_").replace("-", "_")


GROUPS = {
    "luna": ("gpt-6-luna (both tiers)", lambda d: run_id("luna", d)),
    "o4mini": ("o4-mini (both tiers)", lambda d: run_id("o4mini", d)),
    "sol": ("gpt-6-sol (both tiers)", lambda d: run_id("sol", d)),
    "ref_cr021": (
        "reference: CR-021 dev rebuild (gpt-6-sol strong + gpt-6-luna bulk, mixed, earlier run)",
        lambda d: f"cr012_scinlp_cr021dev_{slug(d)}_E0",
    ),
    "ref_cr019": (
        "reference: CR-019 dev runs (earlier production settings, mixed tiers)",
        SB.sc_base,
    ),
}


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
    }


def usage(run_ids: list[str]) -> dict:
    ids, by_model = set(run_ids), {}
    calls = lat = 0
    for line in LOG.read_text().splitlines():
        r = json.loads(line)
        if r["run_id"] not in ids or r["cache_hit"]:
            continue
        m = by_model.setdefault(r["model"], [0, 0])
        m[0] += r["usage"].get("input_tokens", 0)
        m[1] += r["usage"].get("output_tokens", 0)
        calls += 1
        lat += r.get("latency_ms") or 0
    usd = sum(i / 1e6 * PRICE[m][0] + o / 1e6 * PRICE[m][1] for m, (i, o) in by_model.items())
    return {
        "usd": usd,
        "calls": calls,
        "input_tokens": sum(v[0] for v in by_model.values()),
        "output_tokens": sum(v[1] for v in by_model.values()),
        "call_minutes": lat / 60000,
        "by_model": by_model,
    }


def score_group(name: str, rid, ad, sym, gold, dmap) -> dict:
    docs = [d for d in SB.SC_DEV if (PG.run_path(rid(d)) / "checkpoint.json").exists()]
    out: dict = {
        "documents": docs,
        "missing": [d for d in SB.SC_DEV if d not in docs],
        "variants": {},
        "per_doc_idxr1_p1_f1": {},
    }
    graph = Counter()
    for d in docs:
        cp = json.loads((PG.run_path(rid(d)) / "checkpoint.json").read_text())
        if not cp.get("relation_results_v3") and not cp.get("selected_pairs"):
            continue
        graph["concepts"] += len(cp["concepts"])
        graph["selected_pairs"] += len(cp["selected_pairs"])
        graph["edges"] += sum(
            1
            for r in cp["relation_results_v3"]
            if r["outcome"] == "edge" and r.get("group", "selected") == "selected"
        )
    out["graph"] = dict(graph)
    for v in VARIANTS:
        ent, rel, a1, a2, rows = [], [], [], [], []
        for d in docs:
            cp = json.loads((PG.run_path(rid(d)) / "checkpoint.json").read_text())
            res = V.sc_score(dmap[d], gold[d], cp, sym, v)
            ent.append(res["scores"]["entity_strict"])
            rel.append(res["scores"]["rel"])
            if v == "IDXR1-P1":
                out["per_doc_idxr1_p1_f1"][d] = res["scores"]["rel"].f1
                p = C.place(dmap[d], cp, v)
                a1.append(C.direct_relation_prf(gold[d], p, sym, v, H2))
                a2.append(C.surface_hierarchy(dmap[d], gold[d], p, v, H2)["prf"])
                rows += C.relation_rows(dmap[d], gold[d], p, sym)
        x = {"concept_entity_strict": prf_d(pool(ent)), "relation_strict": prf_d(pool(rel))}
        if v == "IDXR1-P1":
            m = C.pooled_macro(rows)
            x |= {
                "hier_direct_H2": prf_d(pool(a1)),
                "hier_surface_ancestor_H2": prf_d(pool(a2)),
                "relation_macro_f1": m["macro_f1"],
                "macro_classes": m["classes_in_macro"],
                "macro_population": m["population"],
            }
        out["variants"][v] = x
    out["usage"] = usage([rid(d) for d in docs])
    return out


def f(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    g = r["groups"]
    L = [
        "# CR-025: three models on the SciNLP dev split",
        "",
        "Written for: the project owner. Descriptive comparison; no adoption decision.",
        "",
        "Corpus: SciNLP release `SciNLP-repo-e78342be`, **dev split, 6 papers**, E0 (the real pipeline end to end), CR-021 recipe with production settings (R1-key matching, rejected-link adjudicator). The test split was not opened (rule 9). Each arm runs ONE model for both tiers (strong effort medium, bulk effort low, escalation off), one run per arm. **o4-mini deviates**: at the production settings it failed twice with truncated answers (status=incomplete: hidden reasoning used the whole output cap, 768 of 800 tokens, then 2,368 of 2,400 even at 3x), so its arm runs with effort LOW on both tiers and every output cap x3; its cost includes the calls of those two failed attempts (resumed steps reuse the cache). No sampling parameters; run-to-run variation is not separated and n=6 papers, so small gaps are not evidence. Scorers: frozen CR-012 strict mention-level scorer, CR-019 occurrence index (IDXR1-P1 = primary here because the runs use R1-key matching), CR-022 hierarchy / macro scorers. Prices (USD per 1M tokens, in / out): "
        + "; ".join(f"{ARMS[a]} {PRICE[ARMS[a]][0]} / {PRICE[ARMS[a]][1]}" for a in ARMS)
        + " (o4-mini and luna from the repo config / third-party listings).",
        "",
        "## Headline (IDXR1-P1 grounding, pooled over the papers)",
        "",
        "| arm | cost (USD) | concept F1 | relation P / R / F1 | direct hierarchy F1 (H2) | surface-ancestor F1 (H2) | relation macro F1 | concepts | edges |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for x in g.values():
        v = x["variants"].get("IDXR1-P1")
        if not v:
            L.append(f"| {x['label']} | n/a | no runs | | | | | | |")
            continue
        rel = v["relation_strict"]
        L.append(
            f"| {x['label']} | {x['usage']['usd']:.2f} | {f(v['concept_entity_strict']['f1'])} | {f(rel['precision'])} / {f(rel['recall'])} / **{f(rel['f1'])}** | {f(v['hier_direct_H2']['f1'])} | {f(v['hier_surface_ancestor_H2']['f1'])} | {f(v['relation_macro_f1'])} ({v['macro_classes']} classes) | {x['graph'].get('concepts')} | {x['graph'].get('edges')} |"
        )
    L += [
        "",
        "Reference rows are earlier runs with a different tier mix (and for CR-019 older settings); they show the run-to-run spread of the existing setup, not a fourth model.",
        "",
        "## Other groundings (relation strict F1, concept F1)",
        "",
        "| arm | FROZEN rel F1 | IDX-P1 rel F1 | IDXR1-P1 rel F1 | FROZEN concept F1 | IDXR1-P1 concept F1 |",
        "|---|---|---|---|---|---|",
    ]
    for x in g.values():
        vs = x["variants"]
        if vs:
            L.append(
                f"| {x['label']} | {f(vs['FROZEN']['relation_strict']['f1'])} | {f(vs['IDX-P1']['relation_strict']['f1'])} | {f(vs['IDXR1-P1']['relation_strict']['f1'])} | {f(vs['FROZEN']['concept_entity_strict']['f1'])} | {f(vs['IDXR1-P1']['concept_entity_strict']['f1'])} |"
            )
    L += [
        "",
        "## Cost and speed (this run's calls, cache hits excluded)",
        "",
        "| arm | USD | calls | input tokens | output tokens | model-call minutes (sequential) | USD per relation-F1 point (x100) |",
        "|---|---|---|---|---|---|---|",
    ]
    for x in g.values():
        u, v = x["usage"], x["variants"].get("IDXR1-P1")
        per = (
            (u["usd"] / (v["relation_strict"]["f1"] * 100))
            if v and v["relation_strict"]["f1"]
            else None
        )
        L.append(
            f"| {x['label']} | {u['usd']:.3f} | {u['calls']} | {u['input_tokens']:,} | {u['output_tokens']:,} | {u['call_minutes']:.1f} | {f(per)} |"
        )
    L += [
        "",
        "## Per paper: relation strict F1 (IDXR1-P1)",
        "",
        "| paper | " + " | ".join(x["label"].split(" (")[0] for x in g.values()) + " |",
        "|---|" + "---|" * len(g),
    ]
    for d in SB.SC_DEV:
        L.append(
            f"| {d} | " + " | ".join(f(x["per_doc_idxr1_p1_f1"].get(d)) for x in g.values()) + " |"
        )
    miss = {k: x["missing"] for k, x in g.items() if x["missing"]}
    L += [
        "",
        "Missing runs: " + (json.dumps(miss) if miss else "none") + ".",
        "",
        "## How to read this",
        "",
        "- Cost is what the run's own calls would cost at the listed prices; a model that writes more reasoning tokens costs more than its list price suggests (compare the token columns).",
        "- A cheaper model changes everything downstream (concepts, pairs, relations), so differences are end-to-end, not per call.",
        "- The reference rows bound the noise: if the three arms differ by less than the two reference rows differ from each other, the data cannot rank them.",
    ]
    return "\n".join(L) + "\n"


def main() -> None:
    ad = SciNLPAdapter()
    sym, gold = ad.symmetric_relations(), ad.gold("dev")
    dmap = {d.doc_key: d for d in ad.load_documents("dev", paragraph_every=SR.PARAGRAPH_EVERY)}
    groups = {
        k: {"label": lab, **score_group(k, rid, ad, sym, gold, dmap)}
        for k, (lab, rid) in GROUPS.items()
    }
    res = {"release": "SciNLP-repo-e78342be", "split": "dev", "groups": groups}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comparison.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (OUT / "comparison.md").write_text(markdown(res), encoding="utf-8")
    print((OUT / "comparison.md").read_text()[:1500])


if __name__ == "__main__":
    main()
