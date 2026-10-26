"""CR-059 DRAFT arm R (relations only): choice b on the adopted profile-v5 concepts, so the endpoint check is measured alone.

Each `cr055ballp` run (first set) is copied to a new run id, its relation results are cleared (concepts and the all-pairs selection are
kept), and only relation classification is re-run under profile v7r (= v5 + endpoint_check choice: relation_choice v8, no node-type check).
Family calls are cache hits (same prompt and input). The source runs are never written.

    uv run python -m cumap.cr059.arm_relations --dry-run
    uv run python -m cumap.cr059.arm_relations --limit 2
    uv run python -m cumap.cr059.arm_relations
Train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr043.papers import first_set
from cumap.cr043.run import recorded_spend, run_id

BASE_TAG, TAG = "cr055ballp", "cr059relR"
PROFILE_V7R = REPO_ROOT / "configs/scinlp_profile_v7r.yaml"
MAX_USD_PER_DOC = 3.0


def cleared(cp: dict) -> dict:
    """Keep concepts and the selected pairs; drop every relation result so classification re-runs."""
    cp["relation_results_v3"] = []
    cp["rejected_relations"] = []
    cp["stage"] = "relations"
    stats = dict(cp.get("selection_stats") or {})
    stats.pop("endpoint_check", None)
    cp["selection_stats"] = stats
    return cp


def worker(split: str, doc_key: str) -> dict:
    import yaml

    from cumap.concepts_v4 import cr009_run as R
    from cumap.config import get_settings
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter

    assert split in ("train", "dev")
    src, dst = PG.run_path(run_id(doc_key, BASE_TAG)), PG.run_path(run_id(doc_key, TAG))
    if not dst.exists():
        shutil.copytree(src, dst)
        cp = cleared(json.loads((dst / "checkpoint.json").read_text()))
        (dst / "checkpoint.json").write_text(json.dumps(cp), encoding="utf-8")
    doc = {
        d.doc_key: d
        for d in SciNLPAdapter().load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)
    }[doc_key]
    info = SR.prepare(split, doc)
    prof = yaml.safe_load(PROFILE_V7R.read_text())
    os.environ.update({"CUMAP_DEMO_SLICE": info["slice_config"], "CUMAP_BENCHMARK_PROFILE": str(PROFILE_V7R),
                       "CUMAP_RELATION_REGISTRY": prof["relation_registry"]})  # fmt: skip
    get_settings.cache_clear()
    rel = R.stage_relations(run_id(doc_key, TAG), dry_run=False, max_usd=MAX_USD_PER_DOC)
    return {"run_id": run_id(doc_key, TAG), "relations": rel}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cap-usd", type=float, default=1.0)
    ap.add_argument("--worker", nargs=2, metavar=("SPLIT", "DOC"))
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(*a.worker), default=str))
        return
    papers = first_set()[: a.limit] if a.limit else first_set()
    spent, pairs = 0.0, 0
    for split, d in papers:
        cp = json.loads((PG.run_path(run_id(d, BASE_TAG)) / "checkpoint.json").read_text())
        fam = sum(1 for r in cp["relation_results_v3"] if r.get("family") == "scinlp")
        pairs += fam
        if a.dry_run:
            print(
                json.dumps({"doc": d, "selected": len(cp["selected_pairs"]), "choice_calls": fam})
            )
            continue
        dck = PG.run_path(run_id(d, TAG)) / "checkpoint.json"
        if dck.exists() and json.loads(dck.read_text()).get("relation_results_v3") and \
                len(json.loads(dck.read_text())["relation_results_v3"]) >= len(cp["selected_pairs"]):  # fmt: skip
            spent += recorded_spend(run_id(d, TAG))
            print(
                json.dumps(
                    {"doc": d, "skipped": "already finished", "spent_so_far": round(spent, 4)}
                ),
                flush=True,
            )
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", "cumap.cr059.arm_relations", "--worker", split, d],
                           capture_output=True, text=True, check=False)  # fmt: skip
        spent += recorded_spend(run_id(d, TAG))
        print(json.dumps({"doc": d, "rc": r.returncode, "s": round(time.time() - t0), "spent_so_far": round(spent, 4),
                          "tail": (r.stdout + r.stderr)[-200:]}), flush=True)  # fmt: skip
        if r.returncode:
            raise SystemExit(f"{d} failed")
        if spent > a.cap_usd:
            raise SystemExit(f"cap reached: ${spent:.3f} > ${a.cap_usd}")
    if a.dry_run:
        print(
            json.dumps(
                {
                    "papers": len(papers),
                    "choice_calls_new_prompt": pairs,
                    "est_usd_luna": round(pairs * 0.0003, 3),
                }
            )
        )


if __name__ == "__main__":
    main()
