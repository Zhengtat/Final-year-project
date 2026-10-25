"""CR-057: M7 hint, profile v6, the rest paper set, head-stripped nested placement (no network, no key)."""

import yaml

from cumap.concepts_v4.verifier import VerifyCtx, _m7
from cumap.config import REPO_ROOT


def test_m7_hints_uncovered_component_phrases_and_skips_stopword_only_heads():
    t = "We add a copying mechanism and a discriminative ranker . The attention mechanism helps ; our parser is a transition-based parser ."
    ctx = VerifyCtx(
        section_text=t,
        paragraphs={"P1": t},
        cards=[],
        lexicon=None,
        nlp=None,
        m7=True,
        m7_heads=("mechanism", "ranker", "parser"),
    )
    out = {
        "new_concepts": [{"name": "attention mechanism", "aliases": []}],
        "existing_mentions": [],
    }
    assert [h.text for h in _m7(out, ctx)] == [
        "copying mechanism",
        "discriminative ranker",
        "transition-based parser",
    ]
    assert VerifyCtx(section_text=t, paragraphs={}, cards=[], lexicon=None, nlp=None).m7 is False


def test_profile_v6_is_v5_plus_m7():
    p5 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v5.yaml").read_text())
    p6 = yaml.safe_load((REPO_ROOT / "configs/scinlp_profile_v6.yaml").read_text())
    r5, r6 = p5["concept_recall"], p6["concept_recall"]
    assert r6["m7"] is True and {k: v for k, v in r6.items() if not k.startswith("m7")} == r5
    assert {k: v for k, v in p6.items() if k not in ("status", "concept_recall")} == {
        k: v for k, v in p5.items() if k not in ("status", "concept_recall")
    }


def test_rest_set_is_the_train_papers_outside_the_first_set():
    from cumap.cr043.papers import first_set, rest_set

    first, rest = {d for _, d in first_set()}, rest_set()
    assert (
        len(rest) == 37 and all(s == "train" for s, _ in rest) and not first & {d for _, d in rest}
    )


def test_nested_view_strips_a_trailing_generic_head():
    from types import SimpleNamespace

    from cumap.cr019.variants import PredNode
    from cumap.cr056.nested import nested_nodes

    doc = SimpleNamespace(tokens=["the", "GLUE", "benchmark", "is", "used"])
    nodes = [PredNode("c1", "d", "dataset", "GLUE benchmark", ((1, 3),))]
    out = nested_nodes(
        doc,
        {"concepts": [{"concept_id": "c1", "canonical_name": "GLUE benchmark"}]},
        nodes,
        rules=(),
    )
    assert set(out[0].mentions) == {(1, 3), (1, 2)}
