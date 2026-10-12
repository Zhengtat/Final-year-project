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
    rec = {
        "status": "FROZEN", "group": group, "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
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
