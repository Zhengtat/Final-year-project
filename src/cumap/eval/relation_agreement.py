"""`cumap eval relation-agreement`: CR-001 §7.3 — scores the two completed
annotation sheets in data/gold/relation_agreement/ against each other. Read-only.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from cumap.schemas.relations import RelationRegistry

CONFUSION_THRESHOLD = 0.20


def _family_or_sentinel(relation: str, registry: RelationRegistry) -> str:
    if relation in ("no_relation", "other") or relation not in registry:
        return relation
    return registry.family_of(relation)


def _kappa(a: list, b: list) -> float:
    """Cohen's κ, with the one degenerate case handled explicitly: sklearn returns NaN
    when the two sequences share only one label in common overall — which can only
    happen when they are identical (perfect agreement), so that's exactly what NaN
    should mean here, not "undefined": κ=1.0 for a real annotator sheet, not "no signal".
    """
    if a == b:
        return 1.0
    k = cohen_kappa_score(a, b)
    return 1.0 if math.isnan(k) else k


def compute_agreement(sheet_a: pd.DataFrame, sheet_b: pd.DataFrame, registry: RelationRegistry) -> dict:
    merged = sheet_a.merge(sheet_b, on="item_id", suffixes=("_a", "_b"))
    if merged.empty:
        raise ValueError("No matching item_id between the two annotator sheets")

    relations_a = merged["relation_a"].fillna("no_relation").tolist()
    relations_b = merged["relation_b"].fillna("no_relation").tolist()

    relation_kappa = _kappa(relations_a, relations_b)

    families_a = [_family_or_sentinel(r, registry) for r in relations_a]
    families_b = [_family_or_sentinel(r, registry) for r in relations_b]
    family_kappa = _kappa(families_a, families_b)

    # Direction agreement: only meaningful where both annotators picked the same relation.
    same_relation_mask = [a == b for a, b in zip(relations_a, relations_b, strict=True)]
    directions_a = merged["direction_a"].fillna("").tolist()
    directions_b = merged["direction_b"].fillna("").tolist()
    comparable = [
        (da == db) for m, da, db in zip(same_relation_mask, directions_a, directions_b, strict=True) if m
    ]
    direction_agreement_rate = (sum(comparable) / len(comparable)) if comparable else None

    all_relations = sorted(set(relations_a) | set(relations_b))
    per_relation_kappa = {}
    for r in all_relations:
        binary_a = [x == r for x in relations_a]
        binary_b = [x == r for x in relations_b]
        if len(set(binary_a)) < 2 and len(set(binary_b)) < 2:
            per_relation_kappa[r] = None  # both annotators agree unanimously (never/always r) — kappa undefined
            continue
        per_relation_kappa[r] = cohen_kappa_score(binary_a, binary_b)

    confusion = Counter(zip(relations_a, relations_b, strict=True))

    confused_pairs = []
    for r in all_relations:
        n_chosen_by_either = sum(1 for a, b in zip(relations_a, relations_b, strict=True) if r in (a, b))
        if n_chosen_by_either == 0:
            continue
        n_disagreements_involving_r = sum(
            1 for a, b in zip(relations_a, relations_b, strict=True) if r in (a, b) and a != b
        )
        rate = n_disagreements_involving_r / n_chosen_by_either
        if rate > CONFUSION_THRESHOLD:
            confused_with = Counter(
                (b if a == r else a) for a, b in zip(relations_a, relations_b, strict=True) if r in (a, b) and a != b
            )
            confused_pairs.append({"relation": r, "confusion_rate": rate, "most_confused_with": confused_with.most_common(1)[0][0] if confused_with else None})

    return {
        "n_items": len(merged),
        "relation_kappa": relation_kappa,
        "family_kappa": family_kappa,
        "direction_agreement_rate": direction_agreement_rate,
        "per_relation_kappa": per_relation_kappa,
        "confusion_matrix": confusion,
        "confused_pairs": confused_pairs,
    }


def write_agreement_report(result: dict, out_path: Path) -> Path:
    lines = ["# M3 relation-set agreement report (CR-001 §7.3)\n"]
    lines.append(f"{result['n_items']} items scored.\n")
    lines.append(f"- **Relation-level Cohen's κ:** {result['relation_kappa']:.3f}")
    lines.append(f"- **Family-level Cohen's κ:** {result['family_kappa']:.3f}")
    da = result["direction_agreement_rate"]
    lines.append(f"- **Direction agreement rate** (items where both picked the same relation): {da:.1%}" if da is not None else "- **Direction agreement rate:** n/a (no items with matching relation)")

    lines.append("\n## Per-relation κ\n")
    lines.append("| relation | κ |")
    lines.append("|---|---|")
    for r, k in sorted(result["per_relation_kappa"].items()):
        lines.append(f"| {r} | {k:.3f} |" if k is not None else f"| {r} | n/a (no variation) |")

    lines.append("\n## Relation pairs confused in >20% of items where either was chosen\n")
    if not result["confused_pairs"]:
        lines.append("None.\n")
    else:
        lines.append("| relation | confusion rate | most confused with |")
        lines.append("|---|---|---|")
        for c in sorted(result["confused_pairs"], key=lambda x: -x["confusion_rate"]):
            lines.append(f"| {c['relation']} | {c['confusion_rate']:.1%} | {c['most_confused_with']} |")

    lines.append(
        "\n## Recommendation (not applied automatically — the human decides)\n\n"
        "Relations with κ < 0.6, or confused in > 20% of items, are merge/split/redefine "
        "candidates. Likely candidates per the research doc: triggers/causes, uses/requires, "
        "has_purpose/uses. Log the decision in `docs/DECISIONS.md`; create "
        "`configs/relations_v1.1.yaml` if the registry itself needs to change.\n"
    )
    low_kappa = [r for r, k in result["per_relation_kappa"].items() if k is not None and k < 0.6]
    if low_kappa:
        lines.append(f"Relations below κ=0.6 in this run: {', '.join(low_kappa)}.\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
