"""CR-052 $0 rescoring variant `IDXR1X-P1`: `IDXR1-P1` with two gold-free span-extension rules applied to every predicted mention
before scoring (rule 35: reported beside `IDXR1-P1`, never instead of it). The rules look only at the paper's own tokens:
- `X-acr`: a mention directly followed by "( Y )", where Y is one acronym-like token, absorbs it ("word sense disambiguation ( WSD )");
- `X-head`: a mention directly followed by a generic head noun absorbs it ("GPT-3 model", "a neural approach").

    uv run python -m cumap.cr052.extend [--tag cr043base]"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re

from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.scoring import PRF
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import TAG, run_id

HEADS = {"approach", "approaches", "model", "models", "method", "methods", "system", "systems", "algorithm", "algorithms",
         "framework", "frameworks", "technique", "techniques", "dataset", "datasets", "corpus", "corpora"}  # fmt: skip


def acronym_like(t: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9\-\.]{1,10}", t)) and sum(c.isupper() for c in t) >= 2


def extend(tokens: list[str], sp: tuple[int, int], rules: tuple[str, ...]) -> tuple[int, int]:
    s, e = sp
    if "X-head" in rules and e < len(tokens) and tokens[e].lower() in HEADS:
        e += 1
    if (
        "X-acr" in rules
        and e + 2 < len(tokens) + 0
        and tokens[e] == "("
        and e + 2 < len(tokens)
        and tokens[e + 2] == ")"
        and acronym_like(tokens[e + 1])
    ):
        e += 3
    return (s, e)


def score(doc, g, cp, sym, rules: tuple[str, ...]):
    pred = V.sc_predict_indexed(doc, cp, "r1key")
    nodes = [
        dataclasses.replace(
            n, mentions=tuple(sorted({extend(doc.tokens, m, rules) for m in n.mentions}))
        )
        for n in pred["nodes"]
    ]
    rels, unplaced = S.project_edges_to_mentions(nodes, pred["edges"])
    res = S.score_scinlp_unit(g, S.project_nodes_to_mentions(nodes), rels, sym)
    r = res["rel"]
    res["rel"] = PRF(r.tp, r.fp + unplaced + pred["stats"]["edges_without_node_or_quote"], r.fn)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=TAG)
    a = ap.parse_args()
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    papers = first_set()
    gold = {s: ad.gold(s) for s in {s for s, _ in papers}}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in gold
    }
    arms = {
        "IDXR1-P1": (),
        "X-acr": ("X-acr",),
        "X-head": ("X-head",),
        "IDXR1X-P1 (both)": ("X-acr", "X-head"),
    }
    out = {}
    for name, rules in arms.items():
        rel, ent = [], []
        for s, d in papers:
            f = PG.run_path(run_id(d, a.tag)) / "checkpoint.json"
            if not f.exists():
                continue
            res = score(docs[s][d], gold[s][d], json.loads(f.read_text()), sym, rules)
            rel.append(res["rel"])
            ent.append(res["entity_strict"])
        R = PRF(sum(x.tp for x in rel), sum(x.fp for x in rel), sum(x.fn for x in rel))
        E = PRF(sum(x.tp for x in ent), sum(x.fp for x in ent), sum(x.fn for x in ent))
        out[name] = {
            "relation": [round(R.precision, 3), round(R.recall, 3), round(R.f1, 3), R.tp],
            "concept": [round(E.precision, 3), round(E.recall, 3), round(E.f1, 3)],
        }
    print(json.dumps({"tag": a.tag, **out}, indent=1))


if __name__ == "__main__":
    main()
