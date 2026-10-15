"""CR-020: one name equivalence for text matching (no network, no key)."""

from pathlib import Path

import pytest
import yaml

from cumap.expert_kg import mentions as M


def test_default_mode_is_token_and_env_overrides(monkeypatch):
    monkeypatch.delenv("CUMAP_MATCHING", raising=False)
    assert M.matching_mode() == "token" and M.MentionMatcher({"x": "x"}).mode == "token"
    monkeypatch.setenv("CUMAP_MATCHING", "r1key")
    assert M.MentionMatcher({"x": "x"}).mode == "r1key"
    monkeypatch.setenv("CUMAP_MATCHING", "fuzzy")
    with pytest.raises(ValueError):
        M.matching_mode()


def test_token_mode_is_unchanged_and_r1key_finds_spelling_variants():
    vocab = {"prefix-tuning": "p", "bit rate": "r", "bit": "b"}
    text = "prefix-tuning, prefixtuning and Prefix tuning; the bit rate and a bit."
    tok = [(m.surface, m.concept_id) for m in M.MentionMatcher(vocab, mode="token").find(text)]
    r1 = [(m.surface, m.concept_id) for m in M.MentionMatcher(vocab, mode="r1key").find(text)]
    assert tok == [("prefix-tuning", "p"), ("bit rate", "r"), ("bit", "b")]
    assert r1 == [
        ("prefix-tuning", "p"),
        ("prefixtuning", "p"),
        ("Prefix tuning", "p"),
        ("bit rate", "r"),
        ("bit", "b"),
    ]


def test_production_mode_comes_from_the_config_file_unless_env_is_set(monkeypatch):
    mode = yaml.safe_load(Path("configs/matching.yaml").read_text())["production_mode"]
    monkeypatch.delenv("CUMAP_MATCHING", raising=False)
    assert M.use_production_matching() == mode == "r1key"
    monkeypatch.setenv("CUMAP_MATCHING", "token")
    assert M.use_production_matching() == "token"


def test_frozen_scorer_pins_token_matching(monkeypatch):
    from cumap.cr012.production_graph import grounded_spans

    monkeypatch.setenv("CUMAP_MATCHING", "r1key")
    c = [
        {
            "concept_id": "p",
            "canonical_name": "prefix-tuning",
            "aliases": [],
            "mentions": [{"section_id": "u", "quote": "prefix-tuning and prefixtuning"}],
        }
    ]
    spans, _ = grounded_spans(c, "prefix-tuning and prefixtuning", "u")
    assert spans == {"p": [(0, 13)]}
