from cumap.organisation.config import load_config
from cumap.organisation.events import (
    NodeSnap,
    mean_displacement,
    node_events,
    stability,
    update_persistent_periphery,
)
from cumap.organisation.inputs import OrgEdge

CFG = load_config()


def snap(cid, ring, basis=0.5, first=2, edges=2, elig=True, nb=()):
    return NodeSnap(cid, cid, first, ring, basis, elig, edges, set(nb))


def edge(eid, s, t, sec="s9", w=1.0, ch=3):
    return OrgEdge(eid, s, t, "is_a", "classification_structure", sec, ch, w)


def _by_type(evs):
    out = {}
    for e in evs:
        out.setdefault(e.type, []).append(e)
    return out


def test_ring_in_carries_the_new_edge_and_section_ids_that_caused_it():
    prev = {"a": snap("a", "outer", 0.2), "b": snap("b", "middle", 0.5)}
    cur = {"a": snap("a", "inner", 0.9, nb=["b"]), "b": snap("b", "middle", 0.5)}
    new = [edge("E1", "a", "b", "3.4"), edge("E2", "b", "z", "3.5")]
    evs = _by_type(node_events("org_x", 3, prev, cur, new, set(), CFG))
    (ring_in,) = evs["ring_in"]
    assert ring_in.subject_ids == ["a"] and (ring_in.from_state, ring_in.to_state) == (
        "outer",
        "inner",
    )
    assert ring_in.because_edge_ids == ["E1"] and ring_in.because_section_ids == ["3.4"]
    assert ring_in.delta_importance == 0.7 and "ring_out" not in evs


def test_late_centraliser_fires_once_for_a_concept_introduced_earlier():
    prev = {"x": snap("x", "outer", first=2)}
    cur = {"x": snap("x", "centre", 0.99, first=2)}
    evs = _by_type(node_events("o", 3, prev, cur, [edge("E", "x", "y")], set(), CFG))
    assert [e.subject_ids for e in evs["late_centraliser"]] == [["x"]]
    assert "enter_centre" in evs
    again = _by_type(
        node_events("o", 3, prev, cur, [], {"x"}, CFG)
    )  # already central before: no repeat
    assert "late_centraliser" not in again
    born_central = _by_type(
        node_events("o", 3, prev, {"n": snap("n", "centre", first=3)}, [], set(), CFG)
    )
    assert "late_centraliser" not in born_central and "node_new" in born_central


def test_fading_and_first_snapshot_all_new():
    evs = _by_type(
        node_events("o", 3, {"f": snap("f", "inner")}, {"f": snap("f", "outer")}, [], set(), CFG)
    )
    assert "fading" in evs and "ring_out" in evs
    first = node_events(
        "o", 2, None, {"a": snap("a", "middle"), "b": snap("b", "outer")}, [], set(), CFG
    )
    assert {e.type for e in first} == {"node_new"}


def test_persistent_periphery_needs_consecutive_snapshots_with_at_most_one_edge():
    streaks: dict[str, int] = {}
    s2 = {
        "p": snap("p", "outer", edges=1),
        "q": snap("q", "outer", edges=3),
        "r": snap("r", "unlinked", edges=0),
    }
    assert update_persistent_periphery(streaks, s2, CFG) == set()
    s3 = {
        "p": snap("p", "outer", edges=1),
        "q": snap("q", "outer", edges=3),
        "r": snap("r", "middle", edges=2),
    }
    assert update_persistent_periphery(streaks, s3, CFG) == {"p"}  # q has > 1 edge; r recovered


def test_stability_metrics_and_displacement():
    prev = {
        c: snap(c, r, b)
        for c, r, b in [
            ("a", "centre", 1.0),
            ("b", "inner", 0.8),
            ("c", "outer", 0.1),
            ("d", "outer", 0.0),
        ]
    }
    cur = {
        c: snap(c, r, b)
        for c, r, b in [
            ("a", "centre", 1.0),
            ("b", "middle", 0.4),
            ("c", "inner", 0.9),
            ("d", "outer", 0.0),
        ]
    }
    s = stability(prev, cur, 0.25)
    assert s["jaccard_core"] == 1 / 3 and s["n_shared"] == 4 and s["mean_displacement"] == 0.25
    assert -1 <= s["kendall_tau"] < 1
    assert stability(None, cur, None)["jaccard_core"] is None
    assert (
        mean_displacement({"a": (0, 0), "b": (1, 0)}, {"a": (0, 1), "b": (1, 0), "z": (5, 5)})
        == 0.5
    )
