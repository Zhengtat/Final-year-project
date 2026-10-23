"""CR-022 Part B scaffolding (no model call): apply an owner-approved SciNLP -> registry mapping to relations.

Only `status: approved` entries take effect (CLAUDE.md rule 11 spirit; the mapping is an owner decision and lives in configs/, never written by code).
Unmapped and not-approved labels are excluded and counted, not guessed. `swap` exchanges source and target (a mapped relation read in the other direction)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class MapEntry:
    target: str | None
    swap: bool = False
    fit: str = "clean"
    status: str = "draft"


def apply_mapping(
    relations: list[tuple[object, object, str]], mapping: dict[str, MapEntry]
) -> tuple[list[tuple[object, object, str]], Counter]:
    """relations are (src, tgt, label). Returns (mapped (src, tgt, target) with swaps applied, excluded counts by reason and label)."""
    out, excluded = [], Counter()
    for s, t, lab in relations:
        e = mapping.get(lab)
        if e is None or e.target is None:
            excluded[f"unmapped:{lab}"] += 1
        elif e.status != "approved":
            excluded[f"not_approved:{lab}"] += 1
        else:
            out.append((t, s, e.target) if e.swap else (s, t, e.target))
    return out, excluded


# ---------------------------------------------------------------- CR-024: the mapping now lives in the merged registry (v1.4 `external_labels`)
REGISTRY_V14 = "configs/relations_v1.4.yaml"


def registry_mapping(registry, source: str = "SciNLP") -> dict[str, MapEntry]:
    """label -> MapEntry from the merged registry: every relation that lists `source` labels. Owner-instructed (2026-10-22), so entries are approved;
    `fit` is `merged` for a relation that existed in v1.3 and `added` for one introduced by v1.4."""
    added = {
        "subtask_of",
        "enhanced_by",
        "measured_by",
        "evaluated_by",
        "evaluated_on",
        "similar_to",
    }
    out: dict[str, MapEntry] = {}
    for r in registry.all_relations():
        for lab in r.external_labels.get(source, []):
            out[lab] = MapEntry(r.name, False, "added" if r.name in added else "merged", "approved")
    return out


def hierarchy_labels(registry, source: str = "SciNLP") -> frozenset[str]:
    """Source labels of the registry's hierarchy relations: classification_structure relations that are transitive (is_a, subtask_of; part_of is only
    transitive within a part type, so it stays out, as in CR-017)."""
    return frozenset(
        lab
        for r in registry.all_relations()
        if r.family == "classification_structure" and r.transitive is True
        for lab in r.external_labels.get(source, [])
    )
