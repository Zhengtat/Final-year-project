import numpy as np

from cumap.organisation.config import load_config
from cumap.organisation.rings import assign_rings, band_counts, radii, ring_rank

CFG = load_config()


def test_band_shares_match_config_and_sum_to_n():
    assert band_counts(100, CFG.rings.shares) == {
        "centre": 5,
        "inner": 15,
        "middle": 30,
        "outer": 50,
    }
    for n in (1, 7, 33, 251):
        c = band_counts(n, CFG.rings.shares)
        assert sum(c.values()) == n and c["centre"] >= 1


def test_unlinked_and_background_are_excluded_from_quantiles():
    n = 120
    basis = np.linspace(1, 0, n)
    linked = np.ones(n, dtype=bool)
    linked[100:] = False  # 20 unlinked
    background = np.zeros(n, dtype=bool)
    background[:0] = True
    background[95:100] = True  # 5 background (linked but generic)
    eligible = linked & ~background
    rings = assign_rings(
        basis, eligible, linked, background, np.zeros(n), [f"n{i}" for i in range(n)], CFG
    )
    assert rings.count("unlinked") == 20 and rings.count("background") == 5
    assert [rings.count(r) for r in ("centre", "inner", "middle", "outer")] == [
        5,
        14,
        29,
        47,
    ]  # 95 eligible nodes: shares of 95, not of 120
    assert rings[0] == "centre" and rings[94] == "outer"
    r = radii(basis, eligible, rings, CFG)
    assert (
        r[0] < r[50] < r[94] < r[100] < r[97]
    )  # centre..outer, then unlinked, then background band


def test_kshell_method_orders_by_coreness_first():
    raw = CFG.model_dump()
    raw["rings"]["method"] = "kshell"
    from cumap.organisation.config import OrgConfig

    cfg = OrgConfig(**raw)
    basis = np.array([0.9, 0.1, 0.5, 0.4])
    core = np.array([1, 3, 2, 2])
    elig = np.ones(4, dtype=bool)
    rings = assign_rings(basis, elig, elig, ~elig, core, list("abcd"), cfg)
    assert rings[1] == "centre"  # highest k-shell wins despite the lowest basis
    assert (
        ring_rank("centre") < ring_rank("outer") < ring_rank("unlinked") < ring_rank("background")
    )
