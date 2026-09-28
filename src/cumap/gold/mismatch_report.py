"""`cumap gold mismatch-report`: tabulates match_type frequencies from the gold
student graphs (BUILD_PLAN M3 task 5). Read-only; reports/ is generated output,
not gold data.

CR-001 §7.4 additions: family_match/part_type_error already fall out of the same
per-edge match_type tally (they're just more MatchType enum values — see
schemas/enums.py); this module adds a chain-link type tally and a coarser
"agreement category" rollup (the closest analogue of "family-level agreement" the
M3-time data supports — true chain-link *alignment* match types
(ChainLinkMatchType.exact/wrong_link_type/...) only exist once the M7 diagnosis
pipeline runs an alignment; that's a separate report, not this one).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

# Mirrors ARCHITECTURE.md §4c's match_type -> verdict table, coarsened to 4 buckets
# so "the relation was in the right ballpark" (family/partial) is visible separately
# from "clean hit" and "wrong ballpark" — CR-001 §7.4's "agreement at the family level".
_AGREEMENT_CATEGORY = {
    "exact": "correct",
    "paraphrase": "correct",
    "valid_extra": "correct",
    "family_match": "same_family_wrong_relation",
    "partial_relation": "same_family_wrong_relation",
    "modality_error": "same_family_wrong_relation",
    # part_type_error means the student got the relation itself right (part_of) and only
    # the part_type qualifier wrong — closer to a same-relation detail slip than a
    # different-relation-same-family case, but grouped here since it's still not a clean hit.
    "part_type_error": "same_family_wrong_relation",
    "reversed": "wrong",
    "polarity_flip": "wrong",
    "substituted_concept": "wrong",
    "condition_error": "wrong",
    "wrong_type": "wrong",
    "unsupported_extra": "extra",
    "(unset)": "(unset)",
    "missing": "missing",
}


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


def collect_chain_link_type_counts(student_pilot_dir: Path) -> Counter:
    counts: Counter = Counter()
    if not student_pilot_dir.exists():
        return counts
    for path in sorted(student_pilot_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        for link in data.get("chain_links", []):
            counts[link.get("type", "(unset)")] += 1
    return counts


def agreement_by_category(match_type_counts: Counter) -> Counter:
    categories: Counter = Counter()
    for match_type, count in match_type_counts.items():
        categories[_AGREEMENT_CATEGORY.get(match_type, "other")] += count
    return categories


def generate_mismatch_report(student_pilot_dir: Path, out_path: Path) -> Path:
    match_counts = collect_match_type_counts(student_pilot_dir)
    chain_link_counts = collect_chain_link_type_counts(student_pilot_dir)

    lines = ["# M3 mismatch-type report\n"]
    if not match_counts:
        lines.append(
            "No gold student graphs found yet under `data/gold/student_pilot/`. "
            "Run this again after annotating with `cumap app review`.\n"
        )
    else:
        total = sum(match_counts.values())
        lines.append(f"{total} labelled items across {len(list(student_pilot_dir.glob('*.yaml')))} answers.\n")

        lines.append("## By match_type (relation level)\n")
        lines.append("| match_type | count | share |")
        lines.append("|---|---|---|")
        for match_type, count in match_counts.most_common():
            lines.append(f"| {match_type} | {count} | {count / total:.1%} |")

        lines.append("\n## By agreement category (family level)\n")
        lines.append(
            "Coarser view: exact/paraphrase/valid_extra -> correct; family_match/partial_relation/"
            "modality_error -> same family, wrong specific relation; everything else that's a real "
            "mismatch -> wrong.\n"
        )
        categories = agreement_by_category(match_counts)
        lines.append("| category | count | share |")
        lines.append("|---|---|---|")
        for category, count in categories.most_common():
            lines.append(f"| {category} | {count} | {count / total:.1%} |")

        lines.append("\n## Chain-link types annotated\n")
        if chain_link_counts:
            lines.append("| type | count |")
            lines.append("|---|---|")
            for link_type, count in chain_link_counts.most_common():
                lines.append(f"| {link_type} | {count} |")
        else:
            lines.append("None annotated yet.\n")
        lines.append(
            "\nNote: this tallies the *types* of chain links students expressed, not whether they "
            "match the expert's chain links (ChainLinkMatchType.exact/wrong_link_type/reversed_link/"
            "missing_link/unsupported_link) — that alignment only exists once the M7 diagnosis "
            "pipeline runs; it will get its own report then.\n"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
