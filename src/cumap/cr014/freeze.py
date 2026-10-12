"""CR-014 freeze: hashes of everything that determines the held-out prediction, and gold hash manifests (the gold file is hashed, never committed or parsed here).

uv run python -m cumap.cr014.freeze v3            # writes reports/cr014/FREEZE_V3.json (refuses on a dirty tree)
uv run python -m cumap.cr014.freeze gold pilot    # writes reports/cr014/gold_manifest_pilot.json
uv run python -m cumap.cr014.freeze gold heldout  # writes reports/cr014/gold_manifest_heldout.json (counts only)"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(".")
FILES = [
    "prompts/cr014_concept_verifier/v1.md", "prompts/cr014_concept_verifier/v2.md", "prompts/cr014_boundary_repair/v1.md",
    "prompts/concept_generator/v4.md", "prompts/canonicalize/v2.md",
    "configs/cr014_concept_extraction.yaml", "configs/cr014_manifest.yaml", "configs/concept_gvp.yaml", "configs/default.yaml",
    "configs/term_lexicon.yaml", "configs/alias_rules.yaml",
    "src/cumap/cr014/union.py", "src/cumap/cr014/proposal.py", "src/cumap/cr014/llm_stage.py", "src/cumap/cr014/v3_core.py",
    "src/cumap/cr014/heldout_run.py", "src/cumap/cr014/freeze.py", "src/cumap/cr012/unit_run.py",
]  # fmt: skip
TREES = ["src/cumap/concepts_v4", "src/cumap/llm", "configs/fewshot"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_hashes() -> dict[str, str]:
    h = {f: sha(ROOT / f) for f in FILES if (ROOT / f).exists()}
    for t in TREES:
        for p in sorted((ROOT / t).rglob("*")):
            if (
                p.is_file()
                and "__pycache__" not in p.parts
                and p.suffix in {".py", ".yaml", ".md", ".json"}
            ):
                h[str(p)] = sha(p)
    return h


def git(*a: str) -> str:
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout.strip()


def versions() -> dict:
    import importlib.metadata as md

    out = {"python": sys.version.split()[0]}
    for p in (
        "openai",
        "spacy",
        "en_core_web_sm",
        "scikit-learn",
        "sentence-transformers",
        "pydantic",
        "numpy",
    ):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


def freeze_v3() -> dict:
    from cumap.config import get_settings

    dirty = [
        x
        for x in git(
            "status", "--porcelain", "--", "src", "prompts", "configs", "tests"
        ).splitlines()
        if x.strip()
    ]
    if dirty:
        raise SystemExit(f"working tree not clean for frozen paths: {dirty[:5]}")
    s = get_settings()
    tiers = {
        k: {"model": v.model, "reasoning_effort": v.reasoning_effort}
        for k, v in s.llm.tiers.items()
    }
    rec = {
        "status": "FROZEN", "candidate": "V3 (U2 proposal union; boundary repair v1; verifier prompt v2; one-token evidence)",
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git("rev-parse", "HEAD"),
        "model_tier_used": "bulk", "tiers": tiers, "max_output_tokens": {"cr014_concept_verifier": 6000, "cr014_boundary_repair": 6000},
        "deterministic_settings": {"sampling_params": "none (reasoning models take no temperature/top_p)", "escalation": False, "cache": "disk, keyed by (model, prompt_version, input hash)", "batching": {"candidates": 25, "families": 15}, "ranker_weights": "equal, fixed a priori", "gate": "none", "manifest_seed": "cr014-manifest-v2"},
        "versions": versions(), "hashes": current_hashes(),
        "no_change_rule": "no threshold, prompt, model, candidate rule, placement rule or boundary rule may change after this freeze (Research, STOP 3B)",
    }  # fmt: skip
    Path("reports/cr014/FREEZE_V3.json").write_text(json.dumps(rec, indent=1))
    return rec


def gold_manifest(kind: str) -> dict:
    path = ROOT / (
        "data/gold/pd_concept_pilot_blind.csv"
        if kind == "pilot"
        else "data/gold/pd_concept_test_blind.csv"
    )
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    st = path.stat()
    rec = {
        "kind": kind, "path": str(path), "sha256": sha(path), "rows": len(rows),
        "concepts": sum(r["row_type"] == "CONCEPT" for r in rows), "mentions": sum(r["row_type"] == "MENTION" for r in rows),
        "nested_valid_mentions": sum((r.get("nested_valid") or "").strip().lower() in {"yes", "true", "1"} for r in rows),
        "file_mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)), "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "annotator_provenance": "TO BE STATED BY THE OWNER (human / LLM-assisted); not asserted by code",
        "raw_file_committed": False,
    }  # fmt: skip
    Path(f"reports/cr014/gold_manifest_{kind}.json").write_text(json.dumps(rec, indent=1))
    return rec


if __name__ == "__main__":
    if sys.argv[1] == "v3":
        print(json.dumps({k: v for k, v in freeze_v3().items() if k != "hashes"}, indent=1))
    else:
        print(json.dumps(gold_manifest(sys.argv[2]), indent=1))
