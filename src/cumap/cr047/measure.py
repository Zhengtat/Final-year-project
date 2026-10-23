"""CR-047 SciNLP check of the qualifier amendments (pre-registered in docs/DECISIONS.md before any call).

Both arms copy each finished `cr043base` paper (same concepts, same selected pairs), clear the relation results and re-run only the
relation stage with `qualifier_checks: v1`:
- `BASE`:  choice v4 / qualifiers v4, registry `relations_scinlp.yaml` (the frozen one; model calls are cache hits of `cr043base`);
- `AMEND`: `qualifier_amendments: v6`, registry `relations_scinlp_v1.0.1.yaml` (profile v2).

    uv run python -m cumap.cr047.measure --arm AMEND --dry-run | --limit 2 | (all)
    uv run python -m cumap.cr043.eval --tag cr047base ; uv run python -m cumap.cr043.eval --tag cr047amend
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
from cumap.cr043.run import TAG as BASE_TAG
from cumap.cr043.run import recorded_spend, run_id

ARMS = {
    "BASE": {"tag": "cr047base", "profile_v2": False, "qualifier_amendments": "off"},
    "AMEND": {"tag": "cr047amend", "profile_v2": True, "qualifier_amendments": "v6"},
}
CAP_USD = 1.0


def worker(split: str, doc_key: str, arm: str) -> dict:
    import yaml

    from cumap.concepts_v4 import experiments as X
    from cumap.config import REPO_ROOT, get_settings
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr047.scinlp_run import use_profile_v2
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.pipeline import load_checkpoint, save_checkpoint
    from cumap.llm.client import LLMClient
    from cumap.schemas.relations import RelationRegistry

    assert split in ("train", "dev")
    cfg = ARMS[arm]
    if cfg["profile_v2"]:
        use_profile_v2()
    src, dst = PG.run_path(run_id(doc_key, BASE_TAG)), PG.run_path(run_id(doc_key, cfg["tag"]))
    if not dst.exists():
        shutil.copytree(src, dst)
        cp = load_checkpoint(dst)
        cp.relation_results_v3 = []
        cp.stage = "relations"
        save_checkpoint(cp, dst)
    doc = {d.doc_key: d for d in SciNLPAdapter().load_documents(split, paragraph_every=SR.PARAGRAPH_EVERY)}[doc_key]  # fmt: skip
    info = SR.prepare(split, doc)
    prof = yaml.safe_load(SR.PROFILE.read_text())
    os.environ.update({"CUMAP_DEMO_SLICE": info["slice_config"], "CUMAP_BENCHMARK_PROFILE": str(SR.PROFILE), "CUMAP_RELATION_REGISTRY": prof["relation_registry"], "CUMAP_MATCHING": "r1key"})  # fmt: skip
    get_settings.cache_clear()
    settings = get_settings()
    settings.llm.stage_budgets_usd["relations"] = (
        3.0  # sol-era preflight bound; real spend capped by CAP_USD
    )
    rid = run_id(doc_key, cfg["tag"])
    cp = load_checkpoint(dst)
    client = LLMClient(settings, run_id=rid)
    registry = RelationRegistry.from_yaml(REPO_ROOT / prof["relation_registry"])
    cp = sr.relations_stage(client, cp, dst, registry, REPO_ROOT / "prompts", X.Embedder(settings.embeddings.model), qualifier_checks="v1", qualifier_amendments=cfg["qualifier_amendments"])  # fmt: skip
    cp.stage = "snapshots"  # the scorecard reads finished runs; relation results are what it scores
    save_checkpoint(cp, dst)
    return {
        "run_id": rid,
        "results": len(cp.relation_results_v3),
        "registry": prof["relation_registry"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS), required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--worker", nargs=2, metavar=("SPLIT", "DOC"))
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(*a.worker, a.arm), default=str))
        return
    tag = ARMS[a.arm]["tag"]
    papers = []
    for s, d in first_set():
        f = PG.run_path(run_id(d, BASE_TAG)) / "checkpoint.json"
        if f.exists() and json.loads(f.read_text()).get("stage") == "snapshots":
            papers.append((s, d))
    papers = papers[: a.limit] if a.limit else papers
    if a.dry_run:
        n = sum(len(json.loads((PG.run_path(run_id(d, BASE_TAG)) / "checkpoint.json").read_text())["selected_pairs"]) for _, d in papers)  # fmt: skip
        print(
            json.dumps(
                {
                    "arm": a.arm,
                    "papers": len(papers),
                    "pairs": n,
                    "est_usd_luna": round(n * 0.0006, 3),
                }
            )
        )
        return
    spent = 0.0
    for s, d in papers:
        dck = PG.run_path(run_id(d, tag)) / "checkpoint.json"
        if not (dck.exists() and json.loads(dck.read_text()).get("stage") == "snapshots"):
            r = subprocess.run([sys.executable, "-m", "cumap.cr047.measure", "--arm", a.arm, "--worker", s, d], capture_output=True, text=True, check=False)  # fmt: skip
            if r.returncode:
                raise SystemExit(f"{d} failed: {(r.stdout + r.stderr)[-400:]}")
        spent += recorded_spend(run_id(d, tag))
        print(json.dumps({"doc": d, "spent_so_far": round(spent, 4)}), flush=True)
        if spent > CAP_USD:
            raise SystemExit(f"cap reached: ${spent:.3f}")


if __name__ == "__main__":
    main()
