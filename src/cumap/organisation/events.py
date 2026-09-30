"""CR-006 §8: restructuring events ("why did it move?"), the persistent-periphery review
flag, and per-chapter stability. Every node event carries the NEW edge IDs and section IDs
behind it. Nothing here deletes or demotes anything; `persistent_periphery` is a review flag."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import kendalltau

from cumap.organisation.config import OrgConfig
from cumap.organisation.inputs import OrgEdge
from cumap.organisation.rings import ring_rank
from cumap.organisation.schemas import RestructureEvent

CENTRAL = {"centre", "inner"}


@dataclass
class NodeSnap:
    concept_id: str
    name: str
    first_chapter: int
    ring: str
    basis: float  # percentile of the chosen importance basis (0 outside the eligible set)
    eligible: bool
    n_edges: int
    neighbours: set[str] = field(default_factory=set)


def _because(
    cid: str, cur: dict[str, NodeSnap], new_edges: list[OrgEdge]
) -> tuple[list[str], list[str]]:
    own = [e for e in new_edges if cid in (e.source, e.target)]
    if not own:  # moved because its neighbourhood changed: the newest edges around its neighbours
        nb = cur[cid].neighbours if cid in cur else set()
        own = sorted(
            (e for e in new_edges if e.source in nb or e.target in nb),
            key=lambda e: (-e.weight, e.edge_id),
        )[:5]
    return [e.edge_id for e in own], sorted({e.section_id for e in own})


def node_events(
    org_id: str,
    chapter: int,
    prev: dict[str, NodeSnap] | None,
    cur: dict[str, NodeSnap],
    new_edges: list[OrgEdge],
    ever_central: set[str],
    cfg: OrgConfig,
) -> list[RestructureEvent]:
    """`ever_central` = concepts that were centre/inner in any earlier snapshot (mutated by
    the caller after this call)."""
    out: list[RestructureEvent] = []
    gap = cfg.events.late_centraliser_gap_chapters
    for cid in sorted(cur):
        n = cur[cid]
        p = prev.get(cid) if prev is not None else None
        edges, secs = _because(cid, cur, new_edges)

        def ev(kind, frm=None, to=None, d=None, *, _cid=cid, _e=edges, _s=secs):
            out.append(
                RestructureEvent(
                    org_id=org_id,
                    chapter=chapter,
                    type=kind,
                    subject_ids=[_cid],
                    from_state=frm,
                    to_state=to,
                    delta_importance=d,
                    because_edge_ids=_e,
                    because_section_ids=_s,
                )
            )

        if p is None:
            ev("node_new", None, n.ring)
        else:
            d = round(n.basis - p.basis, 4)
            step = ring_rank(p.ring) - ring_rank(n.ring)
            if step >= 1:
                ev("ring_in", p.ring, n.ring, d)
            elif step <= -1:
                ev("ring_out", p.ring, n.ring, d)
            if n.ring == "centre" and p.ring != "centre":
                ev("enter_centre", p.ring, n.ring, d)
            if p.ring == "centre" and n.ring != "centre":
                ev("leave_centre", p.ring, n.ring, d)
            if p.ring in CENTRAL and n.ring == "outer":
                ev("fading", p.ring, n.ring, d)
        if (
            n.ring in CENTRAL
            and cid not in ever_central
            and chapter >= n.first_chapter + gap
            and n.first_chapter < chapter
        ):
            ev(
                "late_centraliser",
                f"introduced ch{n.first_chapter}",
                n.ring,
                None if p is None else round(n.basis - p.basis, 4),
            )
    return out


def update_persistent_periphery(
    streaks: dict[str, int], cur: dict[str, NodeSnap], cfg: OrgConfig
) -> set[str]:
    """Outer or unlinked with <= max typed edges for >= min consecutive snapshots."""
    flagged = set()
    for cid, n in cur.items():
        if (
            n.ring in {"outer", "unlinked"}
            and n.n_edges <= cfg.events.persistent_periphery_max_edges
        ):
            streaks[cid] = streaks.get(cid, 0) + 1
        else:
            streaks[cid] = 0
        if streaks[cid] >= cfg.events.persistent_periphery_min_snapshots:
            flagged.add(cid)
    return flagged


def stability(
    prev: dict[str, NodeSnap] | None,
    cur: dict[str, NodeSnap],
    displacement: float | None,
) -> dict:
    if prev is None:
        return {"jaccard_core": None, "kendall_tau": None, "mean_displacement": None, "n_shared": 0}
    a = {c for c, n in prev.items() if n.ring in CENTRAL}
    b = {c for c, n in cur.items() if n.ring in CENTRAL}
    jac = len(a & b) / len(a | b) if (a | b) else 1.0
    shared = sorted(c for c in cur if c in prev and cur[c].eligible and prev[c].eligible)
    tau = None
    if len(shared) >= 3:
        t = kendalltau([prev[c].basis for c in shared], [cur[c].basis for c in shared]).statistic
        tau = None if (t is None or math.isnan(t)) else float(t)
    return {
        "jaccard_core": jac,
        "kendall_tau": tau,
        "mean_displacement": displacement,
        "n_shared": len(shared),
    }


def mean_displacement(
    prev_xy: dict[str, tuple[float, float]], cur_xy: dict[str, tuple[float, float]]
) -> float | None:
    shared = [c for c in cur_xy if c in prev_xy]
    if not shared:
        return None
    return float(np.mean([math.dist(prev_xy[c], cur_xy[c]) for c in shared]))
