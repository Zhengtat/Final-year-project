"""CR-064 Pair Recall loss causes (`cumap.cr064.pair_loss`) on a small text. No network, no model."""

from cumap.cr064 import pair_loss as P

TEXT = "BERT was tested by Smith et al. on parsing. Next, GPT is a model."


def at(word: str) -> int:
    return TEXT.index(word)


def test_cut_after_an_abbreviation_is_a_splitter_cause():
    assert P.cause(TEXT, at("BERT"), at("parsing"), {"a"}, {"b"}) == "splitter_abbreviation"


def test_cut_at_a_real_sentence_end_is_not_an_abbreviation():
    assert P.cause(TEXT, at("parsing"), at("GPT"), {"a"}, {"b"}) == "splitter_other"


def test_same_sentence_causes():
    a, b = at("GPT"), at("model")
    assert P.cause(TEXT, a, b, {"x"}, {"x"}) == "same_concept"
    assert P.cause(TEXT, a, b, {"x"}, set()) == "no_owner"
    assert P.cause(TEXT, a, b, {"x"}, {"y"}) == "distinct_concepts_not_built"
