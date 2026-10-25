"""CR-056 $0 rescoring variant `IDXR1N-P1`: `IDXR1X-P1` (CR-052 span rules) plus NESTED placement: inside every placed mention, every
token-aligned occurrence of another node's name or alias (R1 key) is placed too, for that node ("language model" inside "pre-trained
language model"). Gold-free; reported beside `IDXR1-P1` (rule 35). Recall-first: it adds mentions, so precision can fall.

    uv run python -m cumap.cr056.nested --tag cr055b"""

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
from cumap.cr043.run import run_id
from cumap.cr052 import extend as X


def k(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def nested_nodes(
    doc, cp: dict, nodes: list, *, rules=("X-acr", "X-head"), nested: bool = True
) -> list:
    forms = {}
    for c in cp["concepts"]:
        for f in {c["canonical_name"], *(c.get("aliases") or [])}:
            if f and len(k(f)) >= 2:
                forms.setdefault(k(f), c["concept_id"])
    tok = doc.tokens
    spans = {n.node_id: {X.extend(tok, m, rules) for m in n.mentions} for n in nodes}
    if nested:
        add: dict[str, set] = {}
        for ms in spans.values():
            for a, b in ms:
                for i in range(a, b):
                    for j in range(i + 1, min(b, i + 6) + 1):
                        if (i, j) == (a, b):
                            continue
                        cid = forms.get(k(" ".join(tok[i:j])))
                        if cid and cid in spans:
                            add.setdefault(cid, set()).add((i, j))
        for cid, extra in add.items():
            spans[cid] |= extra
    return [dataclasses.replace(n, mentions=tuple(sorted(spans[n.node_id]))) for n in nodes]


def score(doc, g, cp, sym, nested: bool):
    pred = V.sc_predict_indexed(doc, cp, "r1key")
    nodes = nested_nodes(doc, cp, pred["nodes"], nested=nested)
    rels, unplaced = S.project_edges_to_mentions(nodes, pred["edges"])
    res = S.score_scinlp_unit(g, S.project_nodes_to_mentions(nodes), rels, sym)
    r = res["rel"]
    res["rel"] = PRF(r.tp, r.fp + unplaced + pred["stats"]["edges_without_node_or_quote"], r.fn)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="cr055b")
    a = ap.parse_args()
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    papers = first_set()
    gold = {s: ad.gold(s) for s in {s for s, _ in papers}}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in gold
    }
    out = {"tag": a.tag}
    for name, nested in (("IDXR1X-P1", False), ("IDXR1N-P1", True)):
        rel, ent = [], []
        for s, d in papers:
            res = score(
                docs[s][d],
                gold[s][d],
                json.loads((PG.run_path(run_id(d, a.tag)) / "checkpoint.json").read_text()),
                sym,
                nested,
            )
            rel.append(res["rel"])
            ent.append(res["entity_strict"])
        R = PRF(sum(x.tp for x in rel), sum(x.fp for x in rel), sum(x.fn for x in rel))
        E = PRF(sum(x.tp for x in ent), sum(x.fp for x in ent), sum(x.fn for x in ent))
        out[name] = {
            "relation": [round(R.precision, 3), round(R.recall, 3), round(R.f1, 3)],
            "concept": [round(E.precision, 3), round(E.recall, 3), round(E.f1, 3)],
        }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
