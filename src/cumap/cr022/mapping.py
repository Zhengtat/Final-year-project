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
