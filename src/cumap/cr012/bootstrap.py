"""CR-012 grouping-aware bootstrap (CR section 14, D1). The unit of resampling is the document (SciNLP) or the section (P&D-E2E),
never an individual entity or edge. Paired comparisons resample the SAME units. Deterministic for a fixed seed. With fewer than
`MIN_UNITS_FOR_CI` units the interval is not an inferential result: SciNLP's 3-document test split reports
CI_status = NOT_EVALUABLE_SMALL_N and any bootstrap there is DESCRIPTIVE_SMALL_N_ONLY, never the headline."""

from __future__ import annotations

import math

import numpy as np

from cumap.cr012.types import PRF

MIN_UNITS_FOR_CI = 10
SEED = 20261011
RESAMPLES = 10_000


def _prf_arrays(units: dict[str, PRF]) -> tuple[list[str], np.ndarray]:
    keys = sorted(units)
    return keys, np.array([[units[k].tp, units[k].fp, units[k].fn] for k in keys], dtype=float)


def _metrics(tp, fp, fn):
    p = np.divide(tp, tp + fp, out=np.zeros_like(tp, dtype=float), where=(tp + fp) > 0)
    r = np.divide(tp, tp + fn, out=np.zeros_like(tp, dtype=float), where=(tp + fn) > 0)
    f = np.divide(2 * p * r, p + r, out=np.zeros_like(p), where=(p + r) > 0)
    return p, r, f


def ci_status(n_units: int) -> str:
    return "NOT_EVALUABLE_SMALL_N" if n_units < MIN_UNITS_FOR_CI else "OK"


def cluster_bootstrap(
    units: dict[str, PRF],
    *,
    level: float = 0.95,
    b: int = RESAMPLES,
    seed: int = SEED,
    descriptive_label: str | None = None,
) -> dict:
    """Percentile interval of micro P / R / F1, resampling whole units with replacement."""
    keys, a = _prf_arrays(units)
    n = len(keys)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(b, n))
    tp, fp, fn = (a[idx, j].sum(axis=1) for j in range(3))
    p, r, f = _metrics(tp, fp, fn)
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    pt = _metrics(
        a[:, 0].sum(keepdims=True), a[:, 1].sum(keepdims=True), a[:, 2].sum(keepdims=True)
    )
    status = ci_status(n)
    return {
        "units": n,
        "unit_ids": keys,
        "resampled_unit": "document or section (never edges)",
        "point": {"precision": float(pt[0][0]), "recall": float(pt[1][0]), "f1": float(pt[2][0])},
        "ci": {m: [float(np.percentile(x, lo)), float(np.percentile(x, hi))] for m, x in (("precision", p), ("recall", r), ("f1", f))},
        "level": level,
        "resamples": b,
        "seed": seed,
        "CI_status": status,
        "label": descriptive_label or ("DESCRIPTIVE_SMALL_N_ONLY" if status != "OK" else "inferential"),
        "distinct_resamples_possible": math.comb(2 * n - 1, n),
    }  # fmt: skip


def paired_bootstrap_delta(
    a: dict[str, PRF],
    b_units: dict[str, PRF],
    *,
    level: float = 0.95,
    b: int = RESAMPLES,
    seed: int = SEED,
) -> dict:
    """Paired comparison on the same units: delta of micro-F1 (second minus first)."""
    assert sorted(a) == sorted(b_units), "paired bootstrap needs the same units on both sides"
    keys, x = _prf_arrays(a)
    _k, y = _prf_arrays(b_units)
    n = len(keys)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(b, n))
    fa = _metrics(*(x[idx, j].sum(axis=1) for j in range(3)))[2]
    fb = _metrics(*(y[idx, j].sum(axis=1) for j in range(3)))[2]
    d = fb - fa
    point = (
        _metrics(*(y[:, j].sum(keepdims=True) for j in range(3)))[2][0]
        - _metrics(*(x[:, j].sum(keepdims=True) for j in range(3)))[2][0]
    )
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    return {
        "units": n,
        "delta_f1": float(point),
        "ci": [float(np.percentile(d, lo)), float(np.percentile(d, hi))],
        "CI_status": ci_status(n),
        "seed": seed,
    }
