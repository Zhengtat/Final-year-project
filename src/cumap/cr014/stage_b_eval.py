"""CR-014 Stage B development scoring (IIR dev). Reads arm outputs from data/processed/cr014/stageB and the dev gold; reports exact
micro P/R/F1, one-token metrics, conditional verifier/boundary metrics, the earliest-failure taxonomy, paired bootstrap vs U0 and the
CR-014 §22 eligibility checks. Normalised-name exact match (the IIR gold has no character offsets), never pooled with P&D span-exact.

    uv run python -m cumap.cr014.stage_b_eval [--tag _smoke] [--arms V0 V1 V2 V3]"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from cumap.concepts_v4 import runner as R
from cumap.cr010.nodes_exp import baseline_run, exact_counts, load_cfg, split_data
from cumap.cr014.stage_b import OUT, unions
from cumap.eval.stats import paired_bootstrap_delta
from cumap.expert_kg.face_scorer import GoldConcept

CR_RULES = {
    "min_f1_gain": 0.02,
    "max_precision_drop": 0.02,
    "min_recall_gain": 0.05,
    "max_one_token_regress": 0.02,
}


def prf(counts) -> dict:
    tp = sum(c[0] for c in counts.values())
    fp = sum(c[1] for c in counts.values())
    fn = sum(c[2] for c in counts.values())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": p,
        "recall": r,
        "f1": 2 * p * r / (p + r) if p + r else 0.0,
    }


def one_token_split(rows, gold: list[GoldConcept]) -> dict:
    g1 = [g for g in gold if len(g.concept.split()) == 1]
    matched = {id(r.matched_gold) for r in rows if r.matched_gold is not None}
    tp1 = sum(1 for g in g1 if id(g) in matched)
    p1 = [r for r in rows if len(r.predicted.canonical_name.split()) == 1]
    ptp = sum(1 for r in p1 if r.matched_gold is not None)
    return {
        "one_token_recall": tp1 / len(g1) if g1 else float("nan"),
        "one_token_precision": ptp / len(p1) if p1 else float("nan"),
        "one_token_predicted": len(p1),
        "one_token_gold": len(g1),
    }


def overlaps(a: str, b: str) -> bool:
    x, y = a.split(), b.split()
    sub = lambda s, t: any(s[i : i + len(t)] == t for i in range(len(s) - len(t) + 1))
    return sub(x, y) or sub(y, x)


def evaluate(arms: list[str], tag: str) -> dict:
    import spacy

    nlp = spacy.load("en_core_web_sm")
    sections, emph, gold = split_data("dev")
    out0 = baseline_run("dev", load_cfg())
    data = {
        a: json.loads((OUT / f"{a}{tag}.json").read_text())
        for a in arms
        if (OUT / f"{a}{tag}.json").exists()
    }
    sids = sorted(next(iter(data.values()))["sections"])
    secs = [s for s in sections if s["section_id"] in sids]
    gold = [g for g in gold if g.section_id in sids]
    us = unions(nlp, secs, emph, out0)
    base_preds = {k: v for k, v in R.predictions(out0, secs, {}).items() if k in sids}
    base_counts, base_rows = exact_counts(base_preds, gold)
    base = {**prf(base_counts), **one_token_split(base_rows, gold)}
    cand_exact = {
        g_i: any(g.names() & {c for c in us[g.section_id].cands}) for g_i, g in enumerate(gold)
    }
    res = {"n_gold": len(gold), "sections": len(sids), "U0": base, "arms": {}}
    for arm, d in data.items():
        preds = {
            sid: [{"canonical_name": n, "role": "used"} for n in sorted(sec["accepted"])]
            for sid, sec in d["sections"].items()
        }
        counts, rows = exact_counts(preds, gold)
        m = {**prf(counts), **one_token_split(rows, gold)}
        boot = paired_bootstrap_delta(base_counts, counts, n=5000, seed=0) if len(sids) > 1 else {}
        matched = {id(r.matched_gold) for r in rows if r.matched_gold is not None}
        in_u2 = [g for i, g in enumerate(gold) if cand_exact[i]]
        overlap_only = [
            g for i, g in enumerate(gold)
            if not cand_exact[i] and any(overlaps(c, n) for c in us[g.section_id].cands for n in g.names())
        ]  # fmt: skip
        # earliest-failure taxonomy of the misses
        tax = {"P0": 0, "P1": 0, "B0": 0, "V0": 0, "R0": 0}
        for i, g in enumerate(gold):
            if id(g) in matched:
                continue
            if not cand_exact[i]:
                tax["P1" if g in overlap_only else "P0"] += 1
                continue
            sec = d["sections"][g.section_id]
            names = g.names()
            vs = [
                v
                for v in sec["verdicts"].values()
                if v.get("surface") in names or v.get("verdict") == "PRUNED"
            ]
            if arm == "V0":
                tax["R0"] += 1 if any(n in {v.get("surface") for v in vs} for n in names) else 0
                tax["V0"] += 0 if any(n in {v.get("surface") for v in vs} for n in names) else 1
            else:
                verified_surfaces = {v.get("surface") for v in sec["verdicts"].values()}
                tax["V0" if names & verified_surfaces else "B0"] += 1
        pred_names = {sid: [p["canonical_name"] for p in ps] for sid, ps in preds.items()}
        fp = {"F2_partial_or_overlong": 0, "F_unreviewed": 0}
        fp_sample = []
        for r in rows:
            if r.matched_gold is not None:
                continue
            sid = r.predicted.section_id
            gnames = [n for g in gold if g.section_id == sid for n in g.names()]
            if any(overlaps(r.predicted.canonical_name, n) for n in gnames):
                fp["F2_partial_or_overlong"] += 1
            else:
                fp["F_unreviewed"] += 1
                fp_sample.append((sid, r.predicted.canonical_name))
        random.Random(0).shuffle(fp_sample)
        meta = d["meta"]
        verified = sum(s["n_verified"] for s in d["sections"].values())
        res["arms"][arm] = {
            **m,
            "delta_f1_vs_U0": m["f1"] - base["f1"],
            "bootstrap": boot,
            "precision_delta": m["precision"] - base["precision"],
            "recall_delta": m["recall"] - base["recall"],
            "one_token_recall_delta": m["one_token_recall"] - base["one_token_recall"],
            "eligible": {
                "f1_gain_or_ci": (m["f1"] - base["f1"] >= CR_RULES["min_f1_gain"]) or (boot.get("lo95", -1) > 0),
                "precision": m["precision"] - base["precision"] >= -CR_RULES["max_precision_drop"],
                "recall_gain": m["recall"] - base["recall"] >= CR_RULES["min_recall_gain"],
                "one_token": m["one_token_recall"] - base["one_token_recall"] >= -CR_RULES["max_one_token_regress"],
            },
            "n_predicted": sum(len(v) for v in pred_names.values()),
            "verifier_recall_given_proposal_hit": sum(id(g) in matched for g in in_u2) / len(in_u2) if in_u2 else None,
            "boundary_recovery_of_overlap_only": sum(id(g) in matched for g in overlap_only) / len(overlap_only) if overlap_only else None,
            "n_in_U2_exact": len(in_u2),
            "n_overlap_only": len(overlap_only),
            "miss_taxonomy_earliest": tax,
            "fp_taxonomy": fp,
            "fp_audit_sample_30": fp_sample[:30],
            "candidates_verified": verified,
            "unaddressed_members": sum(len(s["unaddressed"]) for s in d["sections"].values()),
            "invalid_boundary_spans": sum(len(s["invalid_spans"]) for s in d["sections"].values()),
            "no_answer": sum(1 for s in d["sections"].values() for v in s["verdicts"].values() if v.get("verdict") == "NO_ANSWER"),
            "calls": meta["calls"], "cost_usd": meta["cost_usd"], "seconds": meta["seconds"], "errors": len(meta["errors"]),
        }  # fmt: skip
        res["arms"][arm]["eligible"]["all"] = all(res["arms"][arm]["eligible"].values())
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="")
    ap.add_argument("--arms", nargs="+", default=["V0", "V1", "V2", "V3"])
    a = ap.parse_args()
    r = evaluate(a.arms, a.tag)
    Path(OUT / f"stage_b_results{a.tag}.json").write_text(json.dumps(r, indent=1, default=str))
    b = r["U0"]
    print(
        f"U0 P/R/F1 {b['precision']:.3f}/{b['recall']:.3f}/{b['f1']:.3f} one-token R {b['one_token_recall']:.3f}  gold {r['n_gold']}"
    )
    for k, v in r["arms"].items():
        print(
            f"{k}: P/R/F1 {v['precision']:.3f}/{v['recall']:.3f}/{v['f1']:.3f} d={v['delta_f1_vs_U0']:+.3f} 1tokR {v['one_token_recall']:.3f} pred {v['n_predicted']} calls {v['calls']} ${v['cost_usd']} elig {v['eligible']['all']} miss {v['miss_taxonomy_earliest']}"
        )
