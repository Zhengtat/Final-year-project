"""CR-043 arm "all pairs": classify EVERY candidate pair of a paper (pair budget = the whole candidate pool) instead of the D3 budget.

The arm reuses the baseline run's finished concept stage: the baseline run directory is copied to a new run id, its pair selection
and relation results are cleared, and only pair selection and relation classification are re-run. Concepts are therefore identical
to the baseline, so the comparison isolates pair delivery; pairs the baseline already classified are cache hits (same model,
prompt and input). The frozen CR-012 runner (`cr012/scinlp_run.py`, hash-pinned) is not edited; its `prepare` step is reused.

    uv run python -m cumap.cr043.arm_allpairs --dry-run      # pool sizes and extra pairs, no call
    uv run python -m cumap.cr043.arm_allpairs --limit 2
    uv run python -m cumap.cr043.arm_allpairs                 # all papers whose baseline run is finished
Train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from cumap.cr012 import production_graph as PG
from cumap.cr043.papers import first_set
from cumap.cr043.run import TAG as BASE_TAG
from cumap.cr043.run import recorded_spend, run_id

TAG = "cr043allp"
MAX_USD_PER_DOC = 3.0  # the relation stage's preflight bound uses sol-era per-pair prices; real luna spend is capped by --cap-usd


def _cleared(cp: dict) -> dict:
    for k in ("selected_pairs", "sample_pairs", "relation_results_v3", "pair_registry"):
        cp[k] = []
    cp["selection_stats"] = {}
    cp["stage"] = "select"
    return cp


def _baseline_done(doc_key: str) -> bool:
    f = PG.run_path(run_id(doc_key, BASE_TAG)) / "checkpoint.json"
    return f.exists() and json.loads(f.read_text()).get("stage") == "snapshots"


def worker(split: str, doc_key: str) -> dict:
    """One paper (run in its own process, so the profile environment never leaks)."""
    import yaml

    from cumap.concepts_v4 import cr009_run as R
    from cumap.config import get_settings
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr012.unit_run import select_without_sample

    assert split in ("train", "dev")
    src, dst = PG.run_path(run_id(doc_key, BASE_TAG)), PG.run_path(run_id(doc_key, TAG))
    base_cp = json.loads((src / "checkpoint.json").read_text())
    if base_cp.get("stage") != "snapshots":
        raise SystemExit(f"baseline of {doc_key} is not finished")
    if not dst.exists():
        shutil.copytree(src, dst)
        cp = _cleared(json.loads((dst / "checkpoint.json").read_text()))
        (dst / "checkpoint.json").write_text(json.dumps(cp), encoding="utf-8")
    doc = {
        d.doc_key: d
        for d in SciNLPAdapter().load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)
    }[doc_key]
    info = SR.prepare(split, doc)
    prof = yaml.safe_load(SR.PROFILE.read_text())
    os.environ.update(
        {
            "CUMAP_DEMO_SLICE": info["slice_config"],
            "CUMAP_BENCHMARK_PROFILE": str(SR.PROFILE),
            "CUMAP_RELATION_REGISTRY": prof["relation_registry"],
        }
    )
    get_settings.cache_clear()
    rid = run_id(doc_key, TAG)
    pool = (base_cp.get("selection_stats") or {}).get("unique_candidate_pairs") or 0
    sel = select_without_sample(rid, max(pool, 1))
    rel = R.stage_relations(rid, dry_run=False, max_usd=MAX_USD_PER_DOC)
    return {
        "run_id": rid,
        "pool": pool,
        "baseline_selected": len(base_cp["selected_pairs"]),
        "selected": sel.get("selected"),
        "relations": rel,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cap-usd", type=float, default=2.0)
    ap.add_argument("--worker", nargs=2, metavar=("SPLIT", "DOC"))
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(*a.worker), default=str))
        return
    papers = [(s, d) for s, d in first_set() if _baseline_done(d)]
    papers = papers[: a.limit] if a.limit else papers
    spent, extra_total = 0.0, 0
    for split, d in papers:
        cp = json.loads((PG.run_path(run_id(d, BASE_TAG)) / "checkpoint.json").read_text())
        pool = (cp.get("selection_stats") or {}).get("unique_candidate_pairs") or 0
        extra = max(0, pool - len(cp["selected_pairs"]))
        extra_total += extra
        if a.dry_run:
            print(
                json.dumps(
                    {
                        "doc": d,
                        "pool": pool,
                        "baseline_selected": len(cp["selected_pairs"]),
                        "extra_pairs": extra,
                    }
                )
            )
            continue
        dck = PG.run_path(run_id(d, TAG)) / "checkpoint.json"
        if dck.exists() and json.loads(dck.read_text()).get("stage") == "snapshots":
            spent += recorded_spend(run_id(d, TAG))
            print(
                json.dumps(
                    {"doc": d, "skipped": "already finished", "spent_so_far": round(spent, 4)}
                ),
                flush=True,
            )
            continue
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, "-m", "cumap.cr043.arm_allpairs", "--worker", split, d],
            capture_output=True,
            text=True,
            check=False,
        )
        spent += recorded_spend(run_id(d, TAG))
        print(
            json.dumps(
                {
                    "doc": d,
                    "rc": r.returncode,
                    "s": round(time.time() - t0),
                    "extra_pairs": extra,
                    "spent_so_far": round(spent, 4),
                    "tail": (r.stdout + r.stderr)[-200:],
                }
            ),
            flush=True,
        )
        if r.returncode:
            raise SystemExit(f"{d} failed")
        if spent > a.cap_usd:
            raise SystemExit(f"cap reached: ${spent:.3f} > ${a.cap_usd}")
    if a.dry_run:
        print(
            json.dumps(
                {
                    "papers": len(papers),
                    "extra_pairs_total": extra_total,
                    "est_usd_luna": round(extra_total * 0.0005, 3),
                }
            )
        )


if __name__ == "__main__":
    main()
