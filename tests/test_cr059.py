"""CR-059 DRAFT: type-free generator v7, gold-free domain profile, endpoint check by the choice step (mock fixtures only; no network, no key)."""

import re
from pathlib import Path

import pytest
import yaml
from test_relations_v3 import FRAME, MATCHER, SWITCH, pair

from cumap.concepts_v4.bank import card_line
from cumap.concepts_v4.schema import (
    DEFAULT_SCHEMAS,
    UNTYPED,
    UNTYPED_SCHEMAS,
    fill_types,
    make_schemas,
)
from cumap.cr059 import domain_profile as DP
from cumap.cr059 import draft as DR
from cumap.expert_kg.relations_v3 import RegisteredConcept, classify_pair_v3
from cumap.expert_kg.relations_v8 import build_relation_choice_v8, resolve_endpoint_check
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
V15 = RelationRegistry.from_yaml(REPO / "configs/relations_v1.5.yaml")
SAMPLE = "We fine-tune BERT on the task. Then decoding uses beam search with width 5. Overall accuracy improves by 2 points."


def _profile(status="approved", **kw) -> DP.DomainProfile:
    cats = {
        c: {"include": c != "property", "scope": "named_only", "examples": []}
        for c in DP.CATEGORIES
    }
    cats["technique"]["examples"] = [{"term": "beam search", "quote": "decoding uses beam search"}]
    raw = {"name": "t", "version": 1, "status": status, "document_kind": "paper", "domain": "nlp",
           "domain_description": "Research papers on language technology.", "specificity": "named_instances",
           "categories": cats, "always_concepts": [{"term": "accuracy", "quote": "accuracy improves"}],
           "not_alone": [{"term": "corpus", "quote": "a corpus"}], "acronym_convention": "long_form_with_acronym_alias",
           "keep_variant_modifier": True, "provenance": {}, **kw}  # fmt: skip
    return DP.DomainProfile.model_validate(raw)


# ---------------------------------------------------------------- type-free generator
def test_an_empty_type_list_gives_schemas_without_a_node_type_and_the_runner_fills_the_generic_type():
    s = make_schemas([])
    assert s is UNTYPED_SCHEMAS and s.fill_type == UNTYPED == "Concept"
    for model in (s.generator, s.backfill):
        assert "node_type" not in str(model.model_json_schema())
    assert make_schemas(None) is DEFAULT_SCHEMAS and DEFAULT_SCHEMAS.fill_type is None
    out = fill_types(
        {"new_concepts": [{"name": "BERT"}], "existing_mentions": [{"node_id": "n1"}]}, UNTYPED
    )
    assert (
        out["new_concepts"][0]["node_type"] == "Concept"
        and out["existing_mentions"][0]["node_type"] == "Concept"
    )
    assert fill_types({"new_concepts": [{"name": "x"}]}, None) == {"new_concepts": [{"name": "x"}]}


def test_cards_lose_the_type_column_only_when_untyped():
    c = {
        "id": "n_1",
        "name": "BERT",
        "aliases": [],
        "type": "Concept",
        "def": "—",
        "in_text": True,
        "gloss": "g",
    }
    assert "| Concept |" in card_line(c) and "Concept" not in card_line(c, typed=False)


def test_prompt_v7_renders_from_the_profile_with_no_node_type_and_no_scinlp_word_lists():
    p = load_prompt(REPO / "prompts", "concept_generator", "v7")
    fixed = {k: "x" for k in ("examples", "heading_path", "look_alikes", "existing_nodes", "independent_terms",
                              "corrections", "section_paragraphs", "pass_note")}  # fmt: skip
    text = p.render(domain="nlp", **fixed, **DP.prompt_fields(_profile()))
    assert not re.search(r"\{[a-z_]+\}", text)
    for word in (
        "node_type",
        "Node types",
        "task:",
        "method:",
        "dataset:",
        "metric:",
        "Penn Treebank",
        "BLEU",
    ):
        assert word not in text, word
    assert "beam search" in text and '"corpus"' in text and "accuracy" in text
    assert (
        "Not concepts in this domain on their own: properties, states and conditions of things."
        in text
    )


def test_earlier_generator_versions_are_byte_identical():
    import subprocess

    out = subprocess.run(["git", "diff", "--stat", "master", "--", "prompts/concept_generator/v6_scinlp.md",
                          "prompts/concept_generator/v4.md", "prompts/relation_choice/v6.md"],
                         capture_output=True, text=True, cwd=REPO, check=False)  # fmt: skip
    assert out.stdout.strip() == ""


# ---------------------------------------------------------------- domain profile
def test_only_an_approved_profile_loads_and_every_category_must_be_decided(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text(yaml.safe_dump(_profile(status="draft").model_dump()))
    with pytest.raises(ValueError, match="draft"):
        DP.load_domain_profile(f)
    d = _profile().model_dump()
    d["categories"].pop("setting")
    f.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError, match="setting"):
        DP.load_domain_profile(f)


def test_the_drafter_keeps_only_quoted_terms_and_records_a_missing_category(
    tmp_settings, fixtures_dir
):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    out = DR.draft([("d1", SAMPLE)], "purpose", "t", client, dry_run=False)
    prof, dropped = out["profile"], out["dropped"]
    assert prof["status"] == "draft" and prof["provenance"]["gold_used"] is False
    assert [t["term"] for t in prof["always_concepts"]] == ["accuracy"]
    assert prof["categories"]["technique"]["examples"] == [
        {"term": "beam search", "quote": "decoding uses beam search with width 5"}
    ]
    assert prof["categories"]["setting"]["include"] is False and prof["not_alone"] == []
    reasons = {(x["where"], x["reason"]) for x in dropped}
    assert ("always_concepts", "quote_not_in_sample") in reasons and (
        "not_alone",
        "term_not_in_quote",
    ) in reasons
    assert ("category:setting", "category_missing_set_to_false") in reasons
    DP.DomainProfile.model_validate(
        {**prof, "status": "approved"}
    )  # an approved draft loads as a profile


def test_the_dry_run_makes_no_call():
    out = DR.draft([("d1", SAMPLE)], "purpose", "t", None, dry_run=True)
    assert out["dry_run"] and out["input_tokens_est"] > 0


# ---------------------------------------------------------------- endpoint check by the choice step (owner choice b)
def _classify(tmp_settings, fixtures_dir, cx, choice, endpoint_check):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    P = {t: load_prompt(REPO / "prompts", t, v)
         for t, v in (("relation_family", "v3"), ("relation_choice", "v8" if endpoint_check == "choice" else "v6"),
                      ("relation_qualifiers", "v6"))}  # fmt: skip
    return classify_pair_v3(client, P["relation_family"], P["relation_choice"], P["relation_qualifiers"], V15,
                            pair(cx, FRAME, "The switch forwards the frame out of one port."), cx, FRAME, MATCHER,
                            fixtures=("v3_mechanism", choice, "v6_acts_on"), amendments="v6",
                            endpoint_check=endpoint_check)  # fmt: skip


def test_choice_mode_accepts_a_fitting_edge_without_reading_node_types(tmp_settings, fixtures_dir):
    wrong_type = RegisteredConcept(SWITCH.concept_id, "switch", "Parameter", None, "s1")
    assert (
        _classify(tmp_settings, fixtures_dir, wrong_type, "v6_acts_on", "types").reason
        == "domain_range"
    )
    r = _classify(tmp_settings, fixtures_dir, wrong_type, "v8_acts_on_fits", "choice")
    assert r.outcome == "edge" and r.type_errors == [] and r.endpoint_fit["answer"] == "fits"


def test_choice_mode_rejects_a_misfit_with_its_own_reason(tmp_settings, fixtures_dir):
    r = _classify(tmp_settings, fixtures_dir, SWITCH, "v8_acts_on_misfit", "choice")
    assert (
        r.outcome == "rejected"
        and r.reason == "endpoint_fit"
        and r.endpoint_fit["answer"] == "does_not_fit"
    )
    assert "endpoint_fit" in r.to_dict()


def test_the_default_endpoint_check_is_types_and_results_serialise_as_before(
    tmp_settings, fixtures_dir, monkeypatch
):
    monkeypatch.delenv("CUMAP_BENCHMARK_PROFILE", raising=False)
    assert resolve_endpoint_check() == "types"
    monkeypatch.setenv("CUMAP_BENCHMARK_PROFILE", str(REPO / "configs/scinlp_profile_v7r.yaml"))
    assert resolve_endpoint_check() == "choice"
    r = _classify(tmp_settings, fixtures_dir, SWITCH, "v6_acts_on", "types")
    assert r.outcome == "edge" and "endpoint_fit" not in r.to_dict()


def test_choice_v8_schema_is_v6_plus_two_closed_or_required_fields():
    reg = RelationRegistry.from_yaml(REPO / "configs/relations_scinlp_v1.0.1.yaml")
    m = build_relation_choice_v8(reg, "scinlp")
    props = m.model_json_schema()["properties"]
    assert (
        props["endpoint_fit"]["enum"] == ["fits", "does_not_fit"]
        and "endpoint_fit_reason" in m.model_json_schema()["required"]
    )
    assert m.model_config["extra"] == "forbid"


def test_profile_v7_is_v5_with_only_the_cr059_changes():
    p5 = yaml.safe_load((REPO / "configs/scinlp_profile_v5.yaml").read_text())
    p7 = yaml.safe_load((REPO / "configs/scinlp_profile_v7.yaml").read_text())
    changed = {k for k in set(p5) | set(p7) if p5.get(k) != p7.get(k)}
    assert changed == {
        "status",
        "entity_types",
        "generator_prompt",
        "domain_profile",
        "endpoint_check",
    }
    assert p7["entity_types"] == [] and p7["generator_prompt"]["version"] == "v7"


def test_a_committed_profile_keeps_quote_hashes_and_the_evidence_file_verifies_them():
    d = _profile().model_dump()
    prof, ev = DP.split_evidence(d)
    assert "quote" not in str({k: v for k, v in prof.items() if k != "provenance"}).replace(
        "quote_sha256", ""
    )
    p = DP.DomainProfile.model_validate(prof)
    assert DP.verify_evidence(p, ev) == []
    ev[next(iter(ev))] = "something else"
    assert DP.verify_evidence(p, ev) != []


def test_the_approved_scinlp_profile_loads_and_holds_no_quote_text():
    p = DP.load_domain_profile(REPO / "configs/domain_profiles/scinlp_v1.yaml")
    assert p.status == "approved" and p.provenance["gold_used"] is False
    assert all(t.quote is None and t.quote_sha256 for t in [*p.always_concepts, *p.not_alone])
