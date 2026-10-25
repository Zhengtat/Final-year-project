"""CR-056: classify EVERY candidate pair on the concepts of a CR-055 arm (pair budget = the whole pool), pre-registered in docs/DECISIONS.md.

The arm's finished run is copied to `<arm>allp`, its pair selection and relation results are cleared, and only pair selection and
relation classification re-run under the arm's own profile (pairs the arm already classified are cache hits). Concepts are identical
to the arm, so the comparison isolates pair delivery.

    uv run python -m cumap.cr056.allpairs --arm cr055b --dry-run | --limit 2 | (all)
Train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

from cumap.cr012 import production_graph as PG
from cumap.cr043.papers import first_set
from cumap.cr043.run import recorded_spend, run_id

PROFILES = {
    "cr055a": "configs/scinlp_profile_v4.yaml",
    "cr055b": "configs/scinlp_profile_v4_g2.yaml",
}
MAX_USD_PER_DOC = 3.0  # sol-era preflight bound; real luna spend is capped by --cap-usd


def tag_for(arm: str) -> str:
    return f"{arm}allp"


def worker(split: str, doc_key: str, arm: str) -> dict:
    import yaml

    from cumap.concepts_v4 import cr009_run as R
    from cumap.config import get_settings
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr012.unit_run import select_without_sample
    from cumap.cr055.scinlp_run import use_profile

    assert split in ("train", "dev")
    os.environ["CUMAP_SCINLP_PROFILE"] = PROFILES[arm]
    use_profile()
    src, dst = PG.run_path(run_id(doc_key, arm)), PG.run_path(run_id(doc_key, tag_for(arm)))
    base = json.loads((src / "checkpoint.json").read_text())
    if base.get("stage") != "snapshots":
        raise SystemExit(f"{arm} run of {doc_key} is not finished")
    if not dst.exists():
        shutil.copytree(src, dst)
        cp = json.loads((dst / "checkpoint.json").read_text())
        for k in ("selected_pairs", "sample_pairs", "relation_results_v3", "pair_registry"):
            cp[k] = []
        cp["selection_stats"], cp["stage"] = {}, "select"
        (dst / "checkpoint.json").write_text(json.dumps(cp), encoding="utf-8")
    doc = {
        d.doc_key: d
        for d in SciNLPAdapter().load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)
    }[doc_key]
    info = SR.prepare(split, doc)
    prof = yaml.safe_load(SR.PROFILE.read_text())
    os.environ.update({"CUMAP_DEMO_SLICE": info["slice_config"], "CUMAP_BENCHMARK_PROFILE": str(SR.PROFILE), "CUMAP_RELATION_REGISTRY": prof["relation_registry"]})  # fmt: skip
    get_settings.cache_clear()
    rid = run_id(doc_key, tag_for(arm))
    pool = (base.get("selection_stats") or {}).get("unique_candidate_pairs") or 0
    sel = select_without_sample(rid, max(pool, 1))
    rel = R.stage_relations(rid, dry_run=False, max_usd=MAX_USD_PER_DOC)
    return {
        "run_id": rid,
        "pool": pool,
        "arm_selected": len(base["selected_pairs"]),
        "selected": sel.get("selected"),
        "relations": rel,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(PROFILES), required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cap-usd", type=float, default=0.5)
    ap.add_argument("--worker", nargs=2, metavar=("SPLIT", "DOC"))
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(*a.worker, a.arm), default=str))
        return
    papers = first_set()[: a.limit] if a.limit else first_set()
    spent, extra = 0.0, 0
    for s, d in papers:
        cp = json.loads((PG.run_path(run_id(d, a.arm)) / "checkpoint.json").read_text())
        n = max(
            0,
            ((cp.get("selection_stats") or {}).get("unique_candidate_pairs") or 0)
            - len(cp["selected_pairs"]),
        )
        extra += n
        if a.dry_run:
            continue
        dck = PG.run_path(run_id(d, tag_for(a.arm))) / "checkpoint.json"
        if not (dck.exists() and json.loads(dck.read_text()).get("stage") == "snapshots"):
            r = subprocess.run([sys.executable, "-m", "cumap.cr056.allpairs", "--arm", a.arm, "--worker", s, d], capture_output=True, text=True, check=False)  # fmt: skip
            if r.returncode:
                raise SystemExit(f"{d} failed: {(r.stdout + r.stderr)[-400:]}")
        spent += recorded_spend(run_id(d, tag_for(a.arm)))
        print(json.dumps({"doc": d, "extra_pairs": n, "spent_so_far": round(spent, 4)}), flush=True)
        if spent > a.cap_usd:
            raise SystemExit(f"cap reached: ${spent:.3f}")
    if a.dry_run:
        print(
            json.dumps(
                {
                    "arm": a.arm,
                    "papers": len(papers),
                    "extra_pairs": extra,
                    "est_usd_luna": round(extra * 0.00025, 3),
                }
            )
        )


if __name__ == "__main__":
    main()
