"""CR-064 ($0): where relation precision is lost, per relation, for v5 (`cr055ballp`) and arm R2 (`cr064relR2`) on the 20 first-set
papers, under overlap `IDXR1OV-P1` (strict `IDXR1-P1` beside). No model call.

Three views:
1. **Per predicted relation** (mention-level, as the scorer counts): predicted, TP, precision, and every FP split into
   `wrong direction` (gold has the reverse), `wrong label` (gold links the same two mentions with another relation),
   `unannotated pair` (both endpoints are gold mentions, gold links them with nothing), `non-gold endpoint` (one or both endpoints
   are not gold concepts), `unplaced` (the edge has no mention of an endpoint inside its evidence; counted as FP by the scorer).
2. **Per gold relation:** gold count, recall, and the classification-conditional ("oracle pair") rate: of the gold relations whose
   two endpoints were placed and whose pair was classified, how many were credited (the CR-058 funnel, per label).
3. **Checks:** relation results the checks rejected, split into right choice (a gold relation wrongly dropped) / wrong choice, by
   reason (CR-058 funnel accounting).

    uv run python -m cumap.cr064.precision"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter, defaultdict

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id
from cumap.cr058 import funnel as FN
from cumap.cr063 import bottleneck as BN
from cumap.cr063 import tolerant as T

OUT = REPO_ROOT / "reports/cr064"
ARMS = (("v5", "cr055ballp"), ("arm R2", "cr064relR2"), ("arm R3", "cr064relR3"))
FP_KINDS = ("wrong direction", "wrong label", "unannotated pair", "non-gold endpoint", "unplaced")


def edge_rows(doc, g, cp: dict, sym: set[str], mode: str) -> tuple[list[tuple], Counter]:
    """Mention-level predicted relations (snapped to gold for overlap) and the unplaced edge count per relation."""
    pred = V.sc_score(doc, g, cp, sym, "IDXR1-P1")["pred"]
    unplaced: Counter = Counter()
    rows: list[tuple] = []
    for e in pred["edges"]:
        r, n = S.project_edges_to_mentions(pred["nodes"], [e])
        rows += r
        unplaced[e.relation] += n
    unplaced.update({"(edge without node or quote)": pred["stats"]["edges_without_node_or_quote"]})
    if mode == "overlap":
        gs = {m.span for m in g.mentions}
        ps = {s for s, _t in S.project_nodes_to_mentions(pred["nodes"])}
        m = T.snap_map_words(doc, gs, ps, "overlap")
        rows = [(m.get(a, a), m.get(b, b), rel, st, tt) for a, b, rel, st, tt in rows]
    return rows, unplaced


def per_relation(papers, docs, golds, sym, tag: str, mode: str) -> dict:
    stats: dict[str, Counter] = defaultdict(Counter)
    confusion: Counter = Counter()
    for d in papers:
        cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
        doc, g = docs[d], golds[d]
        rows, unplaced = edge_rows(doc, g, cp, sym, mode)
        gm = {m.span for m in g.mentions}
        g_key = {S._rel_key(r.src_span, r.tgt_span, r.relation, sym) for r in g.relations}
        g_pair: dict[frozenset, set[str]] = defaultdict(set)
        g_dir: set[tuple] = set()
        for r in g.relations:
            g_pair[frozenset((r.src_span, r.tgt_span))].add(r.relation)
            g_dir.add((r.src_span, r.tgt_span, r.relation))
        seen = set()
        for a, b, rel, _st, _tt in rows:
            k = S._rel_key(a, b, rel, sym)
            if k in seen:  # the scorer counts a mention-level relation once
                continue
            seen.add(k)
            s = stats[rel]
            s["predicted"] += 1
            if k in g_key:
                s["tp"] += 1
            elif (b, a, rel) in g_dir:
                s["wrong direction"] += 1
            elif g_pair.get(frozenset((a, b))):
                s["wrong label"] += 1
                confusion[(rel, "/".join(sorted(g_pair[frozenset((a, b))])))] += 1
            elif a in gm and b in gm:
                s["unannotated pair"] += 1
            else:
                s["non-gold endpoint"] += 1
        for rel, n in unplaced.items():
            stats[rel]["predicted"] += n
            stats[rel]["unplaced"] += n
    return {"stats": {k: dict(v) for k, v in stats.items()}, "confusion": confusion}


def per_gold(papers, docs, golds, sym, tag: str) -> tuple[dict, dict]:
    """Per gold relation: funnel stages (overlap) and the checks' rejections split right / wrong choice."""
    stages: dict[str, Counter] = defaultdict(Counter)
    checks = {"correct": Counter(), "wrong": Counter()}
    pairs: Counter = Counter()
    for d in papers:
        cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
        doc, g = docs[d], golds[d]
        pred = V.sc_score(doc, g, cp, sym, "IDXR1-P1")["pred"]
        spans = {sp for n in pred["nodes"] for sp in n.mentions}
        m = T.snap_map_words(doc, {x.span for x in g.mentions}, spans, "overlap")
        g2 = BN.relabel(g, {gs: ps for ps, gs in m.items()})
        rf = FN.relation_funnel(doc, g2, cp, sym)
        for k, c in checks.items():
            c.update(rf["checks"][k])
        pairs.update(rf["pairs"])
        for rel in {r.relation for r in g2.relations}:
            gr = dataclasses.replace(g2, relations=[r for r in g2.relations if r.relation == rel])
            stages[rel].update(FN.relation_funnel(doc, gr, cp, sym)["gold_stages"])
    return {k: dict(v) for k, v in stages.items()}, {
        "checks": {k: dict(v) for k, v in checks.items()},
        "pairs": dict(pairs),
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
    papers = [d for _s, d in first_set()]
    res: dict = {}
    for arm, tag in ARMS:
        ov = per_relation(papers, docs, golds, sym, tag, "overlap")
        st = per_relation(papers, docs, golds, sym, tag, "strict")
        stages, chk = per_gold(papers, docs, golds, sym, tag)
        res[arm] = {"overlap": ov["stats"], "strict": st["stats"], "gold_stages": stages, **chk,
                    "confusion_overlap": {f"{p} on gold {g}": n for (p, g), n in ov["confusion"].most_common()}}  # fmt: skip
    L = [
        "# CR-064: relation precision and recall by relation (20 first-set papers; overlap `IDXR1OV-P1`, strict beside)",
        "",
    ]
    for arm, x in res.items():
        L += [f"## {arm}", "", "### Predicted relations (overlap): where precision is lost", "",
              "| relation | predicted | TP | P | " + " | ".join(FP_KINDS) + " | strict P |",
              "|---|---|---|---|" + "---|" * (len(FP_KINDS) + 1)]  # fmt: skip
        tot = Counter()
        for rel, s in sorted(
            x["overlap"].items(), key=lambda kv: -(kv[1]["predicted"] - kv[1].get("tp", 0))
        ):
            tot.update(s)
            sp = x["strict"].get(rel, {})
            sp_p = f"{sp.get('tp', 0) / sp['predicted']:.2f}" if sp.get("predicted") else "–"
            L.append(f"| {rel} | {s['predicted']} | {s.get('tp', 0)} | {s.get('tp', 0) / s['predicted']:.2f} | "
                     + " | ".join(str(s.get(k, 0)) for k in FP_KINDS) + f" | {sp_p} |")  # fmt: skip
        L.append(f"| **all** | {tot['predicted']} | {tot['tp']} | {tot['tp'] / tot['predicted']:.3f} | "
                 + " | ".join(str(tot[k]) for k in FP_KINDS) + " | |")  # fmt: skip
        L += ["", "Most frequent wrong labels (predicted on gold): "
              + "; ".join(f"{k} x{v}" for k, v in list(x["confusion_overlap"].items())[:12]), "",
              "### Gold relations (overlap): recall and the classification-conditional rate", "",
              "| gold relation | gold | endpoints placed | pair classified | choice right | credited | recall | credited / classified |",
              "|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for rel, s in sorted(x["gold_stages"].items(), key=lambda kv: -kv[1]["gold"]):
            cond = f"{s['credited'] / s['pair_selected']:.2f}" if s["pair_selected"] else "–"
            L.append(f"| {rel} | {s['gold']} | {s['endpoints_placed']} | {s['pair_selected']} | {s['choice_right']} | "
                     f"{s['credited']} | {s['credited'] / s['gold']:.2f} | {cond} |")  # fmt: skip
        c = x["checks"]
        L += ["", "### Checks: rejected relation results", "",
              f"- right choice rejected (a gold relation wrongly dropped): {sum(c['correct'].values())} {c['correct']}",
              f"- wrong choice rejected (noise removed): {sum(c['wrong'].values())} {c['wrong']}",
              f"- pair accounting: {x['pairs']}", ""]  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "precision.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "precision.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
