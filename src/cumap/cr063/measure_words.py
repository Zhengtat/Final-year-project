"""CR-063 addendum 2, $0: v5 and v11 under `IDXR1-P1` and the relaxed evaluations `IDXR1T2-P1` (+-2 characters), `IDXR1W1-P1` (+-1 word),
`IDXR1HW-P1` (head-word) and `IDXR1OV-P1` (overlap), on the 57 SciNLP train / dev papers, with a sample of the spans each one credits.
Evaluation only; no model call.

    uv run python -m cumap.cr063.measure_words"""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.types import PRF
from cumap.cr019 import variants as V
from cumap.cr043.eval import PRIMARY, pool, prf_d
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr060 import span_identity as SI
from cumap.cr063 import tolerant as T

OUT = REPO_ROOT / "reports/cr063"
SETS = (("first", "cr055ballp"), ("rest", "cr057rest"))
PROFILES = (("v5", None), ("v11", "A-name"))
RELAXED = (
    ("IDXR1T2-P1", 2),
    ("IDXR1W1-P1", "w1"),
    ("IDXR1HW-P1", "head"),
    ("IDXR1OV-P1", "overlap"),
)
GROUNDINGS = (PRIMARY, *(g for g, _ in RELAXED))


def shape(doc, p, g) -> str:
    if g[0] <= p[0] and p[1] <= g[1]:
        return "prediction inside gold (gold longer)"
    if p[0] <= g[0] and g[1] <= p[1]:
        return "gold inside prediction (prediction longer)"
    return "partial overlap"


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
    shapes = {g: Counter() for g in GROUNDINGS}
    samples: dict[str, Counter] = {g: Counter() for g in GROUNDINGS}
    for set_name, tag in SETS:
        acc = {(p, g): ([], []) for p, _ in PROFILES for g in GROUNDINGS}
        snapped = Counter()
        for _s, d in paper_set(set_name):
            cp0 = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, gold = docs[d], golds[d]
            txt = lambda sp, doc=doc: " ".join(doc.tokens[sp[0] : sp[1]])
            for p, var in PROFILES:
                cp = (
                    cp0
                    if var is None
                    else SI.apply(cp0, doc.text, SI.load_variant(var), symmetric=frozenset(sym))[0]
                )
                r = V.sc_score(doc, gold, cp, sym, PRIMARY)["scores"]
                acc[(p, PRIMARY)][0].append(r["entity_strict"])
                acc[(p, PRIMARY)][1].append(r["rel"])
                for g, mode in RELAXED:
                    t = T.score(doc, gold, cp, sym, mode)
                    acc[(p, g)][0].append(t["scores"]["entity_strict"])
                    acc[(p, g)][1].append(t["scores"]["rel"])
                    snapped[(p, g)] += t["snapped"]
                    if p == "v11":
                        for ps, gs in t["pairs"].items():
                            shapes[g][shape(doc, ps, gs)] += 1
                            samples[g][(txt(ps), txt(gs))] += 1
        res[set_name] = {f"{p} @ {g}": {"concept": prf_d(pool(acc[(p, g)][0])), "relation": prf_d(pool(acc[(p, g)][1])),
                                         "snapped": snapped[(p, g)]} for p, _ in PROFILES for g in GROUNDINGS}  # fmt: skip
    add = lambda a, b: PRF(a["tp"] + b["tp"], a["fp"] + b["fp"], a["fn"] + b["fn"])
    res["all"] = {k: {"concept": prf_d(add(res["first"][k]["concept"], res["rest"][k]["concept"])),
                      "relation": prf_d(add(res["first"][k]["relation"], res["rest"][k]["relation"])),
                      "snapped": res["first"][k]["snapped"] + res["rest"][k]["snapped"]} for k in res["first"]}  # fmt: skip
    res["v11_shapes"] = {g: dict(v) for g, v in shapes.items()}
    res["v11_samples"] = {
        g: [f"{a!r} -> gold {b!r} x{n}" for (a, b), n in v.most_common(25)]
        for g, v in samples.items()
    }
    L = [
        "# CR-063 addendum 2: relaxed evaluations, 57 SciNLP train / dev papers (evaluation only, beside `IDXR1-P1`, rule 35)",
        "",
    ]
    for set_name in ("all", "first", "rest"):
        L += [
            f"## Set `{set_name}`",
            "",
            "| profile @ grounding | spans credited | concept P / R / F2 (F1) | relation P / R / F1 |",
            "|---|---|---|---|",
        ]
        for k, x in res[set_name].items():
            c, r = x["concept"], x["relation"]
            L.append(f"| {k} | {x['snapped']} | {c['precision']:.3f} / {c['recall']:.3f} / **{c['f2']:.3f}** ({c['f1']:.3f}) | "
                     f"{r['precision']:.3f} / {r['recall']:.3f} / {r['f1']:.3f} |")  # fmt: skip
        L.append("")
    L += ["## What each relaxed variant credits (v11, all 57 papers)", ""]
    for g, _m in RELAXED:
        L += [
            f"**{g}**: {res['v11_shapes'][g]}",
            "",
            *[f"- {x}" for x in res["v11_samples"][g][:15]],
            "",
        ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "relaxed.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "relaxed.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
