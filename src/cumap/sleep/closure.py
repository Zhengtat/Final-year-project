"""CR-011 closure (Research 2026-10-09): the no-op CR-012 evaluation handoff. CR-011 adopted no production transformation, so the
'post-sleep' graph is the SAME immutable snapshot as the pre-sleep graph; nothing is migrated and no migrated graph is faked.

    uv run python -m cumap.sleep.closure write      # writes reports/cr011_sleep/CR012_EVAL_HANDOFF.json
    uv run python -m cumap.sleep.closure validate   # re-checks every path and hash it references
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT, get_settings

OUT = REPO_ROOT / "reports/cr011_sleep/CR012_EVAL_HANDOFF.json"
RUN = "slice3_c2"
PROMPTS = {
    "concept_generator": "v4",
    "concept_backfill": "v1",
    "canonicalize": "v2",
    "relation_family": "v3",
    "relation_choice": "v4",
    "relation_qualifiers": "v4",
    "sleep_merge_adjudicator": "v1 (never executed: no LLM arm ran)",
}
CONFIGS = {
    "cr009_concept_stage": "configs/concept_gvp.yaml",
    "cr010_node": "configs/cr010_node.yaml",
    "cr010_experiments": "configs/cr010_experiments.yaml",
    "cr011_sleep": "configs/sleep_consolidation_v1.yaml",
    "relation_registry": "configs/relations_v1.3.yaml",
    "term_lexicon": "configs/term_lexicon.yaml",
    "alias_rules": "configs/alias_rules.yaml",
    "canonical_overrides": "configs/canonical_overrides.yaml",
    "default": "configs/default.yaml",
}
REQUIRED_STATE = {
    "cr011_status": "closed_no_production_change",
    "sleep_adopted": False,
    "automatic_merge_enabled": False,
    "human_gated_review_adopted": False,
    "stop4_executed": False,
    "stop5_executed": False,
    "production_adoption": "NO",
}
NO_OP = {
    "post_sleep_state": "no_op_same_as_pre_sleep",
    "merge_transactions": [],
    "edge_rewrites": [],
    "id_map_status": "identity_no_change",
    "rollback_status": "NOT_APPLICABLE_NO_MIGRATION",
    "evidence_retention_status": "NOT_APPLICABLE_NO_MIGRATION",
    "alias_provenance_migration_status": "NOT_APPLICABLE_NO_MIGRATION",
}
GATES = {
    "automatic_merge_precision": "NOT_EVALUATED / NOT_APPLICABLE - no candidate architecture advanced",
    "wilson_precision_gate": "NOT_EVALUATED / NOT_APPLICABLE",
    "stop4_heldout_safety": "NOT_RUN",
    "stop5_rollback": "NOT_APPLICABLE_NO_MIGRATION",
    "stop5_evidence_retention": "NOT_APPLICABLE_NO_MIGRATION",
    "stop5_alias_provenance_migration": "NOT_APPLICABLE_NO_MIGRATION",
    "production_adoption": "NO",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    ).stdout.strip()


def snapshot_manifest(run: str) -> dict:
    d = REPO_ROOT / "data/processed/kg" / run
    files = {str(p.relative_to(REPO_ROOT)): sha(p) for p in sorted(d.rglob("*")) if p.is_file()}
    return {
        "snapshot_dir": str(d.relative_to(REPO_ROOT)),
        "checkpoint_path": f"data/processed/kg/{run}/checkpoint.json",
        "checkpoint_sha256": sha(d / "checkpoint.json"),
        "files": files,
        "files_count": len(files),
    }


def build() -> dict:
    s = get_settings()
    snap = snapshot_manifest(RUN)
    prompts = {}
    for task, ver in PROMPTS.items():
        p = (
            REPO_ROOT
            / "prompts"
            / (
                "sleep_merge_adjudicator_v1.md"
                if task == "sleep_merge_adjudicator"
                else f"{task}/{ver}.md"
            )
        )
        prompts[task] = {"version": ver, "path": str(p.relative_to(REPO_ROOT)), "sha256": sha(p)}
    cfgs = {k: {"path": v, "sha256": sha(REPO_ROOT / v)} for k, v in CONFIGS.items()}
    lex = yaml.safe_load((REPO_ROOT / CONFIGS["term_lexicon"]).read_text())
    sleep_cfg = yaml.safe_load((REPO_ROOT / CONFIGS["cr011_sleep"]).read_text())
    held = {
        name: {
            "path": f"data/interim/checks/cr011/{name}",
            "sha256": sha(REPO_ROOT / "data/interim/checks/cr011" / name),
            "opened_by_any_pipeline": False,
            "labels_exist": False,
        }
        for name in ("sleep240_heldout_blind_sheet.csv", "sleep_pos160_heldout_blind_sheet.csv")
    }
    return {
        "handoff_kind": "CR-011 no-op closure handoff for CR-012",
        **REQUIRED_STATE,
        "source_run_id": RUN,
        "sleep_id": None,
        "pre_sleep_snapshot": {"run_id": RUN, **snap},
        "post_sleep_snapshot": {
            "run_id": RUN,
            "same_as_pre_sleep": True,
            "checkpoint_sha256": snap["checkpoint_sha256"],
        },
        **NO_OP,
        "suspected_splits": [],
        "organisation": {
            "pre": f"data/processed/kg/{RUN}/organisation",
            "post": f"data/processed/kg/{RUN}/organisation",
            "replayed": False,
        },
        "gates": GATES,
        "heldout_sets": {
            "status": "sealed; held-out evaluation not executed because the frozen development continuation criterion was not met",
            **held,
        },
        "configs": cfgs,
        "registry_version": "relations v1.3 (configs/relations_v1.3.yaml)",
        "term_lexicon_version": str(lex.get("version")),
        "alias_rules_version": yaml.safe_load((REPO_ROOT / CONFIGS["alias_rules"]).read_text()).get(
            "version"
        ),
        "cr011_config_status": sleep_cfg.get("status"),
        "models": {
            t: {"model": c.model, "reasoning_effort": c.reasoning_effort}
            for t, c in s.llm.tiers.items()
        },
        "models_note": "CR-009 concept generator ran on the bulk tier; canonicalisation and relation classification on the strong tier; CR-011 ran no LLM call",
        "prompts": prompts,
        "seeds_and_determinism": {
            "sleep240_seed": 20261009,
            "sleep_pos160_seed": 20261010,
            "scorer_seed": 20261008,
            "llm": "every LLM call is disk-cached by (model, prompt version, input hash); CR-011 made no LLM call",
        },
        "git": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "head_at_handoff": git("rev-parse", "HEAD"),
            "tags": {
                t: git("rev-list", "-n", "1", t) for t in ("cr-009-complete", "cr-010-complete")
            },
        },
        "cr012_interpretation": "CR-011 adopted no production graph transformation, so no pre/post sleep accuracy experiment exists for the production pipeline; the final production graph is the pre-CR-011 graph. Do not claim a measured sleep delta of zero. Canonicalisation error attribution remains available through CR-012's oracle experiments (E2).",
    }


def validate(path: Path = OUT, check_files: bool = True) -> list[str]:
    h = json.loads(path.read_text())
    problems = [
        f"{k} should be {v!r}" for k, v in {**REQUIRED_STATE, **NO_OP}.items() if h.get(k) != v
    ]
    problems += [f"gate {k} should be {v!r}" for k, v in GATES.items() if h["gates"].get(k) != v]
    if (
        h["post_sleep_snapshot"]["checkpoint_sha256"]
        != h["pre_sleep_snapshot"]["checkpoint_sha256"]
    ):
        problems.append("post-sleep graph must be the same snapshot as the pre-sleep graph")
    if not h["post_sleep_snapshot"]["same_as_pre_sleep"]:
        problems.append("post_sleep_snapshot.same_as_pre_sleep must be true")
    for key in (
        "source_run_id",
        "configs",
        "registry_version",
        "term_lexicon_version",
        "models",
        "prompts",
        "seeds_and_determinism",
        "git",
    ):
        if not h.get(key):
            problems.append(f"missing {key}")
    if any(
        h["heldout_sets"][n]["opened_by_any_pipeline"] or h["heldout_sets"][n]["labels_exist"]
        for n in h["heldout_sets"]
        if n.endswith(".csv")
    ):
        problems.append("a held-out set is recorded as opened")
    if check_files:
        for rel, digest in h["pre_sleep_snapshot"]["files"].items():
            p = REPO_ROOT / rel
            if not p.exists() or sha(p) != digest:
                problems.append(f"snapshot file changed or missing: {rel}")
        for group in (h["configs"], h["prompts"]):
            for name, rec in group.items():
                p = REPO_ROOT / rec["path"]
                if not p.exists() or sha(p) != rec["sha256"]:
                    problems.append(f"hash mismatch: {name}")
        for name, rec in h["heldout_sets"].items():
            if name.endswith(".csv") and sha(REPO_ROOT / rec["path"]) != rec["sha256"]:
                problems.append(f"held-out sheet changed: {name}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["write", "validate"])
    a = ap.parse_args()
    if a.phase == "write":
        OUT.write_text(json.dumps(build(), indent=1, sort_keys=False), encoding="utf-8")
    problems = validate()
    print(f"{OUT}: {len(problems)} problems")
    for p in problems:
        print(" -", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
