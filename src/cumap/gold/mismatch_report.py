"""`cumap gold mismatch-report`: tabulates match_type frequencies from the gold
student graphs (BUILD_PLAN M3 task 5). Read-only; reports/ is generated output,
not gold data.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml


def collect_match_type_counts(student_pilot_dir: Path) -> Counter:
    counts: Counter = Counter()
    if not student_pilot_dir.exists():
        return counts
    for path in sorted(student_pilot_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        for edge in data.get("edges", []):
            match_type = edge.get("match_type") or "(unset)"
            counts[match_type] += 1
        for _ in data.get("missing_expected_edges", []):
            counts["missing"] += 1
    return counts


def generate_mismatch_report(student_pilot_dir: Path, out_path: Path) -> Path:
    counts = collect_match_type_counts(student_pilot_dir)

    lines = ["# M3 mismatch-type report\n"]
    if not counts:
        lines.append(
            "No gold student graphs found yet under `data/gold/student_pilot/`. "
            "Run this again after annotating with `cumap app review`.\n"
        )
    else:
        total = sum(counts.values())
        lines.append(f"{total} labelled items across {len(list(student_pilot_dir.glob('*.yaml')))} answers.\n")
        lines.append("| match_type | count | share |")
        lines.append("|---|---|---|")
        for match_type, count in counts.most_common():
            lines.append(f"| {match_type} | {count} | {count / total:.1%} |")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
