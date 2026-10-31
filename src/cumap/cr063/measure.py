"""CR-063 $0 measurement: span identity A-name (v11) and A-name-acr under `IDXR1-P1` and the symbol-aware `IDXR1S-P1`, on the 57 SciNLP
train / dev papers (v5 runs, span identity applied in memory). No model call.

    uv run python -m cumap.cr063.measure"""

from __future__ import annotations

import json

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.eval import PRIMARY, pool, prf_d
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr060 import span_identity as SI
from cumap.cr063 import grounding as G

OUT = REPO_ROOT / "reports/cr063"
SETS = (("first", "cr055ballp"), ("rest", "cr057rest"))
ARMS = ("A-name", "A-name-acr")
GROUNDINGS = (PRIMARY, G.VARIANT)


def main() -> None:
    ad = SciNLPAdapter()
    sym = set(ad.symmetric_relations())
    docs, golds = {}, {}
    for s in ("train", "dev"):
        docs.update(
            {x.doc_key: x for x in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        )
        golds.update(ad.gold(s))
    res: dict = {}
    for set_name, tag in SETS:
        acc = {(a, g): ([], []) for a in ARMS for g in GROUNDINGS}
        ext = {a: 0 for a in ARMS}
        for _s, d in paper_set(set_name):
            cp0 = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, gold = docs[d], golds[d]
            for a in ARMS:
                cp, _ = SI.apply(cp0, doc.text, SI.load_variant(a), symmetric=frozenset(sym))
                r = V.sc_score(doc, gold, cp, sym, PRIMARY)["scores"]
                acc[(a, PRIMARY)][0].append(r["entity_strict"])
                acc[(a, PRIMARY)][1].append(r["rel"])
                gr = G.score(doc, gold, cp, sym)
                acc[(a, G.VARIANT)][0].append(gr["scores"]["entity_strict"])
                acc[(a, G.VARIANT)][1].append(gr["scores"]["rel"])
                ext[a] += gr["pred"]["stats"]["spans_extended"]
        res[set_name] = {
            f"{a} @ {g}": {"concept": prf_d(pool(acc[(a, g)][0])), "relation": prf_d(pool(acc[(a, g)][1]))}
            for a in ARMS for g in GROUNDINGS
        }  # fmt: skip
        res[set_name]["spans_extended"] = ext
    base = {s: res[s][f"A-name @ {PRIMARY}"] for s, _ in SETS}
    L = ["# CR-063: symbol-aware grounding (57 SciNLP train / dev papers; v5 runs + span identity in memory)", "",
         f"Reference: v11 (A-name) under `{PRIMARY}`. `{G.VARIANT}` is reported beside it (rule 35).", ""]  # fmt: skip
    for set_name, _ in SETS:
        L += [f"## Set `{set_name}`", "", "| arm @ grounding | concept P / R / F2 (F1) | recall Δ | relation P / R / F1 | relation F1 Δ |",
              "|---|---|---|---|---|"]  # fmt: skip
        b = base[set_name]
        for k, x in res[set_name].items():
            if k == "spans_extended":
                continue
            c, r = x["concept"], x["relation"]
            L.append(f"| {k} | {c['precision']:.3f} / {c['recall']:.3f} / **{c['f2']:.3f}** ({c['f1']:.3f}) | "
                     f"{c['recall'] - b['concept']['recall']:+.4f} | {r['precision']:.3f} / {r['recall']:.3f} / {r['f1']:.3f} | "
                     f"{r['f1'] - b['relation']['f1']:+.4f} |")  # fmt: skip
        L += ["", f"Spans extended over symbols: {res[set_name]['spans_extended']}.", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "grounding.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "grounding.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
