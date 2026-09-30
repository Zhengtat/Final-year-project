"""CR-006 §7: is there really a core? Run before trusting the sphere.

Fit = Borgatti-Everett discrete correlation between the observed unweighted adjacency and the
ideal pattern (core-core 1, periphery-periphery 0, core-periphery pairs ignored); core = the
centre + inner rings. Two null models (200 samples each) recompute the core by the SAME
importance procedure on every sample, holding `spread` (and exposure) fixed since they are
not structural:
  1. primary   - same-density random graphs G(n, m): "is there a core at all?" (gates the label)
  2. secondary - degree-preserving rewires: "is the core more than a few hubs?" (reported only;
                 Kojaku & Masuda 2018 show a single core is largely explained by degrees).
Labels are gated on the primary null with BOTH z and an effect size (null SDs are tiny).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import networkx as nx
import numpy as np

from cumap.organisation.config import OrgConfig
from cumap.organisation.importance import (
    GraphSpec,
    combine,
    coreness,
    exposure_adjust,
    leiden_membership,
    pagerank,
    participation,
)
from cumap.organisation.rings import assign_rings

LABEL_PRESENT = "core-periphery structure present"
LABEL_WEAK = "weak core"
LABEL_NONE = "no clear core"
BANNER_NONE = "No clear core at this chapter: ring positions are weakly supported."
BANNER_WEAK = "Weak core at this chapter: the centre is only modestly better connected than chance."


def be_fit(spec: GraphSpec, core: np.ndarray) -> float:
    """Pearson correlation of observed adjacency with the ideal core-periphery pattern over
    core-core and periphery-periphery pairs (core-periphery pairs ignored)."""
    n = spec.n
    adj = np.zeros((n, n), dtype=bool)
    for a, b in zip(spec.u, spec.v, strict=True):
        if a != b:
            adj[a, b] = adj[b, a] = True
    i, j = np.triu_indices(n, k=1)
    same = core[i] == core[j]
    obs = adj[i, j][same].astype(float)
    ideal = (core[i] & core[j])[same].astype(float)
    if obs.std() == 0 or ideal.std() == 0:
        return 0.0
    return float(np.corrcoef(obs, ideal)[0, 1])


def _core_by_importance(
    spec: GraphSpec, spread: np.ndarray, exposure: np.ndarray, cfg: OrgConfig
) -> np.ndarray:
    comp = cfg.importance.components
    deg = np.zeros(spec.n)
    for a, b in zip(spec.u, spec.v, strict=True):
        deg[a] += 1
        deg[b] += 1
    eligible = deg > 0
    pr = pagerank(spec, comp["pagerank"].damping or 0.85)
    cs = coreness(spec).astype(float)
    br = participation(
        spec, leiden_membership(spec, cfg.communities.resolution.fine, cfg.communities.seed)
    )
    weights = {k: c.weight for k, c in comp.items()}
    raw, _ = combine(
        {"pagerank": pr, "coreness": cs, "spread": spread, "bridging": br}, weights, eligible
    )
    basis = raw
    if cfg.importance.radius_basis == "adjusted" and cfg.importance.exposure_correction.enabled:
        basis = exposure_adjust(raw, exposure, eligible)
    rings = assign_rings(
        basis,
        eligible,
        eligible,
        np.zeros(spec.n, dtype=bool),
        cs,
        [str(i) for i in range(spec.n)],
        cfg,
    )
    return np.array([r in cfg.rings.core_for_fit for r in rings])


def _random_spec(spec: GraphSpec, rng: np.random.Generator, kind: str, seed: int) -> GraphSpec:
    n, m = spec.n, len(spec.u)
    if kind == "same_density_random":
        allpairs = n * (n - 1) // 2
        picks = rng.choice(allpairs, size=min(m, allpairs), replace=False)
        iu, ju = np.triu_indices(n, k=1)
        edges = list(zip(iu[picks].tolist(), ju[picks].tolist(), strict=True))
    else:
        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(zip(spec.u, spec.v, strict=True))
        nx.double_edge_swap(
            g, nswap=10 * g.number_of_edges(), max_tries=200 * g.number_of_edges(), seed=seed
        )
        edges = list(g.edges())
    order = rng.permutation(len(spec.u))[: len(edges)]
    flips = rng.random(len(edges)) < 0.5
    u = [b if f else a for (a, b), f in zip(edges, flips, strict=True)]
    v = [a if f else b for (a, b), f in zip(edges, flips, strict=True)]
    return GraphSpec(n, u, v, [spec.w[k] for k in order], [spec.mode[k] for k in order])


@dataclass
class NullResult:
    mean: float
    sd: float
    z: float
    delta_rho: float
    n: int


@dataclass
class CPResult:
    rho_obs: float
    primary: NullResult
    secondary: NullResult
    label: str
    banner: str | None
    n_nodes: int
    n_edges: int

    def to_dict(self) -> dict:
        return asdict(self)


def _null(spec, spread, exposure, cfg, kind, rho_obs, seed) -> NullResult:
    rng = np.random.default_rng(seed)
    rhos = []
    for s in range(cfg.null_model.iterations):
        ns = _random_spec(spec, rng, kind, seed + s)
        core = _core_by_importance(ns, spread, exposure, cfg)
        rhos.append(be_fit(ns, core))
    arr = np.array(rhos)
    mean, sd = float(arr.mean()), float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    z = (rho_obs - mean) / sd if sd > 0 else (float("inf") if rho_obs > mean else 0.0)
    return NullResult(mean, sd, float(z), float(rho_obs - mean), len(arr))


def label_for(primary: NullResult, cfg: OrgConfig) -> tuple[str, str | None]:
    t = cfg.null_model.present_if
    if primary.z >= t.z_at_least and primary.delta_rho >= t.delta_rho_at_least:
        return LABEL_PRESENT, None
    if primary.z >= t.z_at_least:
        return LABEL_WEAK, BANNER_WEAK
    return LABEL_NONE, BANNER_NONE


def assess(
    spec: GraphSpec,
    spread: np.ndarray,
    exposure: np.ndarray,
    cfg: OrgConfig,
    *,
    core_mask: np.ndarray | None = None,
) -> CPResult:
    """`spec` must cover exactly the nodes in the fit (linked, non-background). `core_mask`
    is the observed core (centre + inner); if omitted it is derived by the same procedure."""
    if core_mask is None:
        core_mask = _core_by_importance(spec, spread, exposure, cfg)
    rho = be_fit(spec, core_mask)
    seed = cfg.null_model.seed
    primary = _null(spec, spread, exposure, cfg, "same_density_random", rho, seed)
    secondary = _null(spec, spread, exposure, cfg, "degree_preserving_rewire", rho, seed + 10_000)
    label, banner = label_for(primary, cfg)
    return CPResult(rho, primary, secondary, label, banner, spec.n, len(spec.u))
