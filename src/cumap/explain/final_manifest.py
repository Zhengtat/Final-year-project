"""CR-013 STOP 5: the final trace manifest (`reports/cr013/final_trace_manifest.json`). Rebuilds the derived traces and the explorer from the current code, then records source run ids, source
artifact hashes (now, at the trace build, and at the STOP-1 audit), CR-013 code / config hashes, derived-trace hashes and the read-only integrity confirmation. Hashes and paths only.

    uv run python -m cumap.explain.final_manifest"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.explain.build import build, sha

RUNS = ["slice3_c2", "cr012_scinlp_heldout_P17_1058_grobid_E0"]
OVERLAY_INPUTS = [
    "reports/cr012/stop4_heldout_results.json", "reports/cr012/heldout_gold_provenance.json", "data/gold/pd_e2e_test_blind.csv",
    *[f"data/processed/kg/cr012_scinlp_heldout_{d}_E0/checkpoint.json" for d in ("2021_acl_long_353", "2024_acl_long_108_1_9_grobid", "P17_1058_grobid")],
    *[f"data/processed/kg/cr012_heldout_{s}_E0/checkpoint.json" for s in ("4_4", "4_5", "5_4", "6_3", "7_1", "8_2", "9_3")],
]  # fmt: skip
CODE_GLOBS = [
    "src/cumap/explain/*.py",
    "src/cumap/report/kg_explorer.py",
    "src/cumap/report/kg_explorer.html",
    "src/cumap/report/kg_explorer_trace.js",
    "src/cumap/report/kg_explorer_eval.js",
    "configs/cr013_explainability.yaml",
    "tests/test_cr013_*.py",
    "tests/js/*",
]


def git(*a: str) -> str:
    return subprocess.run(
        ["git", *a], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    ).stdout.strip()


def main() -> None:
    audit = {
        a["path"]: a["sha256"]
        for a in json.loads((REPO_ROOT / "reports/cr013/trace_coverage.json").read_text())[
            "artifacts"
        ]
    }
    overlay_before = {p: sha(REPO_ROOT / p) for p in OVERLAY_INPUTS}
    runs: dict = {}
    for run in RUNS:
        r = build(run, replay_enabled=run == "slice3_c2")
        m = r["manifest"]
        d = REPO_ROOT / r["dir"]
        now = {p: sha(REPO_ROOT / p) for p in m["source_artifacts"]}
        runs[run] = {
            "explain_id": m["explain_id"], "derived_dir": r["dir"], "dataset_mode": m["dataset_mode"], "trace_schema_version": m["trace_schema_version"], "renderer_version": m["renderer_version"], "explain_code_hash": m["explain_code_hash"],
            "source_artifact_hashes": m["source_artifacts"], "source_hashes_after_build": m["source_hashes_after_build"],
            "unchanged_during_build": m["source_hashes_unchanged"], "unchanged_now_vs_build_time": now == m["source_artifacts"],
            "unchanged_now_vs_stop1_audit": {p: audit[p] == h for p, h in now.items() if p in audit}, "stop1_audit_artifacts_compared": sum(1 for p in now if p in audit),
            "derived_trace_hashes": {f.name: sha(f) for f in sorted(d.iterdir()) if f.is_file()}, "replay": {k: m["replay"].get(k) for k in ("valid", "deterministic", "eligible_count", "mismatches")}, "counts": m["counts"],
            "two_builds_identical_trace_hash": m["replay_determinism_trace_hash_equal"], "coverage_summary": {k: m["coverage"][k] for k in ("final_objects", "evidence", "explanations")}, "gaps_by_status": m["coverage"]["gaps"]["by_status"],
        }  # fmt: skip
    from cumap.report.kg_explorer import build as build_page

    p1, p2 = (
        REPO_ROOT / "reports/kg_explorer/index.html",
        REPO_ROOT / "data/interim/explorer_second_build.html",
    )
    build_page(p1)
    build_page(p2)
    html = p1.read_text(encoding="utf-8")
    blob = lambda tag: hashlib.sha256(
        gzip.decompress(base64.b64decode(html.split(f'id="{tag}">')[1].split("</script>")[0]))
    ).hexdigest()
    explorer = {
        "path": "reports/kg_explorer/index.html (generated, gitignored: embeds CC BY-NC SciNLP text)",
        "sha256": sha(p1),
        "bytes": p1.stat().st_size,
        "second_build_identical": sha(p1) == sha(p2),
        "trace_payload_json_sha256": blob("trace-gz"),
        "eval_payload_json_sha256": blob("eval-gz"),
    }
    p2.unlink()
    overlay_after = {p: sha(REPO_ROOT / p) for p in OVERLAY_INPUTS}
    code = {}
    for g in CODE_GLOBS:
        for f in sorted(REPO_ROOT.glob(g)):
            if f.is_file() and "__pycache__" not in f.parts:
                code[f.relative_to(REPO_ROOT).as_posix()] = sha(f)
    combined = hashlib.sha256(
        "".join(f"{k}{v}" for k, v in sorted(code.items())).encode()
    ).hexdigest()
    ok = (
        all(
            r["unchanged_during_build"]
            and r["unchanged_now_vs_build_time"]
            and all(r["unchanged_now_vs_stop1_audit"].values())
            for r in runs.values()
        )
        and overlay_before == overlay_after
    )
    manifest = {
        "cr": "CR-013", "scope": "explainability / observability only; no accuracy-improvement claim", "git": {"branch": git("branch", "--show-current"), "head_at_manifest_time": git("rev-parse", "HEAD"), "base_commit": "2e50b6538ab5a8c97c9df3a218ab70646af90695", "cr012_frozen_tag": "cr012-stop4-complete (4697acb)"},
        "source_run_ids": RUNS, "derived_traces": runs, "overlay_frozen_inputs": {"hashes_before": overlay_before, "hashes_after": overlay_after, "unchanged": overlay_before == overlay_after, "note": "read-only inputs of the evaluation overlay (frozen CR-012 outputs, retained E0 checkpoints, owner gold)"},
        "explorer": explorer, "cr013_code_and_config_hashes": code, "cr013_code_combined_sha256": combined, "read_only_integrity": {"all_audited_source_artifacts_byte_identical": ok, "checked_against": ["hashes before and after each trace build", "hashes now", "hashes recorded by the STOP-1 audit"]},
    }  # fmt: skip
    out = REPO_ROOT / "reports/cr013/final_trace_manifest.json"
    out.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "integrity_ok": ok,
                "explain_ids": {k: v["explain_id"] for k, v in runs.items()},
                "explorer_sha": explorer["sha256"][:16],
                "explorer_second_build_identical": explorer["second_build_identical"],
                "code_combined": combined[:16],
                "stop1_artifacts_compared": {
                    k: v["stop1_audit_artifacts_compared"] for k, v in runs.items()
                },
            },
            indent=1,
        )
    )
    _ = Path


if __name__ == "__main__":
    main()
