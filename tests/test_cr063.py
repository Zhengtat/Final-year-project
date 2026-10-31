"""CR-063: symbol-aware grounding (no network, no key)."""

from cumap.cr063 import grounding as G


def test_trailing_symbols_of_a_form():
    assert G.trailing_symbols("Vector Space Model ( VSM )") == ")"
    assert G.trailing_symbols("RNMT+") == "+" and G.trailing_symbols("weighted A *") == "*"
    assert G.trailing_symbols("GloVe model") == ""


def test_a_span_extends_only_over_the_symbols_its_form_ends_with():
    toks = ["the", "Vector", "Space", "Model", "(", "VSM", ")", "and", "RNMT", "+", "and", "RNMT"]
    assert G.extend_span(toks, (1, 6), ["Vector Space Model ( VSM )"]) == (1, 7)
    assert G.extend_span(toks, (8, 9), ["RNMT+"]) == (8, 10)
    assert G.extend_span(toks, (11, 12), ["RNMT+"]) == (11, 12)  # no "+" follows
    assert G.extend_span(toks, (1, 4), ["Vector Space Model ( VSM )"]) == (
        1,
        4,
    )  # key differs: no extension


# ---------------------------------------------------------------- position-tolerant evaluation
from types import SimpleNamespace

from cumap.cr063 import tolerant as T


def _doc(text: str):
    offs, i = [], 0
    for t in text.split(" "):
        offs.append((i, i + len(t)))
        i += len(t) + 1
    return SimpleNamespace(token_offsets=offs)


def test_a_span_within_n_characters_snaps_to_gold_one_to_one():
    doc = _doc("the Vector Space Model ( VSM ) and RNMT + here")
    gold = {(1, 7), (8, 10)}  # "Vector Space Model ( VSM )", "RNMT +"
    pred = {(1, 6), (8, 9), (1, 4)}  # "... ( VSM", "RNMT", "Vector Space Model"
    assert T.snap_map(doc, gold, pred, 2) == {(1, 6): (1, 7), (8, 9): (8, 10)}
    assert T.snap_map(doc, gold, pred, 1) == {}  # one token plus its space is at least 2 characters
    assert T.snap_map(doc, gold, {(1, 7)}, 2) == {}  # an exact match keeps its span


def test_word_level_modes_match_one_to_one():
    doc = SimpleNamespace(
        tokens=["the", "test", "accuracy", "of", "GloVe", "model", "and", "IP", "+", "EM"]
    )
    gold = {(2, 3), (4, 6), (7, 10)}  # "accuracy", "GloVe model", "IP + EM"
    pred = {(1, 3), (4, 5), (7, 8)}  # "test accuracy", "GloVe", "IP"
    assert T.snap_map_words(doc, gold, pred, "w1") == {(1, 3): (2, 3), (4, 5): (4, 6)}
    assert T.snap_map_words(doc, gold, pred, "head") == {
        (1, 3): (2, 3)
    }  # "GloVe" and "IP" end in a different word
    assert T.snap_map_words(doc, gold, pred, "overlap") == {
        (1, 3): (2, 3),
        (4, 5): (4, 6),
        (7, 8): (7, 10),
    }
