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


if __name__ == "__main__":
    print(json.dumps(freeze(sys.argv[1]), indent=1))
