"""CR-060 Part B2, a $0 REPLAY DIAGNOSTIC (rule 24: never a production run): ranked noun-phrase candidates added AS concepts to the saved
v5 checkpoints of the 20 first-set papers. Each added node has one mention whose quote is a paper sentence containing it (exact substring,
rule 3) and no edges. Arms `NPC-k`: the top k uncovered candidates per unit; `NPC-all-nofilter`: every candidate. Objective `IDXR1-P1`.

    uv run python -m cumap.cr060.measure_c"""

from __future__ import annotations

import copy
import json
from collections import Counter

import spacy

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4.verifier import _covered
from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.eval import PRIMARY, pool, prf_d
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id
from cumap.cr060 import np_candidates as NP
from cumap.cr060.measure_b import units_of
from cumap.expert_kg.alias_rules import AliasConfig

OUT = REPO_ROOT / "reports/cr060"
TAG = "cr055ballp"
ARMS = ("control", "NPC-5", "NPC-10", "NPC-20", "NPC-30", "NPC-all", "NPC-all-nofilter")


def _quote(c: NP.Cand, sents: list[str], text: str) -> str | None:
    for i in c.sentences:
        q = " ".join(sents[i].split())
        if q and q in text:
            return q
    return None


def add_np_concepts(cp: dict, ranked: dict[str, list[NP.Cand]], sents: list[str], text: str, doc_key: str,
                    k: int | None, covered) -> tuple[dict, Counter]:  # fmt: skip
    cp = copy.deepcopy(cp)
    st: Counter = Counter()
    seen: set[str] = set()
    for cs in ranked.values():
        pick = [c for c in cs if covered is None or not covered(c.text)]
        for c in pick if k is None else pick[:k]:
            if c.key in seen:
                continue
            seen.add(c.key)
            q = _quote(c, sents, text)
            if q is None:
                st["no_exact_quote"] += 1
                continue
            cp["concepts"].append({"concept_id": f"np_{c.key}", "canonical_name": c.text, "aliases": [], "node_type": "Concept",
                                   "mentions": [{"section_id": doc_key, "quote": q, "surface": c.text}],
                                   "extraction_origin": "cr060_np_replay"})  # fmt: skip
            st["added"] += 1
    return cp, st


def main() -> None:
    cfg = AliasConfig.load()
    ad = SciNLPAdapter()
    sym = set(ad.symmetric_relations())
    nlp = spacy.load("en_core_web_sm")
    embed = X.Embedder(get_settings().embeddings.model)
    papers = first_set()
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in {s for s, _ in papers}
    }
    acc = {a: {"ent": [], "rel": []} for a in ARMS}
    counts = {a: Counter() for a in ARMS}
    for s, d in papers:
        doc, g = docs[s][d], ad.gold(s)[d]
        cp0 = json.loads((PG.run_path(run_id(d, TAG)) / "checkpoint.json").read_text())
        out = {"new_concepts": [{"name": c["canonical_name"], "aliases": c.get("aliases") or []} for c in cp0["concepts"]],
               "existing_mentions": []}  # fmt: skip
        units = units_of(doc)
        ranked = NP.rank(units, nlp, embed)
        sents = [" ".join(s.text.split()) for u in units.values() for s in nlp(u).sents]
        cov = {}

        def covered(t: str, _o=out, _c=cov) -> bool:
            if t not in _c:
                _c[t] = _covered(t, _o, cfg)
            return _c[t]

        for a in ARMS:
            if a == "control":
                cp, st = cp0, Counter()
            else:
                k = None if a.startswith("NPC-all") else int(a.split("-")[1])
                cp, st = add_np_concepts(
                    cp0, ranked, sents, doc.text, d, k, None if a == "NPC-all-nofilter" else covered
                )
            counts[a].update(st)
            counts[a]["concepts"] += len(cp["concepts"])
            r = V.sc_score(doc, g, cp, sym, PRIMARY)
            acc[a]["ent"].append(r["scores"]["entity_strict"])
            acc[a]["rel"].append(r["scores"]["rel"])
    res = {
        "tag": TAG,
        "papers": len(papers),
        "objective": PRIMARY,
        "diagnostic_only": "rule 24",
        "arms": {},
    }
    c0 = None
    for a in ARMS:
        x = {
            "concept": prf_d(pool(acc[a]["ent"])),
            "relation": prf_d(pool(acc[a]["rel"])),
            "counts": dict(counts[a]),
        }
        if c0 is None:
            c0 = x
        else:
            x["vs_control"] = {"concept_recall": round(x["concept"]["recall"] - c0["concept"]["recall"], 4),
                               "concept_f1": round(x["concept"]["f1"] - c0["concept"]["f1"], 4),
                               "relation_f1": round(x["relation"]["f1"] - c0["relation"]["f1"], 4)}  # fmt: skip
        res["arms"][a] = x
    L = [f"# CR-060 Part B2: noun phrases as concepts (REPLAY DIAGNOSTIC, rule 24; `{TAG}`, {len(papers)} papers, `{PRIMARY}`)", "",
         "| arm | concepts | added | concept P / R / F1 | relation F1 | recall vs v5 |", "|---|---|---|---|---|---|"]  # fmt: skip
    for a, x in res["arms"].items():
        cc, n = x["concept"], x["counts"]
        dv = x.get("vs_control", {}).get("concept_recall")
        L.append(f"| {a} | {n.get('concepts', 0)} | {n.get('added', 0)} | {cc['precision']:.3f} / {cc['recall']:.3f} / {cc['f1']:.3f} | "
                 f"{x['relation']['f1']:.3f} | {'—' if dv is None else f'{dv:+.3f}'} |")  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "part_b2_np_concepts.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "part_b2_np_concepts.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
