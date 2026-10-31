"""CR-063 addendum, $0: v5 and v11 under `IDXR1-P1` and the position-tolerant `IDXR1T1-P1` / `IDXR1T2-P1`, on the 57 SciNLP train / dev
papers. No model call.

    uv run python -m cumap.cr063.measure_tol"""

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
from cumap.cr063 import tolerant as T

OUT = REPO_ROOT / "reports/cr063"
SETS = (("first", "cr055ballp"), ("rest", "cr057rest"))
PROFILES = (("v5", None), ("v11", "A-name"))
GROUNDINGS = (PRIMARY, "IDXR1T1-P1", "IDXR1T2-P1")


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
    for set_name, tag in [*SETS, ("all", None)]:
        if set_name == "all":
            continue
        acc = {(p, g): ([], []) for p, _ in PROFILES for g in GROUNDINGS}
        snapped = {(p, g): 0 for p, _ in PROFILES for g in GROUNDINGS}
        for _s, d in paper_set(set_name):
            cp0 = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, gold = docs[d], golds[d]
            for p, var in PROFILES:
                cp = (
                    cp0
                    if var is None
                    else SI.apply(cp0, doc.text, SI.load_variant(var), symmetric=frozenset(sym))[0]
                )
                r = V.sc_score(doc, gold, cp, sym, PRIMARY)["scores"]
                acc[(p, PRIMARY)][0].append(r["entity_strict"])
                acc[(p, PRIMARY)][1].append(r["rel"])
                for n in (1, 2):
                    g = f"IDXR1T{n}-P1"
                    t = T.score(doc, gold, cp, sym, n)
                    acc[(p, g)][0].append(t["scores"]["entity_strict"])
                    acc[(p, g)][1].append(t["scores"]["rel"])
                    snapped[(p, g)] += t["snapped"]
        res[set_name] = {f"{p} @ {g}": {"concept": prf_d(pool(acc[(p, g)][0])), "relation": prf_d(pool(acc[(p, g)][1])),
                                         "snapped": snapped[(p, g)]} for p, _ in PROFILES for g in GROUNDINGS}  # fmt: skip
    res["all"] = {}
    for k in res["first"]:
        f, r = res["first"][k], res["rest"][k]
        from cumap.cr012.types import PRF

        add = lambda a, b: PRF(a["tp"] + b["tp"], a["fp"] + b["fp"], a["fn"] + b["fn"])
        res["all"][k] = {"concept": prf_d(add(f["concept"], r["concept"])), "relation": prf_d(add(f["relation"], r["relation"])),
                         "snapped": f["snapped"] + r["snapped"]}  # fmt: skip
    L = ["# CR-063 addendum: position-tolerant evaluation (+-1 / +-2 characters), 57 SciNLP train / dev papers", "",
         f"Reported beside `{PRIMARY}` (rule 35); evaluation only. A span within N characters of a gold span at both ends counts as that span.", ""]  # fmt: skip
    for set_name in ("first", "rest", "all"):
        L += [
            f"## Set `{set_name}`",
            "",
            "| profile @ grounding | spans snapped | concept P / R / F2 (F1) | relation P / R / F1 |",
            "|---|---|---|---|",
        ]
        for k, x in res[set_name].items():
            c, r = x["concept"], x["relation"]
            L.append(f"| {k} | {x['snapped']} | {c['precision']:.3f} / {c['recall']:.3f} / **{c['f2']:.3f}** ({c['f1']:.3f}) | "
                     f"{r['precision']:.3f} / {r['recall']:.3f} / {r['f1']:.3f} |")  # fmt: skip
        L.append("")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tolerant.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "tolerant.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
