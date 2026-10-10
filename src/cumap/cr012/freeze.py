"""CR-012 freeze records. `schema`: the SciNLP benchmark-local schema (before any SciNLP model run). `final`: all evaluation code and
config (STOP 3 end). Hashes only; nothing here changes behaviour.

    uv run python -m cumap.cr012.freeze schema
    uv run python -m cumap.cr012.freeze final
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from cumap.config import REPO_ROOT

OUT = REPO_ROOT / "reports/cr012/frozen_hashes.json"
SCHEMA_FILES = {
    "scinlp_profile": "configs/cr012_scinlp_schema.yaml",
    "scinlp_relation_registry": "configs/relations_scinlp.yaml",
    "scinlp_generator_prompt": "prompts/concept_generator/v4_scinlp.md",
}
PIPELINE_FILES = {
    "concept_generator_cum": "prompts/concept_generator/v4.md",
    "concept_backfill": "prompts/concept_backfill/v1.md",
    "canonicalize": "prompts/canonicalize/v2.md",
    "relation_family": "prompts/relation_family/v3.md",
    "relation_choice": "prompts/relation_choice/v4.md",
    "relation_qualifiers": "prompts/relation_qualifiers/v4.md",
    "cum_relation_registry": "configs/relations_v1.3.yaml",
    "cum_concept_stage_config": "configs/concept_gvp.yaml",
    "alias_rules": "configs/alias_rules.yaml",
    "default_config": "configs/default.yaml",
    "cr012_eval_config": "configs/cr012_e2e_eval.yaml",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hashes(files: dict[str, str]) -> dict:
    return {k: {"path": v, "sha256": sha(REPO_ROOT / v)} for k, v in files.items()}


def code_hashes() -> dict:
    files = (
        sorted((REPO_ROOT / "src/cumap/cr012").glob("*.py"))
        + [
            REPO_ROOT / f"src/cumap/concepts_v4/{n}.py"
            for n in ("schema", "loop", "runner", "cr009_run")
        ]
        + [REPO_ROOT / "src/cumap/config.py"]
    )
    return {str(p.relative_to(REPO_ROOT)): sha(p) for p in files}


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    ).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["schema", "final"])
    a = ap.parse_args()
    rec = json.loads(OUT.read_text()) if OUT.exists() else {}
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    if a.phase == "schema":
        rec["scinlp_schema_freeze"] = {
            "frozen_at_utc": stamp,
            "git_head": git_head(),
            "files": hashes(SCHEMA_FILES),
            "isolation_scan": json.loads(
                (REPO_ROOT / "reports/cr012/isolation_scan.json").read_text()
            )["verdict"],
            "no_scinlp_model_run_before_this_point": True,
        }
    else:
        rec["final_freeze"] = {
            "frozen_at_utc": stamp,
            "git_head": git_head(),
            "schema_files": hashes(SCHEMA_FILES),
            "pipeline_files": hashes(PIPELINE_FILES),
            "evaluation_code": code_hashes(),
        }
    OUT.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(
        json.dumps(rec[f"{'scinlp_schema' if a.phase == 'schema' else 'final'}_freeze"], indent=1)[
            :1500
        ]
    )


if __name__ == "__main__":
    main()
