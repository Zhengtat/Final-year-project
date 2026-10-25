"""CR-056: profile v5 and the all-pairs budget wrapper; nested placement (no network, no key)."""

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import scinlp_run as SR


def test_profile_v5_is_v4_g2_plus_all_pairs_and_the_wrapper_patches_only_at_call_time():
    p4 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v4_g2.yaml").read_text())
    p5 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v5.yaml").read_text())
    assert p5["pair_budget"] == "all"
    assert {k: v for k, v in p5.items() if k not in ("status", "pair_budget")} == {
        k: v for k, v in p4.items() if k != "status"
    }
    from cumap.cr056 import scinlp_run as W

    old_p, old_b = SR.PROFILE, SR.pair_budget
    try:
        W.use_profile_v5()
        assert SR.PROFILE == W.PROFILE_V5 and SR.pair_budget(5000, 37) == 37
    finally:
        SR.PROFILE, SR.pair_budget = old_p, old_b
    assert SR.pair_budget is old_b


def test_nested_placement_adds_contained_node_names():
    from types import SimpleNamespace

    from cumap.cr019.variants import PredNode
    from cumap.cr056.nested import nested_nodes

    doc = SimpleNamespace(tokens=["a", "pre-trained", "language", "model", "works"])
    cp = {
        "concepts": [
            {"concept_id": "c1", "canonical_name": "pre-trained language model"},
            {"concept_id": "c2", "canonical_name": "language model"},
        ]
    }
    nodes = [
        PredNode("c1", "d", "method", "pre-trained language model", ((1, 4),)),
        PredNode("c2", "d", "method", "language model", ()),
    ]
    out = {n.node_id: n.mentions for n in nested_nodes(doc, cp, nodes, rules=())}
    assert out["c2"] == ((2, 4),) and out["c1"] == ((1, 4),)
