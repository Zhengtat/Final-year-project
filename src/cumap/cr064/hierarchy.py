"""CR-064 ($0): where Hierarchy F1 (`A1-DIR`, `cr022.scoring.hierarchy_direction_prf`) is lost, on the CR-058 development sources
(v5: `cr055ballp` on the 20 first-set papers, `cr057rest` on the 37 rest papers), strict `IDXR1-P1` placement. No model call.

1. **Score:** pooled P/R/F1 and a 95% percentile bootstrap over papers (10,000 resamples, seed 0), beside the strict E2E relation F1.
2. **Per gold hierarchy relation** (mention level, as the scorer counts): hit (and hits that need the two labels merged), or the miss
   reason: endpoint not extracted, hierarchy edge reversed, other relation at the pair (by label), no edge at the pair.
3. **Per false hierarchy link:** reverse of a gold hierarchy relation, a gold non-hierarchy relation at the pair (by label), no gold
   relation at the pair, unplaced (rule 35).
4. **Choice step** (concept-node pairs, CR-058 funnel): the relation chosen at each node pair that carries a gold hierarchy or partOf
   relation (decisions, not relations: one gold relation can map to several node pairs), and the stage each gold hierarchy relation
   is lost at, beside the same split over all gold relations.

    uv run python -m cumap.cr064.hierarchy"""

from __future__ import annotations

import json
import random
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PRF, UnitGold
from cumap.cr019 import variants as V
from cumap.cr022 import scoring as C
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr058 import funnel as FN

OUT = REPO_ROOT / "reports/cr064"
SOURCES = (("first", "cr055ballp"), ("rest", "cr057rest"))  # = cr058.page.DEV_SOURCES
VARIANT = "IDXR1-P1"
H2 = C.HIER_SETS["H2 {subclassOf, subtaskOf}"]
DECLINED = "none/declined"
SHOWN = {
    "hit_needs_label_merge": "of the hits: label differs (hit only because the two labels are one class)",
    "assembled_edge": "assembled: a correct edge is in the graph (the mention-level scorer may still not credit it)",
}


def pool(rs: list[PRF]) -> PRF:
    return PRF(sum(x.tp for x in rs), sum(x.fp for x in rs), sum(x.fn for x in rs))


def prf_d(x: PRF) -> dict:
    return {
        "tp": x.tp,
        "fp": x.fp,
        "fn": x.fn,
        "precision": x.precision,
        "recall": x.recall,
        "f1": x.f1,
    }


def bootstrap_f1(per_paper: list[PRF], n: int = 10_000, seed: int = 0) -> tuple[float, float]:
    """95% percentile interval of the pooled F1, resampling papers with replacement."""
    rng, k = random.Random(seed), len(per_paper)
    f = sorted(pool([per_paper[rng.randrange(k)] for _ in range(k)]).f1 for _ in range(n))
    return f[int(0.025 * n) - 1], f[int(0.975 * n) - 1]


def gold_outcomes(gold: UnitGold, p: C.Placed) -> tuple[Counter, Counter]:
    """(outcome per gold hierarchy relation, gold label -> other predicted label at the pair), mention level."""
    placed = {sp for sp, _ in p.mentions}
    by_dir: dict[tuple, set[str]] = {}
    for a, b, lab, *_ in p.rels:
        by_dir.setdefault((a, b), set()).add(lab)
    out, conf = Counter(), Counter()
    for r in gold.relations:
        if r.relation not in H2:
            continue
        fwd = by_dir.get((r.src_span, r.tgt_span), set())
        rev = by_dir.get((r.tgt_span, r.src_span), set())
        if fwd & H2:
            out["hit"] += 1
            out["hit_needs_label_merge"] += r.relation not in fwd
        elif r.src_span not in placed or r.tgt_span not in placed:
            out["miss_endpoint_not_extracted"] += 1
        elif rev & H2:
            out["miss_reversed"] += 1
        elif fwd | rev:
            out["miss_other_relation"] += 1
            conf.update(f"{r.relation} -> {lab}" for lab in sorted(fwd | rev))
        else:
            out["miss_no_edge_at_pair"] += 1
    return out, conf


def false_links(gold: UnitGold, p: C.Placed) -> Counter:
    """Every predicted hierarchy link that is not a hit, by what gold has at its two mentions."""
    gh = {(r.src_span, r.tgt_span) for r in gold.relations if r.relation in H2}
    at: dict[frozenset, list[str]] = {}
    for r in gold.relations:
        at.setdefault(frozenset((r.src_span, r.tgt_span)), []).append(r.relation)
    out: Counter = Counter()
    for a, b in {(r[0], r[1]) for r in p.rels if r[2] in H2} - gh:
        labs = at.get(frozenset((a, b)))
        if not labs:
            out["no gold relation at pair"] += 1
        elif any(x in H2 for x in labs):
            out["reverse of a gold hierarchy relation"] += 1
        else:
            out.update(f"gold {x}" for x in labs)
    out["unplaced"] += sum(n for lab, n in p.unplaced_by_label.items() if lab in H2)
    return out


def choice_at_gold_pairs(doc, gold: UnitGold, cp: dict, sym: set[str]) -> Counter:
    """Relation chosen at every selected node pair carrying a gold hierarchy or partOf relation (`gold -> chosen`)."""
    pred = V.sc_score(doc, gold, cp, sym, VARIANT)["pred"]
    owner: dict = {}
    for n in pred["nodes"]:
        for sp in n.mentions:
            owner.setdefault(sp, set()).add(n.node_id)
    res = [r for r in cp["relation_results_v3"] if r.get("group", "selected") == "selected"]
    out: Counter = Counter()
    for g in gold.relations:
        if g.relation not in H2 | {"partOf"}:
            continue
        A, B = owner.get(g.src_span, set()), owner.get(g.tgt_span, set())
        for r in res:
            x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
            if x != y and ((x in A and y in B) or (x in B and y in A)):
                out[f"{g.relation} -> {r.get('relation') or DECLINED}"] += 1
    return out


def not_reached(stage: str) -> str:
    """`lost_at` names the first stage not reached, and "credited" for both a relation that reached it and one that was credited."""
    return "assembled_edge" if stage == "credited" else stage


def collect() -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    hier, e2e = [], []
    outc, conf, fls, choice, lost_h, lost_all = (Counter() for _ in range(6))
    for st, tag in SOURCES:
        papers = paper_set(st)
        golds = {s: ad.gold(s) for s in {s for s, _ in papers}}
        docs = {
            s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
            for s in golds
        }
        for s, d in papers:
            cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, g = docs[s][d], golds[s][d]
            p = C.place(doc, cp, VARIANT)
            hier.append(C.hierarchy_direction_prf(g, p, VARIANT, H2))
            e2e.append(V.sc_score(doc, g, cp, sym, VARIANT)["scores"]["rel"])
            o, c = gold_outcomes(g, p)
            outc.update(o)
            conf.update(c)
            fls.update(false_links(g, p))
            choice.update(choice_at_gold_pairs(doc, g, cp, sym))
            lost = FN.relation_funnel(doc, g, cp, sym)["lost_at"]
            lost_all.update(not_reached(x) for x in lost)
            lost_h.update(
                not_reached(at) for r, at in zip(g.relations, lost, strict=True) if r.relation in H2
            )
    h, lo_hi = pool(hier), bootstrap_f1(hier)
    return {
        "sources": dict(SOURCES),
        "variant": VARIANT,
        "papers": len(hier),
        "hierarchy_A1_DIR": prf_d(h),
        "hierarchy_f1_ci95_paper_bootstrap": list(lo_hi),
        "e2e_relation_strict": prf_d(pool(e2e)),
        "gold_hierarchy_relations": h.tp + h.fn,
        "gold_outcomes": dict(outc),
        "other_relation_at_pair": dict(conf),
        "false_links": dict(fls),
        "choice_at_gold_node_pairs": dict(sorted(choice.items())),
        "funnel_not_reached_hierarchy": dict(lost_h),
        "funnel_not_reached_all": dict(lost_all),
    }


def markdown(r: dict) -> str:
    h, e, (lo, hi) = (
        r["hierarchy_A1_DIR"],
        r["e2e_relation_strict"],
        r["hierarchy_f1_ci95_paper_bootstrap"],
    )
    o, n = r["gold_outcomes"], r["gold_hierarchy_relations"]
    miss = n - o.get("hit", 0)

    def table(title: str, c: dict, total: int | None = None) -> list[str]:
        rows = [
            f"| {SHOWN.get(k, k)} | {v} |" + (f" {v / total:.0%} |" if total else "")
            for k, v in sorted(c.items(), key=lambda x: -x[1])
        ]
        head = "| | n |" + (" share |" if total else "")
        return ["", f"## {title}", "", head, "|---|---|" + ("---|" if total else ""), *rows]

    na, nh = (
        sum(r["funnel_not_reached_all"].values()),
        sum(r["funnel_not_reached_hierarchy"].values()),
    )
    L = [
        "# CR-064 Hierarchy F1 breakdown (`A1-DIR`)",
        "",
        (
            f"Sources: {', '.join(f'`{t}` ({s})' for s, t in r['sources'].items())}; {r['papers']} papers; placement `{r['variant']}`; "
            "no model call. Generated by `uv run python -m cumap.cr064.hierarchy`."
        ),
        "",
        "| metric | P | R | F1 | tp / fp / fn |",
        "|---|---|---|---|---|",
        f"| Hierarchy F1 (`A1-DIR`) | {h['precision']:.3f} | {h['recall']:.3f} | **{h['f1']:.3f}** | {h['tp']} / {h['fp']} / {h['fn']} |",
        f"| E2E relation F1, strict | {e['precision']:.3f} | {e['recall']:.3f} | {e['f1']:.3f} | {e['tp']} / {e['fp']} / {e['fn']} |",
        "",
        (
            f"Hierarchy F1 95% interval (paper bootstrap, 10,000 resamples, seed 0): **{lo:.3f} to {hi:.3f}**. "
            f"Gold hierarchy relations: {n} ({n / r['papers']:.1f} per paper). Misses: {miss}."
        ),
        *table("Gold hierarchy relations (mention level)", o, n),
        *table("Misses with another relation at the pair", r["other_relation_at_pair"]),
        *table("False hierarchy links", r["false_links"], h["fp"]),
        *table("Choice step at gold node pairs (decisions)", r["choice_at_gold_node_pairs"]),
        *table(
            "Funnel stage not reached: hierarchy relations", r["funnel_not_reached_hierarchy"], nh
        ),
        *table("Funnel stage not reached: all gold relations", r["funnel_not_reached_all"], na),
    ]
    return "\n".join(L) + "\n"


def main() -> None:
    r = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hierarchy.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    (OUT / "hierarchy.md").write_text(markdown(r), encoding="utf-8")
    print(markdown(r))


if __name__ == "__main__":
    main()
