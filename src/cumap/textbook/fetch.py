"""Shallow-clones the Peterson & Davie textbook source and pins the commit."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def fetch_textbook(clone_dir: Path, repo_url: str) -> str:
    """Shallow-clone `repo_url` into `clone_dir` (or pull if already cloned).

    Returns the resulting commit hash.
    """
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    if (clone_dir / ".git").exists():
        subprocess.run(["git", "-C", str(clone_dir), "fetch", "--depth", "1"], check=True)
        subprocess.run(["git", "-C", str(clone_dir), "reset", "--hard", "FETCH_HEAD"], check=True)
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
            check=True,
        )
    result = subprocess.run(
        ["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def record_pinned_commit(config_path: Path, commit_hash: str) -> None:
    """Rewrite `pinned_commit: ...` in configs/default.yaml in place (regex, keeps comments)."""
    text = config_path.read_text()
    new_text, n = re.subn(
        r"pinned_commit:\s*\S+", f"pinned_commit: {commit_hash}", text, count=1
    )
    if n == 0:
        raise ValueError(f"Could not find a `pinned_commit:` line in {config_path}")
    config_path.write_text(new_text)
