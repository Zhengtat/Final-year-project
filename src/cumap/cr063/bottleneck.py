"""CR-063: where the pipeline loses gold concepts and relations under the overlap headline (`IDXR1OV-P1`), beside strict, for v11 on the
57 SciNLP train / dev papers ($0, no model call).

Overlap funnel: every gold mention that the overlap matching (`cr063.tolerant`, one-to-one, closest first) pairs with a predicted span is
relabelled to that span, and the unchanged CR-058 funnel (`relation_funnel`, `mention_losses`) runs on the relabelled gold, so a gold
relation counts as "endpoints placed" when both of its endpoints are overlap-matched. The funnel's credited count equals the overlap
relation true positives (checked).

    uv run python -m cumap.cr063.bottleneck"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import UnitGold
from cumap.cr019 import variants as V
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr054.recall import run_trace
from cumap.cr058 import funnel as FN
from cumap.cr058 import graphs as GR
from cumap.cr060 import span_identity as SI
from cumap.cr063 import tolerant as T

OUT = REPO_ROOT / "reports/cr063"
SETS = (("first", "cr055ballp"), ("rest", "cr057rest"))
CHAIN = (
    ("gold", *FN.GOLD_REL_STAGES[1:], "credited")
    if FN.GOLD_REL_STAGES[0] == "gold"
    else ("gold", *FN.GOLD_REL_STAGES, "credited")
)


def relabel(gold: UnitGold, inv: dict) -> UnitGold:
    return dataclasses.replace(
        gold,
        mentions=[dataclasses.replace(m, span=inv.get(m.span, m.span)) for m in gold.mentions],
        relations=[dataclasses.replace(r, src_span=inv.get(r.src_span, r.src_span), tgt_span=inv.get(r.tgt_span, r.tgt_span))
                   for r in gold.relations],
    )  # fmt: skip


def choice_misses(g: UnitGold, cp: dict, pred: dict, lost_at: list[str], sym: set[str]) -> Counter:
    """For gold relations lost at the choice step (family right, no right relation + direction): what the pair's results said."""
    owner: dict = {}
    for n in pred["nodes"]:
        for sp in n.mentions:
            owner.setdefault(sp, set()).add(n.node_id)
    by_pair: dict = {}
    for r in cp["relation_results_v3"]:
        if r.get("group", "selected") == "selected":
            by_pair.setdefault(
                frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"])), []
            ).append(r)
    out: Counter = Counter()
    for gr, at in zip(g.relations, lost_at, strict=True):
        if at != "choice_right":
            continue
        A, B = owner.get(gr.src_span, set()), owner.get(gr.tgt_span, set())
        rs = [
            r
            for a in A
            for b in B
            if a != b
            for r in by_pair.get(frozenset((a, b)), [])
            if r.get("family") == FN.FAMILY
        ]
        rels = [r.get("relation") for r in rs]
        if not any(rels):
            out["declined (no relation chosen)"] += 1
        elif gr.relation in rels:
            out["right relation, wrong direction"] += 1
        else:
            out[f"wrong relation: gold {gr.relation} -> {next(x for x in rels if x)}"] += 1
    return out


def main() -> None:
    ad = SciNLPAdapter()
    sym = set(ad.symmetric_relations())
    docs, golds = {}, {}
    for s in ("train", "dev"):
        docs.update(
            {x.doc_key: x for x in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        )
        golds.update(ad.gold(s))
    stages = {"strict": Counter(), "overlap": Counter()}
    losses = {"strict": Counter(), "overlap": Counter()}
    checks = Counter()
    choice = Counter()
    not_selected = Counter()
    examples: dict[str, Counter] = {}
    gold_mentions = 0
    for set_name, tag in SETS:
        for _s, d in paper_set(set_name):
            rid = run_id(d, tag)
            cp = json.loads((PG.run_path(rid) / "checkpoint.json").read_text())
            doc, g = docs[d], golds[d]
            cp, _ = SI.apply(cp, doc.text, SI.load_variant("A-name"), symmetric=frozenset(sym))
            pred = V.sc_score(doc, g, cp, sym, "IDXR1-P1")["pred"]
            spans = {sp for n in pred["nodes"] for sp in n.mentions}
            m = T.snap_map_words(doc, {x.span for x in g.mentions}, spans, "overlap")
            g2 = relabel(g, {gs: ps for ps, gs in m.items()})
            trace = run_trace(rid)
            gold_mentions += len(g.mentions)
            for name, gg in (("strict", g), ("overlap", g2)):
                rf = FN.relation_funnel(doc, gg, cp, sym)
                stages[name].update(rf["gold_stages"])
                for sp, (stage, _det) in GR.mention_losses(doc, gg, cp, spans, trace).items():
                    losses[name][stage] += 1
                    if name == "overlap":
                        examples.setdefault(stage, Counter())[
                            " ".join(doc.tokens[sp[0] : sp[1]])
                        ] += 1
                if name == "overlap":
                    choice.update(choice_misses(gg, cp, pred, rf["lost_at"], sym))
                    not_selected.update(rf["not_selected_split"])
                    ov = T.score(doc, g, cp, sym, "overlap")["scores"]["rel"]
                    checks["funnel_credited"] += rf["gold_stages"]["credited"]
                    checks["overlap_tp"] += ov.tp
    res = {"gold_mentions": gold_mentions, "stages": {k: dict(v) for k, v in stages.items()},
           "concept_losses": {k: dict(v) for k, v in losses.items()}, "check": dict(checks),
           "examples": {k: [t for t, _ in v.most_common(30)] for k, v in examples.items()},
           "choice_misses": dict(choice.most_common()), "not_selected_split": dict(not_selected)}  # fmt: skip
    keys = list(stages["overlap"])
    L = ["# CR-063: bottlenecks under the overlap headline (v11, 57 SciNLP train / dev papers, $0)", "",
         f"Check: funnel credited (overlap) = {checks['funnel_credited']}, overlap relation tp = {checks['overlap_tp']}.", "",
         "## Gold relations reaching each stage", "", "| stage | strict | pass | overlap | pass |", "|---|---|---|---|---|"]  # fmt: skip
    prev = {k: None for k in stages}
    for st in keys:
        row = [st]
        for k in ("strict", "overlap"):
            n = stages[k][st]
            row += [str(n), f"{n / prev[k]:.0%}" if prev[k] else "–"]
            prev[k] = n
        L.append("| " + " | ".join(row) + " |")
    L += [
        "",
        f"## Gold concept mentions missed ({gold_mentions} gold mentions)",
        "",
        "| reason | strict | overlap |",
        "|---|---|---|",
    ]
    for st in sorted(
        set(losses["strict"]) | set(losses["overlap"]), key=lambda s: -losses["overlap"][s]
    ):
        L.append(f"| {st} | {losses['strict'][st]} | {losses['overlap'][st]} |")
    wrong = sum(v for k, v in choice.items() if k.startswith("wrong relation"))
    L += ["", "## Gold relations lost at the choice step (overlap)", "",
          f"- declined (no relation chosen): {choice['declined (no relation chosen)']}",
          f"- right relation, wrong direction: {choice['right relation, wrong direction']}",
          f"- wrong relation: {wrong}; most frequent: " + "; ".join(f"{k[16:]} x{v}" for k, v in choice.most_common() if k.startswith("wrong"))[:900],
          "", f"Pairs never classified (overlap): {dict(not_selected)}"]  # fmt: skip
    L += [
        "",
        "Examples (overlap, never proposed): "
        + ", ".join(res["examples"].get("never_proposed", [])[:30]),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bottleneck.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "bottleneck.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
