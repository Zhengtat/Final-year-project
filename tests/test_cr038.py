"""CR-038 DRAFT: qualifier amendments (registry v1.5, per-relation qualifier schema, dimension quote, prompts v6). Mock fixtures only; never run."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from test_relations_v3 import FIBER, FRAME, MATCHER, SWITCH, WIRE, pair

from cumap.expert_kg import relations_v6 as R6
from cumap.expert_kg.relations_v3 import build_relation_choice_v3, classify_pair_v3
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas import registry_patch as RP
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
V13 = RelationRegistry.from_yaml(REPO / "configs/relations_v1.3.yaml")
V14 = RelationRegistry.from_yaml(REPO / "configs/relations_v1.4.yaml")
V15 = RelationRegistry.from_yaml(REPO / "configs/relations_v1.5.yaml")
P = {
    t: load_prompt(REPO / "prompts", t, v)
    for t, v in (
        ("relation_family", "v3"),
        ("relation_choice", "v6"),
        ("relation_qualifiers", "v6"),
    )
}


# ---------------------------------------------------------------- registry v1.5 (patch file, built from v1.3)
def test_v15_is_built_from_v13_not_v14_and_the_file_is_what_the_patch_generates():
    assert V15.version_label == "1.5" and {r.name for r in V15.all_relations()} == {
        r.name for r in V13.all_relations()
    }
    assert (
        "subtask_of" not in V15 and "subtask_of" in V14
    )  # none of the six unadopted v1.4 relations
    patch = yaml.safe_load(
        (REPO / "configs/registry-patches/CR-038-relations-v1.5.yaml").read_text()
    )
    base = yaml.safe_load((REPO / "configs/relations_v1.3.yaml").read_text())
    assert RP.apply_patch(base, patch) == yaml.safe_load(
        (REPO / "configs/relations_v1.5.yaml").read_text()
    )
    text = (REPO / "configs/relations_v1.5.yaml").read_text()
    assert (
        "NOT from relations_v1.4.yaml" in text.splitlines()[1] and "DRAFT" in text.splitlines()[1]
    )
    with pytest.raises(ValueError, match="registry minor"):
        RP.apply_patch(yaml.safe_load((REPO / "configs/relations_v1.4.yaml").read_text()), patch)


def test_v15_changes_only_the_qualifier_definitions_and_the_contrasts_with_wording():
    assert (
        V15.qualifiers["modality"].values == ["necessary", "always", "typically", "possible"]
        and "never" in V13.qualifiers["modality"].values
    )
    assert "dimension" not in V15.qualifiers and "dimension" in V13.qualifiers
    assert set(V13.qualifiers) - set(V15.qualifiers) == {"dimension"}
    for r in V13.all_relations():
        r15 = V15.get(r.name)
        same = r.model_dump() == r15.model_dump()
        assert same or r.name == "contrasts_with", r.name
    assert (
        "verbatim dimension quote" in V15.get("contrasts_with").definition
        and "dimension qualifier" not in V15.get("contrasts_with").definition
    )


# ---------------------------------------------------------------- per-relation qualifier schema
def test_each_relation_gets_only_the_qualifiers_the_registry_gives_it():
    fields = lambda rel: list(R6.build_qualifiers_v6(V15, rel).model_fields)
    base = ["polarity", "modality", "conditions", "surface_phrase"]
    assert (
        fields("uses") == base
        and fields("part_of") == [*base, "part_type"]
        and fields("acts_on") == [*base, "action_type"]
    )
    assert all("dimension" not in fields(r.name) for r in V15.all_relations())


def test_schema_fields_are_required_not_null_closed_and_modality_has_no_never():
    s = R6.build_qualifiers_v6(V15, "part_of")
    ok = {
        "polarity": "affirmed",
        "modality": "typically",
        "conditions": [],
        "surface_phrase": "is part of",
        "part_type": "component",
    }
    assert s.model_validate(ok).part_type == "component"
    for bad in (
        {**ok, "modality": "never"},
        {**ok, "part_type": None},
        {**ok, "dimension": "x"},
        {k: v for k, v in ok.items() if k != "part_type"},
        {**ok, "part_type": "kind"},
    ):
        with pytest.raises(ValidationError):
            s.model_validate(bad)
    assert all(f.is_required() for f in s.model_fields.values())


def test_v6_refuses_a_registry_that_still_has_never_or_dimension():
    R6.check_registry_for_v6(V15)
    with pytest.raises(ValueError):
        R6.check_registry_for_v6(V13)


def test_choice_v6_schema_has_dimension_quote_and_v3_is_unchanged():
    s6 = R6.build_relation_choice_v6(V15, "comparison")
    s3 = build_relation_choice_v3(V15, "comparison")
    assert "dimension_quote" in s6.model_fields and "comparison_dimension" not in s6.model_fields
    assert "comparison_dimension" in s3.model_fields and "dimension_quote" not in s3.model_fields
    assert list(s3.model_fields) == [
        "relation",
        "direction",
        "evidence_quote",
        "statement",
        "comparison_dimension",
        "other_description",
        "other_suggested_label",
    ]


def test_surface_phrase_must_be_in_the_quote_and_shorter():
    q = "A shielded wire has a lower cost than fiber"
    assert R6.surface_phrase_errors("has a lower cost than", q) == []
    assert R6.surface_phrase_errors(q, q) == ["surface_phrase_not_shorter"]
    assert R6.surface_phrase_errors("is cheaper than", q) == ["surface_phrase_not_in_quote"]
    assert R6.surface_phrase_errors("", q) == ["surface_phrase_not_in_quote"]


# ---------------------------------------------------------------- the drafted prompts
def test_prompts_are_new_versions_with_static_content_first_and_no_retired_relation():
    for t in ("relation_choice", "relation_qualifiers"):
        p = P[t]
        assert p.version == "v6" and "DRAFT" in p.notes and "trades_off_with" not in p.body
        assert (REPO / f"prompts/{t}/v4.md").exists() and (REPO / f"prompts/{t}/v5.md").exists()
        assert p.body.index("Rules:") < p.body.index("Now ")  # instructions first, the case last
    assert set(re.findall(r"\{(\w+)\}", P["relation_choice"].body)) == {
        "family",
        "concept_x",
        "concept_y",
        "sentence",
        "relation_options",
    }
    assert set(re.findall(r"\{(\w+)\}", P["relation_qualifiers"].body)) == {
        "relation",
        "concept_x",
        "concept_y",
        "statement",
        "evidence_quote",
        "sentence",
        "qualifier_fields",
    }
    assert "dimension" not in P["relation_qualifiers"].body.replace(
        "dimension_quote", ""
    )  # the qualifier prompt no longer asks for a dimension
    assert '"never"' not in R6.qualifier_fields_block(
        V15, "uses"
    )  # the modality choices offered have no `never`


# ---------------------------------------------------------------- classification with the drafts (mock fixtures)
def run6(tmp_settings, fixtures_dir, x, y, sentence, fam, choice, qual, **kw):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    return classify_pair_v3(client, P["relation_family"], P["relation_choice"], P["relation_qualifiers"], V15, pair(x, y, sentence), x, y, MATCHER, fixtures=(fam, choice, qual), amendments="v6", **kw)  # fmt: skip


SENT = "A shielded wire has a lower cost than fiber."


def test_a_comparison_with_a_verbatim_dimension_quote_is_an_edge_with_the_narrow_qualifiers(
    tmp_settings, fixtures_dir
):
    r = run6(
        tmp_settings,
        fixtures_dir,
        WIRE,
        FIBER,
        SENT,
        "v3_comparison",
        "v6_contrast_dim",
        "v6_contrast_q",
    )
    assert r.outcome == "edge" and r.comparison_dimension == "lower cost"
    assert set(r.qualifiers) == {
        "polarity",
        "modality",
        "conditions",
        "surface_phrase",
    }  # no dimension, no part_type, no action_type


def test_a_dimension_quote_that_is_not_in_the_sentence_is_no_relation(tmp_settings, fixtures_dir):
    r = run6(
        tmp_settings,
        fixtures_dir,
        WIRE,
        FIBER,
        SENT,
        "v3_comparison",
        "v6_contrast_baddim",
        "v6_contrast_q",
    )
    assert (r.outcome, r.reason) == ("no_relation", "dimension_quote_not_in_sentence")


def test_a_surface_phrase_that_copies_the_whole_quote_is_rejected(tmp_settings, fixtures_dir):
    r = run6(
        tmp_settings,
        fixtures_dir,
        WIRE,
        FIBER,
        SENT,
        "v3_comparison",
        "v6_contrast_dim",
        "v6_whole_quote",
    )
    assert (r.outcome, r.reason) == ("rejected", "surface_phrase_not_shorter")


def test_acts_on_carries_action_type_and_nothing_else_extra(tmp_settings, fixtures_dir):
    r = run6(
        tmp_settings,
        fixtures_dir,
        SWITCH,
        FRAME,
        "The switch forwards the frame out of one port.",
        "v3_mechanism",
        "v6_acts_on",
        "v6_acts_on",
    )
    assert (
        r.outcome == "edge"
        and r.qualifiers["action_type"] == "forward"
        and "part_type" not in r.qualifiers
    )


def test_an_extra_qualifier_field_fails_schema_validation(tmp_settings, fixtures_dir):
    with pytest.raises(Exception):  # noqa: B017  # the mock backend validates against the closed schema (extra="forbid")
        run6(
            tmp_settings,
            fixtures_dir,
            SWITCH,
            FRAME,
            "The switch forwards the frame out of one port.",
            "v3_mechanism",
            "v6_acts_on",
            "v6_extra_field",
        )


# ---------------------------------------------------------------- switch
def test_amendment_switch_reads_the_policy_v6_since_cr047():
    assert (
        R6.resolve_amendments() == "v6"
        and R6.resolve_amendments("v6") == "v6"
        and R6.resolve_amendments(False) == "off"
    )
    with pytest.raises(ValueError):
        R6.resolve_amendments("v7")
    assert (
        yaml.safe_load((REPO / "configs/relation_policy.yaml").read_text())["qualifier_amendments"]
        == "v6"
    )
