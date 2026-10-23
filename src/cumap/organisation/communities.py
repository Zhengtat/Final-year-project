"""CR-006 §6: Leiden communities per snapshot with persistent IDs and lifecycle events.

Matching across consecutive snapshots is by Jaccard overlap of members, matched if >= 0.3
(Greene et al. 2010). Events follow Palla et al. 2007: continue / grow / shrink / merge /
split / birth / death; a continuing community counts as *changed* when Jaccard < 0.7.
Labels are the top-3 concepts by importance (no LLM). Fixed seeds throughout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cumap.organisation.config import CommunitiesCfg

SIZE_CHANGE = 0.20  # relative size change that turns 'continue' into grow / shrink
SHARE = 0.5  # merge / split: this share of the smaller side must overlap the other


@dataclass
class CommEvent:
    type: str  # community_continue | _grow | _shrink | _merge | _split | _birth | _death
    subject_ids: list[str]
    from_state: str | None = None
    to_state: str | None = None
    changed: bool = False


@dataclass
class TrackResult:
    state: dict[str, frozenset[str]]  # persistent id -> members
    events: list[CommEvent] = field(default_factory=list)
    jaccard: dict[str, float] = field(default_factory=dict)  # matched ids only
    changed: set[str] = field(default_factory=set)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def groups_from_membership(
    ids: list[str], membership: list[int], keep: set[str]
) -> list[frozenset[str]]:
    by: dict[int, set[str]] = {}
    for c, m in zip(ids, membership, strict=True):
        if c in keep:
            by.setdefault(m, set()).add(c)
    return [frozenset(g) for g in by.values()]


def track_communities(
    prev: dict[str, frozenset[str]] | None,
    groups: list[frozenset[str]],
    counter: list[int],
    prefix: str,
    cfg: CommunitiesCfg,
) -> TrackResult:
    """`counter` is a one-element list holding the next unused numeric id (mutated)."""
    groups = sorted(groups, key=lambda g: (-len(g), min(g)))
    res = TrackResult(state={})

    def new_id() -> str:
        counter[0] += 1
        return f"{prefix}{counter[0]}"

    if not prev:
        for g in groups:
            cid = new_id()
            res.state[cid] = g
            res.events.append(CommEvent("community_birth", [cid], None, f"size {len(g)}"))
        return res

    pairs = sorted(
        ((jaccard(p, g), pid, gi) for pid, p in prev.items() for gi, g in enumerate(groups)),
        key=lambda t: (-t[0], t[1], t[2]),
    )
    matched_prev: dict[str, int] = {}
    matched_cur: dict[int, str] = {}
    for j, pid, gi in pairs:
        if j < cfg.match_jaccard:
            break
        if pid in matched_prev or gi in matched_cur:
            continue
        matched_prev[pid] = gi
        matched_cur[gi] = pid

    cid_of: dict[int, str] = {}
    for gi, g in enumerate(groups):
        cid_of[gi] = matched_cur.get(gi) or new_id()
        res.state[cid_of[gi]] = g

    # predecessors of each current community / successors of each previous one
    preds = {
        gi: [pid for pid, p in prev.items() if len(p & g) / len(p) >= SHARE]
        for gi, g in enumerate(groups)
    }
    succs = {
        pid: [gi for gi, g in enumerate(groups) if len(p & g) / len(g) >= SHARE]
        for pid, p in prev.items()
    }
    merged_prev = {p for gi in preds for p in preds[gi] if len(preds[gi]) >= 2}
    split_prev = {pid for pid, s in succs.items() if len(s) >= 2}

    for gi, g in enumerate(groups):
        cid = cid_of[gi]
        if gi in matched_cur:
            pid = matched_cur[gi]
            p = prev[pid]
            j = jaccard(p, g)
            res.jaccard[cid] = j
            changed = j < cfg.changed_below_jaccard
            if changed:
                res.changed.add(cid)
            rel = (len(g) - len(p)) / len(p)
            kind = (
                "community_grow"
                if rel >= SIZE_CHANGE
                else ("community_shrink" if rel <= -SIZE_CHANGE else "community_continue")
            )
            res.events.append(
                CommEvent(kind, [cid], f"size {len(p)}", f"size {len(g)}; jaccard {j:.2f}", changed)
            )
        if len(preds[gi]) >= 2:
            res.events.append(
                CommEvent(
                    "community_merge",
                    [cid, *preds[gi]],
                    f"{len(preds[gi])} communities",
                    f"size {len(g)}",
                    True,
                )
            )
            res.changed.add(cid)
        elif gi not in matched_cur and not preds[gi] and not any(gi in s for s in succs.values()):
            res.events.append(CommEvent("community_birth", [cid], None, f"size {len(g)}"))
    for pid, s in succs.items():
        if pid in split_prev:
            res.events.append(
                CommEvent(
                    "community_split",
                    [pid, *(cid_of[gi] for gi in s)],
                    f"size {len(prev[pid])}",
                    f"{len(s)} communities",
                    True,
                )
            )
            for gi in s:
                res.changed.add(cid_of[gi])
        elif pid not in matched_prev and pid not in merged_prev and not s:
            res.events.append(CommEvent("community_death", [pid], f"size {len(prev[pid])}", None))
    return res


def modularity(spec, membership: list[int]) -> float:
    from cumap.organisation.importance import undirected_simple

    g = undirected_simple(spec)
    return float(g.modularity(membership, weights="weight")) if spec.u else 0.0
