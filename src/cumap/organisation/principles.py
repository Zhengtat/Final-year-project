"""CR-006 §11 (principle mode, needs CR-004 STOP C for real data): time-aware activation of
`instantiates` edges. An edge is active from max(the concept's first chapter, the chapter of its
evidence section); a principle appears once it has >= 1 active edge. Principles are never pinned
to the centre: they earn their position like any node."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstantiatesEdge:
    edge_id: str
    concept_id: str
    principle_id: str
    evidence_section_id: str


def activation_chapters(
    edges: list[InstantiatesEdge],
    concept_first_chapter: dict[str, int],
    section_chapter: dict[str, int],
) -> dict[str, int]:
    return {
        e.edge_id: max(concept_first_chapter[e.concept_id], section_chapter[e.evidence_section_id])
        for e in edges
    }


def principles_present(
    edges: list[InstantiatesEdge], activation: dict[str, int], chapter: int
) -> dict[str, list[str]]:
    """principle_id -> its active edge ids at `chapter` (principles without any are absent)."""
    out: dict[str, list[str]] = {}
    for e in edges:
        if activation[e.edge_id] <= chapter:
            out.setdefault(e.principle_id, []).append(e.edge_id)
    return out
