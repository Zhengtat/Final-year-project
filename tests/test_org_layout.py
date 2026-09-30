import math

from cumap.organisation.config import load_config
from cumap.organisation.layout import (
    band_angle,
    circ_mean,
    layout_angles,
    to_xy,
    wrap,
)

CFG = load_config()


def clique_edges(ids, w=1.0):
    return {(a, b): w for i, a in enumerate(ids) for b in ids[i + 1 :]}


def scene1():
    groups = {
        "k1": [f"a{i}" for i in range(8)],
        "k2": [f"b{i}" for i in range(6)],
        "k3": [f"c{i}" for i in range(4)],
    }
    adj = {}
    for ms in groups.values():
        adj.update(clique_edges(ms))
    adj[("a0", "b0")] = 0.5
    adj[("b1", "c0")] = 3.0
    return groups, adj


def test_wrap_and_circular_mean():
    assert wrap(190) == -170 and wrap(-190) == 170 and wrap(180) == 180
    assert abs(circ_mean([170, -170], [1, 1])) > 175  # mean across the +-180 seam, not 0
    assert circ_mean([], []) is None and to_xy(0.5, 90)[1] == 0.5


def test_layout_is_deterministic():
    g, adj = scene1()
    a1, s1 = layout_angles(None, g, adj, CFG)
    a2, s2 = layout_angles(None, g, adj, CFG)
    assert a1 == a2 and s1.centres == s2.centres and s1.order == s2.order


def test_existing_nodes_move_at_most_the_cap_and_sector_centres_are_fixed():
    g, adj = scene1()
    a1, s1 = layout_angles(None, g, adj, CFG)
    g2 = {k: list(v) for k, v in g.items()}
    g2["k1"] += ["a8", "a9"]
    g2["k4"] = ["d0", "d1", "d2"]  # a new community is born
    adj2 = dict(adj) | clique_edges(["d0", "d1", "d2"])
    adj2[("a8", "a1")] = 1.0
    adj2[("d0", "c1")] = 2.0
    adj2[("d1", "c2")] = 2.0
    a2, s2 = layout_angles(s1, g2, adj2, CFG)
    cap = CFG.layout.max_angle_shift_deg
    stayed = [c for c in a1 if c in a2]
    assert stayed and max(abs(wrap(a2[c] - a1[c])) for c in stayed) <= cap + 1e-9
    for k in ("k1", "k2", "k3"):
        assert s2.centres[k] == s1.centres[k]  # fixed once born
    assert "k4" in s2.centres


def test_new_community_is_inserted_between_the_neighbours_it_shares_most_weight_with():
    g, adj = scene1()
    _, s1 = layout_angles(None, g, adj, CFG)
    g2 = dict(g) | {"k4": ["d0", "d1"]}
    adj2 = dict(adj) | {("d0", "d1"): 1.0, ("d0", "b2"): 5.0, ("d1", "c3"): 5.0}
    _, s2 = layout_angles(s1, g2, adj2, CFG)
    i = s2.order.index("k4")
    assert {s2.order[i - 1], s2.order[(i + 1) % len(s2.order)]} == {"k2", "k3"}
    lo, hi = s1.centres["k2"], s1.centres["k3"]
    assert (
        abs(wrap(s2.centres["k4"] - circ_mean([lo, hi], [1, 1]))) < 1.0
    )  # midpoint of the two centres


def test_nodes_stay_inside_or_near_their_sector_and_bands_are_stable():
    g, adj = scene1()
    a1, s1 = layout_angles(None, g, adj, CFG)
    for k, ms in g.items():
        for c in ms:
            assert abs(wrap(a1[c] - s1.centres[k])) <= 180.0 * len(ms) / 18 + 30  # loose sanity
    assert band_angle("x") == band_angle("x") and 0 <= band_angle("x") < 360
    assert math.isclose(to_xy(1.0, 0)[0], 1.0)
