"""CR-014 STOP 4 scoring: reads the frozen held-out gold and the one-shot U0 / V3 outputs. Never imported by the prediction path.

uv run python -m cumap.cr014.heldout_score"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from cumap.cr014 import heldout_run as H
from cumap.cr014 import pilot_run as P
from cumap.eval.stats import paired_bootstrap_delta

ROOT = Path(".")
GOLD_MANIFEST = ROOT / "reports/cr014/gold_manifest_heldout.json"


def main() -> dict:
    import hashlib

    man = yaml.safe_load((ROOT / "configs/cr014_manifest.yaml").read_text())
    gold = ROOT / "data/gold/pd_concept_test_blind.csv"
    frozen = json.loads(GOLD_MANIFEST.read_text())["sha256"]
    if hashlib.sha256(gold.read_bytes()).hexdigest() != frozen:
        raise SystemExit("held-out gold changed since its hash was recorded")
    P.MAN = {**P.MAN, "pilot": man["heldout_sealed"]}
    P.OUT = H.OUT
    P.GOLD = gold
    P.SENT = ROOT / "data/interim/checks/cr014/pd_concept_test_sentences.csv"
    P.u0_surfaces = H.u0_surfaces
    P.DOMAIN = H.DOMAIN
    res = P.run_score()
    secs = man["heldout_sealed"]
    per = {
        arm: {s: res["by_section"][arm][s]["mention_span_exact"] for s in secs}
        for arm in ("U0", "V3")
    }
    cnt = lambda arm: {s: (per[arm][s]["tp"], per[arm][s]["fp"], per[arm][s]["fn"]) for s in secs}
    res["bootstrap_delta_f1_section_clustered"] = paired_bootstrap_delta(
        cnt("U0"), cnt("V3"), n=10000, seed=0
    )
    res["gates"] = {}
    u, v = res["arms"]["U0"], res["arms"]["V3"]
    d = {
        k: v["mention_span_exact"][k] - u["mention_span_exact"][k]
        for k in ("precision", "recall", "f1")
    }
    d1 = (v["one_token"]["recall"] or 0) - (u["one_token"]["recall"] or 0)
    boot = res["bootstrap_delta_f1_section_clustered"]
    res["gates"] = {
        "f1_gain_ge_0.02_or_ci_lower_gt_0": d["f1"] >= 0.02 or boot["lo95"] > 0,
        "precision_delta_ge_-0.02": d["precision"] >= -0.02,
        "recall_delta_ge_+0.05": d["recall"] >= 0.05,
        "one_token_recall_delta_ge_-0.02": d1 >= -0.02,
        "deltas": {**d, "one_token_recall": d1},
        "gold_leakage": 0, "test_time_manual_fixes": 0,
    }  # fmt: skip
    res["gold_sha256"] = frozen
    (H.OUT / "heldout_results.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str)[:6000])
