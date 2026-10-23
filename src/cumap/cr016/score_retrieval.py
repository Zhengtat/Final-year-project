"""CR-016 STOP 2 scoring (main environment; reads the answer key). Metrics, slices, paired bootstrap (clustered by query section), pre-registered gate, cost.

uv run python -m cumap.cr016.score_retrieval --run <dir with out/retrieval_records.jsonl and out/run_manifest.json>"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(".")
CFG = yaml.safe_load((ROOT / "configs/cr016_stage2.yaml").read_text())
KS = CFG["retrieval"]["report_at"]
SLICES = [
    "exact_surface",
    "alias",
    "acronym",
    "one_token",
    "different_boundary",
    "short_gap",
    "long_gap",
    "associative_low_lexical_overlap",
    "same_surface_different_sense",
    "support_rare_le5",
    "support_medium_6_30",
    "support_common_gt30",
]
DIFFICULT = CFG["gate"]["difficult_slices"]


def per_query(rec: dict, relevant: set[str]) -> dict:
    ids = [x["chunk_id"] for x in rec["retrieved"]]
    hits = [i in relevant for i in ids]
    first = next((r + 1 for r, h in enumerate(hits) if h), None)
    out = {f"recall@{k}": float(any(hits[:k])) for k in KS}
    out["mrr"] = 1.0 / first if first and first <= CFG["retrieval"]["mrr_cutoff"] else 0.0
    out["precision@5"] = sum(hits[:5]) / 5
    out["latency_s"] = rec["latency_s"]
    return out


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def boot(deltas_by_sec: dict[str, list[float]], n: int, seed: int) -> tuple[float, float, float]:
    rng = random.Random(seed)
    secs = sorted(deltas_by_sec)
    allv = [d for s in secs for d in deltas_by_sec[s]]
    point = mean(allv)
    out = []
    for _ in range(n):
        pick = [rng.choice(secs) for _ in secs]
        v = [d for s in pick for d in deltas_by_sec[s]]
        out.append(mean(v))
    out.sort()
    return point, out[int(0.025 * n)], out[int(0.975 * n) - 1]


def main(run: Path) -> dict:
    s2 = ROOT / "data/processed/cr016/stage2"
    key = {
        k["query_id"]: k
        for k in (json.loads(x) for x in (s2 / "key.jsonl").read_text().splitlines() if x)
    }
    recs: dict[str, dict[str, dict]] = defaultdict(dict)
    for line in (run / "out/retrieval_records.jsonl").read_text().splitlines():
        if line:
            r = json.loads(line)
            recs[r["backend"]][r["query_id"]] = r
    backends = sorted(recs)
    common = sorted(set.intersection(*(set(recs[b]) for b in backends)))
    pq = {b: {q: per_query(recs[b][q], set(key[q]["relevant"])) for q in common} for b in backends}
    res: dict = {
        "n_queries_scored": len(common),
        "backends": backends,
        "overall": {},
        "slices": {},
        "bootstrap": {},
        "gate": {},
    }
    metrics = [f"recall@{k}" for k in KS] + ["mrr", "precision@5", "latency_s"]
    for b in backends:
        res["overall"][b] = {m: mean([pq[b][q][m] for q in common]) for m in metrics}
    for sl in SLICES:
        qs = [q for q in common if key[q]["flags"][sl]]
        res["slices"][sl] = {
            "support": len(qs),
            "support_sections": len({key[q]["section"] for q in qs}),
            **{
                b: {m: mean([pq[b][q][m] for q in qs]) for m in metrics if m != "latency_s"}
                for b in backends
            },
        }
    m1, m2 = "M1_dense", "M2_hipporag"
    if m1 in pq and m2 in pq:
        n, seed = CFG["gate"]["bootstrap"]["n"], CFG["gate"]["bootstrap"]["seed"]

        def delta_by_sec(metric: str, qs: list[str]) -> dict[str, list[float]]:
            d: dict[str, list[float]] = defaultdict(list)
            for q in qs:
                d[key[q]["section"]].append(pq[m2][q][metric] - pq[m1][q][metric])
            return d

        for metric in ("recall@5", "mrr", "recall@1", "recall@3"):
            p, lo, hi = boot(delta_by_sec(metric, common), n, seed)
            res["bootstrap"][metric] = {"delta": p, "lo95": lo, "hi95": hi}
        sl_boot = {}
        for sl in SLICES:
            qs = [q for q in common if key[q]["flags"][sl]]
            if len(qs) >= 5:
                p, lo, hi = boot(delta_by_sec("recall@5", qs), n, seed)
                sl_boot[sl] = {"support": len(qs), "delta_recall@5": p, "lo95": lo, "hi95": hi}
        res["bootstrap"]["slices_recall@5"] = sl_boot
        d5 = res["overall"][m2]["recall@5"] - res["overall"][m1]["recall@5"]
        viol = sum(
            1
            for b in backends
            for q in recs[b]
            for x in recs[b][q]["retrieved"]
            if x["source_order"] >= recs[b][q]["query_source_order"]
        )
        prov = [
            all(
                x.get("chunk_id")
                and x.get("source_section")
                and x.get("source_order") is not None
                and x.get("source_locator")
                for x in recs[b][q]["retrieved"]
            )
            for b in backends
            for q in recs[b]
        ]
        diff_gain = {
            sl: res["slices"][sl][m2]["recall@5"] - res["slices"][sl][m1]["recall@5"]
            for sl in DIFFICULT
            if res["slices"][sl]["support"] > 0
        }
        g = {
            "a_recall5_abs_gain_ge_0.05": d5 >= CFG["gate"]["recall_at_5_abs_gain"],
            "b_bootstrap_lower_bound_gt_0": res["bootstrap"]["recall@5"]["lo95"] > 0 or res["bootstrap"]["mrr"]["lo95"] > 0,
            "c_difficult_slice_ge_0.10_and_overall_regression_le_0.03": any(v >= CFG["gate"]["difficult_slice_gain"] for v in diff_gain.values()) and d5 >= -CFG["gate"]["overall_recall_at_5_max_regression"],
            "future_violations": viol, "provenance_completeness": sum(prov) / len(prov),
            "difficult_slice_recall5_gain": diff_gain, "overall_delta_recall5": d5,
        }  # fmt: skip
        g["any_condition_met"] = (
            g["a_recall5_abs_gain_ge_0.05"]
            or g["b_bootstrap_lower_bound_gt_0"]
            or g["c_difficult_slice_ge_0.10_and_overall_regression_le_0.03"]
        )
        g["required_met"] = g["future_violations"] == 0 and g["provenance_completeness"] == 1.0
        g["PROCEED_TO_PIPELINE_INTEGRATION"] = bool(g["any_condition_met"] and g["required_met"])
        res["gate"] = g
    # cost
    rows = [
        json.loads(x)
        for x in (ROOT / "data/logs/llm_calls.jsonl").read_text().splitlines()
        if "cr016_s2_hipporag" in x
    ]
    from cumap.config import get_settings

    tiers = get_settings().llm.tiers
    cost: dict = defaultdict(
        lambda: {"calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0}
    )
    for r in rows:
        c = cost[r["task"]]
        c["calls"] += 1
        if r["cache_hit"]:
            c["cache_hits"] += 1
            continue
        t = tiers[r["model_tier"]]
        u = r["usage"]
        c["input_tokens"] += u.get("input_tokens", 0)
        c["output_tokens"] += u.get("output_tokens", 0)
        c["usd"] += (
            u.get("input_tokens", 0) / 1e6 * t.usd_per_1m_input_tokens
            + u.get("output_tokens", 0) / 1e6 * t.usd_per_1m_output_tokens
        )
    res["cost"] = {k: {**v, "usd": round(v["usd"], 4)} for k, v in cost.items()}
    res["cost_total_usd"] = round(sum(v["usd"] for v in cost.values()), 4)
    man = json.loads((run / "out/run_manifest.json").read_text())
    res["manifest"] = {
        k: man[k]
        for k in (
            "embedding",
            "top_k",
            "config_hash",
            "wall_seconds",
            "timings_s",
            "query_counts",
            "environment",
            "final_snapshots",
        )
    }
    (ROOT / "reports/cr016").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports/cr016/stage2_results.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    r = main(Path(ap.parse_args().run))
    print(
        json.dumps(
            {"overall": r["overall"], "gate": r["gate"], "cost_total_usd": r["cost_total_usd"]},
            indent=1,
            default=str,
        )
    )
