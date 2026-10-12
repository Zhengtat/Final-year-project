"""CR-014 Stage A: proposal registry invariants (no network, no gold)."""

import pytest

from cumap.cr014.proposal import add, definitional_hits, norm_surface, u1_registry
from cumap.cr014.stage_a import contains, overlap_match
from cumap.expert_kg.alias_rules import AliasConfig


@pytest.fixture(scope="module")
def nlp():
    spacy = pytest.importorskip("spacy")
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm not installed")


def test_same_span_from_two_sources_is_one_candidate_with_union_provenance():
    reg: dict = {}
    add(reg, "s", "Sliding Window", "a", "the sliding window protocol")
    add(reg, "s", "sliding  window", "b", "the sliding window protocol")
    assert list(reg) == ["sliding window"]
    assert reg["sliding window"].proposal_sources == {"a", "b"}
    assert reg["sliding window"].start_offset == 4


def test_u1_is_noisy_but_keeps_subspans_and_hyphenated_terms(nlp):
    sec = {
        "section_id": "s",
        "text": "A database-style searching system uses an inverted index.",
        "heading": "",
    }
    keys = set(u1_registry(sec, set(), nlp, AliasConfig.load()))
    assert {"inverted index", "index", "database-style searching"} <= keys
    assert all(len(k.split()) <= 4 for k in keys)


def test_overlap_requires_containment_and_ignores_stopword_singletons():
    assert contains(["inverted", "index"], ["index"])
    assert overlap_match({"index"}, {"inverted index"}, set())
    assert not overlap_match({"the"}, {"the index"}, {"the"})


def test_definitional_hits_are_normalised(nlp):
    assert all(h == norm_surface(h) for h in definitional_hits("A router is called a gateway."))
