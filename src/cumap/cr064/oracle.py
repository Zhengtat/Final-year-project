"""CR-064 ($0, no model call): stage-by-stage oracle ladder for the relation step on the 20 first-set papers (train/dev only).

An *oracle at stage k* replaces stage k and everything after it by gold knowledge for the gold relations that reached stage k - 1, so
its score is the ceiling a perfect stage k could give with the earlier stages as they are. Two precision readings, both shown:

- `FPs kept`: every prediction the arm already makes stays (the oracle only adds the newly credited gold relations as predictions).
- `FPs removed`: perfect negatives as well (precision 1), so the figure is 2R / (1 + R) for the recall the stage allows.

Precision-side oracles keep recall fixed and delete one kind of false positive (the kinds of `cumap.cr064.precision`). Everything is
overlap `IDXR1OV-P1`; the arm's own score is recomputed here and must equal `cumap.cr064.measure` (checked in the output).

    uv run python -m cumap.cr064.oracle [--arm cr064relR8]"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id
from cumap.cr058 import funnel as FN
from cumap.cr063 import bottleneck as BN
from cumap.cr063 import tolerant as T
from cumap.cr064.precision import FP_KINDS, per_relation

OUT = REPO_ROOT / "reports/cr064"
ARMS = {"cr064relR8": "R8 (origin sentence, no partOf)", "cr064relR3": "R3", "cr055ballp": "v5"}
STAGES = (  # (oracle name, gold-stage whose count is the number of credited gold relations)
    ("perfect mention-level credit (edge on the right gold mention pair)", "assembled"),
    ("perfect checks and assembly", "choice_right"),
    ("perfect choice (label + direction)", "family_right"),
    ("perfect pair selection and classification", "endpoints_placed"),
    ("perfect concepts (every gold endpoint is a node)", "gold"),
)


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def collect(tag: str) -> dict:
    ad = SciNLPAdapter()
    sym = set(ad.symmetric_relations())
    docs, golds = {}, {}
    for s in ("train", "dev"):
        docs.update(
            {x.doc_key: x for x in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        )
        golds.update(ad.gold(s))
    papers = [d for _s, d in first_set()]
    stages, pairs, split, losses = Counter(), Counter(), Counter(), Counter()
    tp = pred = gold = 0
    for d in papers:
        cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
        doc, g = docs[d], golds[d]
        ov = T.score(doc, g, cp, sym, "overlap")["scores"]["rel"]
        tp, pred, gold = tp + ov.tp, pred + ov.tp + ov.fp, gold + ov.tp + ov.fn
        st = V.sc_score(doc, g, cp, sym, "IDXR1-P1")["pred"]
        spans = {sp for n in st["nodes"] for sp in n.mentions}
        m = T.snap_map_words(doc, {x.span for x in g.mentions}, spans, "overlap")
        rf = FN.relation_funnel(doc, BN.relabel(g, {gs: ps for ps, gs in m.items()}), cp, sym)
        stages.update(rf["gold_stages"])
        pairs.update(rf["pairs"])
        split.update(rf["not_selected_split"])
        losses.update(rf["lost_at"])
    fp = Counter()
    for s in per_relation(papers, docs, golds, sym, tag, "overlap")["stats"].values():
        fp.update({k: s.get(k, 0) for k in FP_KINDS})
    return {"tp": tp, "pred": pred, "gold": gold, "stages": dict(stages), "pairs": dict(pairs),
            "not_selected_split": dict(split), "lost_at": dict(losses), "fp": dict(fp)}  # fmt: skip


def ladder(x: dict) -> list[dict]:
    tp, pred, gold = x["tp"], x["pred"], x["gold"]
    p0, r0 = tp / pred, tp / gold
    rows = [{"name": "as run", "tp": tp, "recall": r0, "p_kept": p0, "f1_kept": f1(p0, r0),
             "f1_clean": f1(1.0, r0)}]  # fmt: skip
    for name, stage in STAGES:
        t = x["stages"][stage]
        p = t / (pred + t - tp)
        rows.append({"name": name, "tp": t, "recall": t / gold, "p_kept": p, "f1_kept": f1(p, t / gold),
                     "f1_clean": f1(1.0, t / gold)})  # fmt: skip
    return rows


def precision_side(x: dict) -> list[dict]:
    tp, pred, gold = x["tp"], x["pred"], x["gold"]
    r = tp / gold
    out, removed = [], 0
    for label, kinds in (
        ("remove wrong direction + wrong label (choice errors on gold pairs)", ("wrong direction", "wrong label")),
        ("also remove unplaced edges", ("unplaced",)),
        ("also remove non-gold endpoints (concept precision)", ("non-gold endpoint",)),
        ("also remove unannotated pairs (gold incompleteness)", ("unannotated pair",)),
    ):  # fmt: skip
        removed += sum(x["fp"].get(k, 0) for k in kinds)
        p = tp / (pred - removed)
        out.append({"name": label, "pred": pred - removed, "precision": p, "f1": f1(p, r)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="cr064relR8")
    tag = ap.parse_args().arm
    x = collect(tag)
    res = {"tag": tag, **x, "ladder": ladder(x), "precision_side": precision_side(x)}
    s, pr = x["stages"], x["pairs"]
    score = (
        f"Recomputed arm score: TP {x['tp']}, predicted {x['pred']}, gold {x['gold']} "
        f"-> P {x['tp'] / x['pred']:.3f} / R {x['tp'] / x['gold']:.3f} / "
        f"F1 {f1(x['tp'] / x['pred'], x['tp'] / x['gold']):.3f}."
    )
    L = [f"# CR-064: relation-step oracle ladder, {ARMS.get(tag, tag)} (20 first-set papers, overlap `IDXR1OV-P1`, $0)", "",
         score, "",
         "## 1. Where the gold relations are lost (each stage keeps only what survived the one before)", "",
         "| stage | gold relations still alive | % of gold | lost here |", "|---|---|---|---|"]  # fmt: skip
    prev = None
    for k in FN.GOLD_REL_STAGES:
        n = s[k]
        L.append(f"| {k} | {n} | {n / x['gold']:.1%} | {'' if prev is None else prev - n} |")
        prev = n
    L += ["", f"Gold relations whose pair was never selected: same sentence vs other sentence = {x['not_selected_split']}.", "",
          "## 2. Pair-level accounting (selected pairs)", "", "```", json.dumps(pr, indent=1), "```", "",
          "## 3. Oracle ladder (recall side): ceiling if that stage and all later ones were perfect", "",
          "| oracle | credited gold | recall | precision (FPs kept) | F1 (FPs kept) | F1 (FPs removed) |", "|---|---|---|---|---|---|"]  # fmt: skip
    for r in res["ladder"]:
        L.append(
            f"| {r['name']} | {r['tp']} | {r['recall']:.3f} | {r['p_kept']:.3f} | **{r['f1_kept']:.3f}** | {r['f1_clean']:.3f} |"
        )
    L += ["", "## 4. Precision-side oracles (recall fixed), cumulative", "",
          "| oracle | predicted left | precision | F1 |", "|---|---|---|---|"]  # fmt: skip
    for r in res["precision_side"]:
        L.append(f"| {r['name']} | {r['pred']} | {r['precision']:.3f} | **{r['f1']:.3f}** |")
    L += ["", f"False positives by kind: {x['fp']}"]
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"oracle_{tag}"
    (OUT / f"{stem}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
