"""CR-015 freeze records (hashes, git commit, clean-tree check).

uv run python -m cumap.cr015.freeze scorer     # scorer definition + tests + split manifest"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

GROUPS = {
    "stageb_design": ["docs/cr015/STAGE_B_DESIGN.md", "prompts/cr015_concept_validity/v1.md", "prompts/cr015_concept_validity/v2.md"],
    "a2": [
        "prompts/cr015_boundary_family/v1.md", "prompts/cr014_concept_verifier/v2.md", "configs/cr014_concept_extraction.yaml", "configs/default.yaml",
        "src/cumap/cr015/selector.py", "src/cumap/cr015/placement.py", "src/cumap/cr015/stage_a.py", "src/cumap/cr015/dev_data.py", "src/cumap/cr015/scoring.py",
        "src/cumap/cr014/union.py", "src/cumap/cr014/proposal.py", "src/cumap/cr014/llm_stage.py", "src/cumap/cr014/v3_core.py", "src/cumap/cr014/pilot_score.py",
    ],
    "scorer": [
        "src/cumap/cr015/scoring.py", "src/cumap/cr014/pilot_score.py", "tests/test_cr015_scoring.py",
        "src/cumap/cr015/manifest.py", "configs/cr015_manifest.yaml",
    ],
}  # fmt: skip


def sha(p: str) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def freeze(group: str) -> dict:
    files = GROUPS[group]
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", *files], capture_output=True, text=True, check=True
    ).stdout.strip()
    if dirty:
        raise SystemExit(f"not committed: {dirty}")
    extra = {}
    if group == "a2":
        extra = {
            "candidate": "A2 = frozen CR-014 U2 -> family boundary selector (prompt cr015_boundary_family v1, bulk tier gpt-6-luna, 15 families/call, output cap 9000) -> frozen CR-014 V3 verifier (prompt v2) -> family-grounded nested-aware placement",
            "model_tier": "bulk (gpt-6-luna, reasoning effort low), no sampling parameters, no escalation",
            "development_outputs_sha256": {
                str(q): sha(str(q))
                for q in sorted(Path("data/processed/cr015/stageA").glob("A2_*.json"))
            },
            "no_change_rule": "no prompt, model, selector label set, placement rule, batch size or candidate rule may change after this freeze (Research, STOP 2 decision)",
        }
    rec = {
        **extra, "status": "FROZEN", "group": group, "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
        "hashes": {f: sha(f) for f in files},
    }  # fmt: skip
    Path(f"reports/cr015/FREEZE_{group.upper()}.json").write_text(json.dumps(rec, indent=1))
    return rec


def gold_manifest(kind: str, path: str, provenance: str, note: str) -> dict:
    import csv
    import time as _t

    rows = list(csv.DictReader(Path(path).open(encoding="utf-8-sig")))
    from collections import Counter

    rec = {
        "kind": kind, "path": path, "sha256": sha(path), "rows": len(rows),
        "concepts": sum(r["row_type"] == "CONCEPT" for r in rows), "mentions": sum(r["row_type"] == "MENTION" for r in rows),
        "nested_valid_mentions": sum((r.get("nested_valid") or "").strip().lower() in {"yes", "true", "1"} for r in rows),
        "review_decision_counts": dict(Counter((r.get("review_decision") or "").split(":")[0].strip().lower() or "blank" for r in rows).most_common()),
        "file_mtime": _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(Path(path).stat().st_mtime)), "recorded_at": _t.strftime("%Y-%m-%d %H:%M:%S"),
        "provenance_label": provenance, "note": note, "raw_file_committed": False,
    }  # fmt: skip
    Path(f"reports/cr015/gold_manifest_{kind}.json").write_text(json.dumps(rec, indent=1))
    return rec


if __name__ == "__main__":
    if sys.argv[1] == "gold-pilot":
        print(
            json.dumps(
                gold_manifest(
                    "pilot", "data/gold/cr015_pd_pilot_gold_draft.csv", sys.argv[2], sys.argv[3]
                ),
                indent=1,
            )
        )
    else:
        print(json.dumps(freeze(sys.argv[1]), indent=1))
