"""CR-064 arm R2 (relations only): role-explicit registry v1.0.2 + relation_choice v9 on the adopted profile-v5 concepts.

Each `cr055ballp` run (first set) is copied to a new run id, its relation results are cleared (concepts and the all-pairs selection are
kept), and only relation classification is re-run under profile v12 (= v5 + registry v1.0.2 + endpoint_check choice + choice_prompt v9;
no node-type check). Family calls are cache hits (same prompt and input). The source runs are never written. Refuses to make a model
call while the registry patch is still a DRAFT (owner approval, 👤). Same procedure as CR-059 arm R (`cumap.cr059.arm_relations`).

    uv run python -m cumap.cr064.arm_relations --dry-run
    uv run python -m cumap.cr064.arm_relations --limit 2
    uv run python -m cumap.cr064.arm_relations
    uv run python -m cumap.cr064.arm_relations --arm r3   # CR-064 arm R3: choice_prompt v10
    uv run python -m cumap.cr064.arm_relations --arm r4   # arm R4: R3 + registry v1.0.3 (partOf rewrite)
    uv run python -m cumap.cr064.arm_relations --arm r6   # arm R6: R3 + origin-sentence background (relation_choice v11)
    uv run python -m cumap.cr064.arm_relations --arm r7   # arm R7: R3 + one-hop neighbourhood background (v12; needs R3 finished)
    uv run python -m cumap.cr064.arm_relations --arm r5   # arm R5: R3 on registry v1.0.4 (partOf removed); r8 = R6 and r9 = R7 (needs R5 finished) the same way
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

BASE_TAG = "cr055ballp"
ARMS = {  # arm -> (run tag, profile)
    "r2": ("cr064relR2", REPO_ROOT / "configs/scinlp_profile_v12.yaml"),
    "r3": (
        "cr064relR3",
        REPO_ROOT / "configs/scinlp_profile_v13.yaml",
    ),  # v12 + choice_prompt v10 (specific ends)
    "r4": (
        "cr064relR4",
        REPO_ROOT / "configs/scinlp_profile_v14.yaml",
    ),  # v13 + registry v1.0.3 (partOf)
    "r6": ("cr064relR6", REPO_ROOT / "configs/scinlp_profile_v15.yaml"),  # v13 + origin sentence
    "r7": ("cr064relR7", REPO_ROOT / "configs/scinlp_profile_v16.yaml"),  # v13 + 1-hop neighbours
}
ARMS.update(
    {
        "r5": ("cr064relR5", REPO_ROOT / "configs/scinlp_profile_v17.yaml"),  # R3 without partOf
        "r8": ("cr064relR8", REPO_ROOT / "configs/scinlp_profile_v18.yaml"),  # R6 without partOf
        "r9": ("cr064relR9", REPO_ROOT / "configs/scinlp_profile_v19.yaml"),  # R7 without partOf
    }
)
GRAPH_SOURCES = {  # neighbour arms read this finished arm's edges as their frozen first pass
    "r7": "cr064relR3",
    "r9": "cr064relR5",
}
PATCHES = {  # arm -> registry patch whose approval gates it
    "r2": "CR-064-relations-scinlp-v1.0.2.yaml",
    "r3": "CR-064-relations-scinlp-v1.0.2.yaml",
    "r4": "CR-064-relations-scinlp-v1.0.3.yaml",
    "r6": "CR-064-relations-scinlp-v1.0.2.yaml",
    "r7": "CR-064-relations-scinlp-v1.0.2.yaml",
    "r5": "CR-064-relations-scinlp-v1.0.4-drop-partOf.yaml",
    "r8": "CR-064-relations-scinlp-v1.0.4-drop-partOf.yaml",
    "r9": "CR-064-relations-scinlp-v1.0.4-drop-partOf.yaml",
}
TAG, PROFILE_V12 = ARMS["r2"]
PATCH = REPO_ROOT / "configs/registry-patches/CR-064-relations-scinlp-v1.0.2.yaml"
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


def approved(arm: str = "r2") -> bool:
    """The registry wording is owner-approved once the patch's header note no longer says DRAFT."""
    import yaml

    patch = PATCH.parent / PATCHES[arm]
    return "DRAFT" not in yaml.safe_load(patch.read_text())["header_note"]


def worker(split: str, doc_key: str, arm: str = "r2") -> dict:
    import yaml

    from cumap.concepts_v4 import cr009_run as R
    from cumap.config import get_settings
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.expert_kg import choice_context as CC

    assert split in ("train", "dev")
    tag, profile = ARMS[arm]
    if not approved(arm):
        raise SystemExit(f"registry patch {PATCHES[arm]} is a DRAFT: owner approval first")
    src, dst = PG.run_path(run_id(doc_key, BASE_TAG)), PG.run_path(run_id(doc_key, tag))
    if not dst.exists():
        shutil.copytree(src, dst)
        cp = cleared(json.loads((dst / "checkpoint.json").read_text()))
        (dst / "checkpoint.json").write_text(json.dumps(cp), encoding="utf-8")
    if (
        arm in GRAPH_SOURCES and not (dst / CC.GRAPH_FILE).exists()
    ):  # the frozen first pass, one sidecar per document
        scp = json.loads(
            (PG.run_path(run_id(doc_key, GRAPH_SOURCES[arm])) / "checkpoint.json").read_text()
        )
        if len(scp["relation_results_v3"]) < len(scp["selected_pairs"]):
            raise SystemExit(f"{GRAPH_SOURCES[arm]} is not finished for {doc_key}")
        edges = CC.graph_from_results(scp["relation_results_v3"])
        (dst / CC.GRAPH_FILE).write_text(
            json.dumps({"source": GRAPH_SOURCES[arm], "edges": edges}), encoding="utf-8"
        )
    doc = {
        d.doc_key: d
        for d in SciNLPAdapter().load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)
    }[doc_key]
    info = SR.prepare(split, doc)
    prof = yaml.safe_load(profile.read_text())
    os.environ.update({"CUMAP_DEMO_SLICE": info["slice_config"], "CUMAP_BENCHMARK_PROFILE": str(profile),
                       "CUMAP_RELATION_REGISTRY": prof["relation_registry"]})  # fmt: skip
    get_settings.cache_clear()
    rel = R.stage_relations(run_id(doc_key, tag), dry_run=False, max_usd=MAX_USD_PER_DOC)
    return {"run_id": run_id(doc_key, tag), "relations": rel}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cap-usd", type=float, default=1.0)
    ap.add_argument("--worker", nargs=2, metavar=("SPLIT", "DOC"))
    ap.add_argument("--arm", choices=sorted(ARMS), default="r2")
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(*a.worker, arm=a.arm), default=str))
        return
    tag = ARMS[a.arm][0]
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
        if not approved(a.arm):
            raise SystemExit(f"registry patch {PATCHES[a.arm]} is a DRAFT: owner approval first")
        dck = PG.run_path(run_id(d, tag)) / "checkpoint.json"
        if dck.exists() and json.loads(dck.read_text()).get("relation_results_v3") and \
                len(json.loads(dck.read_text())["relation_results_v3"]) >= len(cp["selected_pairs"]):  # fmt: skip
            spent += recorded_spend(run_id(d, tag))
            print(
                json.dumps(
                    {"doc": d, "skipped": "already finished", "spent_so_far": round(spent, 4)}
                ),
                flush=True,
            )
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", "cumap.cr064.arm_relations", "--worker", split, d, "--arm", a.arm],
                           capture_output=True, text=True, check=False)  # fmt: skip
        spent += recorded_spend(run_id(d, tag))
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
