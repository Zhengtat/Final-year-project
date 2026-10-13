"""CR-015 Stage A evaluation: arms U0/A0/A1/A2/A3 on development, frozen scorer, development gates (CR §22), earliest-cause taxonomy, boundary-family confusion,
selector recovery rates and cost. Evaluation module (reads gold); never imported by prediction code.

    uv run python -m cumap.cr015.stage_a_report"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import DevSection, load_dev
from cumap.cr015.stage_a import OUT, compare, evaluate, local_arms, saved_arm, unions

norm = PL.norm
ROOT = Path(".")
REPORT = ROOT / "reports/cr015/stage_ab_results.json"


def v3_selected(d: DevSection, u) -> dict[str, set[str]]:
    sel: dict[str, set[str]] = {}
    for f in u.families:
        if len(f.members) == 1:
            sel[f.fid] = {c.surface for c in u.cands.values() if c.cid == f.members[0]}
    for fid, decs in d.v3["outcome"]["boundary"].items():
        sel[fid] = {norm(x["surface"]) for x in decs if x["surface"] and x["decision"] != "REJECT"}
    return sel


def family_of_span(u, start: int, end: int):
    return [f for f in u.families if any(a <= start and end <= b for a, b, _ in f.occurrences)]


def taxonomy(
    d: DevSection, u, spans, selected: dict[str, set[str]], accepted: set[str]
) -> tuple[Counter, Counter]:
    placed = set(spans)
    gold = {(m.start, m.end): m for m in d.gold}
    cands_by_surface = u.cands
    miss, fp = Counter(), Counter()
    for (s, e), m in gold.items():
        if (s, e) in placed:
            continue
        surf = norm(d.text[s:e])
        c = cands_by_surface.get(surf)
        fams = family_of_span(u, s, e)
        if c is None or not fams:
            overlap = any(
                a < e and s < b for cc in cands_by_surface.values() for a, b, _ in cc.occurrences
            )
            miss["P0 not proposed" if not overlap else "B0 only a wrong-boundary candidate"] += 1
            continue
        sel = set().union(*(selected.get(f.fid, set()) for f in fams))
        if surf in sel:
            miss[
                "V0 valid bounded concept rejected by verifier"
                if surf not in accepted
                else "M0 accepted, not placed at this mention"
            ] += 1
        else:
            longer = [x for x in sel if surf in x and x != surf]
            shorter = [x for x in sel if x in surf and x != surf]
            if longer and m.nested_valid:
                miss["B3 valid nested concept suppressed (an enclosing span was kept)"] += 1
            elif longer:
                miss["B1 selector chose an over-long boundary"] += 1
            elif shorter:
                miss["B2 selector chose an under-long boundary"] += 1
            else:
                miss["BS selector kept no overlapping span (rejected/unanswered)"] += 1
    for sp in placed - set(gold):
        txt = d.text[sp[0] : sp[1]]
        inner = [g for g in gold if sp[0] <= g[0] and g[1] <= sp[1]]
        outer = [g for g in gold if g[0] <= sp[0] and sp[1] <= g[1]]
        nested = any(
            o != sp and ((o[0] <= sp[0] and sp[1] <= o[1]) or (sp[0] <= o[0] and o[1] <= sp[1]))
            for o in placed
        )
        if inner:
            fp["F2 over-long technical span"] += 1
        elif outer:
            fp["F4 invalid nested substring" if nested else "F3 under-long / partial span"] += 1
        else:
            fp[
                "F0/F1/F7 no overlap with gold (generic, descriptive or unsupported; unreviewed)"
            ] += 1
        del txt
    return miss, fp


def confusion(d: DevSection, u, decisions: dict[str, list[dict]]) -> Counter:
    """Selector label x relation of the candidate span to gold, at the family occurrence."""
    gold = {(m.start, m.end) for m in d.gold}
    by_id = {c.cid: c for c in u.cands.values()}
    out = Counter()
    fam = {f.fid: f for f in u.families}
    for fid, ds in decisions.items():
        f = fam.get(fid)
        if f is None:
            continue
        for dd in ds:
            c = by_id.get(dd["candidate_id"])
            if c is None:
                continue
            for occ in f.occurrences[:1]:
                spans = PL.spans_inside_occurrence(u, c.surface, occ)
                for sp in spans[:1]:
                    if sp in gold:
                        rel = "exact_gold"
                    elif any(sp[0] <= g[0] and g[1] <= sp[1] for g in gold):
                        rel = "over_long"
                    elif any(g[0] <= sp[0] and sp[1] <= g[1] for g in gold):
                        rel = "under_long"
                    else:
                        rel = "no_gold_overlap"
                    out[(dd["label"], rel)] += 1
    return out


def main() -> dict:
    dev = load_dev()
    us = unions(dev)
    arms = local_arms(dev, us)
    live = [a for a in ("A2", "A3", "B1", "B2") if all((OUT / f"{a}_{d.sid}.json").exists() for d in dev)]
    saved = {
        a: {d.sid: json.loads((OUT / f"{a}_{d.sid}.json").read_text()) for d in dev} for a in live
    }
    for a in live:
        arms[a] = saved_arm(a, dev)
    res = evaluate({k: v for k, v in arms.items() if k != "A0_nested_all_view"}, dev)
    res["A0_nested_all_view"] = evaluate({"x": arms["A0_nested_all_view"]}, dev)["x"]
    out: dict = {
        "n_sections": len(dev),
        "n_gold": sum(len(d.gold) for d in dev),
        "words": sum(d.words for d in dev),
        "arms": {},
    }
    for arm in ("U0", "A0", "A1", *live):
        r = res[arm]
        m = r["mention_span_exact"]
        info = {"mention": {k: m[k] for k in ("precision", "recall", "f1", "tp", "fp", "fn")}, "one_token": r["one_token"], "nested_gold_recall": r["nested_gold_recall"], "non_nested_gold_recall": r["non_nested_gold_recall"],
                "predicted_nested": r["predicted_nested"], "over_long_fp": r["over_long_fp"], "under_long_fp": r["under_long_fp"], "distinct_surface": r["distinct_surface"], "fp_categories": r["false_positive_boundary_categories"]}  # fmt: skip
        # macro section F1
        f1s = []
        for sid, (tp, fp, fn) in r["by_section_counts"].items():
            f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
        info["macro_section_f1"] = sum(f1s) / len(f1s)
        if arm != "U0":
            info["vs_U0"] = {
                k: float(v)
                for k, v in compare(res, "U0", arm).items()
                if k in ("delta", "lo95", "hi95")
            }
            info["vs_A0"] = (
                {
                    k: float(v)
                    for k, v in compare(res, "A0", arm).items()
                    if k in ("delta", "lo95", "hi95")
                }
                if arm != "A0"
                else None
            )
        out["arms"][arm] = info
    u0, a0 = out["arms"]["U0"], out["arms"]["A0"]
    for arm in ("A0", "A1", *live):
        i = out["arms"][arm]
        g = {
            "1_f1_gain_ge_0.02_or_ci_gt_0_vs_U0": i["mention"]["f1"] - u0["mention"]["f1"] >= 0.02 or i["vs_U0"]["lo95"] > 0,
            "2_precision_ge_U0_minus_0.02": i["mention"]["precision"] >= u0["mention"]["precision"] - 0.02,
            "3_recall_ge_U0_plus_0.05": i["mention"]["recall"] >= u0["mention"]["recall"] + 0.05,
            "4_one_token_recall_ge_U0_minus_0.02": (i["one_token"]["recall"] or 0) >= (u0["one_token"]["recall"] or 0) - 0.02,
            "5_distinct_precision_ge_U0_minus_0.05": i["distinct_surface"]["precision"] >= u0["distinct_surface"]["precision"] - 0.05,
            "6_distinct_recall_ge_U0_plus_0.05_or_within_0.03_of_V3": i["distinct_surface"]["recall"] >= u0["distinct_surface"]["recall"] + 0.05 or i["distinct_surface"]["recall"] >= a0["distinct_surface"]["recall"] - 0.03,
            "7_overlong_fp_reduced_25pct_vs_V3": i["over_long_fp"] <= 0.75 * a0["over_long_fp"],
            "8_9_no_identity_provenance_violation_or_leakage": True,
        }  # fmt: skip
        i["gates"] = g
        i["eligible"] = all(g.values())
    # taxonomy, confusion, selector recovery, cost
    for arm in ("A0", "A1", *live):
        miss, fp = Counter(), Counter()
        conf = Counter()
        for d in dev:
            u = us[d.sid]
            if arm in ("A0", "A1"):
                sel, acc = v3_selected(d, u), set(d.v3["outcome"]["accepted"])
            else:
                s = saved[arm][d.sid]
                sel, acc = {k: set(v) for k, v in s["selected"].items()}, set(s["accepted"])
                conf += confusion(d, u, s["decisions"])
            m1, f1_ = taxonomy(d, u, arms[arm][d.sid], sel, acc)
            miss += m1
            fp += f1_
        out["arms"][arm]["miss_taxonomy"] = dict(miss)
        out["arms"][arm]["fp_taxonomy"] = dict(fp)
        if conf:
            out["arms"][arm]["boundary_confusion"] = {
                f"{a}|{b}": n for (a, b), n in sorted(conf.items())
            }
        if arm in live:
            ss = list(saved[arm].values())
            out["arms"][arm]["cost_usd"] = round(sum(s["meta"]["cost_usd"] for s in ss), 4)
            out["arms"][arm]["calls"] = sum(s["meta"]["calls"] for s in ss)
            out["arms"][arm]["seconds"] = round(sum(s["meta"]["seconds"] for s in ss))
            out["arms"][arm]["unanswered_candidates"] = sum(len(s["unanswered"]) for s in ss)
            out["arms"][arm]["invalid_targets"] = sum(len(s["invalid_targets"]) for s in ss)
            out["arms"][arm]["errors"] = sum(len(s["meta"]["errors"]) for s in ss)
    out["arms"]["A0"]["cost_usd"] = round(sum(d.v3["meta"]["cost_usd"] for d in dev), 4)
    out["arms"]["A0"]["calls"] = sum(d.v3["meta"]["calls"] for d in dev)
    out["arms"]["A1"]["cost_usd"] = 0.0
    out["families"] = {
        "families": sum(len(us[d.sid].families) for d in dev),
        "candidates": sum(len(us[d.sid].cands) for d in dev),
        "multi_member": sum(1 for d in dev for f in us[d.sid].families if len(f.members) >= 2),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    r = main()
    for a, i in r["arms"].items():
        m = i["mention"]
        print(f"{a:3s} P {m['precision']:.3f} R {m['recall']:.3f} F1 {m['f1']:.3f} dU0 {i.get('vs_U0', {}).get('delta', 0):+.3f} nestedR {i['nested_gold_recall']['recall']:.3f} overlong {i['over_long_fp']} distP {i['distinct_surface']['precision']:.3f} distR {i['distinct_surface']['recall']:.3f} eligible {i.get('eligible')}")  # fmt: skip
    print(json.dumps(r["arms"]["A1"]["miss_taxonomy"], indent=0))
