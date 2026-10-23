"""CR-006 §5: rings (centre / inner / middle / outer) as quantile bands of the chosen
importance basis over linked, non-background nodes; `unlinked` and `background` are extra
bands outside the disc. Rings are a structural view, NOT CR-004 tiers."""

from __future__ import annotations

import numpy as np

from cumap.organisation.config import RING_ORDER, OrgConfig
from cumap.organisation.importance import percentile

BAND_OFFSET = {"unlinked": 0.10, "background": 0.20}  # radius beyond r_max


def band_counts(n: int, shares: dict[str, float]) -> dict[str, int]:
    """Cumulative rounding so the counts sum to n; the centre gets at least one node."""
    counts, prev = {}, 0
    cum = 0.0
    for name in RING_ORDER:
        cum += shares[name]
        upto = n if name == RING_ORDER[-1] else round(cum * n)
        if name == "centre" and n >= 1:
            upto = max(upto, 1)
        counts[name] = max(upto - prev, 0)
        prev += counts[name]
    return counts


def assign_rings(
    basis: np.ndarray,
    eligible: np.ndarray,
    linked: np.ndarray,
    background: np.ndarray,
    coreness: np.ndarray,
    names: list[str],
    cfg: OrgConfig,
) -> list[str]:
    n = len(basis)
    rings = ["unlinked"] * n
    for i in range(n):
        if background[i]:
            rings[i] = "background"
        elif not linked[i]:
            rings[i] = "unlinked"
    idx = [i for i in range(n) if eligible[i]]
    if cfg.rings.method == "kshell":
        idx.sort(key=lambda i: (-coreness[i], -basis[i], names[i]))
    else:
        idx.sort(key=lambda i: (-basis[i], names[i]))
    counts = band_counts(len(idx), cfg.rings.shares)
    pos = 0
    for name in RING_ORDER:
        for i in idx[pos : pos + counts[name]]:
            rings[i] = name
        pos += counts[name]
    return rings


def radii(basis: np.ndarray, eligible: np.ndarray, rings: list[str], cfg: OrgConfig) -> np.ndarray:
    """r = r_min + (1 - importance) * (r_max - r_min), with `importance` the percentile rank of
    the chosen basis among eligible nodes (so both bases spread evenly over the disc)."""
    lay = cfg.layout
    pct = percentile(basis, eligible)
    r = np.zeros(len(basis))
    for i, ring in enumerate(rings):
        if ring in BAND_OFFSET:
            r[i] = lay.r_max + BAND_OFFSET[ring]
        else:
            r[i] = lay.r_min + (1.0 - pct[i]) * (lay.r_max - lay.r_min)
    return r


def ring_rank(ring: str) -> int:
    order = [*RING_ORDER, "unlinked", "background"]
    return order.index(ring)
