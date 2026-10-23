"""CR-011 revised STOP 3 (Research 2026-10-09, Option A): local review-ranking evaluation ($0, no paid call). Definitions are fixed
in docs/cr011/STOP3_REVISED_PREREGISTRATION.md. A model never merges anything here: it only orders pairs for HUMAN review.

    uv run python -m cumap.sleep.triage --dev240 <marked SLEEP-240 dev sheet> --devpos <marked SLEEP-POS dev sheet>
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cumap.config import REPO_ROOT
from cumap.sleep import build as B
from cumap.sleep import features as F
from cumap.sleep import scorer as S
from cumap.sleep.stop2 import Vectoriser, erst_linked_set, pool_features
from cumap.sleep.typecompat import TypeMap

CHECKS = REPO_ROOT / "data/interim/checks/cr011"
OUT = REPO_ROOT / "data/interim/sleep"
SIM_FEATURES = [
    "name_cos",
    "def_cos",
    "ev_cos",
    "char_ratio",
    "token_jaccard",
    "containment",
    "head_equal",
]
SINGLE = ["name_cos", "char_ratio", "token_jaccard", "def_cos", "ev_cos", "max_sim"]
MUST = {"SAME", "UNSURE"}
TIE = 0.005


@dataclass
class Config:
    name: str
    kind: str  # single | lr | gb
    cols: list[str]
    rank: int  # simplicity order


def configs() -> list[Config]:
    out = [Config(f"single:{c}", "single", [c], i) for i, c in enumerate(SINGLE)]
    out += [
        Config("lr_similarity", "lr", SIM_FEATURES, 10),
        Config("lr_all", "lr", F.FEATURES, 11),
        Config("gb_all", "gb", F.FEATURES, 12),
    ]
    return out


def single_score(name: str, feats: np.ndarray) -> np.ndarray:
    if name == "max_sim":
        i = [F.FEATURES.index(c) for c in ("name_cos", "def_cos", "ev_cos")]
        return feats[:, i].max(axis=1)
    return feats[:, F.FEATURES.index(name)]


def load_dev(sheet: Path, manifest: Path, prefix: str) -> list[dict]:
    with sheet.open(encoding="utf-8-sig", newline="") as f:
        marks = {r["item_id"]: r["decision"].strip() for r in csv.DictReader(f)}
    with manifest.open(encoding="utf-8", newline="") as f:
        man = {r["item_id"]: r for r in csv.DictReader(f)}
    return [
        {
            "set": prefix,
            "item_id": i,
            "decision": d,
            "pair": tuple(sorted((man[i]["pair_a_id"], man[i]["pair_b_id"]))),
            "family": man[i]["candidate_family_id"],
            "stratum": man[i]["stratum"],
        }
        for i, d in marks.items()
        if man[i]["split"] == "dev"
    ]


def fit_score(cfg: Config, x_tr, y_tr, x_te):
    if cfg.kind == "single":
        return single_score(cfg.name.split(":", 1)[1], x_te)
    idx = [F.FEATURES.index(c) for c in cfg.cols]
    return S._fit_predict(cfg.kind, x_tr[:, idx], y_tr, x_te[:, idx])


def oof(cfg: Config, x, y, groups) -> np.ndarray:
    if cfg.kind == "single":
        return single_score(cfg.name.split(":", 1)[1], x)
    out = np.zeros(len(y))
    from sklearn.model_selection import GroupKFold

    for tr, te in GroupKFold(n_splits=min(5, len(set(groups)))).split(x, y, groups):
        out[te] = fit_score(cfg, x[tr], y[tr], x[te])
    return out


def run(dev240: Path, devpos: Path) -> dict:
    sections, snap, lex, ctx, vec = B.load_all()
    types = TypeMap.load()
    vz = Vectoriser(vec)
    erst = erst_linked_set(snap, sections)
    cs = B.candidates(snap, vec, ctx)
    pf = pool_features(snap, sections, ctx, vec, cs, types, lex, vz, erst)
    dev = load_dev(dev240, CHECKS / "sleep240_manifest_DO_NOT_SHARE.csv", "SLEEP-240")
    dev += load_dev(devpos, CHECKS / "sleep_pos160_manifest_DO_NOT_SHARE.csv", "SLEEP-POS")
    eligible = {
        p
        for p, (_f, fl) in pf.items()
        if not fl["lexicon_different"] and not fl["type_incompatible"]
    }
    pool_pairs = sorted(eligible, key=lambda p: tuple(sorted(p)))
    xpool = F.matrix([pf[p][0] for p in pool_pairs])
    rows, y, groups, meta = [], [], [], []
    findings = {
        "must_review_total": 0,
        "must_review_vetoed_by_guard": [],
        "must_review_not_in_candidate_pool": [],
    }
    for d in dev:
        a, b = (snap.nodes[i] for i in d["pair"])
        key = frozenset(d["pair"])
        flags = {
            "lexicon_different": lex.is_different(a.name, b.name)
            or any(lex.is_different(fa, fb) for fa in a.forms() for fb in b.forms()),
            "type_incompatible": not types.compatible(a.type, b.type),
        }
        is_must = d["decision"] in MUST
        findings["must_review_total"] += is_must
        if flags["lexicon_different"] or flags["type_incompatible"]:
            if is_must:
                findings["must_review_vetoed_by_guard"].append((d["set"], d["item_id"], flags))
            continue  # never reaches the scorer, so it is not part of the review universe
        in_pool = key in eligible
        if is_must and not in_pool:
            findings["must_review_not_in_candidate_pool"].append((d["set"], d["item_id"]))
        feats = pf[key][0] if key in pf else F.pair_features(a, b, vz(a), vz(b), ctx, types, erst)
        rows.append(feats)
        y.append(int(is_must))
        groups.append(d["family"])
        meta.append({**d, "in_pool": in_pool})
    x, y, groups = F.matrix(rows), np.array(y), np.array(groups)
    findings["eligible_dev_items"] = len(y)
    findings["eligible_must_review"] = int(y.sum())
    results = []
    for cfg in configs():
        t0 = time.perf_counter()
        o = oof(cfg, x, y, groups)
        pos = [i for i in range(len(y)) if y[i]]
        # a must-review item that is not a candidate of the pool is never reviewed
        sent_pos = [i for i in pos if meta[i]["in_pool"]]
        t = float(min(o[i] for i in sent_pos)) if sent_pos else None
        if cfg.kind == "single":
            pool_scores = single_score(cfg.name.split(":", 1)[1], xpool)
        else:
            pool_scores = fit_score(cfg, x, y, xpool)
        reviewed = int((pool_scores >= t).sum()) if t is not None else len(pool_pairs)
        dev_reviewed = int((o >= t).sum()) if t is not None else len(o)
        recall_sent = sum(1 for i in pos if meta[i]["in_pool"] and o[i] >= t)
        total_must = findings["must_review_total"]
        results.append(
            {
                "config": cfg.name,
                "kind": cfg.kind,
                "n_features": len(cfg.cols),
                "rank": cfg.rank,
                "threshold_oof_min_positive": t,
                "review_recall": recall_sent / total_must,
                "reviewed_pairs": reviewed,
                "eligible_pairs": len(pool_pairs),
                "review_reduction_primary": 1 - reviewed / len(pool_pairs),
                "dev_items_reviewed": dev_reviewed,
                "dev_review_reduction_secondary": 1 - dev_reviewed / len(o),
                "oof_auc": S.discrimination(o, y)["auc"],
                "runtime_s": round(time.perf_counter() - t0, 3),
                "different_violations": 0,
            }
        )
    ok = [r for r in results if r["review_recall"] == 1.0 and r["different_violations"] == 0]
    best = None
    if ok:
        top = max(r["review_reduction_primary"] for r in ok)
        near = [r for r in ok if top - r["review_reduction_primary"] <= TIE]
        best = min(near, key=lambda r: (r["rank"], r["n_features"], r["runtime_s"]))
    gate = bool(best and best["review_reduction_primary"] >= 0.25 and best["review_recall"] == 1.0)
    out = {
        "dev_sets": {
            k: dict(
                sorted(
                    __import__("collections")
                    .Counter(d["decision"] for d in dev if d["set"] == k)
                    .items()
                )
            )
            for k in ("SLEEP-240", "SLEEP-POS")
        },
        "eligible_pairs": len(pool_pairs),
        "findings": findings,
        "configs": results,
        "selected": best,
        "continuation_gate": {
            "review_reduction_min": 0.25,
            "review_recall_required": 1.0,
            "passed": gate,
            "outcome": "STOP 4 MAY PROCEED"
            if gate
            else "STOP CR-011 AFTER STOP 3: NO PRODUCTION CHANGE (no paid call)",
        },
    }
    (OUT / "stop3_triage.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev240", required=True)
    ap.add_argument("--devpos", required=True)
    a = ap.parse_args()
    r = run(Path(a.dev240), Path(a.devpos))
    print(
        json.dumps(
            {
                k: r[k]
                for k in ("dev_sets", "eligible_pairs", "findings", "selected", "continuation_gate")
            },
            indent=1,
            default=str,
        )
    )
    for c in r["configs"]:
        print(
            f"{c['config']:24s} recall={c['review_recall']:.3f} reduction={c['review_reduction_primary']:.3f} dev_red={c['dev_review_reduction_secondary']:.3f} auc={c['oof_auc']}"
        )


if __name__ == "__main__":
    main()
