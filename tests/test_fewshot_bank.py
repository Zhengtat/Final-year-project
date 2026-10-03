"""CR-009 §3.5 / §11: the few-shot bank validates clean and overlaps no section text (no network, no key)."""

import json
from pathlib import Path

import pytest
import spacy

from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.fewshot_bank import load_bank, overlaps_text, validate_bank, validate_example
from cumap.expert_kg.partial_span import noun_form_lexicon

ROOT = Path(__file__).parents[1]
NLP = spacy.load("en_core_web_sm")
BANK = load_bank(ROOT / "configs/fewshot/concepts_v4_draft.yaml")


def test_bank_has_six_examples_and_one_corrective():
    assert (
        len(BANK["examples"]) == 7 and sum(bool(e.get("corrective")) for e in BANK["examples"]) == 1
    )


def test_the_banks_expected_outputs_raise_no_flags():
    assert validate_bank(BANK, NLP) == []


def _validate(ex):
    nf = noun_form_lexicon([" ".join(v.split()) for v in ex["paragraphs"].values()], NLP)
    return validate_example(ex, BANK, NLP, nf, AliasConfig.load())


def test_the_validator_catches_each_rule():
    import copy

    ex = copy.deepcopy(BANK["examples"][1])  # ex2_index
    ex["expected"]["new_concepts"][0]["evidence"] = "not in the passage"
    assert any(p.rule == "F2" for p in _validate(ex))
    ex = copy.deepcopy(BANK["examples"][1])
    ex["expected"]["new_concepts"][0]["anchors"][0]["node_id"] = "n_999"
    assert any(p.rule == "F4" for p in _validate(ex))
    ex = copy.deepcopy(BANK["examples"][1])
    ex["expected"]["existing_mentions"] = []
    assert any(p.rule == "M1" for p in _validate(ex))
    ex = copy.deepcopy(BANK["examples"][1])  # ex2_index: replace "index page" by its tail "page"
    for c in ex["expected"]["new_concepts"]:
        if c["name"] == "index page":
            c["name"] = "page"
    assert any(p.rule == "M2" for p in _validate(ex))  # a partial span would be flagged


def test_no_example_passage_overlaps_any_section_text():
    files = [
        ROOT / "data/interim/textbook_sections.jsonl",
        ROOT / "data/interim/external/iir_sections.jsonl",
        ROOT / "data/interim/external/iir_test_sections_v3.jsonl",
    ]
    present = [f for f in files if f.exists()]
    if not present:
        pytest.skip("section texts are gitignored and not present")
    texts = [
        json.loads(x)["text"]
        for f in present
        for x in f.read_text(encoding="utf-8").splitlines()
        if x
    ]
    assert overlaps_text(BANK, texts) == []
