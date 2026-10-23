"""Small, reusable statistics helpers for human-labelled spot-checks. Wilson score
interval: the standard way to report precision/accuracy on a small human-judged
sample (CR-005 §3.2's edge spot-check, and this module's first user, the
canonicalisation merge-precision check) -- more reliable than a normal-approximation
CI at small n, and never gives a bound outside [0, 1].
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class WilsonInterval:
    point_estimate: float
    low: float
    high: float
    n: int
    successes: int


def wilson_ci(successes: int, n: int, *, confidence: float = 0.95) -> WilsonInterval:
    """Wilson score interval for a binomial proportion. `confidence=0.95` (the
    default, and CR-005's own convention) uses z=1.959963984540054.
    """
    if n == 0:
        return WilsonInterval(point_estimate=0.0, low=0.0, high=0.0, n=0, successes=0)
    if not 0 <= successes <= n:
        raise ValueError(f"successes ({successes}) must be between 0 and n ({n})")

    z = _z_for_confidence(confidence)
    p_hat = successes / n
    denom = 1 + z**2 / n
    centre = p_hat + z**2 / (2 * n)
    margin = z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
    low = (centre - margin) / denom
    high = (centre + margin) / denom
    return WilsonInterval(
        point_estimate=p_hat, low=max(0.0, low), high=min(1.0, high), n=n, successes=successes
    )


def _z_for_confidence(confidence: float) -> float:
    # Only the two levels this project actually uses are supported explicitly, to
    # avoid silently mis-computing an interval for an unsupported confidence level.
    known = {0.95: 1.959963984540054, 0.99: 2.5758293035489004}
    if confidence not in known:
        raise ValueError(
            f"unsupported confidence level {confidence!r}; add it to _z_for_confidence"
        )
    return known[confidence]


# ---------------------------------------------------------------- CR-010: paired section bootstrap
def micro_f1(counts: list[tuple[int, int, int]]) -> float:
    """Micro F1 from per-section (tp, fp, fn) counts."""
    tp, fp, fn = (sum(c[i] for c in counts) for i in range(3))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0


def paired_bootstrap_delta(
    a: dict[str, tuple[int, int, int]],
    b: dict[str, tuple[int, int, int]],
    *,
    n: int = 10000,
    seed: int = 0,
) -> dict[str, float]:
    """Paired section-level bootstrap of the micro-F1 difference (b - a). `a` and `b` map section id -> (tp, fp, fn)
    over the SAME sections; sections are resampled with replacement, jointly for both systems. `lo95` is the 2.5th
    percentile (the CR-010 'lower bound'); `lo90` is the 5th, reported for orientation."""
    import numpy as np

    ids = sorted(a)
    if ids != sorted(b):
        raise ValueError("both systems must be scored on the same sections")
    A = np.array([a[i] for i in ids], dtype=float)
    B = np.array([b[i] for i in ids], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(n, len(ids)))

    def f1(M: np.ndarray) -> np.ndarray:
        s = M[idx].sum(axis=1)  # n x 3
        den = 2 * s[:, 0] + s[:, 1] + s[:, 2]
        return np.divide(2 * s[:, 0], den, out=np.zeros(n), where=den > 0)

    d = f1(B) - f1(A)
    return {
        "delta": micro_f1([tuple(r) for r in B.astype(int)])
        - micro_f1([tuple(r) for r in A.astype(int)]),
        "boot_mean": float(d.mean()),
        "lo95": float(np.percentile(d, 2.5)),
        "hi95": float(np.percentile(d, 97.5)),
        "lo90": float(np.percentile(d, 5)),
        "n": n,
        "sections": len(ids),
    }
