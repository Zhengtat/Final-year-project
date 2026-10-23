"""CR-034: qualifier code checks behind `qualifier_checks: off | v1` (no network, no key)."""

import pytest
from test_relations_v3 import HOST, REG, REPEATER, run

from cumap.expert_kg import qualifier_checks as QC

SENT = "Classical Ethernet hosts can only attach to a repeater between them."
NEG = "Classical Ethernet hosts need not require a repeater between them."


def _nocue(tmp_settings, fixtures_dir, **kw):
    return run(
        tmp_settings,
        fixtures_dir,
        HOST,
        REPEATER,
        SENT,
        "v3_dependency",
        "v3_negated_nocue",
        qual="v3_negated_nocue",
        **kw,
    )


def test_off_is_todays_behaviour_and_serialises_without_the_new_key(tmp_settings, fixtures_dir):
    r = _nocue(tmp_settings, fixtures_dir)
    assert (
        r.outcome == "edge" and r.qualifiers["polarity"] == "negated"
    )  # the wrong negation is kept
    assert "qualifier_flags" not in r.to_dict()


def test_v1_rejects_a_negated_edge_without_a_negation_cue_and_logs_the_reason(
    tmp_settings, fixtures_dir
):
    r = _nocue(tmp_settings, fixtures_dir, qualifier_checks="v1")
    assert r.outcome == "rejected" and r.reason == "negation_without_cue"
    assert r.qualifier_flags == ["negation_without_cue"] and r.to_dict()["qualifier_flags"] == [
        "negation_without_cue"
    ]


def test_v1_keeps_a_negated_edge_that_has_a_cue_and_adds_no_flags(tmp_settings, fixtures_dir):
    r = run(
        tmp_settings,
        fixtures_dir,
        HOST,
        REPEATER,
        NEG,
        "v3_dependency",
        "v3_negated_requires",
        qual="v3_negated",
        qualifier_checks="v1",
    )
    assert r.outcome == "edge" and r.qualifier_flags == [] and "qualifier_flags" not in r.to_dict()


def test_v1_flags_a_misfit_qualifier_and_a_surface_phrase_as_long_as_the_quote_without_rejecting(
    tmp_settings, fixtures_dir
):
    r = run(
        tmp_settings,
        fixtures_dir,
        HOST,
        REPEATER,
        SENT,
        "v3_dependency",
        "v3_negated_nocue",
        qual="v3_misfit_long",
        qualifier_checks="v1",
    )
    assert r.outcome == "edge"
    assert r.qualifier_flags == [
        "qualifier_misfit:dimension",
        "qualifier_misfit:part_type",
        "surface_phrase_long",
    ]


def test_check_edge_unit_cases():
    q = {
        "polarity": "affirmed",
        "part_type": None,
        "dimension": None,
        "surface_phrase": "uses",
        "action_type": None,
    }
    assert QC.check_edge(REG, "requires", q, "A uses B") == []
    assert QC.check_edge(REG, "part_of", {**q, "part_type": "component"}, "A uses B") == []  # fits
    assert QC.check_edge(REG, "is_a", {**q, "part_type": "member"}, "A uses B") == [
        "qualifier_misfit:part_type"
    ]
    assert QC.check_edge(REG, "contrasts_with", {**q, "dimension": "cost"}, "A uses B") == []


@pytest.mark.parametrize(
    "quote,cue",
    [
        ("has no mobility", True),
        ("cannot be built", True),
        ("it does not matter", True),
        ("they don’t care", True),
        ("independent of the clock", True),
        ("neither A nor B", True),
        ("works without a router", True),
        ("can only be built using fixed-length cells", False),
        ("a note on nothing", False),  # word boundaries: 'note', 'nothing' are not cues
        ("", False),
    ],
)
def test_negation_cue(quote, cue):
    assert QC.has_negation_cue(quote) is cue


def test_mode_resolution_reads_policy_and_invalid_raises():
    # CR-045: the owner switched the checks on for new runs
    assert QC.resolve_mode(None) == "v1" and QC.resolve_mode("off") == "off"
    with pytest.raises(ValueError):
        QC.resolve_mode("v2")


def test_a_stored_edge_without_dimension_or_part_type_still_rebuilds_the_pair_registry():
    from types import SimpleNamespace

    from cumap.expert_kg import slice_rerun as sr

    pair = {
        "pair_id": "P1",
        "section_id": "s1",
        "concept_x_id": "a",
        "concept_y_id": "b",
        "sentence": "A uses B.",
    }
    r = {"group": "selected", "outcome": "edge", "pair": pair, "family": "function_means", "relation": "uses", "direction": "forward",
         "statement": "A uses B.", "evidence_quote": "A uses B", "qualifiers": {"polarity": "affirmed", "modality": "typically", "conditions": [], "surface_phrase": "uses"}}  # fmt: skip
    reg = sr.build_pair_registry(SimpleNamespace(relation_results_v3=[r]))
    assert len(reg.all()) == 1


def test_replay_counts_flags_per_check_without_touching_the_run():
    from cumap.cr034.replay import markdown, replay

    def edge(rel, quote, **q):
        base = {
            "polarity": "affirmed",
            "part_type": None,
            "dimension": None,
            "surface_phrase": "uses",
            "action_type": None,
        }
        return {"outcome": "edge", "relation": rel, "evidence_quote": quote, "qualifiers": {**base, **q},
                "pair": {"pair_id": "P", "section_id": "s"}}  # fmt: skip

    cp = {"relation_results_v3": [
        edge("requires", "A needs B"),
        edge("requires", "A can only use B", polarity="negated"),
        edge("requires", "A does not need B", polarity="negated"),
        edge("is_a", "A is a B", part_type="member"),
        edge("uses", "uses", surface_phrase="uses"),
        {"outcome": "no_relation", "pair": {"pair_id": "Q", "section_id": "s"}},
    ]}  # fmt: skip
    res = replay(cp, REG)
    assert (
        res["edges"] == 5 and res["edges_rejected_under_v1"] == 1 and res["negated_with_cue"] == 1
    )
    assert res["by_check"] == {
        "negation_without_cue": 1,
        "qualifier_misfit:part_type": 1,
        "surface_phrase_long": 1,
    }
    assert "negation_without_cue" in markdown("fx", "v1.1", res, True)
