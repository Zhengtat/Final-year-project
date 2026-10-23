import numpy as np
import pytest

from cumap.organisation.config import load_config
from cumap.organisation.importance import (
    GraphSpec,
    build_snap_graph,
    combine,
    compute_importance,
    exposure_adjust,
    generic_flags,
    pagerank,
    percentile,
    relation_mode,
)
from cumap.organisation.inputs import OrgConcept, OrgEdge, OrgInputs

CFG = load_config()


def _inputs(edges, n_sections=6, mentions=None, ncon=None):
    ids = sorted({x for e in edges for x in (e[0], e[2])} | set(ncon or []))
    concepts = {c: OrgConcept(c, c, "Concept", 2) for c in ids}
    secs = {f"s{i}": 2 for i in range(n_sections)}
    order = {f"s{i}": i for i in range(n_sections)}
    ms = mentions or {c: [(f"s{i}", "used") for i in range(2)] for c in ids}
    oe = [
        OrgEdge(f"e{i}", s, t, rel, "classification_structure", "s0", 2, 1.0)
        for i, (s, rel, t) in enumerate(edges)
    ]
    return OrgInputs(concepts, oe, secs, order, ms, [2])


def test_direction_rule_is_from_config():
    assert relation_mode("is_a", CFG) == "target" and relation_mode("requires", CFG) == "target"
    assert relation_mode("has_property", CFG) == "source"
    assert relation_mode("contrasts_with", CFG) == "both"


def test_parent_gains_from_is_a_and_owner_gains_from_has_property():
    inp = _inputs(
        [
            ("c1", "is_a", "P"),
            ("c2", "is_a", "P"),
            ("c3", "is_a", "P"),
            ("A", "has_property", "p1"),
            ("A", "has_property", "p2"),
            ("A", "has_property", "p3"),
        ]
    )
    sg = build_snap_graph(inp, 2, CFG)
    pr = pagerank(sg.spec, 0.85)
    ix = sg.index
    assert pr[ix["P"]] > max(pr[ix["c1"]], pr[ix["c2"]], pr[ix["c3"]])
    assert pr[ix["A"]] > max(pr[ix["p1"]], pr[ix["p2"]], pr[ix["p3"]])


def test_percentile_and_weighted_combination_known_ordering():
    eligible = np.array([True, True, True, True])
    comps = {
        "pagerank": np.array([4.0, 3, 2, 1]),
        "coreness": np.array([1.0, 1, 1, 1]),
        "spread": np.array([0.1, 0.4, 0.2, 0.3]),
        "bridging": np.array([0.0, 0.0, 0.5, 0.0]),
    }
    w = {k: c.weight for k, c in CFG.importance.components.items()}
    raw, pcts = combine(comps, w, eligible)
    assert list(pcts["pagerank"]) == pytest.approx([1, 2 / 3, 1 / 3, 0])
    assert pcts["coreness"].tolist() == [0.5] * 4  # ties -> average rank
    assert raw[0] == pytest.approx(0.35 * 1 + 0.20 * 0.5 + 0.25 * 0 + 0.20 * (1 / 3))
    assert int(np.argmax(raw)) == 1  # best spread outweighs pagerank rank 2
    assert (percentile(np.array([5.0, 1, 3]), np.array([True, False, True])) == [1, 0, 0]).all()


def test_exposure_correction_helps_young_fast_linker_only_in_adjusted():
    # raw grows with age (exposure) for the 6 fillers; A (old) and B (young) tie on raw
    exposure = np.array([12, 2, 3, 4, 6, 8, 10, 12], dtype=float)  # index 0 = A(old), 1 = B(young)
    raw = np.array([0.8, 0.8, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    eligible = np.ones(8, dtype=bool)
    adj = exposure_adjust(raw, exposure, eligible)
    assert raw[1] == raw[0]  # not above in raw
    assert adj[1] > adj[0]  # above in adjusted: same raw with far less exposure
    # an old concept that is MORE central than its age predicts stays high
    raw2 = raw.copy()
    raw2[0], raw2[1] = 0.99, 0.3
    adj2 = exposure_adjust(raw2, exposure, eligible)
    assert adj2[0] > adj2[1] and adj2[0] >= 0.85


def test_background_guard_flags_hub_term_and_override_keep_unflags():
    edges = [("data", "requires", f"x{i}") for i in range(1)] + [
        (f"a{i}", "is_a", f"b{i}") for i in range(8)
    ]
    ids = {x for e in edges for x in (e[0], e[2])}
    mentions = {c: [("s0", "defined"), ("s1", "used")] for c in ids}
    mentions["data"] = [(f"s{i}", "used") for i in range(6)]  # everywhere, never defined
    inp = _inputs(edges, mentions=mentions)
    sg = build_snap_graph(inp, 2, CFG)
    assert generic_flags(sg, CFG)[sg.index["data"]]
    raw = CFG.model_dump()
    raw["generic_guard"]["overrides_keep"] = ["data"]
    from cumap.organisation.config import OrgConfig

    assert not generic_flags(sg, OrgConfig(**raw))[sg.index["data"]]
    raw["generic_guard"]["overrides_keep"] = []
    raw["generic_guard"]["overrides_generic"] = ["a0"]
    assert generic_flags(sg, OrgConfig(**raw))[sg.index["a0"]]


def test_compute_importance_excludes_unlinked_and_background_from_eligible():
    inp = _inputs([("a", "is_a", "b"), ("b", "is_a", "c")], ncon=["lonely"])
    sg = build_snap_graph(inp, 2, CFG)
    imp = compute_importance(sg, CFG, background=np.zeros(sg.spec.n, dtype=bool))
    assert not imp.eligible[sg.index["lonely"]] and imp.eligible[sg.index["a"]]
    assert imp.raw[sg.index["lonely"]] == 0.0


def test_graphspec_undirected_projection_ignores_direction():
    from cumap.organisation.importance import coreness

    spec = GraphSpec(3, [0, 1, 2], [1, 2, 0], [1.0] * 3, ["target"] * 3)
    assert coreness(spec).tolist() == [2, 2, 2]
