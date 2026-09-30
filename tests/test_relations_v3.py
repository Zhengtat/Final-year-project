"""CR-007 §5.2/§5.3/§9 tests: relation prompt v3 on the mock backend (no network, no key)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.relations import CandidatePair, concept_vocab
from cumap.expert_kg.relations_v3 import (
    build_relation_choice_v3,
    classify_pair_v3,
    dimension_grounded,
    endpoint_grounding,
    family_options_v3,
    filled_options,
)
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
REG = RelationRegistry.from_yaml(REPO / "configs/relations_v1.1.yaml")
PROMPTS = {
    t: load_prompt(REPO / "prompts", t, "v3")
    for t in ("relation_family", "relation_choice", "relation_qualifiers")
}


def rc(cid, name, typ="Component"):
    return RegisteredConcept(cid, name, typ, None, "s1")


SWITCH, FRAME, HOST, REPEATER = (
    rc("c_sw", "switch"),
    rc("c_fr", "frame", "DataUnit"),
    rc("c_host", "host"),
    rc("c_rep", "repeater"),
)
WIRE, AIR, FIBER, BIT, RATE = (
    rc("c_wire", "wire", "Concept"),
    rc("c_air", "air", "Concept"),
    rc("c_fiber", "fiber", "Concept"),
    rc("c_bit", "bit", "Concept"),
    rc("c_rate", "bit rate", "Parameter"),
)
MATCHER = MentionMatcher(
    concept_vocab([SWITCH, FRAME, HOST, REPEATER, WIRE, AIR, FIBER, BIT, RATE])
)


def pair(x, y, sentence):
    return CandidatePair("P1", "s1", x.concept_id, y.concept_id, sentence)


def run(tmp_settings, fixtures_dir, x, y, sentence, fam, choice, qual="v3_acts_on", **kw):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    return classify_pair_v3(
        client,
        PROMPTS["relation_family"],
        PROMPTS["relation_choice"],
        PROMPTS["relation_qualifiers"],
        REG,
        pair(x, y, sentence),
        x,
        y,
        MATCHER,
        fixtures=(fam, choice, qual),
        **kw,
    )


def test_options_are_filled_with_the_concept_names_in_both_directions_plus_no_relation_and_other():
    block = filled_options(REG, "mechanism_process", "switch", "frame")
    assert (
        "switch handles frame" in block and "frame handles switch" in block
    )  # acts_on both directions
    assert "{X}" not in block and "{Y}" not in block  # QA4RE-faithful: no literal placeholders
    assert "- no_relation:" in block and "- other:" in block
    sym = filled_options(REG, "classification_structure", "switch", "host")
    assert sym.count("is directly connected to") == 1  # symmetric connected_to: one reading only
    assert (
        "gloss" not in family_options_v3(REG)
        and "acts_on" in family_options_v3(REG)
        and "- other:" in family_options_v3(REG)
    )


def test_rendered_prompt_contains_the_filled_options_and_the_rules():
    text = PROMPTS["relation_choice"].render(
        concept_x="switch",
        concept_y="frame",
        family="mechanism_process",
        sentence="s",
        relation_options=filled_options(REG, "mechanism_process", "switch", "frame"),
    )
    assert (
        "switch handles frame" in text
        and "states OR DENIES a relation" in text
        and "co-mentioned, choose no_relation" in text
    )
    assert "other_description" in text and "comparison_dimension" in text


def test_other_without_description_fails_validation():
    schema = build_relation_choice_v3(REG, "mechanism_process")
    ok = {
        "relation": "other",
        "direction": "forward",
        "evidence_quote": "q",
        "statement": "s",
        "comparison_dimension": None,
        "other_description": "d",
        "other_suggested_label": "connects",
    }
    assert schema.model_validate(ok).relation == "other"
    for missing in ("other_description", "other_suggested_label"):
        with pytest.raises(ValidationError):
            schema.model_validate({**ok, missing: None})
    with pytest.raises(ValidationError):
        schema.model_validate({**ok, "relation": "made_up"})


def test_acts_on_edge_with_action_type_is_accepted_and_logged_hashes_are_recorded(
    tmp_settings, fixtures_dir
):
    r = run(
        tmp_settings,
        fixtures_dir,
        SWITCH,
        FRAME,
        "The switch forwards the frame out of one port.",
        "v3_mechanism",
        "v3_acts_on",
    )
    assert (
        r.outcome == "edge" and r.relation == "acts_on" and r.qualifiers["action_type"] == "forward"
    )
    assert (
        set(r.prompt_hashes) == {"family", "choice", "qualifiers"}
        and r.grounding["quote_x"]
        and r.grounding["quote_y"]
    )


def test_a_negated_sentence_expects_the_relation_plus_polarity_negated(tmp_settings, fixtures_dir):
    r = run(
        tmp_settings,
        fixtures_dir,
        HOST,
        REPEATER,
        "Classical Ethernet hosts need not require a repeater between them.",
        "v3_dependency",
        "v3_negated_requires",
        qual="v3_negated",
    )
    assert (
        r.outcome == "edge" and r.relation == "requires" and r.qualifiers["polarity"] == "negated"
    )


def test_a_list_or_co_mention_is_no_relation_not_other(tmp_settings, fixtures_dir):
    r = run(
        tmp_settings,
        fixtures_dir,
        WIRE,
        AIR,
        "The medium may be a wire, fiber or air.",
        "v3_norel",
        "v3_norel",
    )
    assert (
        r.outcome == "no_relation"
        and r.reason == "family_no_relation"
        and "choice" not in r.prompt_hashes
    )


def test_comparison_without_a_grounded_dimension_is_recorded_as_no_relation(
    tmp_settings, fixtures_dir
):
    """Owner decision (STOP 1): contrasts_with / trades_off_with need a dimension named in the sentence."""
    sentence = "The medium may be a shielded wire, fiber or air."
    r = run(tmp_settings, fixtures_dir, WIRE, AIR, sentence, "v3_comparison", "v3_contrast_nodim")
    assert r.outcome == "no_relation" and r.reason == "comparison_no_grounded_dimension"
    sent = "A shielded wire has a lower cost than fiber."
    ok = run(
        tmp_settings,
        fixtures_dir,
        WIRE,
        FIBER,
        sent,
        "v3_comparison",
        "v3_contrast_dim",
        qual="v3_contrast_q",
    )
    assert (
        ok.outcome == "edge"
        and ok.comparison_dimension == "cost"
        and ok.qualifiers["dimension"] == "cost"
    )
    bad = run(
        tmp_settings,
        fixtures_dir,
        WIRE,
        FIBER,
        sent + " ",
        "v3_comparison",
        "v3_contrast_baddim",
        qual="v3_contrast_q",
    )
    assert bad.outcome == "no_relation" and bad.reason == "comparison_no_grounded_dimension"


def test_dimension_grounding_rule():
    s = "Manchester encoding halves the bit rate, so the clock recovery is easier."
    assert (
        dimension_grounded("bit rate", s)
        and dimension_grounded("clock recovery", s)
        and dimension_grounded("Recovery of the clock", s)
    )
    assert (
        not dimension_grounded("cost", s)
        and not dimension_grounded(None, s)
        and not dimension_grounded("  ", s)
    )


def test_endpoint_grounding_rejects_an_edge_whose_endpoint_is_only_inside_a_longer_mention(
    tmp_settings, fixtures_dir
):
    assert endpoint_grounding("the bit rate is half", MATCHER, "c_bit", "c_rate") == (
        False,
        True,
    )  # 'bit' only inside 'bit rate'
    r = run(
        tmp_settings,
        fixtures_dir,
        SWITCH,
        FRAME,
        "A switch forwards each frame.",
        "v3_mechanism",
        "v3_acts_on_ungrounded",
    )
    assert (
        r.outcome == "rejected"
        and r.reason == "endpoint_not_grounded"
        and r.grounding["sentence_x"]
    )
    lenient = run(
        tmp_settings,
        fixtures_dir,
        SWITCH,
        FRAME,
        "A switch forwards each frame.",
        "v3_mechanism",
        "v3_acts_on_ungrounded",
        grounding_scope="sentence",
    )
    assert lenient.outcome == "edge"


def test_domain_range_rejection_names_the_relation(tmp_settings, fixtures_dir):
    ok = run(
        tmp_settings,
        fixtures_dir,
        SWITCH,
        FRAME,
        "The switch forwards the frame.",
        "v3_mechanism",
        "v3_acts_on",
    )
    assert ok.outcome == "edge"  # switch (Component) acts_on frame (DataUnit): valid
    swapped = run(
        tmp_settings,
        fixtures_dir,
        FRAME,
        SWITCH,
        "The frame forwards the switch.",
        "v3_mechanism",
        "v3_acts_on_frame_first",
    )
    assert (
        swapped.outcome == "rejected" and swapped.reason == "domain_range"
    )  # a data unit is not an actor
    assert "acts_on" in swapped.type_errors[0]


def test_other_carries_its_description_and_label_and_invalid_other_is_rejected(
    tmp_settings, fixtures_dir
):
    r = run(tmp_settings, fixtures_dir, FRAME, SWITCH, "s", "v3_mechanism", "v3_other_ok")
    assert (
        r.outcome == "other" and r.other_suggested_label == "is carried in" and r.other_description
    )
    bad = run(
        tmp_settings,
        fixtures_dir,
        FRAME,
        SWITCH,
        "a different sentence",
        "v3_mechanism",
        "v3_other_bad",
    )
    assert bad.outcome == "rejected" and bad.reason.startswith("schema_invalid")


def test_acts_on_without_action_type_is_rejected(tmp_settings, fixtures_dir):
    r = run(
        tmp_settings,
        fixtures_dir,
        SWITCH,
        FRAME,
        "The switch forwards the frame.",
        "v3_mechanism",
        "v3_acts_on",
        qual="v3_acts_on_noaction",
    )
    assert r.outcome == "rejected" and r.reason == "acts_on_without_action_type"
