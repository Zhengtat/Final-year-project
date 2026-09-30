"""CR-006 §3-§4: the per-snapshot graph, the four importance components, percentile
combination, exposure correction and the background-vocabulary guard.

Everything here is pure (arrays in, arrays out) so the null models in coreperiphery.py can
re-run the same procedure on random graphs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import igraph as ig
import leidenalg
import numpy as np
from scipy.stats import rankdata

from cumap.organisation.config import OrgConfig
from cumap.organisation.inputs import OrgInputs


@dataclass
class GraphSpec:
    """Typed edges over node indices 0..n-1. `mode` is where importance flows:
    'target' (to v), 'source' (to u), or 'both'."""

    n: int
    u: list[int]
    v: list[int]
    w: list[float]
    mode: list[str]


@dataclass
class SnapGraph:
    chapter: int
    ids: list[str]
    index: dict[str, int]
    spec: GraphSpec
    edge_ids: list[str]
    edge_sections: list[str]
    n_edges_per_node: np.ndarray
    n_sections: int
    appear_sections: np.ndarray  # sections (any role) each concept appears in, within G_N
    spread: np.ndarray  # share of G_N sections where defined or used
    ever_defined: np.ndarray
    exposure: np.ndarray  # G_N sections at or after the concept's first mention
    first_chapter: np.ndarray


def relation_mode(relation: str, cfg: OrgConfig) -> str:
    d = cfg.importance.pagerank_direction
    if relation in d.toward_target:
        return "target"
    if relation in d.toward_source:
        return "source"
    return "both"


def build_snap_graph(inp: OrgInputs, chapter: int, cfg: OrgConfig) -> SnapGraph:
    ids = sorted(c for c, k in inp.concepts.items() if k.first_chapter <= chapter)
    index = {c: i for i, c in enumerate(ids)}
    edges = [
        e for e in inp.edges if e.chapter <= chapter and e.source in index and e.target in index
    ]
    spec = GraphSpec(
        len(ids),
        [index[e.source] for e in edges],
        [index[e.target] for e in edges],
        [e.weight for e in edges],
        [relation_mode(e.relation, cfg) for e in edges],
    )
    deg = np.zeros(len(ids))
    for a, b in zip(spec.u, spec.v, strict=True):
        deg[a] += 1
        deg[b] += 1

    secs = {s for s, ch in inp.section_chapter.items() if ch <= chapter}
    spread_roles = set(cfg.importance.components["spread"].roles or ["defined", "used"])
    n = len(ids)
    appear, spread, defined, expo = np.zeros(n), np.zeros(n), np.zeros(n, dtype=bool), np.zeros(n)
    first_ch = np.zeros(n, dtype=int)
    for c, i in index.items():
        ms = [(s, r) for s, r in inp.mentions.get(c, []) if s in secs]
        appear[i] = len({s for s, _ in ms})
        spread[i] = len({s for s, r in ms if r in spread_roles}) / max(len(secs), 1)
        defined[i] = any(r == "defined" for _, r in ms)
        first_order = min((inp.section_order[s] for s, _ in ms), default=None)
        expo[i] = (
            sum(1 for s in secs if inp.section_order[s] >= first_order)
            if first_order is not None
            else 0
        )
        first_ch[i] = inp.concepts[c].first_chapter
    return SnapGraph(
        chapter,
        ids,
        index,
        spec,
        [e.edge_id for e in edges],
        [e.section_id for e in edges],
        deg,
        len(secs),
        appear,
        spread,
        defined,
        expo,
        first_ch,
    )


# ---------------------------------------------------------------- structural components
def _directed_edges(spec: GraphSpec) -> tuple[list[tuple[int, int]], list[float]]:
    pairs, ws = [], []
    for a, b, w, m in zip(spec.u, spec.v, spec.w, spec.mode, strict=True):
        if m in ("target", "both"):
            pairs.append((a, b))
            ws.append(w)
        if m in ("source", "both"):
            pairs.append((b, a))
            ws.append(w)
    return pairs, ws


def pagerank(spec: GraphSpec, damping: float) -> np.ndarray:
    pairs, ws = _directed_edges(spec)
    g = ig.Graph(n=spec.n, edges=pairs, directed=True)
    if not pairs:
        return np.full(spec.n, 1.0 / max(spec.n, 1))
    return np.array(g.pagerank(directed=True, damping=damping, weights=ws))


def undirected_simple(spec: GraphSpec) -> ig.Graph:
    g = ig.Graph(n=spec.n, edges=list(zip(spec.u, spec.v, strict=True)))
    g.es["weight"] = spec.w
    return g


def coreness(spec: GraphSpec) -> np.ndarray:
    g = undirected_simple(spec)
    g.simplify(multiple=True, loops=True, combine_edges="max")
    return np.array(g.coreness())


def leiden_membership(spec: GraphSpec, resolution: float, seed: int) -> list[int]:
    g = undirected_simple(spec)
    part = leidenalg.find_partition(
        g,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight",
        resolution_parameter=resolution,
        seed=seed,
    )
    return list(part.membership)


def participation(spec: GraphSpec, membership: list[int]) -> np.ndarray:
    """Guimera & Amaral (2005) participation coefficient, weighted."""
    k = np.zeros(spec.n)
    per: list[dict[int, float]] = [{} for _ in range(spec.n)]
    for a, b, w in zip(spec.u, spec.v, spec.w, strict=True):
        if a == b:
            continue
        for x, y in ((a, b), (b, a)):
            k[x] += w
            per[x][membership[y]] = per[x].get(membership[y], 0.0) + w
    out = np.zeros(spec.n)
    for i in range(spec.n):
        if k[i] > 0:
            out[i] = 1.0 - sum((kc / k[i]) ** 2 for kc in per[i].values())
    return out


# ---------------------------------------------------------------- combination
def percentile(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank (0..1, ties averaged) within the masked nodes; 0 outside the mask."""
    out = np.zeros(len(values))
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return out
    if len(idx) == 1:
        out[idx[0]] = 0.5
        return out
    out[idx] = (rankdata(values[idx], method="average") - 1) / (len(idx) - 1)
    return out


def combine(
    comps: dict[str, np.ndarray], weights: dict[str, float], eligible: np.ndarray
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    pcts = {k: percentile(v, eligible) for k, v in comps.items()}
    raw = sum(weights[k] * pcts[k] for k in weights)
    return np.where(eligible, raw, 0.0), pcts


def exposure_adjust(raw: np.ndarray, exposure: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    """Percentile rank of the residual of raw ~ log1p(exposure). Removes only the *average*
    age effect: an old concept more central than its age predicts stays high."""
    idx = np.flatnonzero(eligible)
    if len(idx) < 3:
        return percentile(raw, eligible)
    x = np.log1p(exposure[idx])
    if np.ptp(x) == 0:
        return percentile(raw, eligible)
    slope, intercept = np.polyfit(x, raw[idx], 1)
    resid = np.zeros(len(raw))
    resid[idx] = raw[idx] - (slope * x + intercept)
    return percentile(resid, eligible)


def generic_flags(sg: SnapGraph, cfg: OrgConfig) -> np.ndarray:
    """Background vocabulary ("data", "network"): appears in >= min_section_share of the
    sections, never `defined`, and typed edges per appearance in the bottom quartile."""
    g = cfg.generic_guard
    n = sg.spec.n
    flags = np.zeros(n, dtype=bool)
    if not g.enabled or sg.n_sections == 0:
        return flags
    share = sg.appear_sections / sg.n_sections
    per_app = np.divide(sg.n_edges_per_node, np.maximum(sg.appear_sections, 1))
    present = sg.appear_sections > 0
    cut = (
        np.quantile(per_app[present], g.max_edges_per_appearance_quantile) if present.any() else 0.0
    )
    for i in range(n):
        ok = share[i] >= g.min_section_share and per_app[i] <= cut
        if g.require_never_defined:
            ok = ok and not sg.ever_defined[i]
        flags[i] = ok
    keep = {sg.index[c] for c in g.overrides_keep if c in sg.index}
    generic = {sg.index[c] for c in g.overrides_generic if c in sg.index}
    for i in keep:
        flags[i] = False
    for i in generic:
        flags[i] = True
    return flags


@dataclass
class Importance:
    eligible: np.ndarray
    background: np.ndarray
    pagerank: np.ndarray
    coreness: np.ndarray
    bridging: np.ndarray
    fine_membership: list[int]
    coarse_membership: list[int]
    pcts: dict[str, np.ndarray]
    raw: np.ndarray
    adj: np.ndarray


def compute_importance(
    sg: SnapGraph, cfg: OrgConfig, *, background: np.ndarray | None = None
) -> Importance:
    comp = cfg.importance.components
    bg = generic_flags(sg, cfg) if background is None else background
    linked = sg.n_edges_per_node > 0
    eligible = linked & ~bg
    fine = leiden_membership(sg.spec, cfg.communities.resolution.fine, cfg.communities.seed)
    coarse = leiden_membership(sg.spec, cfg.communities.resolution.coarse, cfg.communities.seed)
    lvl = comp["bridging"].community_level or "fine"
    pr = pagerank(sg.spec, comp["pagerank"].damping or 0.85)
    cs = coreness(sg.spec)
    br = participation(sg.spec, fine if lvl == "fine" else coarse)
    weights = {k: c.weight for k, c in comp.items()}
    raw, pcts = combine(
        {"pagerank": pr, "coreness": cs.astype(float), "spread": sg.spread, "bridging": br},
        weights,
        eligible,
    )
    adj = (
        exposure_adjust(raw, sg.exposure, eligible)
        if cfg.importance.exposure_correction.enabled
        else percentile(raw, eligible)
    )
    return Importance(eligible, bg, pr, cs, br, fine, coarse, pcts, raw, adj)


def log_ok(x: float) -> bool:
    return math.isfinite(x)
