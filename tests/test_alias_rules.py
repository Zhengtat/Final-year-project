"""CR-008 §8: R1-R3 deterministic alias rules (no network, no key)."""

from __future__ import annotations

import pytest

from cumap.expert_kg.alias_rules import (
    AliasConfig,
    acronym_collision,
    alias_statements,
    find_abbreviations,
    r1_key,
    split_embedded_acronym,
)
from cumap.expert_kg.mentions import build_vocab


@pytest.fixture(scope="module")
def cfg() -> AliasConfig:
    return AliasConfig.load()


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Ethernet", "ethernet"),
        ("frequency-hopping", "frequency hopping"),
        ("multi-access", "multiaccess"),
        ("the Internet", "Internet"),
        ("BBUs", "BBU"),
        ("adaptor", "adapter"),
        ("Non-Return-to-Zero (NRZ)", "non-return to zero (NRZ)"),
    ],
)
def test_r1_merges(cfg, a, b):
    assert r1_key(a, cfg) == r1_key(b, cfg)


def test_r1_does_not_merge_different_terms(cfg):
    assert r1_key("routing table", cfg) != r1_key("forwarding table", cfg)


def test_r1_acronym_guard(cfg):
    assert acronym_collision("AS", "as", cfg)
    assert acronym_collision("CAN", "can", cfg)
    assert not acronym_collision("CRC", "crc", cfg)


def test_r2_detects_both_directions(cfg):
    pairs = find_abbreviations(
        "The maximum transmission unit (MTU) is large. The MTU (maximum transmission unit) is "
        "fixed.",
        cfg,
    )
    assert {(p.long_form.lower(), p.short_form) for p in pairs} == {
        ("maximum transmission unit", "MTU")
    }


def test_r2_splits_embedded_acronym(cfg):
    assert split_embedded_acronym("cyclic redundancy check (CRC)", cfg) == (
        "cyclic redundancy check",
        "CRC",
    )
    assert split_embedded_acronym("exclusive OR (XOR)", cfg) == ("exclusive OR", "XOR")


def test_r2_rejects_examples_and_plain_parentheticals(cfg):
    assert split_embedded_acronym("4B/5B encoding (or the similar 8B/10B)", cfg) is None
    assert (
        find_abbreviations("Each node builds an array (a vector) of costs (that is, hops).", cfg)
        == []
    )


def _vocab(*names: str) -> dict[str, str]:
    return build_vocab([{"concept_id": f"c{i}", "canonical_name": n} for i, n in enumerate(names)])


def test_r3_strong_and_weak(cfg):
    vocab = _vocab("latency", "delay", "access network", "last-mile link")
    strong = alias_statements(
        "Network performance has bandwidth and latency (also called delay).", vocab, cfg
    )
    assert [(s.strength, s.rule) for s in strong] == [("strong", "also_called")]
    weak = alias_statements(
        "through last-mile links (or alternatively, access networks) provided", vocab, cfg
    )
    assert [s.strength for s in weak] == ["weak"]
    assert "or alternatively" in weak[0].quote


def test_r3_requires_full_noun_phrase(cfg):
    vocab = _vocab("path", "LTE")
    text = "the industry has followed a fairly well-defined evolutionary path known as LTE."
    assert alias_statements(text, vocab, cfg) == []
