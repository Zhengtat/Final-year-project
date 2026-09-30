"""CR-006 §9: the sphere layout. A 2D disc: radius comes from the ring/importance (rings.py),
angle from the concept's coarse community sector. Built to keep the mental map (Misue et al.
1995): sector centres are fixed once a community is born, an existing node keeps its angle while
it stays in the same community, and any relaxation is capped (20 degrees per chapter).

Unlinked and background nodes sit on outer bands at a stable hash-based angle. Deterministic.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from cumap.organisation.config import OrgConfig

MIN_HALF_WIDTH = 4.0


@dataclass
class LayoutState:
    centres: dict[str, float] = field(default_factory=dict)  # coarse community id -> centre angle
    order: list[str] = field(default_factory=list)  # circular order of community ids
    angles: dict[str, float] = field(default_factory=dict)  # concept id -> angle (eligible nodes)
    comm_of: dict[str, str] = field(default_factory=dict)  # concept id -> coarse community id


def wrap(a: float) -> float:
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def circ_mean(angles: list[float], weights: list[float]) -> float | None:
    if not angles:
        return None
    x = sum(w * math.cos(math.radians(a)) for a, w in zip(angles, weights, strict=True))
    y = sum(w * math.sin(math.radians(a)) for a, w in zip(angles, weights, strict=True))
    return None if abs(x) + abs(y) < 1e-12 else math.degrees(math.atan2(y, x))


def hash_unit(key: str) -> float:
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def band_angle(concept_id: str) -> float:
    return hash_unit("band:" + concept_id) * 360.0


def _weights_between(
    groups: dict[str, list[str]], adj: dict[tuple[str, str], float]
) -> dict[tuple[str, str], float]:
    where = {c: g for g, ms in groups.items() for c in ms}
    out: dict[tuple[str, str], float] = {}
    for (a, b), w in adj.items():
        ga, gb = where.get(a), where.get(b)
        if ga and gb and ga != gb:
            key = (ga, gb) if ga < gb else (gb, ga)
            out[key] = out.get(key, 0.0) + w
    return out


def _place_communities(
    state: LayoutState, groups: dict[str, list[str]], between: dict[tuple[str, str], float]
) -> None:
    def w(a: str, b: str) -> float:
        return between.get((a, b) if a < b else (b, a), 0.0)

    state.order = [c for c in state.order if c in groups]
    state.centres = {c: a for c, a in state.centres.items() if c in groups}
    new = sorted((c for c in groups if c not in state.centres), key=lambda c: (-len(groups[c]), c))
    if not state.order and new:
        chain = [new.pop(0)]  # largest first, then greedy nearest neighbour by shared edge weight
        while new:
            nxt = max(new, key=lambda c: (w(chain[-1], c), len(groups[c]), c))
            new.remove(nxt)
            chain.append(nxt)
        step = 360.0 / len(chain)
        state.order = chain
        state.centres = {c: -180.0 + step * (i + 0.5) for i, c in enumerate(chain)}
        return
    for c in new:
        k = len(state.order)
        if k == 0:
            state.order, state.centres[c] = [c], 0.0
            continue
        if k == 1:
            other = state.order[0]
            state.centres[c] = wrap(state.centres[other] + 180.0)
            state.order.append(c)
            continue
        best_i = max(
            range(k), key=lambda i: (w(c, state.order[i]) + w(c, state.order[(i + 1) % k]), -i)
        )
        a, b = state.order[best_i], state.order[(best_i + 1) % k]
        gap = wrap(state.centres[b] - state.centres[a])
        gap = gap if gap > 0 else gap + 360.0
        state.centres[c] = wrap(state.centres[a] + gap / 2.0)
        state.order.insert(best_i + 1, c)


def _half_widths(state: LayoutState, groups: dict[str, list[str]]) -> dict[str, float]:
    total = sum(len(m) for m in groups.values()) or 1
    k = len(state.order)
    out = {}
    for i, c in enumerate(state.order):
        want = 180.0 * len(groups[c]) / total
        if k > 1:
            prev_gap = abs(wrap(state.centres[c] - state.centres[state.order[i - 1]]))
            next_gap = abs(wrap(state.centres[state.order[(i + 1) % k]] - state.centres[c]))
            want = min(want, 0.45 * min(prev_gap, next_gap))
        out[c] = max(want, MIN_HALF_WIDTH)
    return out


def layout_angles(
    prev: LayoutState | None,
    groups: dict[str, list[str]],  # persistent coarse community id -> eligible member concept ids
    adj: dict[tuple[str, str], float],  # eligible-eligible edge weights
    cfg: OrgConfig,
) -> tuple[dict[str, float], LayoutState]:
    """Returns concept angles (degrees) and the state to carry to the next chapter."""
    cap = cfg.layout.max_angle_shift_deg
    state = LayoutState(
        dict(prev.centres) if prev else {}, list(prev.order) if prev else [], {}, {}
    )
    _place_communities(state, groups, _weights_between(groups, adj))
    half = _half_widths(state, groups)
    where = {c: g for g, ms in groups.items() for c in ms}
    nbrs: dict[str, list[tuple[str, float]]] = {}
    for (a, b), w in adj.items():
        nbrs.setdefault(a, []).append((b, w))
        nbrs.setdefault(b, []).append((a, w))

    def sector_clamp(cid: str, ang: float) -> float:
        g = where[cid]
        d = wrap(ang - state.centres[g])
        return wrap(state.centres[g] + max(-half[g], min(half[g], d)))

    prev_ang = prev.angles if prev else {}
    prev_comm = prev.comm_of if prev else {}
    start: dict[str, float] = {}
    stay = {c for c in where if c in prev_ang and prev_comm.get(c) == where[c]}
    for c in stay:
        start[c] = prev_ang[c]
    todo = sorted((c for c in where if c not in stay), key=lambda c: (-len(nbrs.get(c, [])), c))
    for c in todo:  # new or moved: strongest already-placed neighbour, else a stable sector offset
        placed = [(n, w) for n, w in nbrs.get(c, []) if n in start]
        if placed:
            n, _ = max(placed, key=lambda t: (t[1], t[0]))
            start[c] = start[n]
        else:
            g = where[c]
            start[c] = wrap(state.centres[g] + (hash_unit(c) - 0.5) * 1.2 * half[g])
        start[c] = sector_clamp(c, start[c])

    angles: dict[str, float] = {}
    for c in sorted(where):  # light relaxation towards same-community neighbours, capped
        same = [
            (start[n], w) for n, w in nbrs.get(c, []) if n in start and where.get(n) == where[c]
        ]
        target = circ_mean([a for a, _ in same], [w for _, w in same])
        a0 = start[c]
        a1 = a0 if target is None else wrap(a0 + 0.3 * wrap(target - a0))
        if c in stay:
            a1 = sector_clamp(c, a1)
            a1 = wrap(prev_ang[c] + max(-cap, min(cap, wrap(a1 - prev_ang[c]))))
        else:
            a1 = sector_clamp(c, a1)
        angles[c] = a1
    state.angles = dict(angles)
    state.comm_of = dict(where)
    return angles, state


def to_xy(radius: float, angle_deg: float) -> tuple[float, float]:
    t = math.radians(angle_deg)
    return radius * math.cos(t), radius * math.sin(t)
