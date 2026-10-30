"""CR-060 Part B sizing at $0: choose k (hints per unit) for the M8 noun-phrase hint on the 20 first-set papers, by the pre-registered
criterion: F1 of hint keys against the R1 keys of gold mentions the v5 run (`cr055ballp`) never proposed; ties -> smaller k. Coverage is
approximated by the v5 run's final concepts (names, aliases, recorded surfaces) for the whole paper, so the hint counts are a lower bound
of what the live run shows. No model call (the local embedder only).

    uv run python -m cumap.cr060.measure_b"""

from __future__ import annotations

import json
from collections import Counter

import spacy

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4 import pd_run as P
from cumap.concepts_v4.verifier import _covered
from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id
from cumap.cr058 import graphs as GR
from cumap.cr060 import np_candidates as NP
from cumap.expert_kg.alias_rules import AliasConfig, r1_key

OUT = REPO_ROOT / "reports/cr060"
KS = (5, 10, 15, 20, 30)
TAG = "cr055ballp"


def units_of(doc) -> dict[str, str]:
    us = P.make_units(
        [{"section_id": doc.doc_key, "chapter_num": 1, "order_index": 0, "text": doc.text}]
    )
    return {u["section_id"]: u["text"] for u in us}


def never_proposed(doc, g, cp) -> list[str]:
    """Gold mention surfaces the v5 run never proposed (the CR-058 / CR-054 trace)."""
    from cumap.cr019 import variants as V
    from cumap.cr054.recall import run_trace

    pred = V.sc_predict_indexed(doc, cp, "r1key")
    spans = {sp for n in pred["nodes"] for sp in n.mentions}
    trace = run_trace(run_id(doc.doc_key, TAG))
    losses = GR.mention_losses(doc, g, cp, spans, trace)
    return [GR._txt(doc, sp) for sp, (stage, _d) in losses.items() if stage == "never_proposed"]


def main() -> None:
    cfg = AliasConfig.load()
    ad = SciNLPAdapter()
    nlp = spacy.load("en_core_web_sm")
    embed = X.Embedder(get_settings().embeddings.model)
    papers = first_set()
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in {s for s, _ in papers}
    }
    tot = {k: Counter() for k in KS}
    per_paper, examples = {}, []
    for s, d in papers:
        doc, g = docs[s][d], ad.gold(s)[d]
        cp = json.loads((PG.run_path(run_id(d, TAG)) / "checkpoint.json").read_text())
        out = {"new_concepts": [{"name": c["canonical_name"], "aliases": c.get("aliases") or []} for c in cp["concepts"]],
               "existing_mentions": [{"surface": m.get("surface", "")} for c in cp["concepts"] for m in c.get("mentions", [])
                                     if m.get("surface")]}  # fmt: skip
        np_keys = {r1_key(t, cfg) for t in never_proposed(doc, g, cp)}
        gold_keys = {r1_key(GR._txt(doc, m.span), cfg) for m in g.mentions}
        ranked = NP.rank(units_of(doc), nlp, embed)
        per_paper[d] = {"units": len(ranked), "never_proposed_keys": len(np_keys)}
        for k in KS:
            hints = set()
            for cs in ranked.values():
                shown = [c for c in cs if not _covered(c.text, out, cfg)][:k]
                hints |= {c.key for c in shown}
                if k == 15 and len(examples) < 60:
                    examples += [f"{d}: {c.text}" + (" [GOLD-NP]" if c.key in np_keys else " [gold]" if c.key in gold_keys else "")
                                 for c in shown[:3]]  # fmt: skip
            tot[k].update(hints=len(hints), hit_np=len(hints & np_keys), np_keys=len(np_keys),
                          hit_gold=len(hints & gold_keys))  # fmt: skip
    res = {"tag": TAG, "papers": len(papers), "rows": {}}
    for k in KS:
        t = tot[k]
        p = t["hit_np"] / t["hints"] if t["hints"] else 0.0
        r = t["hit_np"] / t["np_keys"] if t["np_keys"] else 0.0
        res["rows"][k] = {**dict(t), "precision_np": round(p, 4), "recall_np": round(r, 4),
                          "f1_np": round(2 * p * r / (p + r), 4) if p + r else 0.0,
                          "precision_any_gold": round(t["hit_gold"] / t["hints"], 4) if t["hints"] else 0.0}  # fmt: skip
    best = max(KS, key=lambda k: (res["rows"][k]["f1_np"], -k))
    res["chosen_k"] = best
    res["examples_k15"] = examples
    res["per_paper"] = per_paper
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "part_b_sizing.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    L = [f"# CR-060 Part B sizing ($0, {len(papers)} first-set papers, coverage by `{TAG}`)", "",
         "| k per unit | hints | never-proposed gold keys hit | of | P (np) | R (np) | F1 (np) | hints that are any gold key |",
         "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for k in KS:
        x = res["rows"][k]
        L.append(f"| {k} | {x['hints']} | {x['hit_np']} | {x['np_keys']} | {x['precision_np']:.3f} | {x['recall_np']:.3f} | "
                 f"{x['f1_np']:.3f} | {x['precision_any_gold']:.3f} |")  # fmt: skip
    L += ["", f"**Chosen k (pre-registered criterion): {best}**"]
    (OUT / "part_b_sizing.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
