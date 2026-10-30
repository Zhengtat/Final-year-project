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
    assert G.extend_span(toks, (1, 4), ["Vector Space Model ( VSM )"]) == (1, 4)  # key differs: no extension
