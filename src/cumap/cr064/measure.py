"""CR-064 measurement ($0): arm R2 (`cr064relR2`, registry v1.0.2 + relation_choice v9, no node types) against the v5 baseline
(`cr055ballp`) and CR-059 arm R (`cr059relR`) on the first-set papers that every arm has finished, under overlap `IDXR1OV-P1`
(headline and adoption metric) and strict `IDXR1-P1` beside it (rule 35). Also: the choice-step confusions (overlap funnel, as
`cumap.cr063.bottleneck`) and the endpoint drops split into gold-linked / not gold-linked pairs.

    uv run python -m cumap.cr064.measure"""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.eval import HEADLINE, PRIMARY, pool, prf_d
from cumap.cr043.papers import first_set
from cumap.cr043.run import recorded_spend, run_id
from cumap.cr058 import funnel as FN
from cumap.cr063 import bottleneck as BN
from cumap.cr063 import tolerant as T

OUT = REPO_ROOT / "reports/cr064"
ARMS = (("v5", "cr055ballp"), ("arm R (CR-059)", "cr059relR"), ("arm R2", "cr064relR2"), ("arm R3", "cr064relR3"))
DROPS = ("domain_range", "endpoint_fit")
RULE = -0.005


def finished(tag: str, doc_key: str) -> bool:
    p = PG.run_path(run_id(doc_key, tag)) / "checkpoint.json"
    if not p.exists():
        return False
    cp = json.loads(p.read_text())
    return len(cp["relation_results_v3"]) >= len(cp["selected_pairs"]) > 0


def gold_linked(g, pred: dict) -> set[frozenset]:
    """Node-id pairs that some gold relation links (via the strict placement of its endpoints)."""
    owner: dict = {}
    for n in pred["nodes"]:
        for sp in n.mentions:
            owner.setdefault(sp, set()).add(n.node_id)
    return {
        frozenset((a, b))
        for r in g.relations
        for a in owner.get(r.src_span, ())
        for b in owner.get(r.tgt_span, ())
        if a != b
    }


def main() -> None:
    ad = SciNLPAdapter()
    sym = set(ad.symmetric_relations())
    docs, golds = {}, {}
    for s in ("train", "dev"):
        docs.update(
            {x.doc_key: x for x in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        )
        golds.update(ad.gold(s))
    papers = [d for _s, d in first_set() if all(finished(t, d) for _a, t in ARMS)]
    res: dict = {"papers": papers, "arms": {}}
    for arm, tag in ARMS:
        acc = {k: ([], []) for k in (HEADLINE, PRIMARY)}
        choice, drops, outcomes = Counter(), Counter(), Counter()
        for d in papers:
            cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, g = docs[d], golds[d]
            st = V.sc_score(doc, g, cp, sym, PRIMARY)
            acc[PRIMARY][0].append(st["scores"]["entity_strict"])
            acc[PRIMARY][1].append(st["scores"]["rel"])
            ov = T.score(doc, g, cp, sym, "overlap")["scores"]
            acc[HEADLINE][0].append(ov["entity_strict"])
            acc[HEADLINE][1].append(ov["rel"])
            pred = st["pred"]
            spans = {sp for n in pred["nodes"] for sp in n.mentions}
            m = T.snap_map_words(doc, {x.span for x in g.mentions}, spans, "overlap")
            g2 = BN.relabel(g, {gs: ps for ps, gs in m.items()})
            rf = FN.relation_funnel(doc, g2, cp, sym)
            choice.update(BN.choice_misses(g2, cp, pred, rf["lost_at"], sym))
            linked = gold_linked(g2, pred)
            for r in cp["relation_results_v3"]:
                if r.get("group", "selected") != "selected":
                    continue
                outcomes[r.get("outcome")] += 1
                if r.get("reason") in DROPS:
                    key = frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
                    drops[(r["reason"], "gold-linked" if key in linked else "not gold-linked")] += 1
        res["arms"][arm] = {
            "tag": tag,
            **{f"{k} concept": prf_d(pool(v[0])) for k, v in acc.items()},
            **{f"{k} relation": prf_d(pool(v[1])) for k, v in acc.items()},
            "choice_misses": dict(choice.most_common()),
            "drops": {f"{a} / {b}": n for (a, b), n in sorted(drops.items())},
            "outcomes": dict(outcomes),
            "spend_usd": round(sum(recorded_spend(run_id(d, tag)) for d in papers), 4)
            if tag != "cr055ballp"
            else None,
        }
    base = res["arms"]["v5"][f"{HEADLINE} relation"]["f1"]
    r2 = res["arms"]["arm R2"][f"{HEADLINE} relation"]["f1"]
    res["rule"] = {"delta_overlap_relation_f1": round(r2 - base, 4), "passes": r2 - base >= RULE}
    L = [f"# CR-064: arm R2 (registry v1.0.2 + relation_choice v9, no node types) on {len(papers)} first-set papers", "",
         (f"Adoption rule (pre-registered): overlap relation F1 >= v5 {RULE:+}. Delta {res['rule']['delta_overlap_relation_f1']:+.4f}: "
          f"**{'passes' if res['rule']['passes'] else 'fails'}**. trainedWith wording is gold-informed (owner option B)."), "",
         "| arm | overlap concept P / R / F2 | overlap relation P / R / F1 | strict relation P / R / F1 | spend |", "|---|---|---|---|---|"]  # fmt: skip
    for arm, x in res["arms"].items():
        c, ro, rs = x[f"{HEADLINE} concept"], x[f"{HEADLINE} relation"], x[f"{PRIMARY} relation"]
        L.append(f"| {arm} | {c['precision']:.3f} / {c['recall']:.3f} / {c['f2']:.3f} | {ro['precision']:.3f} / {ro['recall']:.3f} / "
                 f"**{ro['f1']:.3f}** | {rs['precision']:.3f} / {rs['recall']:.3f} / {rs['f1']:.3f} | "
                 f"{'' if x['spend_usd'] is None else '$' + str(x['spend_usd'])} |")  # fmt: skip
    for arm, x in res["arms"].items():
        top = "; ".join(f"{k} x{v}" for k, v in list(x["choice_misses"].items())[:10])
        L += ["", f"## {arm}", "", f"- choice-step losses (overlap): {top}", f"- endpoint drops: {x['drops']}",
              f"- outcomes (selected pairs): {x['outcomes']}"]  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "arm_r2.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "arm_r2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
