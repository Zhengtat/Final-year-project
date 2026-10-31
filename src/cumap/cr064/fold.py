"""CR-064 ($0): a "partOf fold" scoring variant, reported BESIDE the overlap and strict numbers, never instead of them.

Owner question (2026-11-01): if partOf is dropped from the registry and the model answers subclassOf, enhancedBy or UsedFor on a pair
whose gold label is partOf, count it as correct. Rule: a predicted mention-level relation (a, b, label) with label in FOLD_FROM that is
not itself a gold relation is credited when gold has (a, b, partOf) for the same ordered pair; each gold partOf is credited once.
Precision keeps every predicted edge in its denominator and recall keeps all gold relations, so the variant only moves wrong-label
answers on gold partOf pairs. It is evaluation only (the gold is never changed) and not comparable with published SciNLP numbers.

The unfolded numbers recomputed here must equal `cumap.cr064.measure` (checked in the output) -- the variant shares its matching.

    uv run python -m cumap.cr064.fold [--arms v5,cr055ballp ...]"""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr043.eval import pool, prf_d
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id
from cumap.cr063 import tolerant as T
from cumap.cr064.measure import finished
from cumap.cr064.precision import edge_rows

OUT = REPO_ROOT / "reports/cr064"
TARGET = "partOf"
FOLD_FROM = ("subclassOf", "enhancedBy", "UsedFor")
ARMS = (
    ("v5", "cr055ballp"),
    ("arm R2", "cr064relR2"),
    ("arm R3", "cr064relR3"),
    ("arm R4", "cr064relR4"),
    ("arm R5", "cr064relR5"),
    ("arm R6", "cr064relR6"),
    ("arm R7", "cr064relR7"),
)


def score_paper(doc, g, cp, sym, *, fold: bool) -> tuple[int, int, int, Counter]:
    """(true positives, predicted, gold, folded credits by predicted label) for one paper, overlap matching."""
    rows, unplaced = edge_rows(doc, g, cp, sym, "overlap")
    g_key = {S._rel_key(r.src_span, r.tgt_span, r.relation, sym) for r in g.relations}
    seen: set = set()
    tp = 0
    credited: set = set()
    folded: Counter = Counter()
    for a, b, rel, _st, _tt in rows:
        k = S._rel_key(a, b, rel, sym)
        if k in seen:
            continue
        seen.add(k)
        if k in g_key:
            tp += 1
        elif fold and rel in FOLD_FROM:
            gk = S._rel_key(a, b, TARGET, sym)
            if gk in g_key and gk not in credited:
                credited.add(gk)
                tp += 1
                folded[rel] += 1
    return tp, len(seen) + sum(unplaced.values()), len(g_key), folded


def prf(tp: int, pred: int, gold: int) -> dict:
    p, r = tp / pred if pred else 0.0, tp / gold if gold else 0.0
    return {"tp": tp, "pred": pred, "gold": gold, "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0}  # fmt: skip


def main() -> None:
    ad = SciNLPAdapter()
    sym = set(ad.symmetric_relations())
    docs, golds = {}, {}
    for s in ("train", "dev"):
        docs.update(
            {x.doc_key: x for x in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        )
        golds.update(ad.gold(s))
    arms = [(a, t) for a, t in ARMS if any(finished(t, d) for _s, d in first_set())]
    papers = [d for _s, d in first_set() if all(finished(t, d) for _a, t in arms)]
    res: dict = {"papers": papers, "target": TARGET, "fold_from": list(FOLD_FROM), "arms": {}}
    L = [
        f"# CR-064: partOf fold scoring variant ({len(papers)} first-set papers; overlap `IDXR1OV-P1`)",
        "",
        (
            f"A predicted {', '.join(FOLD_FROM)} on a pair whose gold label is {TARGET} (same ordered pair) counts as correct; "
            "reported BESIDE the overlap and strict numbers, never instead of them; not comparable with published SciNLP numbers."
        ),
        "",
        "| arm | overlap P / R / F1 (as scored) | check vs measure | **folded** P / R / F1 | credits by predicted label |",
        "|---|---|---|---|---|",
    ]
    for arm, tag in arms:
        base, fold = [0, 0, 0], [0, 0, 0]
        folded: Counter = Counter()
        official = []
        for d in papers:
            cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, g = docs[d], golds[d]
            for acc, f in ((base, False), (fold, True)):
                tp, pred, gold, fc = score_paper(doc, g, cp, sym, fold=f)
                acc[0] += tp
                acc[1] += pred
                acc[2] += gold
                if f:
                    folded.update(fc)
            official.append(T.score(doc, g, cp, sym, "overlap")["scores"]["rel"])
        pb, pf, po = prf(*base), prf(*fold), prf_d(pool(official))
        ok = abs(pb["f1"] - po["f1"]) < 5e-4 and abs(pb["precision"] - po["precision"]) < 5e-4
        res["arms"][arm] = {"tag": tag, "as_scored": pb, "folded": pf, "official_overlap": po,
                            "matches_official": ok, "credits": dict(folded)}  # fmt: skip
        L.append(
            f"| {arm} | {pb['precision']:.3f} / {pb['recall']:.3f} / {pb['f1']:.3f} | "
            f"{'ok' if ok else 'MISMATCH ' + format(po['f1'], '.3f')} | "
            f"{pf['precision']:.3f} / {pf['recall']:.3f} / **{pf['f1']:.3f}** | {dict(folded) or '–'} |"
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fold.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "fold.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
